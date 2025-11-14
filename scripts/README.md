# Provisioning and Deployment Scripts

Automation scripts for provisioning new sites and deploying to devices.

## Directory Structure

```
scripts/
├── provision/
│   ├── provision_site.py      # Main provisioning orchestrator
│   ├── aws_iot_setup.py        # AWS IoT Thing provisioning
│   ├── generate_config.py      # Configuration file generator
│   ├── __init__.py             # Python module init
│   └── requirements.txt        # Python dependencies
├── deploy_balena.sh            # Balena deployment automation
├── upload_certificates.sh      # Certificate upload to Balena device
└── README.md                   # This file
```

## Quick Start

### Provision a New Site

```bash
# Install dependencies
pip install -r provision/requirements.txt

# Provision site
python provision/provision_site.py \
  --site-id SITE_001 \
  --site-name "Main Substation" \
  --transformer-sn TX-12345 \
  --aws-region us-east-1
```

### Deploy to Balena

```bash
# Deploy to Balena fleet
./deploy_balena.sh SITE_001

# Flash SD card
balena local flash provisioned_sites/SITE_001/balena-SITE_001.img

# Upload certificates (after device online)
./upload_certificates.sh SITE_001
```

## Script Reference

### provision_site.py

**Purpose:** Complete site provisioning automation

**Usage:**
```bash
python provision/provision_site.py \
  --site-id SITE_001 \
  --site-name "Main Substation" \
  --transformer-sn TX-12345 \
  --aws-region us-east-1 \
  --timezone America/New_York \
  --address "123 Power St, City, State" \
  --balena-app transformer-monitor \
  --output-dir ./provisioned_sites
```

**Arguments:**
- `--site-id` (required) - Unique site identifier
- `--site-name` (required) - Human-readable site name
- `--transformer-sn` (required) - Transformer serial number
- `--aws-region` (default: us-east-1) - AWS region
- `--timezone` (default: UTC) - Site timezone
- `--address` - Physical site address
- `--ftp-host` - FTP server (optional)
- `--ftp-username` - FTP username (optional)
- `--ftp-password` - FTP password (optional)
- `--balena-app` (default: transformer-monitor) - Balena app name
- `--output-dir` (default: ./provisioned_sites) - Output directory

**Output:**
- AWS IoT Thing and certificates
- Site configuration files
- S3 bucket structure
- Balena configuration
- Deployment package (ZIP)

**Exit Codes:**
- 0: Success
- 1: Provisioning failed

### aws_iot_setup.py

**Purpose:** AWS IoT Thing provisioning (standalone use)

**Usage:**
```bash
# Provision
python provision/aws_iot_setup.py SITE_001-monitor us-east-1

# Deprovision (cleanup)
python provision/aws_iot_setup.py SITE_001-monitor us-east-1 deprovision
```

**Features:**
- Creates AWS IoT Thing with attributes
- Generates and downloads certificates
- Creates IoT policy with necessary permissions
- Attaches policy and certificate to thing
- Retrieves IoT endpoint

**Output Files:**
- `device.pem.crt` - Device certificate
- `private.pem.key` - Private key (600 permissions)
- `public.pem.key` - Public key
- `AmazonRootCA1.pem` - Amazon Root CA
- `iot_policy.json` - IoT policy document

### generate_config.py

**Purpose:** Generate site configuration files (standalone use)

**Usage:**
```bash
python provision/generate_config.py SITE_001 "Main Substation" TX-12345
```

**Features:**
- Generates `site_config.yaml`
- Generates `aws_config.yaml`
- Generates `ftp_config.yaml` (if FTP configured)
- Generates `.env` for Docker

**Output:**
- `site_config.yaml` - Site and hardware configuration
- `aws_config.yaml` - AWS IoT and S3 configuration
- `.env` - Environment variables for Docker

### deploy_balena.sh

**Purpose:** Automate Balena deployment

**Usage:**
```bash
./deploy_balena.sh SITE_001
```

**Prerequisites:**
- Balena CLI installed and authenticated
- Site provisioned (certificates and config exist)
- Balena application created

