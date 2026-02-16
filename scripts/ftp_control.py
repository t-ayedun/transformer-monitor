#!/usr/bin/env python3
"""
FTP Control Utility
Manually pause/resume FTP uploads or check status
"""

import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config_manager import ConfigManager
from ftp_publisher import FTPPublisher
import time


def get_ftp_publisher():
    """Initialize FTP publisher from config"""
    config = ConfigManager()
    config.load_configs()
    
    # Check if FTP is enabled
    ftp_enabled = config.get('ftp_storage.enabled', False) or config.get('ftp.enabled', False)
    
    if not ftp_enabled:
        print("ERROR: FTP is not enabled in configuration")
        sys.exit(1)
    
    # Determine which config section to use
    if config.get('ftp_storage.enabled'):
        ftp_config_prefix = 'ftp_storage'
    else:
        ftp_config_prefix = 'ftp'
    
    # Get password from env var or config
    ftp_password = os.getenv('FTP_PASSWORD') or config.get(f'{ftp_config_prefix}.password', '')
    
    publisher = FTPPublisher(
        host=config.get(f'{ftp_config_prefix}.host'),
        username=config.get(f'{ftp_config_prefix}.username'),
        password=ftp_password,
        remote_dir=config.get(f'{ftp_config_prefix}.remote_dir', '/transformer-data'),
        port=config.get(f'{ftp_config_prefix}.port', 21),
        passive=config.get(f'{ftp_config_prefix}.passive', True)
    )
    
    return publisher


def show_status(publisher):
    """Show FTP upload status"""
    stats = publisher.get_stats()
    
    print("\n=== FTP Upload Status ===")
    print(f"Circuit Breaker Active: {stats['circuit_breaker_active']}")
    
    if stats['circuit_breaker_active'] and stats['circuit_breaker_until']:
        remaining = stats['circuit_breaker_until'] - time.time()
        if remaining > 0:
            print(f"Paused until: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(stats['circuit_breaker_until']))}")
            print(f"Time remaining: {int(remaining)} seconds ({int(remaining/60)} minutes)")
        else:
            print("Circuit breaker expired, will retry on next upload attempt")
    
    print(f"\nConsecutive Failures: {stats['consecutive_failures']}")
    print(f"Total Uploads Success: {stats['uploads_success']}")
    print(f"Total Uploads Failed: {stats['uploads_failed']}")
    print(f"Success Rate: {stats['success_rate']*100:.1f}%")
    print(f"Total Bytes Uploaded: {stats['bytes_uploaded']:,} bytes")
    print()


def pause_uploads(publisher, duration_minutes):
    """Pause FTP uploads for specified duration"""
    duration_seconds = duration_minutes * 60
    publisher.pause_uploads(duration_seconds)
    print(f"\n✓ FTP uploads paused for {duration_minutes} minutes")
    print(f"  Will resume at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time() + duration_seconds))}")
    print()


def resume_uploads(publisher):
    """Resume FTP uploads"""
    publisher.resume_uploads()
    print("\n✓ FTP uploads resumed")
    print()


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python ftp_control.py status              - Show FTP upload status")
        print("  python ftp_control.py pause <minutes>     - Pause FTP uploads for N minutes")
        print("  python ftp_control.py resume              - Resume FTP uploads")
        print()
        print("Examples:")
        print("  python ftp_control.py status")
        print("  python ftp_control.py pause 60            - Pause for 1 hour")
        print("  python ftp_control.py pause 1440          - Pause for 24 hours")
        print("  python ftp_control.py resume")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    # Note: This creates a separate FTP publisher instance just to set the circuit breaker state
    # The actual running service will pick up the state from the shared FTP connection
    # For a production solution, you'd want to use IPC or a shared state file
    print("\nWARNING: This utility creates a separate FTP publisher instance.")
    print("To control the running service, you need to restart it after making changes.")
    print("For immediate effect, consider adding a control endpoint to the web interface.\n")
    
    publisher = get_ftp_publisher()
    
    if command == 'status':
        show_status(publisher)
    
    elif command == 'pause':
        if len(sys.argv) < 3:
            print("ERROR: Please specify duration in minutes")
            print("Example: python ftp_control.py pause 60")
            sys.exit(1)
        
        try:
            duration_minutes = int(sys.argv[2])
            if duration_minutes <= 0:
                print("ERROR: Duration must be positive")
                sys.exit(1)
            
            pause_uploads(publisher, duration_minutes)
        except ValueError:
            print("ERROR: Duration must be a number")
            sys.exit(1)
    
    elif command == 'resume':
        resume_uploads(publisher)
    
    else:
        print(f"ERROR: Unknown command '{command}'")
        print("Valid commands: status, pause, resume")
        sys.exit(1)


if __name__ == '__main__':
    main()
