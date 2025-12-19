import sys
import os
import time
from pathlib import Path
import yaml
import logging

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / 'src'))

from ftp_publisher import FTPPublisher

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_manual_upload():
    print("--- Manual FTP Upload Test ---")
    
    # 1. Load Config
    config_path = Path('config/site_config.yaml')
    if not config_path.exists():
        print(f"❌ config/site_config.yaml not found. Trying C468...")
        config_path = Path('config/site_config.C468.yaml')
    
    print(f"Loading config from: {config_path}")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    ftp_conf = config.get('ftp_storage', {})
    print(f"Config loaded. Host: {ftp_conf.get('host')}, User: {ftp_conf.get('username')}, Remote Dir: {ftp_conf.get('remote_dir')}")

    # 2. Initialize Publisher
    print("\nInitializing FTPPublisher...")
    try:
        publisher = FTPPublisher(
            host=ftp_conf.get('host'),
            username=ftp_conf.get('username'),
            password=ftp_conf.get('password'),
            remote_dir=ftp_conf.get('remote_dir'),
            port=ftp_conf.get('port', 21),
            passive=ftp_conf.get('passive', True)
        )
        print("✅ Publisher initialized.")
    except Exception as e:
        print(f"❌ Failed to initialize publisher: {e}")
        return

    # 3. Create Test File
    test_file = Path('test_upload_manual.txt')
    with open(test_file, 'w') as f:
        f.write(f"This is a manual upload test at {time.ctime()}")
    print(f"\nCreated local test file: {test_file}")

    # 4. Attempt Upload
    remote_path = "videos/test_upload_manual.txt"
    print(f"Attempting valid upload to: {remote_path} ...")
    
    try:
        success = publisher.upload_file(str(test_file), remote_path)
        if success:
            print(f"✅ Upload SUCCESSFUL! Check FTP folder '{ftp_conf.get('remote_dir')}/videos'")
        else:
            print("❌ Upload FAILED (method returned False).")
    except Exception as e:
        print(f"❌ Upload Exception: {e}")
        import traceback
        traceback.print_exc()

    # Cleanup
    if test_file.exists():
        test_file.unlink()
        print("\nCleaned up local test file.")

if __name__ == "__main__":
    test_manual_upload()
