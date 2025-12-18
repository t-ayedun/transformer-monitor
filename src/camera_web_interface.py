
"""
Camera Web Interface
Provides live streaming, ROI visualization, and remote configuration
"""

import io
import logging
import time
import json
import threading
import psutil
import shutil
from datetime import datetime
from pathlib import Path
from threading import Thread, Lock, Event
from collections import deque

import numpy as np
from flask import Flask, render_template, Response, request, jsonify, send_file, send_from_directory
from PIL import Image, ImageDraw, ImageFont
import cv2


class CameraWebInterface:
    """Web interface for camera monitoring and configuration"""

    def __init__(self, smart_camera, config, thermal_capture=None, data_processor=None, aws_publisher=None, port=5000):
        self.logger = logging.getLogger(__name__)
        self.smart_camera = smart_camera
        self.thermal_capture = thermal_capture
        self.data_processor = data_processor
        self.aws_publisher = aws_publisher
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

        # Image cache
        self.image_cache = {
            'thermal': {'data': None, 'timestamp': 0},
            'visual': {'data': None, 'timestamp': 0},
            'fusion': {'data': None, 'timestamp': 0}
        }
        self.cache_duration = self.config.get('web_interface.image_cache_duration', 10)

        # Temperature history for metrics (store up to 7 days at 10-second intervals)
        # 7 days * 24 hours * 6 readings per minute = ~60,480 readings max
        self.temperature_history = deque(maxlen=60480)
        self.last_temp_record = 0

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

        @self.app.route('/thermal-heatmap')
        def thermal_heatmap():
            """Thermal heatmap validation view"""
            return render_template('thermal_heatmap.html')

        @self.app.route('/camera-alignment')
        def camera_alignment():
            """Camera alignment and calibration tool"""
            return render_template('camera_alignment.html')

        @self.app.route('/smart-roi-mapper')
        def smart_roi_mapper():
            """Smart ROI mapper - thermal native with auto-detection"""
            return render_template('smart_roi_mapper.html')

        @self.app.route('/api/thermal-data')
        def get_thermal_data():
            """Get current thermal frame data with actual temperature values"""
            try:
                if self.latest_thermal_frame is None:
                    return jsonify({'success': False, 'error': 'No thermal data available'})

                with self.thermal_frame_lock:
                    # Convert numpy array to list for JSON serialization
                    frame_list = self.latest_thermal_frame.tolist()

                return jsonify({
                    'success': True,
                    'frame': frame_list,
                    'width': 32,
                    'height': 24,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Failed to get thermal data: {e}")
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/api/detect-hotspots')
        def detect_hotspots_api():
            """Auto-detect hotspots and suggest ROIs"""
            try:
                if self.latest_thermal_frame is None:
                    return jsonify({'success': False, 'error': 'No thermal data available'})

                if self.thermal_capture is None:
                    return jsonify({'success': False, 'error': 'Thermal capture not initialized'})

                with self.thermal_frame_lock:
                    frame = self.latest_thermal_frame.copy()

                # Get threshold from request or use default
                threshold = request.args.get('threshold', type=float, default=50.0)

                # Detect hotspots using thermal_capture's built-in method
                hotspots = self.thermal_capture.detect_hotspots(frame, threshold=threshold)

                # Generate suggested ROIs from hotspots
                suggested_rois = []
                for i, hotspot in enumerate(hotspots):
                    # Create bounding box around hotspot (with padding)
                    center_x, center_y = hotspot['center']
                    area = hotspot['area']

                    # Calculate ROI size based on hotspot area
                    size = max(2, int(np.sqrt(area) * 1.5))  # 1.5x padding
                    x1 = max(0, center_x - size)
                    y1 = max(0, center_y - size)
                    x2 = min(32, center_x + size)
                    y2 = min(24, center_y + size)

                    suggested_roi = {
                        'name': f'Hotspot_{i+1}',
                        'enabled': True,
                        'coordinates': [[x1, y1], [x2, y2]],
                        'weight': 1.0,
                        'emissivity': 0.95,
                        'thresholds': {
                            'warning': min(75.0, hotspot['max_temp'] - 10),
                            'critical': min(85.0, hotspot['max_temp'] - 5),
                            'emergency': min(95.0, hotspot['max_temp'])
                        },
                        'detected_max_temp': hotspot['max_temp'],
                        'detected_avg_temp': hotspot['avg_temp']
                    }
                    suggested_rois.append(suggested_roi)

                self.logger.info(f"Auto-detected {len(hotspots)} hotspots with threshold {threshold}°C")

                return jsonify({
                    'success': True,
                    'hotspots': hotspots,
                    'suggested_rois': suggested_rois,
                    'threshold_used': threshold,
                    'timestamp': datetime.now().isoformat()
                })

            except Exception as e:
                self.logger.error(f"Failed to detect hotspots: {e}")
                return jsonify({'success': False, 'error': str(e)})

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
            # Check if AWS is enabled and connected
            aws_enabled = self.config.get('aws_iot.enabled', False)
            aws_connected = False
            if aws_enabled and self.aws_publisher:
                # Check if aws_publisher has a connected property or method
                aws_connected = getattr(self.aws_publisher, 'connected', False)

            status = {
                'site_id': self.config.get('site.id', 'UNKNOWN'),
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'thermal_data': self.latest_thermal_data,
                'camera_stats': self.smart_camera.get_stats() if self.smart_camera else None,
                'aws_enabled': aws_enabled,
                'aws_connected': aws_connected,
            }
            return jsonify(status)

        @self.app.route('/api/temperature-history')
        def get_temperature_history():
            """Get temperature history for metrics dashboard"""
            try:
                time_range = request.args.get('range', '1h')

                # Convert time range to seconds
                range_seconds = {
                    '1h': 3600,
                    '6h': 21600,
                    '24h': 86400,
                    '7d': 604800
                }.get(time_range, 3600)

                # Get current time
                now = time.time()
                cutoff_time = now - range_seconds

                # Filter history based on time range
                filtered_history = [
                    {
                        'timestamp': entry['timestamp'],
                        'temperature': entry['temperature']
                    }
                    for entry in self.temperature_history
                    if entry['timestamp'] >= cutoff_time
                ]

                # If we have data, downsample for better performance
                # Target: ~100 data points regardless of time range
                if len(filtered_history) > 100:
                    step = len(filtered_history) // 100
                    filtered_history = filtered_history[::step]

                return jsonify({
                    'success': True,
                    'history': filtered_history,
                    'range': time_range,
                    'count': len(filtered_history)
                })

            except Exception as e:
                self.logger.error(f"Failed to get temperature history: {e}")
                return jsonify({'success': False, 'error': str(e)})

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

                self.logger.info(f"Updated {len(new_rois)} ROIs - config reloaded")
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
                # Return relative path that can be served via /snapshots/ route
                filename = Path(filepath).name
                return jsonify({'success': True, 'filepath': f'/snapshots/{filename}'})
            except Exception as e:
                return jsonify({'error': str(e)}), 500

<<<<<<< HEAD
        @self.app.route('/api/recent-files')
        def get_recent_files():
            """Get list of recent recordings and snapshots"""
            try:
                recent_files = {
                    'recordings': [],
                    'snapshots': []
                }

                # Get recent recordings (videos)
                video_dir = Path('/data/videos')
                if video_dir.exists():
                    video_files = sorted(video_dir.glob('*.h264'), key=lambda p: p.stat().st_mtime, reverse=True)
                    recent_files['recordings'] = [
                        {
                            'filename': f.name,
                            'size': f.stat().st_size,
                            'timestamp': f.stat().st_mtime,
                            'url': f'/videos/{f.name}'
                        }
                        for f in video_files[:10]  # Last 10 recordings
                    ]

                # Get recent snapshots (images)
                image_dir = Path('/data/images')
                if image_dir.exists():
                    image_files = sorted(image_dir.glob('*.jpg'), key=lambda p: p.stat().st_mtime, reverse=True)
                    recent_files['snapshots'] = [
                        {
                            'filename': f.name,
                            'size': f.stat().st_size,
                            'timestamp': f.stat().st_mtime,
                            'url': f'/snapshots/{f.name}'
                        }
                        for f in image_files[:10]  # Last 10 snapshots
                    ]

                return jsonify(recent_files)
            except Exception as e:
                self.logger.error(f"Error getting recent files: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/snapshots/<filename>')
        def serve_snapshot(filename):
            """Serve captured snapshot images"""
            try:
                # Snapshots are stored in /data/images or local path
                snapshot_dir = Path('/data/images') if Path('/data/images').exists() else Path('.')
                filepath = snapshot_dir / filename

                if filepath.exists():
                    return send_file(str(filepath), mimetype='image/jpeg')
                else:
                    return jsonify({'error': 'Snapshot not found'}), 404
            except Exception as e:
                self.logger.error(f"Error serving snapshot: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/video/thermal')
        def thermal_stream():
            """MJPEG stream of thermal camera with ROI overlay"""
            response = Response(
                self._generate_thermal_stream(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response

        @self.app.route('/video/visual')
        def visual_stream():
            """MJPEG stream of Pi camera"""
            response = Response(
                self._generate_visual_stream(),
                mimetype='multipart/x-mixed-replace; boundary=frame'
            )
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response

    def _generate_thermal_stream(self):
        """Generate thermal camera stream with ROI overlays"""
        while self.running:
=======
        @self.app.route('/api/snapshot/<type>')
        def get_snapshot(type):
            """Get on-demand snapshot (thermal, visual, or fusion)"""
            if type not in ['thermal', 'visual', 'fusion']:
                return jsonify({'error': 'Invalid snapshot type'}), 400

            # Check cache
            current_time = time.time()
            if (self.image_cache[type]['data'] is not None and 
                current_time - self.image_cache[type]['timestamp'] < self.cache_duration):
                return send_file(
                    io.BytesIO(self.image_cache[type]['data']),
                    mimetype='image/jpeg'
                )

            # Generate new image
>>>>>>> fix/pi4-mlx90640
            try:
                img_data = None
                if type == 'thermal':
                    img_data = self._generate_thermal_image()
                elif type == 'visual':
                    img_data = self._generate_visual_image()
                elif type == 'fusion':
                    img_data = self._generate_fusion_image()

                if img_data:
                    # Update cache
                    self.image_cache[type]['data'] = img_data
                    self.image_cache[type]['timestamp'] = current_time
                    
                    return send_file(
                        io.BytesIO(img_data),
                        mimetype='image/jpeg'
                    )
                else:
                    return jsonify({'error': 'Failed to generate image'}), 503

            except Exception as e:
                self.logger.error(f"Snapshot error: {e}")
                return jsonify({'error': str(e)}), 500

    def _generate_thermal_image(self):
        """Generate thermal image with overlays"""
        if self.latest_thermal_frame is None:
            return None

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
        return buffer.tobytes()

    def _generate_visual_image(self):
        """Generate visual image"""
        if not self.smart_camera or not self.smart_camera.camera:
            return None

<<<<<<< HEAD
=======
        # Capture frame
        frame = self.smart_camera.camera.capture_array("main")

        # Convert RGB to BGR for OpenCV
        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        # Add metadata overlay
        frame_bgr = self._add_metadata_overlay(frame_bgr)

        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buffer.tobytes()

    def _generate_fusion_image(self):
        """Generate fusion image"""
        if self.latest_thermal_frame is None or not self.smart_camera:
            return None

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
        
        # Add metadata overlay
        fusion = self._add_metadata_overlay(fusion)

        # Encode as JPEG
        _, buffer = cv2.imencode('.jpg', fusion, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return buffer.tobytes()

>>>>>>> fix/pi4-mlx90640
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

        # Apply rotation if configured
        rotation = self.config.get('thermal_camera.rotation', 0)
        if rotation == 90:
            colored = cv2.rotate(colored, cv2.ROTATE_90_CLOCKWISE)
        elif rotation == 180:
            colored = cv2.rotate(colored, cv2.ROTATE_180)
        elif rotation == 270:
            colored = cv2.rotate(colored, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # Resize for better visibility (24x32 -> 480x640 or adjusted for rotation)
        if rotation in [90, 270]:
            resized = cv2.resize(colored, (480, 640), interpolation=cv2.INTER_CUBIC)
        else:
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
            coords = roi.get('coordinates')

            # Validate coordinates
            if not coords or len(coords) != 2:
                continue
            if not all(isinstance(c, (list, tuple)) and len(c) == 2 for c in coords):
                continue
            if not all(isinstance(val, (int, float)) for c in coords for val in c):
                continue

            # Ensure coordinates are within bounds
            try:
                x1_thermal = max(0, min(int(coords[0][0]), 31))
                y1_thermal = max(0, min(int(coords[0][1]), 23))
                x2_thermal = max(0, min(int(coords[1][0]), 32))
                y2_thermal = max(0, min(int(coords[1][1]), 24))

                # Skip if ROI is invalid (zero or negative size)
                if x2_thermal <= x1_thermal or y2_thermal <= y1_thermal:
                    continue

                # Scale coordinates for display
                x1 = int(x1_thermal * scale_x)
                y1 = int(y1_thermal * scale_y)
                x2 = int(x2_thermal * scale_x)
                y2 = int(y2_thermal * scale_y)

                # Extract ROI temperature with validated coordinates
                roi_data = thermal_frame[y1_thermal:y2_thermal, x1_thermal:x2_thermal]
            except (ValueError, TypeError, IndexError) as e:
                self.logger.debug(f"Skipping invalid ROI {name}: {e}")
                continue
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

            # Record temperature for metrics (every 10 seconds)
            current_time = time.time()
            if current_time - self.last_temp_record >= 10:
                if processed_data and 'ambient_temp' in processed_data:
                    self.temperature_history.append({
                        'timestamp': current_time,
                        'temperature': processed_data['ambient_temp']
                    })
                    self.last_temp_record = current_time

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
