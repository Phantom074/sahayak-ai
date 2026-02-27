# Sahayak AI — Architecture Guide

## System Components

### 1. Voice Pipeline

```
User Audio → S3 Upload → Amazon Transcribe → Text
Text Response → Amazon Polly → MP3 → S3 → Presigned URL → User
```

**Transcribe configuration:**
- Languages: hi-IN (Hindi), en-IN (English)
- Auto language detection with 70% confidence threshold
- Custom vocabulary: `sahayak-govterm-vocabulary-v2` (scheme names, govt terms)
- IVR channel: 8kHz audio, phone quality filter

**Polly configuration:**
- Hindi: Kajal (Neural) — natural Hindi TTS
- English: Joanna (Neural)
- Format: MP3 22kHz for bandwidth efficiency
- Cache: content-hash based S3 cache for repeated phrases

### 2. RAG Pipeline

```
Query → Titan Embeddings → KNN Search (OpenSearch)
      ↘ BM25 Search (OpenSearch)
                ↓
        Reciprocal Rank Fusion
                ↓
          Top-5 Chunks → LLM Context
```

**OpenSearch index:** `sahayak-schemes-v2`
- KNN vector: 1536-dim Titan Embeddings V2, HNSW algorithm
- Text fields: text_en, text_hi, scheme_name (BM25)
- Filters: eligible_states, eligible_occupations

**Anti-hallucination measures:**
- System prompt mandates context-only answers
- Temperature: 0.1 (near-deterministic)
- Source citations required in response
- Fallback: "I don't have verified information" when confidence < 0.5

### 3. Eligibility Engine

Rules stored in DynamoDB (schema: `sahayak-{env}-eligibility-rules`):
```json
{
  "scheme_id": "PM-KISAN-2024",
  "sk": "RULES#latest",
  "criteria": [
    {
      "field": "occupation",
      "operator": "in",
      "value": ["farmer"],
      "weight": 2.5
    }
  ]
}
```

Operators: eq, in, not_in, lte, gte, between, exists, bool
Weight >= 2.0 = knockout criterion (any fail = ineligible)

### 4. Security Architecture

```
Internet → CloudFront → WAF → API Gateway → Lambda (VPC)
                                               ↓
                                         DynamoDB (VPC endpoint)
                                         OpenSearch (VPC)
                                         S3 (VPC endpoint)
```

PII Encryption:
- KMS CMK: `alias/sahayak-{env}-pii`
- Encrypted fields: phone, name, aadhaar_hash
- Aadhaar: SHA-256(salt + digits) — never stored raw
- Client-side encryption via AWS Encryption SDK before DynamoDB writes

### 5. Scalability Targets

| Metric | Target |
|--------|--------|
| Concurrent users | 1,000,000 |
| P50 latency | < 1.5s |
| P95 latency | < 3s (text), < 5s (audio) |
| Availability | 99.9% |
| RTO | < 15 minutes |
| RPO | < 1 hour |

### 6. Cost Optimization

| Strategy | Saving |
|----------|--------|
| 3-tier LLM routing (cache/Haiku/Sonnet) | ~75% Bedrock cost |
| Arm64 Lambda (Graviton2) | 34% compute cost |
| DynamoDB TTL for session data | Storage cost control |
| OpenSearch UltraWarm for old docs | 90% storage saving |
| CloudFront for audio delivery | 60% S3 transfer saving |
| TTS content-hash caching | ~40% Polly cost |
