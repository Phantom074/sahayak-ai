
variable "environment" {}
variable "lambda_function_names" { type = map(string) }

# CloudWatch Log Groups with 90-day retention
resource "aws_cloudwatch_log_group" "lambda" {
  for_each          = var.lambda_function_names
  name              = "/aws/lambda/${each.value}"
  retention_in_days = var.environment == "prod" ? 90 : 14
}

# Dashboard
resource "aws_cloudwatch_dashboard" "sahayak" {
  dashboard_name = "Sahayak-${var.environment}"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", width = 12, height = 6,
        properties = {
          title  = "API Latency P50/P95/P99 (ms)"
          metrics = [
            ["Sahayak/Services", "RequestDuration", "ServiceName", "conversation-orchestrator", { stat = "p50", label = "P50" }],
            ["...", { stat = "p95", label = "P95" }],
            ["...", { stat = "p99", label = "P99" }]
          ]
          period = 60
        }
      },
      {
        type = "metric", width = 12, height = 6,
        properties = {
          title  = "Error Rate"
          metrics = [
            ["Sahayak/Services", "FailedRequests", "ServiceName", "conversation-orchestrator"],
            ["Sahayak/Services", "SuccessfulRequests", "ServiceName", "conversation-orchestrator"]
          ]
          period = 60
        }
      }
    ]
  })
}

# Alarms
resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "sahayak-${var.environment}-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FailedRequests"
  namespace           = "Sahayak/Services"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "Error rate exceeded threshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "high_latency" {
  alarm_name          = "sahayak-${var.environment}-high-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "RequestDuration"
  namespace           = "Sahayak/Services"
  period              = 60
  extended_statistic  = "p95"
  threshold           = 5000
  alarm_description   = "P95 latency exceeded 5 seconds"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_sns_topic" "alerts" {
  name = "sahayak-${var.environment}-alerts"
}
