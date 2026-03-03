"""
Conversation Models
Data classes for conversation-related entities in the Sahayak AI system.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class Intent(Enum):
    """Possible intents for user queries."""
    GREETING = "greeting"
    ASK_SCHEME_INFO = "ask_scheme_info"
    CHECK_ELIGIBILITY = "check_eligibility"
    APPLY_SCHEME = "apply_scheme"
    FIND_SCHEMES = "find_schemes"
    GENERAL_INQUIRY = "general_inquiry"
    GOODBYE = "goodbye"
    UNKNOWN = "unknown"


class Channel(Enum):
    """Communication channels supported."""
    WEB = "web"
    MOBILE = "mobile"
    IVR = "ivr"
    KIOSK = "kiosk"


@dataclass
class UserInput:
    """Model for user input."""
    text: str
    audio_url: Optional[str] = None
    language: str = "hi"  # Default to Hindi
    channel: Channel = Channel.WEB
    session_id: Optional[str] = None
    user_id: Optional[str] = None


@dataclass
class ConversationContext:
    """Model for conversation context."""
    session_id: str
    user_id: Optional[str] = None
    current_intent: Optional[Intent] = None
    user_profile: Optional[Dict[str, Any]] = None
    conversation_history: Optional[List[Dict[str, str]]] = None
    active_scheme_id: Optional[str] = None
    language_preference: str = "hi"
    channel: Channel = Channel.WEB
    last_interaction_time: Optional[datetime] = None


@dataclass
class IntentClassification:
    """Model for intent classification results."""
    intent: Intent
    confidence: float
    extracted_entities: Dict[str, Any]
    scheme_id: Optional[str] = None
    user_profile_updates: Optional[Dict[str, Any]] = None


@dataclass
class ConversationResponse:
    """Model for conversation responses."""
    response_text: str
    response_audio_url: Optional[str] = None
    intent: Optional[Intent] = None
    scheme_details: Optional[Dict[str, Any]] = None
    eligibility_result: Optional[Dict[str, Any]] = None
    suggested_schemes: Optional[List[Dict[str, Any]]] = None
    follow_up_questions: Optional[List[str]] = None
    language: str = "hi"
    session_expired: bool = False


@dataclass
class ConversationState:
    """Model for tracking conversation state."""
    session_id: str
    user_input: UserInput
    context: ConversationContext
    intent_classification: Optional[IntentClassification] = None
    response: Optional[ConversationResponse] = None
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()
    is_active: bool = True


@dataclass
class SchemeInfo:
    """Model for scheme information."""
    scheme_id: str
    scheme_name: str
    description: str
    benefits: List[str]
    eligibility_criteria: List[Dict[str, Any]]
    documents_required: List[str]
    application_process: str
    contact_info: Optional[Dict[str, str]] = None
    official_link: Optional[str] = None
    status: str = "active"
    categories: Optional[List[str]] = None


@dataclass
class EligibilityCheck:
    """Model for eligibility check results."""
    scheme_id: str
    user_id: str
    eligible: bool
    eligibility_percentage: Optional[float] = None
    detailed_results: Optional[Dict[str, Any]] = None
    recommendations: Optional[List[str]] = None
    checked_at: datetime = datetime.utcnow()


@dataclass
class ConversationMetrics:
    """Model for conversation metrics."""
    session_id: str
    duration_seconds: float
    user_satisfaction: Optional[int] = None  # 1-5 scale
    resolved: bool = False
    intent_accuracy: Optional[float] = None
    response_time_ms: Optional[float] = None
    language_used: str = "hi"
    channel: Channel = Channel.WEB
    feedback: Optional[str] = None
    collected_at: datetime = datetime.utcnow()