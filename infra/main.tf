terraform {
  required_version = ">= 1.5"

  required_providers {
    minio = {
      source  = "aminueza/minio"
      version = "~> 2.0"
    }
  }
}

provider "minio" {
  minio_server   = var.minio_server
  minio_user     = var.minio_user
  minio_password = var.minio_password
  minio_ssl      = false
}

# ── Buckets ──────────────────────────────────────────────────────────────────

resource "minio_s3_bucket" "raw_data" {
  bucket        = "raw-data"
  acl           = "private"
  force_destroy = true
}

resource "minio_s3_bucket" "trusted_data" {
  bucket        = "trusted-data"
  acl           = "private"
  force_destroy = true
}

# ── Pipeline IAM user + policy ───────────────────────────────────────────────

resource "minio_iam_user" "pipeline" {
  name   = "pipeline"
  secret = var.minio_pipeline_secret
}

resource "minio_iam_policy" "rw_buckets" {
  name = "rw-lakehouse-buckets"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:*"]
        Resource = [
          "arn:aws:s3:::${minio_s3_bucket.raw_data.bucket}",
          "arn:aws:s3:::${minio_s3_bucket.raw_data.bucket}/*",
          "arn:aws:s3:::${minio_s3_bucket.trusted_data.bucket}",
          "arn:aws:s3:::${minio_s3_bucket.trusted_data.bucket}/*",
        ]
      }
    ]
  })
}

resource "minio_iam_user_policy_attachment" "pipeline_attach" {
  user_name   = minio_iam_user.pipeline.name
  policy_name = minio_iam_policy.rw_buckets.id
}
