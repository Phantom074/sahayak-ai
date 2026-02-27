# infrastructure/terraform/environments/prod/main.tf
# Production environment — India primary region ap-south-1 (Mumbai)

terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }

  backend "s3" {
    bucket         = "sahayak-terraform-state-prod"
    key            = "sahayak/prod/terraform.tfstate"
    region         = "ap-south-1"
    encrypt        = true
    dynamodb_table = "sahayak-terraform-locks"
  }
}

provider "aws" {
  region = "ap-south-1"

  default_tags {
    tags = {
      Project     = "sahayak-ai"
      Environment = "prod"
      ManagedBy   = "terraform"
      Compliance  = "DPDP-2023"
      DataRegion  = "ap-south-1"
    }
  }
}

# ── Networking ────────────────────────────────────────────────────────

module "networking" {
  source = "../../modules/networking"

  environment         = "prod"
  vpc_cidr            = "10.0.0.0/16"
  availability_zones  = ["ap-south-1a", "ap-south-1b", "ap-south-1c"]
  private_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnet_cidrs  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  # VPC endpoints to avoid internet for AWS services (security + cost)
  enable_s3_endpoint         = true
  enable_dynamodb_endpoint   = true
  enable_bedrock_endpoint    = true
  enable_opensearch_endpoint = false  # Not supported via VPC endpoint yet
}

# ── Security (KMS, IAM, WAF) ─────────────────────────────────────────

module "security" {
  source = "../../modules/security"

  environment        = "prod"
  vpc_id             = module.networking.vpc_id
  enable_shield_advanced = true      # DDoS protection for national platform
  waf_rate_limit     = 10000         # Requests per 5-min window per IP
}

# ── Storage (DynamoDB, OpenSearch, S3) ───────────────────────────────

module "storage" {
  source = "../../modules/storage"

  environment         = "prod"
  kms_key_arn         = module.security.pii_kms_key_arn
  private_subnet_ids  = module.networking.private_subnet_ids
  vpc_id              = module.networking.vpc_id

  # OpenSearch — 3-node multi-AZ for HA
  opensearch_instance_type  = "r6g.xlarge.search"
  opensearch_instance_count = 3
  opensearch_volume_gb      = 100

  # DynamoDB on-demand (handles viral traffic spikes)
  dynamodb_billing_mode = "PAY_PER_REQUEST"

  # S3 lifecycle policies for cost optimization
  audio_files_ia_days       = 30     # Move to Infrequent Access after 30d
  audio_files_expire_days   = 90     # Delete audio files after 90d
  scheme_docs_archive_days  = 365    # Archive scheme PDFs after 1y
}

# ── AI Services ──────────────────────────────────────────────────────

module "ai_services" {
  source = "../../modules/ai-services"

  environment = "prod"
  kms_key_arn = module.security.pii_kms_key_arn

  # Transcribe custom vocabulary for government terms
  create_transcribe_vocabulary = true
  vocabulary_name              = "sahayak-govterm-vocabulary"
  vocabulary_s3_key            = "config/transcribe-vocabulary.txt"

  # Polly — neural voices only
  polly_output_bucket = module.storage.audio_output_bucket_id
}

# ── Compute (Lambda functions) ────────────────────────────────────────

module "compute" {
  source = "../../modules/compute"

  environment        = "prod"
  private_subnet_ids = module.networking.private_subnet_ids
  security_group_ids = [module.security.lambda_sg_id]

  opensearch_endpoint = module.storage.opensearch_endpoint
  sessions_table_name = module.storage.sessions_table_name
  users_table_name    = module.storage.users_table_name
  schemes_table_name  = module.storage.schemes_table_name
  rules_table_name    = module.storage.rules_table_name
  event_bus_name      = module.messaging.event_bus_name

  kms_key_arn = module.security.pii_kms_key_arn

  # Provisioned concurrency to eliminate cold starts on critical path
  orchestrator_provisioned_concurrency  = 50
  retrieval_provisioned_concurrency     = 30
  eligibility_provisioned_concurrency   = 20

  # Reserved concurrency to prevent Lambda from consuming all account capacity
  orchestrator_reserved_concurrency     = 500
  voice_service_reserved_concurrency    = 300
}

# ── API Gateway ──────────────────────────────────────────────────────

module "api_gateway" {
  source = "../../modules/api-gateway"

  environment            = "prod"
  cognito_user_pool_arn  = module.auth.user_pool_arn
  lambda_invoke_arns     = module.compute.lambda_invoke_arns
  waf_acl_arn            = module.security.waf_acl_arn

  # Custom domain
  domain_name    = "api.sahayak.gov.in"
  certificate_arn = var.acm_certificate_arn

  # Throttling
  default_throttling_burst_limit = 5000
  default_throttling_rate_limit  = 10000
}

# ── Messaging (EventBridge, SQS, SNS) ────────────────────────────────

module "messaging" {
  source = "../../modules/messaging"

  environment = "prod"
  kms_key_arn = module.security.pii_kms_key_arn

  # DLQ retry config
  sqs_max_receive_count         = 3
  sqs_visibility_timeout_seconds = 30
}

# ── Auth (Cognito) ───────────────────────────────────────────────────

module "auth" {
  source = "../../modules/auth"

  environment    = "prod"
  app_name       = "sahayak-ai"
  # MFA for admin users only (citizens use OTP login via phone)
  mfa_config     = "OPTIONAL"
  kms_key_arn    = module.security.pii_kms_key_arn
}

# ── Observability ─────────────────────────────────────────────────────

module "observability" {
  source = "../../modules/observability"

  environment            = "prod"
  lambda_function_names  = module.compute.all_function_names
  opensearch_domain_name = module.storage.opensearch_domain_name

  # Alarm thresholds
  orchestrator_p95_threshold_ms = 3000
  error_rate_threshold_percent  = 2.0
  rag_zero_result_threshold     = 0.05   # Alert if >5% queries return no results

  # Alert destinations
  alert_sns_topic_arn = module.messaging.alerts_sns_topic_arn
  oncall_email        = var.oncall_email
}

# ── CloudFront (CDN for audio files) ─────────────────────────────────

module "cdn" {
  source = "../../modules/cdn"

  environment              = "prod"
  audio_output_bucket_id   = module.storage.audio_output_bucket_id
  audio_output_bucket_arn  = module.storage.audio_output_bucket_arn

  # Cache audio responses aggressively (most are reusable)
  default_ttl = 300   # 5 minutes
  max_ttl     = 3600  # 1 hour

  waf_acl_arn = module.security.cloudfront_waf_acl_arn
}

# ── Outputs ──────────────────────────────────────────────────────────

output "api_endpoint" {
  value       = module.api_gateway.invoke_url
  description = "Production API base URL"
}

output "opensearch_endpoint" {
  value     = module.storage.opensearch_endpoint
  sensitive = true
}

output "cognito_user_pool_id" {
  value = module.auth.user_pool_id
}

output "event_bus_name" {
  value = module.messaging.event_bus_name
}
