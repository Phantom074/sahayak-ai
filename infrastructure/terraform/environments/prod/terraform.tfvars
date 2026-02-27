# infrastructure/terraform/environments/prod/terraform.tfvars
# Production variable values — non-sensitive only
# Secrets injected via GitHub Actions secrets or AWS Secrets Manager

environment = "prod"
aws_region  = "ap-south-1"

# OpenSearch
opensearch_instance_type  = "r6g.xlarge.search"
opensearch_instance_count = 3
opensearch_volume_gb      = 100

# Lambda
orchestrator_provisioned_concurrency = 50
retrieval_provisioned_concurrency    = 30
eligibility_provisioned_concurrency  = 20
orchestrator_reserved_concurrency    = 500

# Security
enable_shield_advanced = true
waf_rate_limit         = 10000

# Monitoring thresholds
orchestrator_p95_threshold_ms  = 3000
error_rate_threshold_percent   = 2.0
rag_zero_result_threshold      = 0.05

# Cost optimization
audio_files_ia_days       = 30
audio_files_expire_days   = 90
scheme_docs_archive_days  = 365
