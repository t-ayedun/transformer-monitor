# ============================================================
# Site Module - Creates resources for one monitoring site
# ============================================================

# Create IoT Thing
resource "aws_iot_thing" "transformer" {
  name = "transformer-monitor-${var.site_id}"

  attributes = {
    site_id     = var.site_id
    site_name   = var.site_name
    location    = var.site_location
    description = var.site_description
  }
}

# Create and activate certificate
resource "aws_iot_certificate" "cert" {
  active = true
}

# Create IoT Policy
resource "aws_iot_policy" "policy" {
  name = "transformer-policy-${var.site_id}"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["iot:Connect"]
        Resource = [
          "arn:aws:iot:${var.aws_region}:${var.aws_account_id}:client/transformer-monitor-${var.site_id}"
        ]
      },
      {
        Effect = "Allow"
        Action = ["iot:Publish"]
        Resource = [
          "arn:aws:iot:${var.aws_region}:${var.aws_account_id}:topic/transformers/transformer-monitor-${var.site_id}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = ["iot:Subscribe"]
        Resource = [
          "arn:aws:iot:${var.aws_region}:${var.aws_account_id}:topicfilter/transformers/transformer-monitor-${var.site_id}/commands"
        ]
      },
      {
        Effect = "Allow"
        Action = ["iot:Receive"]
        Resource = [
          "arn:aws:iot:${var.aws_region}:${var.aws_account_id}:topic/transformers/transformer-monitor-${var.site_id}/commands"
        ]
      }
    ]
  })
}

# Attach policy to certificate
resource "aws_iot_policy_attachment" "attach_policy" {
  policy = aws_iot_policy.policy.name
  target = aws_iot_certificate.cert.arn
}

# Attach certificate to thing
resource "aws_iot_thing_principal_attachment" "attach_cert" {
  thing     = aws_iot_thing.transformer.name
  principal = aws_iot_certificate.cert.arn
}

# Save certificate files locally
resource "local_file" "certificate" {
  content         = aws_iot_certificate.cert.certificate_pem
  filename        = "${path.root}/certs/${var.site_id}/certificate.pem.crt"
  file_permission = "0644"
}

resource "local_file" "private_key" {
  content         = aws_iot_certificate.cert.private_key
  filename        = "${path.root}/certs/${var.site_id}/private.pem.key"
  file_permission = "0600"
}

resource "local_file" "public_key" {
  content         = aws_iot_certificate.cert.public_key
  filename        = "${path.root}/certs/${var.site_id}/public.pem.key"
  file_permission = "0644"
}