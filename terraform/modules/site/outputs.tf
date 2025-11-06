output "thing_name" {
  description = "IoT Thing name"
  value       = aws_iot_thing.transformer.name
}

output "thing_arn" {
  description = "IoT Thing ARN"
  value       = aws_iot_thing.transformer.arn
}

output "certificate_id" {
  description = "Certificate ID"
  value       = aws_iot_certificate.cert.id
}

output "certificate_arn" {
  description = "Certificate ARN"
  value       = aws_iot_certificate.cert.arn
}

output "policy_name" {
  description = "IoT Policy name"
  value       = aws_iot_policy.policy.name
}