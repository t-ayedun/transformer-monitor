#!/usr/bin/env python3
"""
Site Provisioning Script
Automates the complete provisioning of a new transformer monitoring site

Usage:
    python provision_site.py --site-id SITE_001 --site-name "Main Substation" \
        --transformer-sn TX-12345 --aws-region us-east-1

This script will:
1. Create AWS IoT Thing and generate certificates
2. Generate site configuration files
3. Create S3 bucket structure
4. Set up IoT policies and permissions
5. Generate deployment package
"""

import argparse
import sys
import os
import json
import yaml
from pathlib import Path
from datetime import datetime
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from aws_iot_setup import AWSIoTProvisioner
from generate_config import ConfigGenerator


class SiteProvisioner:
    """Orchestrates complete site provisioning"""

    def __init__(self, args):
        self.site_id = args.site_id
        self.site_name = args.site_name
        self.transformer_sn = args.transformer_sn
        self.aws_region = args.aws_region
        self.timezone = args.timezone
        self.site_address = args.address
        self.output_dir = Path(args.output_dir) / self.site_id

        # Optional FTP configuration
        self.ftp_host = args.ftp_host
        self.ftp_username = args.ftp_username
        self.ftp_password = args.ftp_password

        # Balena configuration
        self.balena_app = args.balena_app
        self.balena_device_name = f"{self.site_id}-monitor"

        self.output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"  Transformer Monitor - Site Provisioning")
        print(f"{'='*60}")
        print(f"Site ID:           {self.site_id}")
        print(f"Site Name:         {self.site_name}")
        print(f"Transformer SN:    {self.transformer_sn}")
        print(f"AWS Region:        {self.aws_region}")
        print(f"Output Directory:  {self.output_dir}")
        print(f"{'='*60}\n")

    def provision(self):
        """Execute complete provisioning workflow"""
        try:
            # Step 1: AWS IoT Provisioning
            print("\n[Step 1/5] Provisioning AWS IoT Thing...")
            aws_config = self.provision_aws_iot()

            # Step 2: Generate Site Configuration
            print("\n[Step 2/5] Generating site configuration...")
            self.generate_site_config(aws_config)

            # Step 3: Create S3 Structure
            print("\n[Step 3/5] Setting up S3 bucket structure...")
            self.setup_s3_structure()

            # Step 4: Generate Balena Configuration
            print("\n[Step 4/5] Generating Balena configuration...")
            self.generate_balena_config(aws_config)

            # Step 5: Create Deployment Package
            print("\n[Step 5/5] Creating deployment package...")
            self.create_deployment_package()

            # Print summary
            self.print_summary()

            return True

        except Exception as e:
            print(f"\n❌ Provisioning failed: {e}")
            import traceback
            traceback.print_exc()
            return False

    def provision_aws_iot(self):
        """Provision AWS IoT Thing and certificates"""
        provisioner = AWSIoTProvisioner(
            region=self.aws_region,
            thing_name=f"{self.site_id}-monitor",
            output_dir=self.output_dir / 'certificates'
        )

        # Create IoT Thing
        thing_arn = provisioner.create_thing(
            thing_name=f"{self.site_id}-monitor",
            attributes={
                'site_id': self.site_id,
                'site_name': self.site_name,
                'transformer_sn': self.transformer_sn,
                'device_type': 'thermal_monitor'
            }
        )
        print(f"  ✓ Created IoT Thing: {thing_arn}")

        # Create and attach certificates
        cert_info = provisioner.create_certificates()
        print(f"  ✓ Generated certificates: {cert_info['certificateId']}")

        # Create and attach policy
        policy_name = f"{self.site_id}-monitor-policy"
        provisioner.create_policy(
            policy_name=policy_name,
            thing_name=f"{self.site_id}-monitor"
        )
        print(f"  ✓ Created IoT policy: {policy_name}")

        # Get IoT endpoint
        endpoint = provisioner.get_iot_endpoint()
        print(f"  ✓ IoT Endpoint: {endpoint}")

        return {
            'thing_name': f"{self.site_id}-monitor",
            'thing_arn': thing_arn,
            'endpoint': endpoint,
            'region': self.aws_region,
            'certificates': cert_info,
            'policy_name': policy_name
        }

    def generate_site_config(self, aws_config):
        """Generate site configuration files"""
        generator = ConfigGenerator(
            site_id=self.site_id,
            site_name=self.site_name,
            transformer_sn=self.transformer_sn,
            output_dir=self.output_dir / 'config'
        )

        # Generate site_config.yaml
        site_config = generator.generate_site_config(
            timezone=self.timezone,
            address=self.site_address
        )
        print(f"  ✓ Generated site_config.yaml")

        # Generate aws_config.yaml
        aws_config_yaml = generator.generate_aws_config(
            iot_endpoint=aws_config['endpoint'],
            thing_name=aws_config['thing_name'],
            region=aws_config['region'],
            cert_paths={
                'ca_cert': '/data/certificates/AmazonRootCA1.pem',
                'device_cert': '/data/certificates/device.pem.crt',
                'private_key': '/data/certificates/private.pem.key'
            }
        )
        print(f"  ✓ Generated aws_config.yaml")

        # Generate FTP config if provided
        if self.ftp_host:
            ftp_config = generator.generate_ftp_config(
                host=self.ftp_host,
                username=self.ftp_username,
                password=self.ftp_password
            )
            print(f"  ✓ Generated ftp_config.yaml")

        # Generate environment file for Balena
        env_file = self.output_dir / 'config' / '.env'
        with open(env_file, 'w') as f:
            f.write(f"SITE_ID={self.site_id}\n")
            f.write(f"SITE_NAME={self.site_name}\n")
            f.write(f"TRANSFORMER_SN={self.transformer_sn}\n")
            f.write(f"TIMEZONE={self.timezone}\n")
            f.write(f"AWS_REGION={self.aws_region}\n")
            f.write(f"IOT_ENDPOINT={aws_config['endpoint']}\n")
            f.write(f"IOT_THING_NAME={aws_config['thing_name']}\n")
        print(f"  ✓ Generated .env file")

    def setup_s3_structure(self):
        """Create S3 bucket folder structure"""
        try:
            import boto3

            s3_client = boto3.client('s3', region_name=self.aws_region)
            bucket_name = f"transformer-monitor-data-{self.aws_region}"

            # Create bucket if it doesn't exist
            try:
                s3_client.head_bucket(Bucket=bucket_name)
                print(f"  ✓ Using existing bucket: {bucket_name}")
            except:
                if self.aws_region == 'us-east-1':
                    s3_client.create_bucket(Bucket=bucket_name)
                else:
                    s3_client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': self.aws_region}
                    )
                print(f"  ✓ Created S3 bucket: {bucket_name}")

            # Create folder structure
            folders = [
                f"{self.site_id}/thermal_frames/",
                f"{self.site_id}/snapshots/",
                f"{self.site_id}/videos/",
                f"{self.site_id}/logs/"
            ]

            for folder in folders:
                s3_client.put_object(Bucket=bucket_name, Key=folder, Body=b'')

            print(f"  ✓ Created folder structure for {self.site_id}")

        except Exception as e:
            print(f"  ⚠ S3 setup warning: {e}")
            print(f"  → You may need to create the S3 bucket manually")

    def generate_balena_config(self, aws_config):
        """Generate Balena device configuration"""
        balena_dir = self.output_dir / 'balena'
        balena_dir.mkdir(exist_ok=True)

        # Create device environment variables file
        env_vars = {
            'SITE_ID': self.site_id,
            'SITE_NAME': self.site_name,
            'TRANSFORMER_SN': self.transformer_sn,
            'TIMEZONE': self.timezone,
            'AWS_REGION': self.aws_region,
            'IOT_ENDPOINT': aws_config['endpoint'],
            'IOT_THING_NAME': aws_config['thing_name'],
            'PRODUCTION_MODE': 'true'
        }

        if self.ftp_host:
            env_vars.update({
                'FTP_HOST': self.ftp_host,
                'FTP_USERNAME': self.ftp_username,
                'FTP_PASSWORD': self.ftp_password
            })

        # Save as JSON for Balena CLI import
        with open(balena_dir / 'device_env_vars.json', 'w') as f:
            json.dump(env_vars, f, indent=2)

        print(f"  ✓ Generated Balena environment variables")

        # Create device registration script
        register_script = balena_dir / 'register_device.sh'
        with open(register_script, 'w') as f:
            f.write(f"""#!/bin/bash
# Balena Device Registration Script
# Generated: {datetime.now().isoformat()}

BALENA_APP="{self.balena_app or 'transformer-monitor'}"
DEVICE_NAME="{self.balena_device_name}"

echo "Registering device with Balena..."
echo "App: $BALENA_APP"
echo "Device: $DEVICE_NAME"

# Create device
balena device register $BALENA_APP --name $DEVICE_NAME

# Set environment variables
balena env add -d $DEVICE_NAME SITE_ID "{self.site_id}"
balena env add -d $DEVICE_NAME SITE_NAME "{self.site_name}"
balena env add -d $DEVICE_NAME TRANSFORMER_SN "{self.transformer_sn}"
balena env add -d $DEVICE_NAME TIMEZONE "{self.timezone}"
balena env add -d $DEVICE_NAME AWS_REGION "{self.aws_region}"
balena env add -d $DEVICE_NAME IOT_ENDPOINT "{aws_config['endpoint']}"
balena env add -d $DEVICE_NAME IOT_THING_NAME "{aws_config['thing_name']}"
balena env add -d $DEVICE_NAME PRODUCTION_MODE "true"

echo "✓ Device registered successfully"
echo "Next steps:"
echo "1. Download OS image: balena os download $BALENA_APP -o balena.img"
echo "2. Flash to SD card: balena local flash balena.img"
echo "3. Insert SD card into Raspberry Pi and power on"
""")
        register_script.chmod(0o755)
        print(f"  ✓ Generated Balena registration script")

    def create_deployment_package(self):
        """Create deployment package with all files"""
        package_dir = self.output_dir / 'deployment_package'
        package_dir.mkdir(exist_ok=True)

        # Copy certificates
        cert_src = self.output_dir / 'certificates'
        cert_dst = package_dir / 'certificates'
        if cert_src.exists():
            shutil.copytree(cert_src, cert_dst, dirs_exist_ok=True)

        # Copy configuration
        config_src = self.output_dir / 'config'
        config_dst = package_dir / 'config'
        if config_src.exists():
            shutil.copytree(config_src, config_dst, dirs_exist_ok=True)

        # Create README
        readme = package_dir / 'README.md'
        with open(readme, 'w') as f:
            f.write(f"""# Deployment Package: {self.site_id}

**Site:** {self.site_name}
**Transformer:** {self.transformer_sn}
**Generated:** {datetime.now().isoformat()}

## Contents

- `certificates/` - AWS IoT certificates and keys
- `config/` - Site and AWS configuration files
- `README.md` - This file

## Deployment Instructions

### Option 1: Balena Deployment (Recommended)

1. **Register device with Balena:**
   ```bash
   cd ../balena
   ./register_device.sh
   ```

2. **Download Balena OS:**
   ```bash
   balena os download transformer-monitor -o balena.img
   ```

3. **Flash to SD card:**
   ```bash
   balena local flash balena.img
   ```

4. **Copy certificates to device:**
   After device comes online, copy certificates:
   ```bash
   balena ssh {self.balena_device_name}
   # On device:
   mkdir -p /data/certificates
   exit

   # Copy certificates
   balena scp certificates/* {self.balena_device_name}:/data/certificates/
   ```

### Option 2: Manual Deployment

1. **Flash Raspberry Pi OS to SD card**

2. **Copy deployment package to Pi:**
   ```bash
   scp -r deployment_package/* pi@<pi-ip>:/home/pi/transformer-monitor/
   ```

3. **SSH to Pi and install:**
   ```bash
   ssh pi@<pi-ip>
   cd /home/pi/transformer-monitor
   sudo ./install.sh
   ```

## Verification

1. **Check device is online:**
   ```bash
   balena devices | grep {self.site_id}
   ```

2. **View logs:**
   ```bash
   balena logs {self.balena_device_name} --tail
   ```

3. **Test AWS IoT connection:**
   ```bash
   balena ssh {self.balena_device_name}
   python3 -c "from aws_publisher import AWSPublisher; print('AWS IoT SDK available')"
   ```

## Support

For issues during deployment, contact the operations team.

## Security Notice

⚠️ **IMPORTANT:** The `certificates/` directory contains sensitive credentials.
- Store securely
- Do not commit to version control
- Delete after successful deployment
- Keep backup in secure location (e.g., password manager, encrypted storage)
""")

        print(f"  ✓ Created deployment package")

        # Create archive
        archive_name = f"{self.site_id}_deployment_{datetime.now().strftime('%Y%m%d')}"
        shutil.make_archive(
            self.output_dir / archive_name,
            'zip',
            package_dir
        )
        print(f"  ✓ Created archive: {archive_name}.zip")

    def print_summary(self):
        """Print provisioning summary"""
        print(f"\n{'='*60}")
        print(f"  Provisioning Complete!")
        print(f"{'='*60}")
        print(f"\n📦 Deployment Package: {self.output_dir}/deployment_package/")
        print(f"📄 Certificate Files:   {self.output_dir}/certificates/")
        print(f"⚙️  Configuration Files: {self.output_dir}/config/")
        print(f"☁️  Balena Scripts:      {self.output_dir}/balena/")
        print(f"\n✓ AWS IoT Thing:        {self.site_id}-monitor")
        print(f"✓ Site Configuration:   {self.site_id}")
        print(f"\n{'='*60}")
        print(f"\n📋 Next Steps:")
        print(f"  1. Review deployment package")
        print(f"  2. Securely store certificates")
        print(f"  3. Register device with Balena (see balena/register_device.sh)")
        print(f"  4. Deploy to Raspberry Pi")
        print(f"  5. Verify device connectivity")
        print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Provision a new transformer monitoring site',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Required arguments
    parser.add_argument('--site-id', required=True,
                        help='Site identifier (e.g., SITE_001)')
    parser.add_argument('--site-name', required=True,
                        help='Human-readable site name')
    parser.add_argument('--transformer-sn', required=True,
                        help='Transformer serial number')

    # AWS arguments
    parser.add_argument('--aws-region', default='us-east-1',
                        help='AWS region (default: us-east-1)')

    # Site information
    parser.add_argument('--timezone', default='UTC',
                        help='Site timezone (default: UTC)')
    parser.add_argument('--address', default='',
                        help='Site physical address')

    # FTP arguments (optional)
    parser.add_argument('--ftp-host', help='FTP server hostname')
    parser.add_argument('--ftp-username', help='FTP username')
    parser.add_argument('--ftp-password', help='FTP password')

    # Balena arguments
    parser.add_argument('--balena-app', default='transformer-monitor',
                        help='Balena application name')

    # Output arguments
    parser.add_argument('--output-dir', default='./provisioned_sites',
                        help='Output directory for provisioned files')

    args = parser.parse_args()

    # Provision site
    provisioner = SiteProvisioner(args)
    success = provisioner.provision()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
