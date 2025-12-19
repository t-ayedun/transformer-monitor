"""
Camera Snapshot
Handles Raspberry Pi camera captures with event organization and management
"""

import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Tuple
from picamera2 import Picamera2
from PIL import Image, ImageDraw, ImageFont
import io


class CameraSnapshot:
    """
    Raspberry Pi camera interface with event-based snapshot management

    Features:
    - Event-organized storage by date and type
    - Image compression (max 500KB)
    - Metadata overlays (timestamp, event_type, confidence)
    - Auto-cleanup of old images (30 days)
    - Summary image generation (3 snapshots side-by-side)
    """

    # Storage paths
    BASE_IMAGE_PATH = "/home/smartie/transformer_monitor_data/images"
    EVENT_IMAGE_PATH = "/home/smartie/transformer_monitor_data/images/events"

    # Image settings
    MAX_IMAGE_SIZE_KB = 500
    RETENTION_DAYS = 30

    def __init__(self, resolution: list, quality: int = 85, init_camera: bool = True):
        self.logger = logging.getLogger(__name__)
        self.resolution = tuple(resolution)
        self.quality = quality
        self.camera = None

        if init_camera:
            self._init_camera()

    def _init_camera(self):
        """Initialize Pi camera"""
        try:
            self.camera = Picamera2()
            config = self.camera.create_still_configuration(
                main={"size": self.resolution}
            )
            self.camera.configure(config)
            self.camera.start()

            self.logger.info(f"Camera initialized at {self.resolution}")

        except Exception as e:
            self.logger.error(f"Camera initialization failed: {e}")
            self.camera = None

    def capture(self, add_timestamp: bool = True) -> str:
        """
        Capture simple snapshot (legacy method)

        Returns: Path to saved image
        """
        if not self.camera:
            self.logger.error("Camera not initialized")
            return None

        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"snapshot_{timestamp}.jpg"
            filepath = f"{self.BASE_IMAGE_PATH}/{filename}"

            # Ensure directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            # Capture
            self.camera.capture_file(filepath)

            # Add timestamp overlay if requested
            if add_timestamp:
                self._add_timestamp_overlay(filepath)

            self.logger.info(f"Captured snapshot: {filename}")
            return filepath

        except Exception as e:
            self.logger.error(f"Capture failed: {e}")
            return None

    def capture_event_snapshot(
        self,
        event_type: str,
        snapshot_type: str,
        confidence: float = 0.0,
        site_id: str = "UNKNOWN",
        timestamp: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Capture event-based snapshot with organization and metadata

        Args:
            event_type: 'maintenance_visit', 'security_breach', 'animal'
            snapshot_type: 'start', 'peak', 'end'
            confidence: Classification confidence score (0-1)
            site_id: Site identifier
            timestamp: Event timestamp (default: now)

        Returns:
            Path to saved image
        """
        if not self.camera:
            self.logger.error("Camera not initialized")
            return None

        if timestamp is None:
            timestamp = datetime.now()

        try:
            # Organize by date and event type
            date_str = timestamp.strftime('%Y-%m-%d')
            time_str = timestamp.strftime('%Y%m%d_%H%M%S')

            # Create directory structure: /data/images/events/YYYY-MM-DD/event_type/
            event_dir = Path(self.EVENT_IMAGE_PATH) / date_str / event_type
            event_dir.mkdir(parents=True, exist_ok=True)

            # Filename: timestamp_type.jpg
            filename = f"{time_str}_{snapshot_type}.jpg"
            filepath = event_dir / filename

            # Capture to temporary file
            temp_path = f"/tmp/{filename}"
            self.camera.capture_file(temp_path)

            # Add metadata overlay
            self._add_event_metadata_overlay(
                temp_path,
                event_type=event_type,
                snapshot_type=snapshot_type,
                confidence=confidence,
                site_id=site_id,
                timestamp=timestamp
            )

            # Compress image to max size
            self._compress_image(temp_path, str(filepath), self.MAX_IMAGE_SIZE_KB)

            # Remove temp file
            Path(temp_path).unlink()

            self.logger.info(
                f"Captured event snapshot: {event_type}/{filename} "
                f"(confidence: {confidence:.2f})"
            )

            return str(filepath)

        except Exception as e:
            self.logger.error(f"Event capture failed: {e}")
            return None

    def _add_timestamp_overlay(self, filepath: str):
        """Add simple timestamp overlay to image (legacy)"""
        try:
            img = Image.open(filepath)
            draw = ImageDraw.Draw(img)

            # Timestamp text
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Use default font (or specify path to TTF font)
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
            except:
                font = ImageFont.load_default()

            # Position at bottom-right
            text_bbox = draw.textbbox((0, 0), timestamp, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            position = (img.width - text_width - 20, img.height - text_height - 20)

            # Draw shadow
            draw.text((position[0]+2, position[1]+2), timestamp, fill='black', font=font)
            # Draw text
            draw.text(position, timestamp, fill='white', font=font)

            img.save(filepath, quality=self.quality)

        except Exception as e:
            self.logger.warning(f"Failed to add timestamp overlay: {e}")

    def _add_event_metadata_overlay(
        self,
        filepath: str,
        event_type: str,
        snapshot_type: str,
        confidence: float,
        site_id: str,
        timestamp: datetime
    ):
        """
        Add metadata overlay to event snapshot

        Overlay includes: timestamp, event_type, confidence, site_id, snapshot_type
        """
        try:
            img = Image.open(filepath)
            draw = ImageDraw.Draw(img)

            # Load font
            try:
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
            except:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # Prepare text lines
            time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            event_label = event_type.replace('_', ' ').title()
            confidence_str = f"Confidence: {confidence:.0%}"
            snapshot_label = snapshot_type.upper()

            # Color coding by event type
            if event_type == 'security_breach':
                event_color = (255, 50, 50)  # Red
            elif event_type == 'maintenance_visit':
                event_color = (50, 200, 50)  # Green
            elif event_type == 'animal':
                event_color = (255, 200, 50)  # Yellow
            else:
                event_color = (200, 200, 200)  # Gray

            # Draw top banner with event info
            banner_height = 120
            # Semi-transparent black background
            overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            overlay_draw.rectangle([(0, 0), (img.width, banner_height)], fill=(0, 0, 0, 180))

            # Composite overlay
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            img = Image.alpha_composite(img, overlay)

            # Draw text on main image
            draw = ImageDraw.Draw(img)

            # Line 1: Site ID and Time
            line1 = f"{site_id} | {time_str}"
            draw.text((20, 15), line1, fill='white', font=font_small)

            # Line 2: Event Type (colored)
            draw.text((20, 55), event_label, fill=event_color, font=font_large)

            # Line 3: Confidence
            draw.text((20, 90), confidence_str, fill='white', font=font_small)

            # Draw snapshot type badge (top right)
            badge_text = f"[{snapshot_label}]"
            text_bbox = draw.textbbox((0, 0), badge_text, font=font_large)
            badge_width = text_bbox[2] - text_bbox[0]
            badge_x = img.width - badge_width - 20

            # Badge background
            overlay2 = Image.new('RGBA', img.size, (0, 0, 0, 0))
            overlay2_draw = ImageDraw.Draw(overlay2)
            overlay2_draw.rectangle(
                [(badge_x - 10, 15), (img.width - 10, 75)],
                fill=(0, 0, 0, 200)
            )
            img = Image.alpha_composite(img, overlay2)

            draw = ImageDraw.Draw(img)
            draw.text((badge_x, 20), badge_text, fill=event_color, font=font_large)

            # Save as RGB JPEG
            img.convert('RGB').save(filepath, quality=self.quality)

        except Exception as e:
            self.logger.warning(f"Failed to add event metadata overlay: {e}")

    def _compress_image(
        self,
        input_path: str,
        output_path: str,
        max_size_kb: int
    ):
        """
        Compress image to maximum file size

        Args:
            input_path: Source image path
            output_path: Destination image path
            max_size_kb: Maximum file size in KB
        """
        try:
            img = Image.open(input_path)

            # Convert RGBA to RGB if necessary
            if img.mode == 'RGBA':
                img = img.convert('RGB')

            # Start with current quality
            quality = self.quality

            # Try to save and check size
            for _ in range(10):  # Max 10 attempts
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG', quality=quality, optimize=True)
                size_kb = len(buffer.getvalue()) / 1024

                if size_kb <= max_size_kb or quality <= 20:
                    # Save to file
                    with open(output_path, 'wb') as f:
                        f.write(buffer.getvalue())

                    self.logger.debug(
                        f"Compressed image to {size_kb:.1f}KB "
                        f"(quality: {quality})"
                    )
                    break

                # Reduce quality and try again
                quality -= 10

        except Exception as e:
            self.logger.warning(f"Failed to compress image: {e}")
            # Fall back to copying without compression
            import shutil
            shutil.copy(input_path, output_path)

    def create_summary_image(
        self,
        snapshot_paths: List[str],
        output_path: Optional[str] = None,
        event_type: str = "unknown",
        timestamp: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Create summary image with 3 snapshots side-by-side

        Args:
            snapshot_paths: List of 3 snapshot paths [start, peak, end]
            output_path: Optional output path (auto-generated if None)
            event_type: Event type for organization
            timestamp: Event timestamp

        Returns:
            Path to summary image
        """
        if len(snapshot_paths) != 3:
            self.logger.error(f"Need exactly 3 snapshots, got {len(snapshot_paths)}")
            return None

        if timestamp is None:
            timestamp = datetime.now()

        try:
            # Load all 3 images
            images = []
            for path in snapshot_paths:
                if Path(path).exists():
                    images.append(Image.open(path))
                else:
                    self.logger.warning(f"Snapshot not found: {path}")
                    return None

            if len(images) != 3:
                return None

            # Calculate summary image dimensions
            # Side-by-side with small gaps
            gap = 10
            single_width = images[0].width
            single_height = images[0].height

            total_width = single_width * 3 + gap * 2
            total_height = single_height + 60  # Extra space for labels

            # Create summary image
            summary = Image.new('RGB', (total_width, total_height), color='black')

            # Paste images
            labels = ['START', 'PEAK', 'END']
            colors = [(50, 200, 50), (255, 200, 50), (255, 50, 50)]

            for i, (img, label, color) in enumerate(zip(images, labels, colors)):
                x_pos = i * (single_width + gap)
                summary.paste(img, (x_pos, 0))

                # Add label at bottom
                draw = ImageDraw.Draw(summary)
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
                except:
                    font = ImageFont.load_default()

                # Center label under image
                text_bbox = draw.textbbox((0, 0), label, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                label_x = x_pos + (single_width - text_width) // 2
                label_y = single_height + 15

                # Shadow
                draw.text((label_x + 2, label_y + 2), label, fill='black', font=font)
                # Text
                draw.text((label_x, label_y), label, fill=color, font=font)

            # Generate output path if not provided
            if output_path is None:
                date_str = timestamp.strftime('%Y-%m-%d')
                time_str = timestamp.strftime('%Y%m%d_%H%M%S')

                summary_dir = Path(self.EVENT_IMAGE_PATH) / date_str / event_type
                summary_dir.mkdir(parents=True, exist_ok=True)

                output_path = str(summary_dir / f"{time_str}_summary.jpg")

            # Save summary image
            summary.save(output_path, quality=self.quality, optimize=True)

            self.logger.info(f"Created summary image: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Failed to create summary image: {e}")
            return None

    def cleanup_old_images(self, days_to_keep: int = None):
        """
        Delete event images older than specified days

        Args:
            days_to_keep: Number of days to keep (default: RETENTION_DAYS)

        Returns:
            Number of files deleted
        """
        if days_to_keep is None:
            days_to_keep = self.RETENTION_DAYS

        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d')

            event_path = Path(self.EVENT_IMAGE_PATH)
            if not event_path.exists():
                return 0

            deleted_count = 0
            deleted_size = 0

            # Iterate through date directories
            for date_dir in event_path.iterdir():
                if not date_dir.is_dir():
                    continue

                # Check if directory name is older than cutoff
                try:
                    dir_date = datetime.strptime(date_dir.name, '%Y-%m-%d')
                    if dir_date < cutoff_date:
                        # Delete entire date directory
                        for file in date_dir.rglob('*'):
                            if file.is_file():
                                deleted_size += file.stat().st_size
                                file.unlink()
                                deleted_count += 1

                        # Remove empty directories
                        for subdir in sorted(date_dir.rglob('*'), reverse=True):
                            if subdir.is_dir() and not list(subdir.iterdir()):
                                subdir.rmdir()

                        # Remove date directory
                        if not list(date_dir.iterdir()):
                            date_dir.rmdir()

                except ValueError:
                    # Not a date directory, skip
                    continue

            if deleted_count > 0:
                deleted_mb = deleted_size / (1024 * 1024)
                self.logger.info(
                    f"Cleanup: Deleted {deleted_count} images "
                    f"({deleted_mb:.1f} MB) older than {days_to_keep} days"
                )

            return deleted_count

        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
            return 0

    def process_event_snapshot(
        self,
        source_image_path: str,
        event_type: str,
        snapshot_type: str,
        confidence: float,
        site_id: str = "UNKNOWN",
        timestamp: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Process an existing image as an event snapshot
        (for use when camera capture is handled elsewhere)

        Args:
            source_image_path: Path to existing image file
            event_type: 'maintenance_visit', 'security_breach', 'animal'
            snapshot_type: 'start', 'peak', 'end'
            confidence: Classification confidence score (0-1)
            site_id: Site identifier
            timestamp: Event timestamp

        Returns:
            Path to processed and saved event image
        """
        if timestamp is None:
            timestamp = datetime.now()

        try:
            # Organize by date and event type
            date_str = timestamp.strftime('%Y-%m-%d')
            time_str = timestamp.strftime('%Y%m%d_%H%M%S')

            # Create directory structure
            event_dir = Path(self.EVENT_IMAGE_PATH) / date_str / event_type
            event_dir.mkdir(parents=True, exist_ok=True)

            # Filename
            filename = f"{time_str}_{snapshot_type}.jpg"
            filepath = event_dir / filename

            # Copy to temp location for processing
            import shutil
            temp_path = f"/tmp/{filename}"
            shutil.copy(source_image_path, temp_path)

            # Add metadata overlay
            self._add_event_metadata_overlay(
                temp_path,
                event_type=event_type,
                snapshot_type=snapshot_type,
                confidence=confidence,
                site_id=site_id,
                timestamp=timestamp
            )

            # Compress image to max size
            self._compress_image(temp_path, str(filepath), self.MAX_IMAGE_SIZE_KB)

            # Remove temp file
            Path(temp_path).unlink()

            self.logger.info(
                f"Processed event snapshot: {event_type}/{filename} "
                f"(confidence: {confidence:.2f})"
            )

            return str(filepath)

        except Exception as e:
            self.logger.error(f"Event snapshot processing failed: {e}")
            return None

    def get_event_images(
        self,
        event_type: Optional[str] = None,
        date: Optional[datetime] = None
    ) -> List[str]:
        """
        Get list of event images

        Args:
            event_type: Filter by event type (None = all types)
            date: Filter by date (None = all dates)

        Returns:
            List of image paths
        """
        try:
            event_path = Path(self.EVENT_IMAGE_PATH)
            if not event_path.exists():
                return []

            images = []

            # Filter by date if specified
            if date:
                date_str = date.strftime('%Y-%m-%d')
                search_path = event_path / date_str
                if not search_path.exists():
                    return []
            else:
                search_path = event_path

            # Filter by event type if specified
            if event_type:
                search_path = search_path / "**" / event_type

            # Find all JPG files
            for img_file in search_path.rglob('*.jpg'):
                images.append(str(img_file))

            return sorted(images)

        except Exception as e:
            self.logger.error(f"Failed to get event images: {e}")
            return []

    def close(self):
        """Close camera"""
        if self.camera:
            self.camera.stop()
            self.camera.close()
            self.logger.info("Camera closed")
