from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class ConversationTurn:
    session_id: str
    turn_number: int
    user_id: str
    language: str
    user_input: str
    bot_response: str
    detected_intent: str
    schemes_referenced: List[str] = field(default_factory=list)

@dataclass  
class SessionContext:
    session_id: str
    user_id: str
    user_profile: Dict = field(default_factory=dict)
    recent_turns: List[Dict] = field(default_factory=list)
    language: str = "hi"
    channel: str = "web"
    created_at: Optional[str] = None
