# Sahayak AI — National-Scale GovTech Platform

> Voice-first, multilingual AI assistant helping Indian citizens access government schemes

## Architecture Overview

Sahayak AI is a production-grade, event-driven serverless platform built on AWS, designed to scale to millions of concurrent users across Web, Mobile, IVR, and Rural Kiosk channels.

## Quick Start

```bash
git clone https://github.com/Phantom074/sahayak-ai.git
cd sahayak-ai

# Deploy infrastructure (dev)
cd infrastructure/terraform/environments/dev
terraform init && terraform plan && terraform apply

# Install service dependencies
cd services/conversation-orchestrator
pip install -r requirements.txt
```

## Services

| Service | Description |
|---------|-------------|
| voice-service | STT (Transcribe) + TTS (Polly) |
| conversation-orchestrator | Main pipeline + Bedrock LLM |
| scheme-retrieval-service | RAG pipeline + OpenSearch |
| eligibility-engine | Rule-based eligibility evaluation |
| user-profile-service | Citizen profile + DPDP compliance |
| scheme-management-service | Admin scheme ingestion + indexing |

## Tech Stack
- **Runtime**: Python 3.11 (Lambda)
- **LLM**: Amazon Bedrock (Claude 3 Sonnet)
- **Vector DB**: OpenSearch 2.11 (KNN)
- **Database**: DynamoDB (on-demand)
- **Voice**: Amazon Transcribe + Amazon Polly (Neural)
- **Auth**: Amazon Cognito | **IVR**: Amazon Connect
- **IaC**: Terraform 1.7+ | **CI/CD**: GitHub Actions

## Compliance
- India DPDP Act 2023 compliant
- Data stored exclusively in ap-south-1 (Mumbai)
- PII encrypted at rest with AWS KMS CMK
