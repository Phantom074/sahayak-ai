"""
Voice Service Models
Data classes for voice-related entities in the Sahayak AI system.
"""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class AudioConfig:
    """Configuration for audio processing."""
    sample_rate: int = 22050
    channels: int = 1
    bit_depth: int = 16
    format: str = "mp3"


@dataclass
class TranscriptionRequest:
    """Request model for speech-to-text conversion."""
    audio_url: str
    language_hint: Optional[str] = "auto"
    media_format: str = "webm"
    channel: str = "web"
    session_id: Optional[str] = None


@dataclass
class TranscriptionResponse:
    """Response model for speech-to-text conversion."""
    transcript: str
    language_code: str
    language_short: str
    confidence: float
    duration_seconds: Optional[float] = None
    word_timings: Optional[List[dict]] = None


@dataclass
class SynthesisRequest:
    """Request model for text-to-speech conversion."""
    text: str
    language: str
    session_id: str
    voice_id: Optional[str] = None
    speed: float = 1.0
    pitch: float = 0.0


@dataclass
class SynthesisResponse:
    """Response model for text-to-speech conversion."""
    audio_url: str
    duration_seconds: float
    voice_id: str
    language: str
    cache_hit: bool = False