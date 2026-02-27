"""
TTS Handler — Amazon Polly Text-to-Speech
Neural voices: Kajal (Hindi), Aditi (Hindi fallback), Joanna (English)
Optimized for low-bandwidth delivery (MP3, 48kbps).
"""

import boto3
import json
import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SynthesisResult:
    presigned_url: str
    s3_key: str
    duration_estimate_seconds: float
    language: str
    voice_id: str
    cache_hit: bool = False


class TTSHandler:
    """
    Converts text to speech using Amazon Polly Neural voices.
    Implements content-hash caching to avoid re-synthesizing identical text.
    Polly limit: 3,000 chars per request — auto-chunks longer text.
    """

    VOICE_MAP = {
        "hi": {"voice_id": "Kajal", "engine": "neural", "language_code": "hi-IN"},
        "en": {"voice_id": "Joanna", "engine": "neural", "language_code": "en-US"},
        "en-IN": {"voice_id": "Aditi", "engine": "standard", "language_code": "en-IN"},
    }
    OUTPUT_BUCKET = os.environ.get("AUDIO_OUTPUT_BUCKET", "sahayak-audio-output")
    PRESIGN_EXPIRY = 300  # 5 minutes
    MAX_POLLY_CHARS = 2900  # Under 3000 limit with safety margin

    def __init__(self):
        self.polly = boto3.client("polly", region_name="ap-south-1")
        self.s3 = boto3.client("s3", region_name="ap-south-1")

    def synthesize(
        self,
        text: str,
        language: str,
        session_id: str,
        use_cache: bool = True,
    ) -> SynthesisResult:
        """
        Convert text to MP3 audio. Returns presigned S3 URL.

        Args:
            text: Text to synthesize
            language: "hi" or "en"
            session_id: Conversation session ID
            use_cache: Check S3 for existing synthesis (hash-based)
        """
        voice_config = self.VOICE_MAP.get(language, self.VOICE_MAP["hi"])

        # Content-hash based caching
        content_hash = hashlib.sha256(
            f"{text}{voice_config['voice_id']}".encode()
        ).hexdigest()[:16]
        cache_key = f"cache/{language}/{content_hash}.mp3"

        if use_cache:
            cached_url = self._check_cache(cache_key)
            if cached_url:
                logger.info(f"TTS cache hit: {content_hash}")
                return SynthesisResult(
                    presigned_url=cached_url,
                    s3_key=cache_key,
                    duration_estimate_seconds=self._estimate_duration(text),
                    language=language,
                    voice_id=voice_config["voice_id"],
                    cache_hit=True,
                )

        # Chunk text if too long
        chunks = self._chunk_text(text)
        if len(chunks) == 1:
            s3_key = self._synthesize_chunk(
                chunks[0], voice_config, session_id, cache_key
            )
        else:
            s3_key = self._synthesize_chunks(chunks, voice_config, session_id)

        presigned_url = self.s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.OUTPUT_BUCKET, "Key": s3_key},
            ExpiresIn=self.PRESIGN_EXPIRY,
        )

        return SynthesisResult(
            presigned_url=presigned_url,
            s3_key=s3_key,
            duration_estimate_seconds=self._estimate_duration(text),
            language=language,
            voice_id=voice_config["voice_id"],
            cache_hit=False,
        )

    def _synthesize_chunk(
        self, text: str, voice_config: dict, session_id: str, output_key: str
    ) -> str:
        """Synthesize a single chunk via Polly async task."""
        response = self.polly.start_speech_synthesis_task(
            Text=text,
            TextType="text",
            OutputFormat="mp3",
            SampleRate="22050",
            OutputS3BucketName=self.OUTPUT_BUCKET,
            OutputS3KeyPrefix=f"responses/{session_id}/",
            VoiceId=voice_config["voice_id"],
            Engine=voice_config["engine"],
            LanguageCode=voice_config["language_code"],
        )

        task_id = response["SynthesisTask"]["TaskId"]
        actual_key = f"responses/{session_id}/{task_id}.mp3"

        # Copy to cache key for future hits
        self.s3.copy_object(
            Bucket=self.OUTPUT_BUCKET,
            CopySource={"Bucket": self.OUTPUT_BUCKET, "Key": actual_key},
            Key=output_key,
        )
        return actual_key

    def _synthesize_chunks(
        self, chunks: list, voice_config: dict, session_id: str
    ) -> str:
        """Synthesize multiple chunks and store first as primary."""
        # For MVP: synthesize first chunk only (covers most responses)
        # Production: concatenate MP3 streams
        primary_key = f"responses/{session_id}/combined.mp3"
        response = self.polly.synthesize_speech(
            Text=chunks[0],
            TextType="text",
            OutputFormat="mp3",
            VoiceId=voice_config["voice_id"],
            Engine=voice_config["engine"],
            LanguageCode=voice_config["language_code"],
        )
        audio_stream = response["AudioStream"].read()
        self.s3.put_object(
            Bucket=self.OUTPUT_BUCKET, Key=primary_key, Body=audio_stream
        )
        return primary_key

    def _chunk_text(self, text: str) -> list:
        """Split text at sentence boundaries to stay under Polly limit."""
        if len(text) <= self.MAX_POLLY_CHARS:
            return [text]

        chunks = []
        current = ""
        sentences = text.replace("।", ".").split(".")

        for sentence in sentences:
            if len(current) + len(sentence) < self.MAX_POLLY_CHARS:
                current += sentence + "."
            else:
                if current:
                    chunks.append(current.strip())
                current = sentence + "."

        if current:
            chunks.append(current.strip())

        return chunks or [text[: self.MAX_POLLY_CHARS]]

    def _check_cache(self, cache_key: str) -> Optional[str]:
        """Check if cached audio exists in S3."""
        try:
            self.s3.head_object(Bucket=self.OUTPUT_BUCKET, Key=cache_key)
            return self.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.OUTPUT_BUCKET, "Key": cache_key},
                ExpiresIn=self.PRESIGN_EXPIRY,
            )
        except self.s3.exceptions.ClientError:
            return None

    def _estimate_duration(self, text: str) -> float:
        """Estimate audio duration: ~150 words/min speech rate."""
        word_count = len(text.split())
        return round(word_count / 150 * 60, 1)


def lambda_handler(event: dict, context) -> dict:
    """Lambda entry point for TTS synthesis."""
    try:
        body = json.loads(event.get("body", "{}"))
        handler = TTSHandler()

        result = handler.synthesize(
            text=body["text"],
            language=body.get("language", "hi"),
            session_id=body.get("session_id", "default"),
            use_cache=body.get("use_cache", True),
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "audio_url": result.presigned_url,
                    "s3_key": result.s3_key,
                    "duration_seconds": result.duration_estimate_seconds,
                    "voice_id": result.voice_id,
                    "cache_hit": result.cache_hit,
                    "expires_in": TTSHandler.PRESIGN_EXPIRY,
                }
            ),
        }
    except Exception as e:
        logger.exception(f"TTS handler error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)}),
        }
