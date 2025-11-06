"""
Helper utilities
"""

import os
import shutil
import platform
import psutil
from pathlib import Path
from datetime import datetime
from typing import Dict


def ensure_directory(path: str) -> Path:
    """
    Ensure directory exists, create if it doesn't
    
    Args:
        path: Directory path
        
    Returns:
        Path object
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_disk_usage(path: str = '/') -> Dict:
    """
    Get disk usage statistics
    
    Args:
        path: Mount point to check
        
    Returns:
        Dictionary with total, used, free, percent
    """
    usage = shutil.disk_usage(path)
    return {
        'total_gb': usage.total / (1024**3),
        'used_gb': usage.used / (1024**3),
        'free_gb': usage.free / (1024**3),
        'percent': (usage.used / usage.total) * 100
    }


def get_system_info() -> Dict:
    """
    Get system information
    
    Returns:
        Dictionary with system stats
    """
    return {
        'platform': platform.system(),
        'platform_release': platform.release(),
        'architecture': platform.machine(),
        'hostname': platform.node(),
        'cpu_count': psutil.cpu_count(),
        'memory_total_gb': psutil.virtual_memory().total / (1024**3),
        'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
    }


def format_bytes(bytes_value: int) -> str:
    """
    Format bytes to human-readable string
    
    Args:
        bytes_value: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"


def parse_datetime(dt_string: str) -> datetime:
    """
    Parse datetime string with multiple format support
    
    Args:
        dt_string: Datetime string
        
    Returns:
        datetime object
    """
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%d %H:%M:%S',
        '%Y%m%d_%H%M%S'
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(dt_string, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Unable to parse datetime: {dt_string}")


def get_cpu_temperature() -> float:
    """
    Get Raspberry Pi CPU temperature
    
    Returns:
        Temperature in Celsius, or None if unavailable
    """
    try:
        with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
            temp = float(f.read()) / 1000.0
            return temp
    except:
        return None


def check_i2c_device(bus: int, address: int) -> bool:
    """
    Check if I2C device exists at address
    
    Args:
        bus: I2C bus number (usually 1)
        address: Device address (e.g., 0x33)
        
    Returns:
        True if device found
    """
    import subprocess
    try:
        result = subprocess.run(
            ['i2cdetect', '-y', str(bus)],
            capture_output=True,
            text=True,
            timeout=5
        )
        hex_addr = f"{address:02x}"
        return hex_addr in result.stdout.lower()
    except:
        return False