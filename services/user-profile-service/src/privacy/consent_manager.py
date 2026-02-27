"""
DPDP Act 2023 Consent Manager.
Manages explicit user consent for data collection, processing, and marketing.
Implements right to erasure (Article 12 DPDP Act).
"""
import boto3
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

CONSENT_PURPOSES = {
    "data_processing": "Processing personal data to check scheme eligibility",
    "scheme_notifications": "Sending notifications about relevant government schemes",
    "analytics_anonymized": "Using anonymized data to improve service quality",
    "marketing": "Sending promotional communications",
}


class ConsentManager:
    USERS_TABLE = os.environ.get("USERS_TABLE", "sahayak-dev-users")
    AUDIT_TABLE = os.environ.get("AUDIT_TABLE", "sahayak-dev-audit-log")

    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
        self.users_table = self.dynamodb.Table(self.USERS_TABLE)
        self.audit_table = self.dynamodb.Table(self.AUDIT_TABLE)

    def record_consent(self, user_id: str, consents: Dict[str, bool], ip_address: str = None) -> Dict:
        """Record explicit user consent. Returns consent record."""
        timestamp = datetime.now(timezone.utc).isoformat()
        consent_record = {
            **{purpose: consents.get(purpose, False) for purpose in CONSENT_PURPOSES},
            "consent_timestamp": timestamp,
            "consent_version": "v2.1",
            "consent_method": "explicit_digital",
        }
        self.users_table.update_item(
            Key={"user_id": user_id, "sk": "PROFILE#v1"},
            UpdateExpression="SET consent = :c, updated_at = :t",
            ExpressionAttributeValues={":c": consent_record, ":t": timestamp},
        )
        self._audit_log(user_id, "CONSENT_RECORDED", {"consents": consents}, ip_address)
        logger.info(f"Consent recorded for user {user_id}")
        return consent_record

    def check_consent(self, user_id: str, purpose: str) -> bool:
        """Check if user has consented to a specific purpose."""
        try:
            response = self.users_table.get_item(
                Key={"user_id": user_id, "sk": "PROFILE#v1"},
                ProjectionExpression="consent",
            )
            consent = response.get("Item", {}).get("consent", {})
            return consent.get(purpose, False)
        except Exception as e:
            logger.error(f"Consent check failed: {e}")
            return False  # Default deny on error

    def process_erasure_request(self, user_id: str, request_reason: str) -> Dict:
        """
        DPDP Act Article 12: Right to Erasure.
        Deletes/anonymizes all user PII within 72 hours.
        Returns erasure request ID for tracking.
        """
        import uuid
        erasure_id = f"era_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        # Mark profile for erasure (async job processes within 72h)
        self.users_table.update_item(
            Key={"user_id": user_id, "sk": "PROFILE#v1"},
            UpdateExpression="SET erasure_requested = :t, erasure_id = :eid, erasure_reason = :r",
            ExpressionAttributeValues={
                ":t": timestamp,
                ":eid": erasure_id,
                ":r": request_reason,
            },
        )
        self._audit_log(user_id, "ERASURE_REQUESTED", {"erasure_id": erasure_id, "reason": request_reason})
        logger.info(f"Erasure requested: user={user_id}, id={erasure_id}")
        return {
            "erasure_id": erasure_id,
            "status": "pending",
            "expected_completion": "within 72 hours",
            "message": "Your data erasure request has been received and will be processed within 72 hours as per DPDP Act 2023.",
        }

    def _audit_log(self, user_id: str, action: str, details: dict, actor: str = None):
        """Immutable audit trail for all PII access (DPDP compliance)."""
        try:
            self.audit_table.put_item(Item={
                "audit_id": f"aud_{user_id}_{datetime.now(timezone.utc).timestamp()}",
                "user_id": user_id,
                "action": action,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "actor": actor or "system",
                "details": json.dumps(details),
            })
        except Exception as e:
            logger.error(f"Audit log failed (non-blocking): {e}")
