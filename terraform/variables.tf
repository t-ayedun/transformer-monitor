# ============================================================
# Variable Definitions - DO NOT EDIT
# (Edit values in terraform.tfvars instead)
# ============================================================

variable "aws_region" {
  description = "AWS region to deploy resources"
  type        = string
}

variable "aws_account_id" {
  description = "AWS Account ID"
  type        = string
}

variable "company_name" {
  description = "Company name for resource naming"
  type        = string
}

variable "environment" {
  description = "Environment (production, staging, test)"
  type        = string
  default     = "production"
}

variable "s3_bucket_name" {
  description = "S3 bucket name for thermal data storage (must be globally unique)"
  type        = string
}

variable "sites" {
  description = "Map of transformer monitoring sites"
  type = map(object({
    name        = string
    location    = string
    description = string
    enabled     = bool
  }))
}

variable "alert_email_addresses" {
  description = "Email addresses for alerts"
  type        = list(string)
}

variable "temperature_thresholds" {
  description = "Temperature alert thresholds in Celsius"
  type = object({
    warning   = number
    critical  = number
    emergency = number
  })
}

variable "data_retention" {
  description = "Data retention policies"
  type = object({
    s3_standard_days      = number
    s3_ia_days            = number
    s3_glacier_days       = number
    s3_deep_archive_days  = number
    timestream_memory_hours = number
    timestream_magnetic_days = number
  })
}

variable "common_tags" {
  description = "Common tags for all resources"
  type        = map(string)
}