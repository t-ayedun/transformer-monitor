"""
Camera Web Interface
Provides live streaming, ROI visualization, and remote configuration
"""

import io
import logging
import time
import json
from datetime import datetime
from pathlib import Path
from threading import Thread, Lock, Event
from collections import deque

import numpy as np
from flask import Flask, render_template, Response, request, jsonify, send_file
from PIL import Image, ImageDraw, ImageFont
import cv2


class CameraWebInterface:
    """Web interface for camera monitoring and configuration"""

    def __init__(self, smart_camera, config, thermal_capture=None, data_processor=None, port=5000):
        self.logger = logging.getLogger(__name__)
        self.smart_camera = smart_camera
        self.thermal_capture = thermal_capture
        self.data_processor = data_processor
        self.config = config
        self.port = port

        # Flask app
        template_dir = Path(__file__).parent / 'templates'
        self.app = Flask(__name__, template_folder=str(template_dir))
        self.app.config['SECRET_KEY'] = 'transformer-monitor-secret'

        # State
        self.running = False
        self.server_thread = None
        self.thermal_frame_lock = Lock()
        self.latest_thermal_frame = None
        self.latest_thermal_data = None
        self.roi_configs = []

        # Frame buffers for streaming
        self.thermal_frame_buffer = deque(maxlen=30)
        self.video_frame_buffer = deque(maxlen=30)

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.app.route('/')
        def index():
            """Main dashboard page"""
            return render_template('dashboard.html', site_id=self.config.get('site.id', 'UNKNOWN'))

        @self.app.route('/roi-mapper')
        def roi_mapper():
            """ROI mapper interface"""
            return render_template('roi_mapper.html')

        @self.app.route('/health')
        def health():
            """Health check endpoint"""
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'thermal_camera': self.thermal_capture is not None,
                'smart_camera': self.smart_camera is not None,
                'site_id': self.config.get('site.id', 'UNKNOWN')
            })

        @self.app.route('/api/status')
        def get_status():
            """Get system status"""
            status = {
                'site_id': self.config.get('site.id', 'UNKNOWN'),
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'thermal_data': self.latest_thermal_data,
                'camera_stats': self.smart_camera.get_stats() if self.smart_camera else None,
            }
            return jsonify(status)

        @self.app.route('/api/rois')
        def get_rois():
            """Get ROI configurations"""
            rois = self.config.get('regions_of_interest', [])
            return jsonify({'rois': rois})

        @self.app.route('/api/rois', methods=['POST'])
        def update_rois():
            """Update ROI configurations"""
            try:
                new_rois = request.json.get('rois', [])
                # Validate ROIs
                for roi in new_rois:
                    if not all(k in roi for k in ['name', 'coordinates', 'enabled']):
                        return jsonify({'error': 'Invalid ROI format'}), 400

                # Update configuration
                self.config.set('regions_of_interest', new_rois)
                self.config.save_config('site')

                # Reload data processor with new ROIs
                if self.data_processor:
                    self.data_processor.rois = new_rois

                self.logger.info(f"Updated {len(new_rois)} ROIs")
                return jsonify({'success': True, 'message': f'Updated {len(new_rois)} ROIs'})

            except Exception as e:
                self.logger.error(f"Failed to update ROIs: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/config')
        def get_config():
            """Get configuration parameters"""
            return jsonify({
                'site': {
                    'id': self.config.get('site.id'),
                    'name': self.config.get('site.name'),
                    'address': self.config.get('site.address'),
                },
                'thermal_camera': {
                    'refresh_rate': self.config.get('thermal_camera.refresh_rate'),
                    'i2c_address': self.config.get('thermal_camera.i2c_address'),
                },
                'data_capture': {
                    'interval': self.config.get('data_capture.interval'),
                    'save_full_frame_interval': self.config.get('data_capture.save_full_frame_interval'),
                },
                'pi_camera': {
                    'enabled': self.config.get('pi_camera.enabled'),
                    'motion_detection': self.config.get('pi_camera.motion_detection'),
                    'snapshot_interval': self.config.get('pi_camera.snapshot_interval'),
                }
            })

        @self.app.route('/api/config', methods=['POST'])
        def update_config():
            """Update configuration parameters"""
            try:
                updates = request.json

                # Apply updates
                for key, value in updates.items():
                    self.config.set(key, value)

                self.config.save_config('site')
                self.logger.info(f"Configuration updated: {list(updates.keys())}")

                return jsonify({'success': True, 'message': 'Configuration updated'})

            except Exception as e:
                self.logger.error(f"Failed to update config: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/snapshot')
        def capture_snapshot():
            """Trigger manual snapshot"""
            if not self.smart_camera:
                return jsonify({'error': 'Camera not available'}), 503

            try:
                filepath = self.smart_camera.capture_snapshot(custom_name='manual')
                return jsonify({'success': True, 'filepath': filepath})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/video/thermal')
        def thermal_stream():
            """MJPEG stream of thermal camera with ROI overlay"""
            return Response(
                self._generate_thermal_stream(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )

        @self.app.route('/video/visual')
        def visual_stream():
            """MJPEG stream of Pi camera"""
            return Response(
                self._generate_visual_stream(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )

        @self.app.route('/video/fusion')
        def fusion_stream():
            """MJPEG stream of thermal+visual fusion"""
            return Response(
                self._generate_fusion_stream(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )

    def _generate_thermal_stream(self):
        """Generate thermal camera stream with ROI overlays"""
        while self.running:
            try:
                if self.latest_thermal_frame is None:
                    time.sleep(0.1)
                    continue

                with self.thermal_frame_lock:
                    frame = self.latest_thermal_frame.copy()

                # Convert thermal data to RGB image with colormap
                img = self._thermal_to_rgb(frame)

                # Draw ROI overlays
                img = self._draw_roi_overlays(img, frame)

                # Add metadata overlay
                img = self._add_metadata_overlay(img)

                # Encode as JPEG
                _, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                frame_bytes = buffer.tobytes()

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

                time.sleep(0.033)  # ~30 FPS

            except Exception as e:
                self.logger.error(f"Thermal stream error: {e}")
                time.sleep(1)

    def _generate_visual_stream(self):
        """Generate Pi camera stream"""
        while self.running:
            try:
                if not self.smart_camera or not self.smart_camera.camera:
                    time.sleep(0.1)
                    continue

                # Capture frame
                frame = self.smart_camera.camera.capture_array("main")

                # Convert RGB to BGR for OpenCV
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                # Encode as JPEG
                _, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
                frame_bytes = buffer.tobytes()

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

                time.sleep(0.033)  # ~30 FPS

            except Exception as e:
                self.logger.error(f"Visual stream error: {e}")
                time.sleep(1)

    def _generate_fusion_stream(self):
        """Generate thermal+visual fusion stream"""
        while self.running:
            try:
                if self.latest_thermal_frame is None or not self.smart_camera:
                    time.sleep(0.1)
                    continue

                # Get visual frame
                visual_frame = self.smart_camera.camera.capture_array("main")
                visual_frame = cv2.cvtColor(visual_frame, cv2.COLOR_RGB2BGR)

                # Get thermal frame
                with self.thermal_frame_lock:
                    thermal_frame = self.latest_thermal_frame.copy()

                # Create thermal overlay
                thermal_rgb = self._thermal_to_rgb(thermal_frame)

                # Resize thermal to match visual
                h, w = visual_frame.shape[:2]
                thermal_resized = cv2.resize(thermal_rgb, (w, h), interpolation=cv2.INTER_CUBIC)

                # Blend: 60% visual + 40% thermal
                fusion = cv2.addWeighted(visual_frame, 0.6, thermal_resized, 0.4, 0)

                # Encode as JPEG
                _, buffer = cv2.imencode('.jpg', fusion, [cv2.IMWRITE_JPEG_QUALITY, 85])
                frame_bytes = buffer.tobytes()

                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

                time.sleep(0.033)  # ~30 FPS

            except Exception as e:
                self.logger.error(f"Fusion stream error: {e}")
                time.sleep(1)

    def _thermal_to_rgb(self, thermal_frame):
        """Convert thermal frame to RGB image with colormap"""
        # Normalize to 0-255
        min_temp = np.min(thermal_frame)
        max_temp = np.max(thermal_frame)

        if max_temp - min_temp > 0:
            normalized = ((thermal_frame - min_temp) / (max_temp - min_temp) * 255).astype(np.uint8)
        else:
            normalized = np.zeros_like(thermal_frame, dtype=np.uint8)

        # Apply colormap (INFERNO or JET for thermal imaging)
        colored = cv2.applyColorMap(normalized, cv2.COLORMAP_INFERNO)

        # Resize for better visibility (24x32 -> 480x640)
        resized = cv2.resize(colored, (640, 480), interpolation=cv2.INTER_CUBIC)

        return resized

    def _draw_roi_overlays(self, img, thermal_frame):
        """Draw ROI rectangles and temperature values on image"""
        rois = self.config.get('regions_of_interest', [])

        # Scale factors (thermal is 32x24, image is 640x480)
        scale_x = 640 / 32
        scale_y = 480 / 24

        for roi in rois:
            if not roi.get('enabled', True):
                continue

            name = roi['name']
            coords = roi['coordinates']

            # Scale coordinates
            x1 = int(coords[0][0] * scale_x)
            y1 = int(coords[0][1] * scale_y)
            x2 = int(coords[1][0] * scale_x)
            y2 = int(coords[1][1] * scale_y)

            # Extract ROI temperature
            roi_data = thermal_frame[coords[0][1]:coords[1][1], coords[0][0]:coords[1][0]]
            max_temp = np.max(roi_data)
            avg_temp = np.mean(roi_data)

            # Determine color based on thresholds
            thresholds = roi.get('thresholds', {})
            if max_temp >= thresholds.get('emergency', float('inf')):
                color = (0, 0, 255)  # Red
            elif max_temp >= thresholds.get('critical', float('inf')):
                color = (0, 165, 255)  # Orange
            elif max_temp >= thresholds.get('warning', float('inf')):
                color = (0, 255, 255)  # Yellow
            else:
                color = (0, 255, 0)  # Green

            # Draw rectangle
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

            # Draw label with temperature
            label = f"{name}: {max_temp:.1f}C (avg: {avg_temp:.1f}C)"

            # Background for text
            (text_width, text_height), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            cv2.rectangle(
                img,
                (x1, y1 - text_height - 5),
                (x1 + text_width, y1),
                (0, 0, 0),
                -1
            )

            # Text
            cv2.putText(
                img, label, (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1
            )

        return img

    def _add_metadata_overlay(self, img):
        """Add timestamp and metadata overlay"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        site_id = self.config.get('site.id', 'UNKNOWN')

        # Add semi-transparent black box at bottom
        overlay = img.copy()
        cv2.rectangle(overlay, (0, img.shape[0] - 40), (img.shape[1], img.shape[0]), (0, 0, 0), -1)
        img = cv2.addWeighted(overlay, 0.7, img, 0.3, 0)

        # Add text
        text = f"{site_id} | {timestamp}"
        cv2.putText(img, text, (10, img.shape[0] - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Add temperature scale
        if self.latest_thermal_frame is not None:
            min_temp = np.min(self.latest_thermal_frame)
            max_temp = np.max(self.latest_thermal_frame)
            scale_text = f"Range: {min_temp:.1f}C - {max_temp:.1f}C"
            cv2.putText(img, scale_text, (img.shape[1] - 250, img.shape[0] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return img

    def update_thermal_frame(self, frame, processed_data=None):
        """Update the latest thermal frame for streaming"""
        with self.thermal_frame_lock:
            self.latest_thermal_frame = frame
            self.latest_thermal_data = processed_data

    def start(self):
        """Start web server"""
        self.running = True
        self.server_thread = Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        self.logger.info(f"Web interface started on port {self.port}")

    def _run_server(self):
        """Run Flask server"""
        try:
            self.app.run(
                host='0.0.0.0',
                port=self.port,
                debug=False,
                threaded=True,
                use_reloader=False
            )
        except Exception as e:
            self.logger.error(f"Web server error: {e}")

    def stop(self):
        """Stop web server"""
        self.running = False
        self.logger.info("Web interface stopped")
