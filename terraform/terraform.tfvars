# ============================================================
# TRANSFORMER MONITORING - TERRAFORM CONFIGURATION
# ============================================================
# INSTRUCTIONS:
# 1. Replace ALL values that say "REPLACE_ME_*"
# 2. Keep the structure exactly as shown
# 3. Save this file
# 4. Run: terraform apply
# ============================================================

# ------------------------------------------------------------
# AWS Configuration
# ------------------------------------------------------------
aws_region = "REPLACE_ME_YOUR_AWS_REGION"  # Example: "us-east-1" or "eu-west-1"
aws_account_id = "REPLACE_ME_YOUR_AWS_ACCOUNT_ID"  # Example: "123456789012"

# Your company name (used for naming resources)
company_name = "REPLACE_ME_COMPANY_NAME"  # Example: "acme-power" (lowercase, no spaces)

# Project environment
environment = "production"  # Options: "production", "staging", "test"

# ------------------------------------------------------------
# S3 Bucket Configuration
# ------------------------------------------------------------
# Note: S3 bucket names must be globally unique
s3_bucket_name = "REPLACE_ME_UNIQUE_BUCKET_NAME"  # Example: "acme-power-transformer-data-2025"

# ------------------------------------------------------------
# Site Definitions
# ------------------------------------------------------------
# Add your 3 sites here (2 production + 1 test)
# Keep the structure exactly as shown

sites = {
  # PRODUCTION SITE 1
  "SITE_001" = {
    name        = "REPLACE_ME_SITE_1_NAME"        # Example: "Lagos North Substation"
    location    = "REPLACE_ME_SITE_1_LOCATION"    # Example: "Ikeja, Lagos, Nigeria"
    description = "REPLACE_ME_SITE_1_DESCRIPTION" # Example: "Main distribution transformer - 100kVA"
    enabled     = true                             # Set to false to disable alerts
  },

  # PRODUCTION SITE 2
  "SITE_002" = {
    name        = "REPLACE_ME_SITE_2_NAME"        # Example: "Lagos South Substation"
    location    = "REPLACE_ME_SITE_2_LOCATION"    # Example: "Victoria Island, Lagos, Nigeria"
    description = "REPLACE_ME_SITE_2_DESCRIPTION" # Example: "Secondary distribution - 50kVA"
    enabled     = true
  },

  # TEST SITE
  "SITE_TEST" = {
    name        = "REPLACE_ME_TEST_SITE_NAME"     # Example: "Test Lab Transformer"
    location    = "REPLACE_ME_TEST_LOCATION"      # Example: "Office Lab, Lagos"
    description = "Testing and development site"
    enabled     = false  # No alerts for test site
  }
}

# ------------------------------------------------------------
# Alert Configuration
# ------------------------------------------------------------
# Email addresses for temperature alerts
alert_email_addresses = [
  "REPLACE_ME_EMAIL_1",  # Example: "operations@yourcompany.com"
  "REPLACE_ME_EMAIL_2",  # Example: "maintenance@yourcompany.com"
]

# Temperature thresholds (Celsius)
temperature_thresholds = {
  warning   = 80  # Send warning alert
  critical  = 90  # Send critical alert
  emergency = 100 # Send emergency alert
}

# ------------------------------------------------------------
# Data Retention
# ------------------------------------------------------------
# How long to keep data in different storage tiers

data_retention = {
  # S3 storage lifecycle
  s3_standard_days    = 30   # Keep in S3 Standard for 30 days
  s3_ia_days          = 90   # Move to Infrequent Access after 90 days
  s3_glacier_days     = 365  # Move to Glacier after 1 year
  s3_deep_archive_days = 1095 # Move to Deep Archive after 3 years

  # Timestream retention
  timestream_memory_hours = 24    # Keep in memory for 24 hours (fast queries)
  timestream_magnetic_days = 365  # Keep in magnetic storage for 1 year
}

# ------------------------------------------------------------
# Tags (for cost tracking and organization)
# ------------------------------------------------------------
common_tags = {
  Project     = "transformer-monitoring"
  ManagedBy   = "terraform"
  Environment = "production"
  Owner       = "REPLACE_ME_YOUR_NAME"  # Example: "john.doe@yourcompany.com"
  CostCenter  = "REPLACE_ME_COST_CENTER" # Example: "operations" or "IT-001"
}