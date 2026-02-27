
variable "environment" {}

# SQS Dead Letter Queue for failed Lambda invocations
resource "aws_sqs_queue" "dlq" {
  name                      = "sahayak-${var.environment}-dlq"
  message_retention_seconds = 1209600  # 14 days
}

# SQS for async document indexing
resource "aws_sqs_queue" "document_indexing" {
  name                       = "sahayak-${var.environment}-doc-indexing"
  visibility_timeout_seconds = 300
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })
}

# EventBridge for scheme update events
resource "aws_cloudwatch_event_bus" "sahayak" {
  name = "sahayak-${var.environment}-events"
}

output "dlq_arn"                   { value = aws_sqs_queue.dlq.arn }
output "document_indexing_queue_url" { value = aws_sqs_queue.document_indexing.url }
output "event_bus_name"            { value = aws_cloudwatch_event_bus.sahayak.name }
