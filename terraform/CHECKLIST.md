# Pre-Flight Checklist

Before running `terraform apply`, verify:

## ✓ Checklist

### Configuration File (`terraform.tfvars`)
- [ ] `aws_region` set (e.g., "us-east-1")
- [ ] `aws_account_id` set (find in AWS Console → top right)
- [ ] `company_name` set (lowercase, no spaces)
- [ ] `s3_bucket_name` set (must be globally unique)
- [ ] All 3 sites configured:
  - [ ] SITE_001 name, location, description filled
  - [ ] SITE_002 name, location, description filled
  - [ ] SITE_TEST name, location, description filled
- [ ] `alert_email_addresses` contains valid emails
- [ ] Temperature thresholds make sense (warning < critical < emergency)
- [ ] Data retention periods acceptable
- [ ] `common_tags` Owner and CostCenter filled

### AWS Setup
- [ ] AWS CLI installed (`aws --version`)
- [ ] AWS credentials configured (`aws sts get-caller-identity`)
- [ ] Correct AWS region selected
- [ ] User has administrator permissions

### Terraform Setup
- [ ] Terraform installed (`terraform version`)
- [ ] In correct directory (`cd terraform`)
- [ ] Initialized (`terraform init` completed)

### Post-Apply Checklist
- [ ] `terraform apply` completed successfully
- [ ] No errors in output
- [ ] `outputs.json` file created
- [ ] Email confirmation received for all alert addresses
- [ ] Email confirmations clicked
- [ ] Certificates generated in `certs/` directory (3 folders)
- [ ] Root CA certificate downloaded (`certs/AmazonRootCA1.pem`)
- [ ] Outputs provided to developer

## Quick Test Commands
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Check what will be created
terraform plan

# See current outputs
terraform output

# List certificate files
ls -R certs/

# Verify IoT endpoint
aws iot describe-endpoint --endpoint-type iot:Data-ATS
```

## Success Criteria

After `terraform apply`, you should have:
1. ✅ 3 IoT Things in AWS IoT Core
2. ✅ 3 active certificates
3. ✅ 1 S3 bucket
4. ✅ 1 Timestream database with 1 table
5. ✅ 1 SNS topic with 2 email subscriptions
6. ✅ 2 IoT Rules (data routing + alerts)
7. ✅ Certificate files in `terraform/certs/SITE_001/`, `certs/SITE_002/`, `certs/SITE_TEST/`

## If Something Goes Wrong
```bash
# See detailed error
terraform plan

# Destroy and start over
terraform destroy
# Edit terraform.tfvars to fix issues
terraform apply

# Get help
terraform --help
```

## Contact Developer If:
- [ ] Terraform errors you don't understand
- [ ] Resources not created in AWS
- [ ] Certificate files missing
- [ ] Need to modify infrastructure