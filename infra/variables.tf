variable "minio_server" {
  description = "MinIO server address (host:port). Use localhost:9000 when running Terraform outside Docker."
  default     = "localhost:9000"
}

variable "minio_user" {
  description = "MinIO root user (MINIO_ROOT_USER)"
  default     = "minioadmin"
}

variable "minio_password" {
  description = "MinIO root password (MINIO_ROOT_PASSWORD)"
  default     = "minioadmin"
  sensitive   = true
}

variable "minio_pipeline_secret" {
  description = "Secret key for the pipeline IAM user"
  default     = "pipeline-secret-123"
  sensitive   = true
}
