# infrastructure/terraform/modules/security/main.tf
# KMS keys, IAM roles, WAF, and Shield configuration

variable "environment" {}
variable "vpc_id" {}
variable "enable_shield_advanced" { default = false }
variable "waf_rate_limit" { default = 10000 }

# ── KMS Keys ─────────────────────────────────────────────────────────

resource "aws_kms_key" "pii" {
  description             = "Sahayak ${var.environment} PII Data Encryption"
  deletion_window_in_days = 30
  enable_key_rotation     = true
  multi_region            = false   # Data localization: stay in ap-south-1

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow Lambda encryption"
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.orchestrator_lambda.arn
        }
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:ReEncrypt*"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = [
              "dynamodb.ap-south-1.amazonaws.com",
              "s3.ap-south-1.amazonaws.com"
            ]
          }
        }
      },
      {
        Sid    = "Allow CloudWatch Logs"
        Effect = "Allow"
        Principal = {
          Service = "logs.ap-south-1.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Classification = "SENSITIVE"
    Compliance     = "DPDP-2023"
  }
}

resource "aws_kms_alias" "pii" {
  name          = "alias/sahayak-${var.environment}-pii"
  target_key_id = aws_kms_key.pii.key_id
}

# ── IAM Roles (Least Privilege per Service) ───────────────────────────

resource "aws_iam_role" "orchestrator_lambda" {
  name = "sahayak-${var.environment}-orchestrator-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "orchestrator_policy" {
  name = "sahayak-${var.environment}-orchestrator-policy"
  role = aws_iam_role.orchestrator_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BedrockInvoke"
        Effect = "Allow"
        Action = ["bedrock:InvokeModel"]
        Resource = [
          "arn:aws:bedrock:ap-south-1::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0",
          "arn:aws:bedrock:ap-south-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
        ]
      },
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = [
          "arn:aws:dynamodb:ap-south-1:${data.aws_caller_identity.current.account_id}:table/sahayak-${var.environment}-sessions",
          "arn:aws:dynamodb:ap-south-1:${data.aws_caller_identity.current.account_id}:table/sahayak-${var.environment}-sessions/index/*",
          "arn:aws:dynamodb:ap-south-1:${data.aws_caller_identity.current.account_id}:table/sahayak-${var.environment}-users"
        ]
      },
      {
        Sid    = "InvokeDownstreamLambdas"
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = [
          "arn:aws:lambda:ap-south-1:${data.aws_caller_identity.current.account_id}:function:sahayak-${var.environment}-voice-service",
          "arn:aws:lambda:ap-south-1:${data.aws_caller_identity.current.account_id}:function:sahayak-${var.environment}-scheme-retrieval-service",
          "arn:aws:lambda:ap-south-1:${data.aws_caller_identity.current.account_id}:function:sahayak-${var.environment}-eligibility-engine"
        ]
      },
      {
        Sid    = "EventBridgePutEvents"
        Effect = "Allow"
        Action = ["events:PutEvents"]
        Resource = "arn:aws:events:ap-south-1:${data.aws_caller_identity.current.account_id}:event-bus/sahayak-${var.environment}"
      },
      {
        Sid    = "VPCAccess"
        Effect = "Allow"
        Action = [
          "ec2:CreateNetworkInterface",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DeleteNetworkInterface"
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:ap-south-1:*:*"
      },
      {
        Sid    = "XRayTracing"
        Effect = "Allow"
        Action = [
          "xray:PutTraceSegments",
          "xray:PutTelemetryRecords"
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchMetrics"
        Effect = "Allow"
        Action = ["cloudwatch:PutMetricData"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role" "voice_lambda" {
  name = "sahayak-${var.environment}-voice-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "voice_policy" {
  name = "sahayak-${var.environment}-voice-policy"
  role = aws_iam_role.voice_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "TranscribeAccess"
        Effect = "Allow"
        Action = [
          "transcribe:StartTranscriptionJob",
          "transcribe:GetTranscriptionJob",
          "transcribe:DeleteTranscriptionJob"
        ]
        Resource = "*"
      },
      {
        Sid    = "PollyAccess"
        Effect = "Allow"
        Action = [
          "polly:StartSpeechSynthesisTask",
          "polly:GetSpeechSynthesisTask",
          "polly:SynthesizeSpeech"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3AudioAccess"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:GeneratePresignedUrl"]
        Resource = [
          "arn:aws:s3:::sahayak-${var.environment}-audio-input-*/*",
          "arn:aws:s3:::sahayak-${var.environment}-audio-output-*/*",
          "arn:aws:s3:::sahayak-${var.environment}-transcripts-*/*"
        ]
      }
    ]
  })
}

# ── Lambda Security Group ─────────────────────────────────────────────

resource "aws_security_group" "lambda" {
  name        = "sahayak-${var.environment}-lambda"
  description = "Lambda functions — egress only"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS to AWS services"
  }

  egress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP for health checks"
  }
}

# ── WAF (API Gateway Protection) ─────────────────────────────────────

resource "aws_wafv2_web_acl" "api" {
  name  = "sahayak-${var.environment}-api-waf"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  # Block common attack patterns
  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1

    override_action { none {} }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CommonRuleSet"
      sampled_requests_enabled   = true
    }
  }

  # Rate limiting per IP
  rule {
    name     = "RateLimitRule"
    priority = 2

    action { block {} }

    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimit"
      sampled_requests_enabled   = true
    }
  }

  # Block SQL injection
  rule {
    name     = "SQLiRule"
    priority = 3

    override_action { none {} }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesSQLiRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "SQLiRule"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "sahayak-${var.environment}-waf"
    sampled_requests_enabled   = true
  }
}

data "aws_caller_identity" "current" {}

output "pii_kms_key_arn" { value = aws_kms_key.pii.arn }
output "pii_kms_key_id" { value = aws_kms_key.pii.key_id }
output "lambda_sg_id" { value = aws_security_group.lambda.id }
output "waf_acl_arn" { value = aws_wafv2_web_acl.api.arn }
output "cloudfront_waf_acl_arn" { value = aws_wafv2_web_acl.api.arn }
output "orchestrator_lambda_role_arn" { value = aws_iam_role.orchestrator_lambda.arn }
output "voice_lambda_role_arn" { value = aws_iam_role.voice_lambda.arn }
