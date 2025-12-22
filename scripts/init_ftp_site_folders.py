#!/usr/bin/env python3
"""
Initialize FTP Site Folders
Creates the required directory structure on the FTP server for both sites
"""

import ftplib
import sys

# FTP Configuration
FTP_HOST = "ftp.smarterise.com"
FTP_PORT = 21
FTP_USER = "t.ayedun@smarterise.com"
FTP_PASS = "Sm@rterise"

# Sites to initialize
SITES = ["C368", "C468"]

# Subdirectories for each site
SUBDIRS = [
    "thermal",
    "visual", 
    "videos",
    "temperature"
]

def create_directory_structure():
    """Create directory structure on FTP server"""
    try:
        # Connect to FTP
        print(f"Connecting to {FTP_HOST}...")
        ftp = ftplib.FTP()
        ftp.connect(FTP_HOST, FTP_PORT)
        ftp.login(FTP_USER, FTP_PASS)
        ftp.set_pasv(True)
        
        print(f"Connected successfully!")
        print(f"Current directory: {ftp.pwd()}")
        print()
        
        # Create site folders
        for site in SITES:
            print(f"Setting up site: {site}")
            
            # Create site root folder
            try:
                ftp.mkd(site)
                print(f"  ✓ Created /{site}")
            except ftplib.error_perm as e:
                if "exists" in str(e).lower():
                    print(f"  - /{site} already exists")
                else:
                    print(f"  ✗ Failed to create /{site}: {e}")
                    continue
            
            # Create subdirectories
            for subdir in SUBDIRS:
                path = f"{site}/{subdir}"
                try:
                    ftp.mkd(path)
                    print(f"  ✓ Created /{path}")
                except ftplib.error_perm as e:
                    if "exists" in str(e).lower():
                        print(f"  - /{path} already exists")
                    else:
                        print(f"  ✗ Failed to create /{path}: {e}")
            
            print()
        
        # List created directories
        print("Verifying structure:")
        try:
            dirs = ftp.nlst()
            for site in SITES:
                if site in dirs:
                    print(f"✓ {site}/")
                    try:
                        ftp.cwd(site)
                        subdirs = ftp.nlst()
                        for subdir in subdirs:
                            print(f"  ✓ {subdir}/")
                        ftp.cwd("..")
                    except:
                        pass
                else:
                    print(f"✗ {site}/ NOT FOUND")
        except Exception as e:
            print(f"Could not verify: {e}")
        
        ftp.quit()
        print("\n✅ FTP initialization complete!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = create_directory_structure()
    sys.exit(0 if success else 1)
