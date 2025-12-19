"""
Temperature Data Collector
Collects minute-by-minute temperature readings and exports to CSV files
"""

import csv
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional
import pytz


class TemperatureDataCollector:
    """Collects and exports temperature data to CSV files"""
    
    def __init__(self, config, base_dir=None):
        self.logger = logging.getLogger(__name__)
        self.config = config
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            self.base_dir = Path.home() / 'transformer_monitor_data' / 'temperature'
        self.buffer: List[Dict] = []
        self.current_hour = None
        self.current_csv_path = None
        
        # Get timezone from config
        tz_name = self.config.get('site.timezone', 'UTC')
        try:
            self.timezone = pytz.timezone(tz_name)
        except Exception as e:
            self.logger.warning(f"Invalid timezone {tz_name}, using UTC: {e}")
            self.timezone = pytz.UTC
        
        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Temperature data collector initialized: {self.base_dir}")
    
    def record_reading(self, processed_data: Dict) -> None:
        """
        Record a temperature reading from processed thermal data
        
        Args:
            processed_data: Processed data from DataProcessor
        """
        try:
            # Get current time with timezone
            now = datetime.now(self.timezone)
            current_hour = now.strftime('%Y%m%d_%H')
            
            # Check if we've moved to a new hour
            if self.current_hour and self.current_hour != current_hour:
                self.logger.info(f"Hour changed from {self.current_hour} to {current_hour}, flushing buffer")
                self.flush_to_csv()
            
            self.current_hour = current_hour
            
            # Extract temperature data
            reading = self._extract_temperature_data(processed_data, now)
            
            if reading:
                self.buffer.append(reading)
                self.logger.debug(f"Recorded temperature reading: {reading['timestamp']}")
            else:
                self.logger.warning("Failed to extract temperature data from processed_data")
                
        except Exception as e:
            self.logger.error(f"Failed to record temperature reading: {e}", exc_info=True)
    
    def _extract_temperature_data(self, processed_data: Dict, timestamp: datetime) -> Optional[Dict]:
        """
        Extract temperature data from processed data
        
        Priority:
        1. transformer_region (ROI-detected)
        2. composite_temperature (fallback)
        3. frame_stats (last resort)
        """
        site_id = processed_data.get('site_id', self.config.get('site.id', 'UNKNOWN'))
        
        # Try transformer region first (best option)
        if processed_data.get('transformer_region'):
            transformer = processed_data['transformer_region']
            return {
                'timestamp': timestamp.isoformat(),
                'site_id': site_id,
                'roi_name': 'transformer_auto',
                'min_temp': round(transformer.get('min_temp', 0), 2),
                'max_temp': round(transformer.get('max_temp', 0), 2),
                'avg_temp': round(transformer.get('avg_temp', 0), 2),
                'q1_temp': round(transformer.get('q1_temp', 0), 2),
                'q3_temp': round(transformer.get('q3_temp', 0), 2),
                'detection_confidence': round(transformer.get('detection_confidence', 0), 3)
            }
        
        # Fallback to composite temperature
        elif processed_data.get('composite_temperature'):
            comp_temp = processed_data['composite_temperature']
            frame_stats = processed_data.get('frame_stats', {})
            
            return {
                'timestamp': timestamp.isoformat(),
                'site_id': site_id,
                'roi_name': 'composite',
                'min_temp': round(frame_stats.get('min_temp', comp_temp), 2),
                'max_temp': round(frame_stats.get('max_temp', comp_temp), 2),
                'avg_temp': round(comp_temp, 2),
                'q1_temp': round(comp_temp, 2),  # No quartile data available
                'q3_temp': round(comp_temp, 2),
                'detection_confidence': 0.0  # No detection
            }
        
        # Last resort: use frame stats
        elif processed_data.get('frame_stats'):
            frame_stats = processed_data['frame_stats']
            avg_temp = frame_stats.get('avg_temp', 0)
            
            return {
                'timestamp': timestamp.isoformat(),
                'site_id': site_id,
                'roi_name': 'full_frame',
                'min_temp': round(frame_stats.get('min_temp', avg_temp), 2),
                'max_temp': round(frame_stats.get('max_temp', avg_temp), 2),
                'avg_temp': round(avg_temp, 2),
                'q1_temp': round(avg_temp, 2),
                'q3_temp': round(avg_temp, 2),
                'detection_confidence': 0.0
            }
        
        return None
    
    def flush_to_csv(self) -> Optional[Path]:
        """
        Write buffered readings to CSV file
        
        Returns:
            Path to created CSV file, or None if no data to write
        """
        if not self.buffer:
            self.logger.debug("No data in buffer to flush")
            return None
        
        try:
            # Get CSV file path
            csv_path = self._get_csv_path()
            
            # Ensure directory exists
            csv_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if file exists to determine if we need headers
            file_exists = csv_path.exists()
            
            # Write to CSV
            with open(csv_path, 'a', newline='') as f:
                fieldnames = [
                    'timestamp', 'site_id', 'roi_name', 
                    'min_temp', 'max_temp', 'avg_temp', 
                    'q1_temp', 'q3_temp', 'detection_confidence'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                
                # Write header if new file
                if not file_exists:
                    writer.writeheader()
                
                # Write all buffered readings
                writer.writerows(self.buffer)
            
            self.logger.info(f"Flushed {len(self.buffer)} readings to {csv_path}")
            
            # Clear buffer
            buffer_size = len(self.buffer)
            self.buffer.clear()
            
            return csv_path
            
        except Exception as e:
            self.logger.error(f"Failed to flush buffer to CSV: {e}", exc_info=True)
            # Keep buffer for retry
            return None
    
    def _get_csv_path(self) -> Path:
        """
        Get path for current hour's CSV file
        
        Format: /data/temperature/YYYY/MM/DD/SITE_ID_temp_YYYYMMDD_HH.csv
        """
        if not self.current_hour:
            # Use current time if no hour set
            now = datetime.now(self.timezone)
            self.current_hour = now.strftime('%Y%m%d_%H')
        
        # Parse hour to get date components
        date_str = self.current_hour[:8]  # YYYYMMDD
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]
        
        # Build path
        site_id = self.config.get('site.id', 'UNKNOWN')
        filename = f"{site_id}_temp_{self.current_hour}.csv"
        
        csv_path = self.base_dir / year / month / day / filename
        
        return csv_path
    
    def force_flush(self) -> Optional[Path]:
        """
        Force flush buffer to CSV (for shutdown or testing)
        
        Returns:
            Path to created CSV file
        """
        self.logger.info("Force flushing temperature data buffer")
        return self.flush_to_csv()
    
    def get_stats(self) -> Dict:
        """Get collector statistics"""
        return {
            'buffer_size': len(self.buffer),
            'current_hour': self.current_hour,
            'current_csv_path': str(self.current_csv_path) if self.current_csv_path else None,
            'base_dir': str(self.base_dir)
        }
