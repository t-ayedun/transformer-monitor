import ftplib
import os

HOST = "ftp.smarterise.com"
USER = "t.ayedun@smarterise.com"
PASS = "Sm@rterise"
PORT = 21
TARGET_SITE = "C468"

def init_ftp():
    print(f"Connecting to {HOST}...")
    try:
        ftp = ftplib.FTP()
        ftp.connect(HOST, PORT)
        ftp.login(USER, PASS)
        print(f"✅ Login successful.")
        
        # 1. Create Site Directory
        try:
            ftp.mkd(TARGET_SITE)
            print(f"✅ Created directory '{TARGET_SITE}'")
        except Exception as e:
            print(f"ℹ️ Directory '{TARGET_SITE}' likely exists ({e})")

        # 2. Enter Site Directory
        try:
            ftp.cwd(TARGET_SITE)
            print(f"✅ Entered '{TARGET_SITE}'")
        except Exception as e:
            print(f"❌ Could not enter '{TARGET_SITE}': {e}")
            return

        # 3. Create Subdirectories
        subdirs = ['videos', 'images', 'temperature', 'snapshots', 'events']
        for sd in subdirs:
            try:
                ftp.mkd(sd)
                print(f"✅ Created '{sd}'")
            except Exception as e:
                print(f"ℹ️ '{sd}' likely exists ({e})")
                
        print("\nFinal Structure:")
        ftp.retrlines('LIST')
        ftp.quit()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    init_ftp()
