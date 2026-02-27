# infrastructure/terraform/modules/storage/main.tf
# DynamoDB tables, OpenSearch domain, and S3 buckets

variable "environment" {}
variable "kms_key_arn" {}
variable "private_subnet_ids" { type = list(string) }
variable "vpc_id" {}
variable "opensearch_instance_type" { default = "t3.small.search" }
variable "opensearch_instance_count" { default = 1 }
variable "opensearch_volume_gb" { default = 20 }
variable "dynamodb_billing_mode" { default = "PAY_PER_REQUEST" }
variable "audio_files_ia_days" { default = 30 }
variable "audio_files_expire_days" { default = 90 }
variable "scheme_docs_archive_days" { default = 365 }

locals {
  is_prod = var.environment == "prod"
}

# ── DynamoDB Tables ───────────────────────────────────────────────────

resource "aws_dynamodb_table" "sessions" {
  name           = "sahayak-${var.environment}-sessions"
  billing_mode   = var.dynamodb_billing_mode
  hash_key       = "session_id"
  range_key      = "sk"

  attribute {
    name = "session_id"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "user_id"
    type = "S"
  }

  global_secondary_index {
    name            = "UserSessionsIndex"
    hash_key        = "user_id"
    range_key       = "sk"
    projection_type = "INCLUDE"
    non_key_attributes = ["session_id", "created_at", "channel", "language"]
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = local.is_prod
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }
}

resource "aws_dynamodb_table" "users" {
  name         = "sahayak-${var.environment}-users"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "user_id"
  range_key    = "sk"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }

  point_in_time_recovery {
    enabled = local.is_prod
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }
}

resource "aws_dynamodb_table" "schemes" {
  name         = "sahayak-${var.environment}-schemes"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "scheme_id"
  range_key    = "sk"

  attribute {
    name = "scheme_id"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  attribute {
    name = "ministry"
    type = "S"
  }

  global_secondary_index {
    name            = "MinistryIndex"
    hash_key        = "ministry"
    range_key       = "scheme_id"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }
}

resource "aws_dynamodb_table" "eligibility_rules" {
  name         = "sahayak-${var.environment}-eligibility-rules"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "scheme_id"
  range_key    = "sk"

  attribute {
    name = "scheme_id"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }
}

resource "aws_dynamodb_table" "audit_log" {
  name         = "sahayak-${var.environment}-audit-log"
  billing_mode = var.dynamodb_billing_mode
  hash_key     = "user_id"
  range_key    = "sk"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }

  # Audit logs: 7-year retention per DPDP compliance
  # TTL NOT enabled — these must be kept

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }
}

# ── OpenSearch Domain ─────────────────────────────────────────────────

resource "aws_security_group" "opensearch" {
  name        = "sahayak-${var.environment}-opensearch"
  description = "OpenSearch cluster access — Lambda only"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    description = "HTTPS from Lambda security group"
    # Reference Lambda SG — passed in as variable in full implementation
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_opensearch_domain" "schemes" {
  domain_name    = "sahayak-${var.environment}-schemes"
  engine_version = "OpenSearch_2.11"

  cluster_config {
    instance_type          = var.opensearch_instance_type
    instance_count         = var.opensearch_instance_count
    zone_awareness_enabled = var.opensearch_instance_count > 1

    dynamic "zone_awareness_config" {
      for_each = var.opensearch_instance_count > 1 ? [1] : []
      content {
        availability_zone_count = min(var.opensearch_instance_count, 3)
      }
    }
  }

  ebs_options {
    ebs_enabled = true
    volume_size = var.opensearch_volume_gb
    volume_type = "gp3"
    throughput  = 250
    iops        = 3000
  }

  encrypt_at_rest {
    enabled    = true
    kms_key_id = var.kms_key_arn
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  vpc_options {
    subnet_ids         = slice(var.private_subnet_ids, 0, min(length(var.private_subnet_ids), var.opensearch_instance_count))
    security_group_ids = [aws_security_group.opensearch.id]
  }

  advanced_options = {
    "rest.action.multi.allow_explicit_index" = "true"
    "indices.query.bool.max_clause_count"    = "1024"
  }

  advanced_security_options {
    enabled                        = true
    anonymous_auth_enabled         = false
    internal_user_database_enabled = false

    master_user_options {
      master_user_arn = var.kms_key_arn  # Replace with actual IAM role ARN
    }
  }

  # Auto-tune for production
  dynamic "auto_tune_options" {
    for_each = local.is_prod ? [1] : []
    content {
      desired_state = "ENABLED"
    }
  }
}

# ── S3 Buckets ────────────────────────────────────────────────────────

resource "aws_s3_bucket" "audio_input" {
  bucket = "sahayak-${var.environment}-audio-input-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audio_input" {
  bucket = aws_s3_bucket.audio_input.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "audio_input" {
  bucket = aws_s3_bucket.audio_input.id
  rule {
    id     = "expire-audio-input"
    status = "Enabled"
    expiration {
      days = 7   # Audio input files deleted after 7 days
    }
  }
}

resource "aws_s3_bucket" "audio_output" {
  bucket = "sahayak-${var.environment}-audio-output-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_lifecycle_configuration" "audio_output" {
  bucket = aws_s3_bucket.audio_output.id
  rule {
    id     = "tiered-audio-output"
    status = "Enabled"
    transition {
      days          = var.audio_files_ia_days
      storage_class = "STANDARD_IA"
    }
    expiration {
      days = var.audio_files_expire_days
    }
  }
}

resource "aws_s3_bucket" "scheme_docs" {
  bucket = "sahayak-${var.environment}-scheme-docs-${data.aws_caller_identity.current.account_id}"
}

resource "aws_s3_bucket_versioning" "scheme_docs" {
  bucket = aws_s3_bucket.scheme_docs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "scheme_docs" {
  bucket = aws_s3_bucket.scheme_docs.id
  rule {
    id     = "archive-old-scheme-docs"
    status = "Enabled"
    transition {
      days          = var.scheme_docs_archive_days
      storage_class = "GLACIER_IR"
    }
  }
}

data "aws_caller_identity" "current" {}

# ── Outputs ──────────────────────────────────────────────────────────

output "sessions_table_name" { value = aws_dynamodb_table.sessions.name }
output "users_table_name" { value = aws_dynamodb_table.users.name }
output "schemes_table_name" { value = aws_dynamodb_table.schemes.name }
output "rules_table_name" { value = aws_dynamodb_table.eligibility_rules.name }
output "opensearch_endpoint" { value = aws_opensearch_domain.schemes.endpoint }
output "opensearch_domain_name" { value = aws_opensearch_domain.schemes.domain_name }
output "audio_input_bucket_id" { value = aws_s3_bucket.audio_input.id }
output "audio_output_bucket_id" { value = aws_s3_bucket.audio_output.id }
output "audio_output_bucket_arn" { value = aws_s3_bucket.audio_output.arn }
output "scheme_docs_bucket_id" { value = aws_s3_bucket.scheme_docs.id }