**What it does:**
1. Checks Balena application exists
2. Registers device
3. Sets environment variables from provisioned config
4. Builds and pushes Docker image to Balena
5. Downloads configured Balena OS image
6. Configures OS image with device credentials

**Output:**
- Configured Balena OS image ready to flash

**Exit Codes:**
- 0: Success
- 1: Deployment failed

### upload_certificates.sh

**Purpose:** Upload AWS IoT certificates to Balena device

**Usage:**
```bash
./upload_certificates.sh SITE_001
```

**Prerequisites:**
- Device registered and online in Balena
- Certificates provisioned

**What it does:**
1. Checks device is online
2. Creates `/data/certificates/` directory on device
3. Uploads certificate files via `balena scp`
4. Sets restrictive permissions on private key (600)

**Exit Codes:**
- 0: Success
- 1: Upload failed

## Environment Variables

Scripts use these environment variables (optional):

- `BALENA_APP` - Override default Balena application name
- `AWS_PROFILE` - Use specific AWS CLI profile
- `AWS_REGION` - Override default AWS region

## Error Handling

All scripts include error handling:

- Exit on first error (`set -e` in bash scripts)
- Descriptive error messages
- Non-zero exit codes on failure
- Resource cleanup on failure

## Security Considerations

### Certificate Management

- Private keys are set to 600 permissions automatically
- Certificates are never committed to version control
- Provisioning output excluded via `.gitignore`
- Certificates should be backed up securely after generation

### Credential Storage

- FTP passwords can be passed via command line (not recommended for production)
- Use environment variables or secure secret storage
- AWS credentials use AWS CLI configuration (IAM roles preferred)

### Balena Security

- Balena authentication required before deployment
- Environment variables can be set via Balena dashboard (preferred for secrets)
- Certificate upload uses secure Balena SSH tunnel

## Troubleshooting

### "AWS credentials not configured"

**Solution:**
```bash
aws configure
# Enter your AWS access key, secret key, and region
```

Or use IAM role if running on EC2.

### "Balena CLI not found"

**Solution:**
```bash
npm install -g balena-cli
balena login
```

### "Thing already exists"

**Solution:**
Script will use existing thing. To start fresh:
```bash
python provision/aws_iot_setup.py SITE_001-monitor us-east-1 deprovision
```

### "Device not online"

**Solution:**
Wait for device to boot and connect to internet. Check status:
```bash
balena devices
```

### "Permission denied" when running scripts

**Solution:**
```bash
chmod +x scripts/*.sh
chmod +x scripts/provision/*.py
```

## Development

### Testing Provisioning

Test provisioning without AWS resources:

```bash
# Set AWS to dry-run mode (mock, not implemented yet)
# Test config generation only
python provision/generate_config.py TESTSITE "Test Site" TX-TEST
```

### Adding Custom Configuration

Modify `generate_config.py` to add custom fields:

```python
def generate_site_config(self, timezone='UTC', address='', custom_field=None):
    config = {
        # ... existing config ...
        'custom': {
            'field': custom_field
        }
    }
```

## Best Practices

1. **Provisioning Workflow**:
   - Provision all sites before deploying
   - Review generated configs before deployment
   - Backup certificates immediately after provisioning
   - Use consistent naming convention (SITE_001, SITE_002, etc.)

2. **Balena Deployment**:
   - Use separate Balena apps per customer/region
   - Set common variables at app level
   - Set site-specific variables at device level
   - Tag devices with metadata (customer, location, etc.)

3. **Certificate Management**:
   - Store certificates in password manager
   - Rotate certificates annually
   - Never commit certificates to git
   - Keep backup in encrypted storage

4. **Multi-Site Deployment**:
   - Use batch provisioning for multiple sites
   - Pre-configure SD cards before shipping
   - Document deployment in spreadsheet/database
   - Verify each deployment with health check

## Support

For issues or questions:

1. Check [PROVISIONING.md](../PROVISIONING.md) for detailed documentation
2. Review error messages and troubleshooting section
3. Check Balena dashboard for device status
4. Review AWS IoT Core for thing status
5. Contact operations team

## License

Same as main project.
