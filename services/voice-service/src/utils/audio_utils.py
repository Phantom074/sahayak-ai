"""
Audio Utilities
Helper functions for audio processing, validation, and manipulation.
"""

import io
import wave
import struct
from typing import Tuple, Optional
from urllib.parse import urlparse


def validate_audio_url(audio_url: str) -> bool:
    """Validate that the audio URL is properly formatted."""
    try:
        result = urlparse(audio_url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def get_audio_duration(audio_bytes: bytes) -> Optional[float]:
    """Get duration of audio in seconds from bytes."""
    try:
        with wave.open(io.BytesIO(audio_bytes), 'rb') as wav_file:
            frames = wav_file.getnframes()
            sample_rate = wav_file.getframerate()
            return frames / float(sample_rate)
    except Exception:
        return None


def estimate_audio_size(duration_sec: float, bitrate_kbps: int = 128) -> int:
    """Estimate audio file size in bytes."""
    return int((bitrate_kbps * 1000 / 8) * duration_sec)


def convert_sample_rate(audio_bytes: bytes, target_rate: int) -> bytes:
    """Convert audio sample rate if needed."""
    # Placeholder for actual sample rate conversion
    # In a real implementation, this would use a library like scipy or librosa
    return audio_bytes


def calculate_audio_md5(audio_bytes: bytes) -> str:
    """Calculate MD5 hash of audio data."""
    import hashlib
    return hashlib.md5(audio_bytes).hexdigest()


def is_valid_audio_format(audio_bytes: bytes, format_type: str = 'mp3') -> bool:
    """Check if audio bytes are in valid format."""
    if format_type.lower() == 'mp3':
        # Check for MP3 header
        return audio_bytes.startswith(b'\xff\xfb') or \
               audio_bytes.startswith(b'\xff\xf3') or \
               audio_bytes.startswith(b'\xff\xf2')
    elif format_type.lower() == 'wav':
        # Check for WAV header
        return audio_bytes.startswith(b'RIFF') and audio_bytes[8:12] == b'WAVE'
    elif format_type.lower() == 'webm':
        # Check for WebM header
        return audio_bytes.startswith(b'\x1aE\xdf\xa3')
    return False


def normalize_volume(audio_bytes: bytes, target_db: float = -20.0) -> bytes:
    """Normalize audio volume to target dB level."""
    # Placeholder for actual volume normalization
    # In a real implementation, this would use a library like pydub
    return audio_bytes


def trim_silence(audio_bytes: bytes, silence_threshold: float = 0.01) -> bytes:
    """Remove leading/trailing silence from audio."""
    # Placeholder for actual silence trimming
    # In a real implementation, this would use a library like pydub
    return audio_bytes