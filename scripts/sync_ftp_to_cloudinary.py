
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

    def sync_thermal_images(self, days_back=2):
        """
        Sync thermal images from /{SiteID}/... to Cloudinary
        
        Args:
            days_back: Number of recent days to scan (default 2: today + yesterday)
        """
        logger.info(f"Syncing thermal images for {self.site_id} (last {days_back} days)...")
        
        # Path: /{SiteID}/
        try:
            self.ftp.cwd(self.site_id)
        except Exception as e:
            logger.error(f"Site directory {self.site_id} not found: {e}")
            return

        # Calculate target dates
        from datetime import  timedelta
        target_dates = set()
        for i in range(days_back):
            d = datetime.now() - timedelta(days=i)
            target_dates.add(d.strftime('%Y-%m-%d'))
            
        # Iterate Date Folders (YYYY-MM-DD)
        try:
            items = []
            self.ftp.retrlines('LIST', items.append)
        except Exception as e:
            logger.error(f"Failed to list directory: {e}")
            return
        
        for item in items:
            parts = item.split()
            date_dir = parts[-1]
            
            # Optimization: Only process relevant dates
            if date_dir not in target_dates:
                continue
            
            logger.info(f"Scanning date: {date_dir}")
            
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
        try:
            self.ftp.retrlines('LIST', files.append)
        except:
            return
        
        for file_item in files:
            parts = file_item.split()
            filename = parts[-1]
            
            if filename.endswith('.png') or filename.endswith('.jpg'):
                try:
                    # Upload
                    self._upload_to_cloudinary(filename, date_context, category)
                except Exception as e:
                    logger.error(f"Failed to upload {filename}: {e}")

    def _upload_to_cloudinary(self, filename, date_context, category):
        # Download
        bio = BytesIO()
        self.ftp.retrbinary(f"RETR {filename}", bio.write)
        bio.seek(0)
        
        # Cloudinary Folder: thermal_images/{SiteID}
        # We flatten daily folders into one SiteID bucket for easier web app access,
        # relying on filename timestamps for sorting.
        parts = date_context.split('/') # [SiteID, Date]
        folder = f"thermal_images/{parts[0]}"
        
        public_id = filename.rsplit('.', 1)[0]
        
        # Check if already exists? Cloudinary handles this with 'overwrite=True' 
        # but for speed we might want to skip.
        # However, checking existence is an API call too.
        # We'll just upload (overwrite ensures updates).
        
        # logger.info(f"Uploading {filename} to {folder}...")
        
        try:
            resp = cloudinary.uploader.upload(
                bio,
                folder=folder,
                public_id=public_id,
                resource_type="image",
                overwrite=True
            )
            logger.info(f"  ✓ Uploaded {filename}")
        except Exception as e:
            logger.error(f"Cloudinary error: {e}")

    def close(self):
        if self.ftp:
            self.ftp.quit()

# AWS Lambda Handler
def lambda_handler(event, context):
    """
    AWS Lambda Entry Point
    Expects environment variables:
    - FTP_HOST
    - FTP_USER
    - FTP_PASS
    - SITE_ID
    - CLOID_NAME
    - API_KEY
    - API_SECRET
    """
    ftp_config = {
        'host': os.environ.get('FTP_HOST', 'ftp.smarterise.com'),
        'user': os.environ['FTP_USER'], # Required
        'password': os.environ['FTP_PASS'] # Required
    }
    
    cloudinary_config = {
        'cloud_name': os.environ.get('CLOUD_NAME', 'dfn84o2fl'),
        'api_key': os.environ.get('API_KEY', '474218481819232'),
        'api_secret': os.environ.get('API_SECRET', 'Z1ZRyYP2nD-Z6IhA_J8PbfyiBig')
    }
    
    site_id = os.environ.get('SITE_ID', 'C468')
    
    syncer = CloudinarySyncer(ftp_config, cloudinary_config, site_id)
    try:
        syncer.connect_ftp()
        syncer.sync_thermal_images(days_back=2)
        return {'statusCode': 200, 'body': 'Sync completed'}
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return {'statusCode': 500, 'body': str(e)}
    finally:
        syncer.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--ftp-host', default=os.environ.get('FTP_HOST', 'ftp.smarterise.com'))
    parser.add_argument('--ftp-user', default=os.environ.get('FTP_USER'))
    parser.add_argument('--ftp-pass', default=os.environ.get('FTP_PASS'))
    parser.add_argument('--site-id', default=os.environ.get('SITE_ID'))
    
    # Cloudinary
    parser.add_argument('--cloud-name', default=os.environ.get('CLOUD_NAME', 'dfn84o2fl'))
    parser.add_argument('--api-key', default=os.environ.get('API_KEY', '474218481819232'))
    parser.add_argument('--api-secret', default=os.environ.get('API_SECRET', 'Z1ZRyYP2nD-Z6IhA_J8PbfyiBig'))
    
    args = parser.parse_args()
    
    # Validation for CLI
    if not args.ftp_user or not args.ftp_pass or not args.site_id:
        print("Error: --ftp-user, --ftp-pass, and --site-id are required (or set via env vars)")
        exit(1)
    
    syncer = CloudinarySyncer(
        {'host': args.ftp_host, 'user': args.ftp_user, 'password': args.ftp_pass},
        {'cloud_name': args.cloud_name, 'api_key': args.api_key, 'api_secret': args.api_secret},
        args.site_id
    )
    
    try:
        syncer.connect_ftp()
        syncer.sync_thermal_images(days_back=2)
    finally:
        syncer.close()
