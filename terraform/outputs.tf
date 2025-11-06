# ============================================================
# Terraform Outputs
# ============================================================
# These values are displayed after 'terraform apply'
# Use 'terraform output -json > outputs.json' to save them
# ============================================================

output "iot_endpoint" {
  description = "AWS IoT endpoint (use in device configuration)"
  value       = data.aws_iot_endpoint.endpoint.endpoint_address
}

output "s3_bucket_name" {
  description = "S3 bucket for thermal data"
  value       = aws_s3_bucket.thermal_data.id
}

output "timestream_database" {
  description = "Timestream database name"
  value       = aws_timestreamwrite_database.telemetry.database_name
}

output "timestream_table" {
  description = "Timestream table name"
  value       = aws_timestreamwrite_table.temperature_readings.table_name
}

output "sns_topic_arn" {
  description = "SNS topic for alerts"
  value       = aws_sns_topic.temperature_alerts.arn
}

output "site_configurations" {
  description = "Configuration for each site (use in Balena device variables)"
  value = {
    for site_id, site in module.sites : site_id => {
      site_id        = site_id
      thing_name     = site.thing_name
      certificate_id = site.certificate_id
      policy_name    = site.policy_name
      
      # These values go in Balena device variables
      device_variables = {
        SITE_ID         = site_id
        IOT_THING_NAME  = site.thing_name
        IOT_ENDPOINT    = data.aws_iot_endpoint.endpoint.endpoint_address
        AWS_REGION      = var.aws_region
        S3_BUCKET_NAME  = aws_s3_bucket.thermal_data.id
      }
      
      # Certificate files location
      certificates = {
        device_cert = "${path.module}/certs/${site_id}/certificate.pem.crt"
        private_key = "${path.module}/certs/${site_id}/private.pem.key"
        root_ca     = "${path.module}/certs/AmazonRootCA1.pem"
      }
    }
  }
  sensitive = false
}

output "setup_instructions" {
  description = "Next steps after terraform apply"
  value = <<-EOT
    
    ============================================================
    TERRAFORM APPLY COMPLETE!
    ============================================================
    
    Next Steps:
    
    1. SAVE OUTPUTS
       Run: terraform output -json > outputs.json
    
    2. CONFIRM EMAIL SUBSCRIPTIONS
       Check emails at: ${join(", ", var.alert_email_addresses)}
       Click confirmation links in AWS SNS emails
    
    3. UPLOAD CERTIFICATES TO DEVICES
       For each site, upload these files to /data/certs/:
       ${join("\n       ", [for site_id in keys(var.sites) : "- ${site_id}: ./certs/${site_id}/"])}
    
    4. CONFIGURE BALENA DEVICE VARIABLES
       For each device, set these variables:
       (See "site_configurations" output for exact values)
       - SITE_ID
       - IOT_THING_NAME
       - IOT_ENDPOINT
       - AWS_REGION
       - S3_BUCKET_NAME
    
    5. VERIFY CONNECTIVITY
       - Check device logs: balena logs <device-uuid> --tail
       - Monitor AWS IoT Core test client
       - Check S3 bucket for incoming data
    
    IoT Endpoint: ${data.aws_iot_endpoint.endpoint.endpoint_address}
    S3 Bucket: ${aws_s3_bucket.thermal_data.id}
    
    ============================================================
  EOT
}

# Get IoT endpoint
data "aws_iot_endpoint" "endpoint" {
  endpoint_type = "iot:Data-ATS"
}