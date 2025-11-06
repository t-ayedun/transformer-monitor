# SETUP INSTRUCTIONS

## What This Does

Creates AWS resources for 3 transformer monitoring sites:
- 2 production sites
- 1 test site

**Estimated Cost**: $5-10/month total

## Step-by-Step Setup

### 1. Prerequisites (One-Time)

Install Terraform:
```bash
# On macOS
brew install terraform

# On Ubuntu/Debian
sudo apt-get update
sudo apt-get install terraform

# On Windows
# Download from https://www.terraform.io/downloads
```

Configure AWS credentials:
```bash
aws configure
# Enter your AWS Access Key ID
# Enter your AWS Secret Access Key
# Enter region (e.g., us-east-1)
```

### 2. Edit Configuration

Open `terraform.tfvars` in a text editor.

Replace EVERY value that says `REPLACE_ME_*`:
```hcl
aws_region = "us-east-1"  # ← Your AWS region
aws_account_id = "123456789012"  # ← Your AWS account ID

company_name = "acme-power"  # ← Your company (lowercase, no spaces)

s3_bucket_name = "acme-transformer-data-2025"  # ← Must be globally unique

sites = {
  "SITE_001" = {
    name        = "Lagos North Substation"  # ← Real site name
    location    = "Ikeja, Lagos"
    description = "100kVA distribution transformer"
    enabled     = true
  },
  # ... repeat for SITE_002 and SITE_TEST
}

alert_email_addresses = [
  "ops@yourcompany.com",  # ← Your email addresses
  "maintenance@yourcompany.com"
]
```

**Save the file.**

### 3. Initialize Terraform
```bash
cd terraform
terraform init
```

You should see: "Terraform has been successfully initialized!"

### 4. Preview Changes
```bash
terraform plan
```

Review what will be created. You should see:
- 3 IoT Things (one per site)
- 3 IoT Certificates
- 3 IoT Policies
- 1 S3 Bucket
- 1 Timestream Database
- 1 SNS Topic
- IAM roles and policies

### 5. Create Resources
```bash
terraform apply
```

Type `yes` when prompted.

This takes 2-3 minutes.

### 6. Save Outputs
```bash
terraform output -json > outputs.json
```

This creates `outputs.json` with all configuration values.

### 7. Confirm Email Subscriptions

Check your inbox for emails from AWS SNS.
Click the confirmation links.

### 8. Provide Info to Developer

Give developer:
1. `outputs.json` file
2. Certificate files in `terraform/certs/` directory

**IMPORTANT**: Do NOT commit `certs/` to git!

## Adding a New Site Later

1. Edit `terraform.tfvars`
2. Add new site to `sites` map:
```hcl
   "SITE_003" = {
     name = "New Site Name"
     location = "Location"
     description = "Description"
     enabled = true
   }
```
3. Run: `terraform apply`

## Viewing Resources

AWS Console locations:
- IoT Things: IoT Core → Manage → Things
- Certificates: IoT Core → Security → Certificates
- S3 Bucket: S3 → Buckets
- Timestream: Amazon Timestream → Databases

## Costs

Monthly estimate for 3 sites:
- IoT Core: $0 (free tier - 500K messages/month)
- S3: $1-2 (image/video storage)
- Timestream: $3-5 (telemetry data)
- SNS: $0 (free tier - email notifications)

**Total: ~$5-10/month**

## Troubleshooting

**"bucket name already taken"**:
- S3 bucket names are globally unique
- Change `s3_bucket_name` in terraform.tfvars

**"invalid credentials"**:
- Run: `aws configure`
- Enter correct AWS credentials

**"permission denied"**:
- Your AWS user needs admin permissions
- Contact AWS account owner

## Cleanup (Delete Everything)

To remove all resources:
```bash
terraform destroy
```

Type `yes` to confirm.

**WARNING**: This deletes all data permanently!