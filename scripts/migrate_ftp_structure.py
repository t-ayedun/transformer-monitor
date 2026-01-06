
import ftplib
import argparse
import os
import re
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FTPMigrator:
    def __init__(self, host, user, password, dry_run=True):
        self.host = host
        self.user = user
        self.password = password
        self.dry_run = dry_run
        self.ftp = None
        self.stats = {'moved': 0, 'errors': 0, 'skipped': 0}

    def connect(self):
        try:
            self.ftp = ftplib.FTP(self.host)
            self.ftp.login(self.user, self.password)
            logger.info("Connected to FTP server")
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise

    def close(self):
        if self.ftp:
            self.ftp.quit()

    def _ensure_dir(self, path):
        """Ensure remote directory exists"""
        if self.dry_run:
            return
            
        parts = path.strip('/').split('/')
        current = ''
        for part in parts:
            current = f"{current}/{part}" if current else part
            try:
                self.ftp.mkd(current)
            except:
                pass # Exists

    def migrate_site(self, site_id):
        """Migrate files for a specific site from old structure to /{SiteID}/{YYYY-MM-DD}/"""
        logger.info(f"Starting migration for site: {site_id}")
        
        # 1. Scan root folders: thermal, visual, videos, videos (legacy root)
        dirs_to_scan = ['thermal', 'visual', 'videos', 'events', 'snapshots']
        
        for root_dir in dirs_to_scan:
            self._scan_and_migrate_dir(root_dir, site_id)
            
        # 2. Scan root for loose files (CSVs)
        # Often CSVs are in C468/ or root?
        # Let's check /{site_id}/ (old folder if exists)
        self._scan_legacy_site_folder(site_id)

    def _scan_and_migrate_dir(self, current_dir, site_id):
        """Recursively scan old directories and move files"""
        try:
            self.ftp.cwd('/')
            try:
                self.ftp.cwd(current_dir)
            except:
                logger.warning(f"Directory not found: {current_dir}")
                return

            items = []
            self.ftp.retrlines('LIST', items.append)
            
            for item in items:
                parts = item.split()
                name = parts[-1]
                
                # Check for recursion
                # LIST format is tricky, assuming unix style
                is_dir = item.startswith('d')
                
                full_path = f"{current_dir}/{name}"
                
                if is_dir:
                    if name in ('.', '..'): continue
                    # Recurse
                    self._scan_and_migrate_dir(full_path, site_id)
                    
                    # Try to remove dir if empty (and not dry run)
                    if not self.dry_run:
                        try:
                            self.ftp.rmd(full_path)
                        except:
                            pass
                else:
                    # File found
                    self._process_file(full_path, name, site_id)

        except Exception as e:
            logger.error(f"Error scanning {current_dir}: {e}")

    def _process_file(self, full_path, filename, site_id):
        """Decide if file needs moving and move it"""
        # We only move files that belong to this site
        # BUT many old files might NOT have site_id in filename if under legacy root folders?
        # E.g. /thermal/2025/12/15/img.png
        # If we are migrating generic folders, we must know which site they belong to.
        # IF multiple sites share the FTP root, this is dangerous unless filename has ID.
        
        # Assumption: Filename usually has SiteID (e.g. C468_...) OR we assume strict ownership.
        # User prompt implies "no overlap", so maybe we assume only files with ID or ALL files if dedicated bucket.
        # Safest: Check filename for site_id.
        
        if site_id not in filename and site_id not in full_path:
            # Maybe generic name like 'recording.h264'? 
            # If so, we skip to be safe, unless user forces.
            # logger.debug(f"Skipping {full_path}: SiteID {site_id} not found in path/name")
            return

        # Determine Date
        # Try to parse from path (e.g. /thermal/2025/12/15/...)
        date_str = None
        path_parts = full_path.split('/')
        
        # Look for YYYY/MM/DD pattern
        for i in range(len(path_parts)-2):
            p1, p2, p3 = path_parts[i], path_parts[i+1], path_parts[i+2]
            if p1.isdigit() and len(p1)==4 and p2.isdigit() and len(p2)==2 and p3.isdigit() and len(p3)==2:
                date_str = f"{p1}-{p2}-{p3}"
                break
        
        # Try filename extraction
        if not date_str:
            # Regex for YYYYMMDD
            match = re.search(r'(\d{8})', filename)
            if match:
                d = match.group(1)
                date_str = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
        
        if not date_str:
             # Fallback to modification time? 
             # FTP MDTM
             try:
                 mdtm = self.ftp.sendcmd(f"MDTM {full_path}")
                 # Format: 213 YYYYMMDDHHMMSS
                 if mdtm.startswith('213 '):
                     ts = mdtm.split()[1]
                     date_str = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
             except:
                 pass

        if not date_str:
            logger.warning(f"Could not determine date for {full_path}, skipping.")
            return

        # Determine Category (thermal, visual, videos, etc.)
        category = 'other'
        if 'thermal' in full_path or 'thermal' in filename.lower(): category = 'thermal'
        elif 'visual' in full_path or 'visual' in filename.lower(): category = 'visual'
        elif 'videos' in full_path or filename.endswith('.h264') or filename.endswith('.mp4'): category = 'videos'
        elif 'events' in full_path: category = 'events'
        elif 'snapshots' in full_path: category = 'snapshots'
        elif filename.endswith('.csv'): category = 'telemetry' # Or root?
        elif filename.endswith('.zip'): category = 'zips'

        # New Path: /{SiteID}/{YYYY-MM-DD}/{category}/{filename}
        # Special case: CSVs usually go to root of date folder?
        # Plan said: /{SiteID}/{YYYY-MM-DD}/{filename}.csv (in simplified view)
        # But categorization is better. Let's stick to 'telemetry' or root of date.
        # "Simplified Flat Alternative" -> root of date for CSV.
        
        if category == 'telemetry' or category == 'zips':
             new_path = f"{site_id}/{date_str}/{filename}"
        else:
             new_path = f"{site_id}/{date_str}/{category}/{filename}"
        
        # Check against old path
        if full_path.strip('/') == new_path.strip('/'):
             return

        logger.info(f"[MOVE] {full_path} -> {new_path}")
        self.stats['moved'] += 1
        
        if not self.dry_run:
            try:
                # Ensure dir
                self._ensure_dir(os.path.dirname(new_path))
                # Rename
                self.ftp.rename(full_path, new_path)
            except Exception as e:
                logger.error(f"Failed to move {full_path}: {e}")
                self.stats['errors'] += 1

    def _scan_legacy_site_folder(self, site_id):
        # Scan /C468/ assuming it exists and has mixed content
        pass # To be implemented if needed

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Migrate FTP files to new structure')
    parser.add_argument('--host', default='ftp.smarterise.com')
    parser.add_argument('--user', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--site-id', required=True, help='Site ID filter (e.g. C468)')
    parser.add_argument('--dry-run', action='store_true', help='Print actions without executing')
    
    args = parser.parse_args()
    
    migrator = FTPMigrator(args.host, args.user, args.password, args.dry_run)
    try:
        migrator.connect()
        migrator.migrate_site(args.site_id)
    finally:
        migrator.close()
        print("\nMigration Stats:")
        print(f"Moved:   {migrator.stats['moved']}")
        print(f"Errors:  {migrator.stats['errors']}")
