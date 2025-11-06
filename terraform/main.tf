# ============================================================
# Main Terraform Configuration
# ============================================================

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.4"
    }
  }

  # Uncomment below to use S3 backend for state storage
  # backend "s3" {
  #   bucket = "REPLACE_ME_YOUR_TERRAFORM_STATE_BUCKET"
  #   key    = "transformer-monitor/terraform.tfstate"
  #   region = "REPLACE_ME_YOUR_AWS_REGION"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = var.common_tags
  }
}

# Get AWS account info
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# ============================================================
# S3 Bucket for Thermal Images and Videos
# ============================================================

resource "aws_s3_bucket" "thermal_data" {
  bucket = var.s3_bucket_name

  tags = {
    Name = "Transformer Thermal Data"
  }
}

# Enable versioning
resource "aws_s3_bucket_versioning" "thermal_data" {
  bucket = aws_s3_bucket.thermal_data.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Lifecycle rules for cost optimization
resource "aws_s3_bucket_lifecycle_configuration" "thermal_data" {
  bucket = aws_s3_bucket.thermal_data.id

  rule {
    id     = "thermal-images-lifecycle"
    status = "Enabled"

    filter {
      prefix = "images/"
    }

    transition {
      days          = var.data_retention.s3_standard_days
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = var.data_retention.s3_glacier_days
      storage_class = "GLACIER"
    }

    transition {
      days          = var.data_retention.s3_deep_archive_days
      storage_class = "DEEP_ARCHIVE"
    }
  }

  rule {
    id     = "videos-lifecycle"
    status = "Enabled"

    filter {
      prefix = "videos/"
    }

    transition {
      days          = var.data_retention.s3_ia_days
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = var.data_retention.s3_glacier_days
      storage_class = "GLACIER"
    }

    # Videos older than 1 year can be deleted
    expiration {
      days = 365
    }
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "thermal_data" {
  bucket = aws_s3_bucket.thermal_data.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ============================================================
# Timestream Database for Telemetry
# ============================================================

resource "aws_timestreamwrite_database" "telemetry" {
  database_name = "${var.company_name}-transformer-telemetry"

  tags = {
    Name = "Transformer Telemetry Database"
  }
}

resource "aws_timestreamwrite_table" "temperature_readings" {
  database_name = aws_timestreamwrite_database.telemetry.database_name
  table_name    = "temperature_readings"

  retention_properties {
    memory_store_retention_period_in_hours  = var.data_retention.timestream_memory_hours
    magnetic_store_retention_period_in_days = var.data_retention.timestream_magnetic_days
  }

  tags = {
    Name = "Temperature Readings"
  }
}

# ============================================================
# SNS Topic for Alerts
# ============================================================

resource "aws_sns_topic" "temperature_alerts" {
  name = "${var.company_name}-transformer-alerts"

  tags = {
    Name = "Transformer Temperature Alerts"
  }
}

# Subscribe email addresses
resource "aws_sns_topic_subscription" "email_alerts" {
  count = length(var.alert_email_addresses)

  topic_arn = aws_sns_topic.temperature_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email_addresses[count.index]
}

# ============================================================
# IAM Role for IoT Rule
# ============================================================

resource "aws_iam_role" "iot_rule_role" {
  name = "${var.company_name}-transformer-iot-rule-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "iot.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy" "iot_rule_policy" {
  name = "${var.company_name}-transformer-iot-rule-policy"
  role = aws_iam_role.iot_rule_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "timestream:WriteRecords"
        ]
        Resource = aws_timestreamwrite_table.temperature_readings.arn
      },
      {
        Effect = "Allow"
        Action = [
          "timestream:DescribeEndpoints"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "sns:Publish"
        ]
        Resource = aws_sns_topic.temperature_alerts.arn
      }
    ]
  })
}

# ============================================================
# IoT Rule for Temperature Data
# ============================================================

resource "aws_iot_topic_rule" "temperature_to_timestream" {
  name        = "${replace(var.company_name, "-", "_")}_temp_to_timestream"
  description = "Route temperature data to Timestream"
  enabled     = true
  sql         = "SELECT * FROM 'transformers/+/telemetry'"
  sql_version = "2016-03-23"

  timestream {
    database_name = aws_timestreamwrite_database.telemetry.database_name
    table_name    = aws_timestreamwrite_table.temperature_readings.table_name
    role_arn      = aws_iam_role.iot_rule_role.arn

    dimension {
      name  = "site_id"
      value = "$${site_id}"
    }

    dimension {
      name  = "device"
      value = "$${topic(2)}"
    }

    timestamp {
      unit  = "MILLISECONDS"
      value = "$${timestamp()}"
    }
  }
}

# IoT Rule for Temperature Alerts
resource "aws_iot_topic_rule" "temperature_alerts" {
  name        = "${replace(var.company_name, "-", "_")}_temp_alerts"
  description = "Send alerts for high temperatures"
  enabled     = true
  sql         = <<-SQL
    SELECT 
      site_id,
      composite_temperature,
      timestamp,
      '${var.temperature_thresholds.emergency}' as threshold_emergency,
      '${var.temperature_thresholds.critical}' as threshold_critical,
      '${var.temperature_thresholds.warning}' as threshold_warning
    FROM 'transformers/+/telemetry'
    WHERE composite_temperature >= ${var.temperature_thresholds.warning}
  SQL
  sql_version = "2016-03-23"

  sns {
    target_arn = aws_sns_topic.temperature_alerts.arn
    role_arn   = aws_iam_role.iot_rule_role.arn
    message_format = "RAW"
  }
}

# ============================================================
# Create Site Resources (Things, Certificates, Policies)
# ============================================================

module "sites" {
  source = "./modules/site"

  for_each = var.sites

  site_id          = each.key
  site_name        = each.value.name
  site_location    = each.value.location
  site_description = each.value.description
  site_enabled     = each.value.enabled

  aws_region     = var.aws_region
  aws_account_id = var.aws_account_id
  s3_bucket_name = aws_s3_bucket.thermal_data.id
  sns_topic_arn  = aws_sns_topic.temperature_alerts.arn
}

# ============================================================
# Download Root CA Certificate
# ============================================================

resource "null_resource" "download_root_ca" {
  provisioner "local-exec" {
    command = <<-EOT
      mkdir -p ${path.module}/certs
      curl -o ${path.module}/certs/AmazonRootCA1.pem https://www.amazontrust.com/repository/AmazonRootCA1.pem
    EOT
  }

  triggers = {
    always_run = timestamp()
  }
}