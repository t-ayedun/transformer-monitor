
import ftplib
import argparse
import os
import logging
from io import BytesIO
import cloudinary
import cloudinary.uploader
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

class CloudinarySyncer:
    def __init__(self, ftp_config, cloudinary_config, site_id):
        self.ftp_config = ftp_config
        self.site_id = site_id
        
        # Configure Cloudinary
        cloudinary.config(
            cloud_name=cloudinary_config['cloud_name'],
            api_key=cloudinary_config['api_key'],
            api_secret=cloudinary_config['api_secret']
        )
        
        self.ftp = None

    def connect_ftp(self):
        self.ftp = ftplib.FTP(self.ftp_config['host'])
        self.ftp.login(self.ftp_config['user'], self.ftp_config['password'])
        logger.info("Connected to FTP")

    def sync_thermal_images(self):
        """Sync thermal images from /{SiteID}/... to Cloudinary"""
        logger.info(f"Syncing thermal images for {self.site_id}...")
        
        # Path: /{SiteID}/
        try:
            self.ftp.cwd(self.site_id)
        except Exception as e:
            logger.error(f"Site directory {self.site_id} not found: {e}")
            return

        # Iterate Date Folders (YYYY-MM-DD)
        dates = []
        self.ftp.retrlines('LIST', dates.append)
        
        for date_item in dates:
            parts = date_item.split()
            date_dir = parts[-1]
            if not date_dir.replace('-','').isdigit(): continue # Skip non-date folders
            
            # Enter Date Dir
            try:
                self.ftp.cwd(date_dir)
                
                # Check for 'thermal' folder
                if 'thermal' in self.ftp.nlst():
                    self.ftp.cwd('thermal')
                    self._process_directory(f"{self.site_id}/{date_dir}", "thermal")
                    self.ftp.cwd('..') # Exit thermal
                
                self.ftp.cwd('..') # Exit date dir
            except Exception as e:
                logger.error(f"Error processing {date_dir}: {e}")
                try: self.ftp.cwd('..') 
                except: pass

    def _process_directory(self, date_context, category):
        """Upload images in current directory"""
        files = []
        self.ftp.retrlines('LIST', files.append)
        
        for file_item in files:
            parts = file_item.split()
            filename = parts[-1]
            
            if filename.endswith('.png') or filename.endswith('.jpg'):
                try:
                    # Check if relevant (redundant check, but safe)
                    # Upload
                    self._upload_to_cloudinary(filename, date_context, category)
                except Exception as e:
                    logger.error(f"Failed to upload {filename}: {e}")

    def _upload_to_cloudinary(self, filename, date_context, category):
        # Download
        bio = BytesIO()
        self.ftp.retrbinary(f"RETR {filename}", bio.write)
        bio.seek(0)
        
        # Cloudinary Folder: thermal_images/{SiteID}/{YYYY-MM-DD}
        # date_context is "SiteID/YYYY-MM-DD"
        # User example: thermal_images/{SiteID}/
        # Let's use: thermal_images/{SiteID}/{YYYY-MM-DD}/
        
        # User requested: "C368 images: .../thermal_images/C368/"
        # Ideally we follow that but keep dates?
        # Let's assume folder structure: thermal_images/{SiteID}/{YYYY-MM-DD} is cleaner.
        # Or flatten to thermal_images/{SiteID} if user insistence.
        # User output suggests "C368 images: .../thermal_images/C368/" implies flat or maybe just root?
        # I'll use `thermal_images/{SiteID}` and let filename sort it, or filename with date.
        
        parts = date_context.split('/') # [SiteID, Date]
        folder = f"thermal_images/{parts[0]}"
        
        public_id = filename.rsplit('.', 1)[0]
        # Ensure public_id is unique if flat folder, or append date?
        # Filename usually has timestamp, so unique.
        
        logger.info(f"Uploading {filename} to {folder}...")
        
        resp = cloudinary.uploader.upload(
            bio,
            folder=folder,
            public_id=public_id,
            resource_type="image",
            overwrite=True # Set to False to prevent re-upload if needed, but True ensures latest
        )
        logger.info(f"  ✓ URL: {resp['secure_url']}")

    def close(self):
        if self.ftp:
            self.ftp.quit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--ftp-host', default='ftp.smarterise.com')
    parser.add_argument('--ftp-user', required=True)
    parser.add_argument('--ftp-pass', required=True)
    parser.add_argument('--site-id', required=True)
    
    # Cloudinary
    parser.add_argument('--cloud-name', default='dfn84o2fl')
    parser.add_argument('--api-key', default='474218481819232')
    parser.add_argument('--api-secret', default='Z1ZRyYP2nD-Z6IhA_J8PbfyiBig')
    
    args = parser.parse_args()
    
    syncer = CloudinarySyncer(
        {'host': args.ftp_host, 'user': args.ftp_user, 'password': args.ftp_pass},
        {'cloud_name': args.cloud_name, 'api_key': args.api_key, 'api_secret': args.api_secret},
        args.site_id
    )
    
    try:
        syncer.connect_ftp()
        syncer.sync_thermal_images()
    finally:
        syncer.close()
