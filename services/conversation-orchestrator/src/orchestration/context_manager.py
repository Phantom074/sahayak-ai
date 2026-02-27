"""
Context Manager — DynamoDB-backed conversation session management.
Stores and retrieves conversation turns with TTL-based expiry.
"""
import boto3
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class SessionContext:
    session_id: str
    user_id: str
    user_profile: Dict = field(default_factory=dict)
    recent_turns: List[Dict] = field(default_factory=list)
    language: str = "hi"
    channel: str = "web"
    created_at: Optional[str] = None


class ContextManager:
    """
    Manages conversation state in DynamoDB.
    Implements sliding window of last N turns for LLM context.
    """

    SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", "sahayak-dev-sessions")
    USERS_TABLE = os.environ.get("USERS_TABLE", "sahayak-dev-users")
    MAX_HISTORY_TURNS = 5
    SESSION_TTL_HOURS = 24  # Anonymous sessions
    AUTH_SESSION_TTL_DAYS = 90  # Authenticated sessions

    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
        self.sessions_table = self.dynamodb.Table(self.SESSIONS_TABLE)
        self.users_table = self.dynamodb.Table(self.USERS_TABLE)

    def load_session(self, session_id: str, user_id: str) -> SessionContext:
        """Load session context including recent conversation history."""
        # Load recent turns (last MAX_HISTORY_TURNS)
        response = self.sessions_table.query(
            KeyConditionExpression="session_id = :sid",
            ExpressionAttributeValues={":sid": session_id},
            ScanIndexForward=False,  # Latest first
            Limit=self.MAX_HISTORY_TURNS,
        )

        turns = [
            {
                "user_input": item.get("user_input", ""),
                "bot_response": item.get("bot_response", ""),
                "intent": item.get("detected_intent", ""),
                "language": item.get("language", "hi"),
            }
            for item in reversed(response.get("Items", []))
        ]

        # Load user profile if authenticated
        user_profile = {}
        if user_id != "anonymous":
            user_profile = self._load_user_profile(user_id)

        language = turns[-1]["language"] if turns else "hi"

        return SessionContext(
            session_id=session_id,
            user_id=user_id,
            user_profile=user_profile,
            recent_turns=turns,
            language=language,
        )

    def save_turn(
        self,
        session_id: str,
        user_id: str,
        user_input: str,
        bot_response: str,
        language: str,
        intent: str,
        schemes_referenced: List[str],
        channel: str,
    ) -> int:
        """Persist a conversation turn. Returns new turn number."""
        # Get current turn count
        response = self.sessions_table.query(
            KeyConditionExpression="session_id = :sid",
            ExpressionAttributeValues={":sid": session_id},
            Select="COUNT",
        )
        turn_number = response.get("Count", 0) + 1

        # TTL: longer for authenticated users
        if user_id == "anonymous":
            ttl = int((datetime.now(timezone.utc) + timedelta(hours=self.SESSION_TTL_HOURS)).timestamp())
        else:
            ttl = int((datetime.now(timezone.utc) + timedelta(days=self.AUTH_SESSION_TTL_DAYS)).timestamp())

        item = {
            "session_id": session_id,
            "turn_number": Decimal(str(turn_number)),
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "language": language,
            "user_input": user_input,
            "bot_response": bot_response,
            "detected_intent": intent,
            "schemes_referenced": schemes_referenced,
            "session_metadata": {"channel": channel},
            "expires_at": Decimal(str(ttl)),
        }

        self.sessions_table.put_item(Item=item)
        logger.info(f"Saved turn {turn_number} for session {session_id}")
        return turn_number

    def _load_user_profile(self, user_id: str) -> Dict:
        """Load decrypted user profile from DynamoDB."""
        try:
            response = self.users_table.get_item(
                Key={"user_id": user_id, "sk": "PROFILE#v1"}
            )
            item = response.get("Item", {})
            # Return only non-PII fields for LLM context
            return {
                "state": item.get("state"),
                "district": item.get("district"),
                "age": int(item.get("age", 0)) if item.get("age") else None,
                "gender": item.get("gender"),
                "occupation": item.get("occupation"),
                "annual_income": int(item.get("annual_income", 0)) if item.get("annual_income") else None,
                "land_holdings_acres": float(item.get("land_holdings_acres", 0)) if item.get("land_holdings_acres") else None,
                "caste_category": item.get("caste_category"),
                "disability": item.get("disability", False),
                "user_id": user_id,
            }
        except Exception as e:
            logger.error(f"Failed to load user profile {user_id}: {e}")
            return {}

    def end_session(self, session_id: str) -> None:
        """Mark session as ended (for analytics)."""
        logger.info(f"Session ended: {session_id}")
