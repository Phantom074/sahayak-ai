"""
STT Handler — Amazon Transcribe Speech-to-Text
Supports Hindi (hi-IN) and English (en-IN) with auto language detection.
Optimized for rural low-bandwidth audio (Opus/WebM, 32kbps).
"""

import boto3
import json
import uuid
import time
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


@dataclass
class TranscriptionResult:
    transcript: str
    language_code: str  # "hi-IN" or "en-IN"
    language_short: str  # "hi" or "en"
    confidence: float
    job_name: str
    duration_seconds: Optional[float] = None


class STTHandler:
    """
    Handles audio transcription via Amazon Transcribe.
    Supports streaming (for real-time) and batch (for IVR recordings).
    """

    SUPPORTED_LANGUAGES = ["hi-IN", "en-IN", "en-US"]
    CUSTOM_VOCABULARY = "sahayak-govterm-vocabulary-v2"
    INPUT_BUCKET = os.environ.get("AUDIO_INPUT_BUCKET", "sahayak-audio-input")
    TRANSCRIPT_BUCKET = os.environ.get("TRANSCRIPT_BUCKET", "sahayak-transcripts")

    def __init__(self):
        self.transcribe = boto3.client("transcribe", region_name="ap-south-1")
        self.s3 = boto3.client("s3", region_name="ap-south-1")

    def transcribe_audio(
        self,
        s3_key: str,
        language_hint: str = "auto",
        media_format: str = "webm",
        channel: str = "web",
    ) -> TranscriptionResult:
        """
        Main entry point. Transcribes audio from S3.

        Args:
            s3_key: S3 object key for the audio file
            language_hint: "hi", "en", or "auto"
            media_format: webm, mp3, wav, ogg, flac
            channel: web | mobile | ivr | kiosk

        Returns:
            TranscriptionResult with transcript and metadata
        """
        job_name = f"sahayak-{channel}-{uuid.uuid4().hex[:12]}"
        media_uri = f"s3://{self.INPUT_BUCKET}/{s3_key}"

        start_params = {
            "TranscriptionJobName": job_name,
            "Media": {"MediaFileUri": media_uri},
            "MediaFormat": media_format,
            "OutputBucketName": self.TRANSCRIPT_BUCKET,
            "OutputKey": f"transcripts/{job_name}.json",
            "Settings": {
                "ShowSpeakerLabels": False,
                "MaxSpeakerLabels": 1,
            },
        }

        # Language configuration
        if language_hint == "auto":
            start_params["IdentifyLanguage"] = True
            start_params["LanguageOptions"] = ["hi-IN", "en-IN"]
        else:
            lang_map = {"hi": "hi-IN", "en": "en-IN"}
            start_params["LanguageCode"] = lang_map.get(language_hint, "hi-IN")
            # Add custom vocabulary for known language
            start_params["Settings"]["VocabularyName"] = self.CUSTOM_VOCABULARY

        # IVR-specific: phone quality audio filter
        if channel == "ivr":
            start_params["MediaSampleRateHertz"] = 8000

        logger.info(f"Starting transcription job: {job_name}")
        self.transcribe.start_transcription_job(**start_params)

        # Poll for completion (Lambda timeout: 30s)
        result = self._wait_for_completion(job_name)
        transcript_data = self._fetch_transcript(job_name)

        detected_lang = result["TranscriptionJob"].get("LanguageCode", "hi-IN")
        confidence = result["TranscriptionJob"].get("IdentifiedLanguageScore", 1.0)

        transcript_text = (
            transcript_data.get("results", {})
            .get("transcripts", [{}])[0]
            .get("transcript", "")
        )

        logger.info(
            f"Transcription complete: job={job_name}, "
            f"lang={detected_lang}, confidence={confidence:.2f}, "
            f"chars={len(transcript_text)}"
        )

        return TranscriptionResult(
            transcript=transcript_text,
            language_code=detected_lang,
            language_short=detected_lang.split("-")[0],
            confidence=float(confidence),
            job_name=job_name,
        )

    def _wait_for_completion(self, job_name: str, max_wait_seconds: int = 25) -> dict:
        """Poll Transcribe until job completes or timeout."""
        start = time.time()
        while time.time() - start < max_wait_seconds:
            response = self.transcribe.get_transcription_job(
                TranscriptionJobName=job_name
            )
            status = response["TranscriptionJob"]["TranscriptionJobStatus"]

            if status == "COMPLETED":
                return response
            elif status == "FAILED":
                reason = response["TranscriptionJob"].get("FailureReason", "Unknown")
                raise TranscriptionError(f"Transcription failed: {reason}")

            time.sleep(0.8)

        raise TranscriptionTimeoutError(
            f"Transcription job {job_name} exceeded {max_wait_seconds}s"
        )

    def _fetch_transcript(self, job_name: str) -> dict:
        """Fetch transcript JSON from S3."""
        response = self.s3.get_object(
            Bucket=self.TRANSCRIPT_BUCKET, Key=f"transcripts/{job_name}.json"
        )
        return json.loads(response["Body"].read().decode("utf-8"))

    def detect_language_heuristic(self, text: str) -> str:
        """
        Fast client-side language detection before Transcribe.
        Checks for Devanagari Unicode range (U+0900–U+097F).
        """
        if not text:
            return "en"
        devanagari_count = sum(1 for c in text if "\u0900" <= c <= "\u097F")
        ratio = devanagari_count / len(text)
        return "hi" if ratio > 0.15 else "en"


class TranscriptionError(Exception):
    pass


class TranscriptionTimeoutError(Exception):
    pass


def lambda_handler(event: dict, context) -> dict:
    """Lambda entry point for async STT processing."""
    try:
        body = json.loads(event.get("body", "{}"))
        handler = STTHandler()

        result = handler.transcribe_audio(
            s3_key=body["audio_s3_key"],
            language_hint=body.get("language_hint", "auto"),
            media_format=body.get("media_format", "webm"),
            channel=body.get("channel", "web"),
        )

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "transcript": result.transcript,
                    "language": result.language_short,
                    "language_code": result.language_code,
                    "confidence": result.confidence,
                    "job_name": result.job_name,
                }
            ),
            "headers": {"Content-Type": "application/json"},
        }

    except TranscriptionTimeoutError as e:
        logger.error(f"Transcription timeout: {e}")
        return {
            "statusCode": 504,
            "body": json.dumps(
                {
                    "error": "transcription_timeout",
                    "message": "Audio processing took too long. Please try again.",
                    "message_hi": "ऑडियो प्रोसेसिंग में समय लग रहा है। कृपया पुनः प्रयास करें।",
                }
            ),
        }
    except Exception as e:
        logger.exception(f"STT handler error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "internal_error", "message": str(e)}),
        }
