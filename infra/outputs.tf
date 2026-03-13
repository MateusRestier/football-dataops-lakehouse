output "raw_bucket" {
  description = "Name of the raw-data bucket"
  value       = minio_s3_bucket.raw_data.bucket
}

output "trusted_bucket" {
  description = "Name of the trusted-data bucket"
  value       = minio_s3_bucket.trusted_data.bucket
}

output "pipeline_user" {
  description = "IAM user name for pipeline access"
  value       = minio_iam_user.pipeline.name
}
