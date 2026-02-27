# DPDP Act 2023 Compliance Guide

## Data Protection Principles

### 1. Lawful Basis
- All processing based on explicit consent
- Consent recorded with timestamp, version, method
- Consent can be withdrawn at any time via /users/consent endpoint

### 2. Data Minimization
- Only collect data necessary for scheme eligibility
- Anonymous sessions for discovery queries
- Profile data optional for basic functionality

### 3. Data Localization
- All data stored exclusively in ap-south-1 (Mumbai)
- Cross-region replication disabled
- No data transferred outside India

### 4. Right to Erasure (Article 12)
- /users/data DELETE endpoint triggers erasure workflow
- Completed within 72 hours
- Cascades: DynamoDB, OpenSearch (user data), S3 (audio files)
- Audit trail preserved (anonymized) for compliance

### 5. Security Safeguards
- Aadhaar: SHA-256 hash only, never stored raw
- Phone/Name: AES-256 encrypted with KMS CMK
- Access logs: 7-year immutable retention in CloudWatch
- Annual penetration testing required

### 6. Data Breach Response
- CloudWatch alarm: unusual DynamoDB read patterns
- SNS notification to security team within 1 hour
- CERT-In notification within 6 hours (as required)
- Affected user notification within 72 hours

### 7. Data Fiduciary Obligations
- Privacy notice displayed before data collection
- Grievance officer contact: privacy@sahayak.gov.in
- Annual DPDP compliance audit
