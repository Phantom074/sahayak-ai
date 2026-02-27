"""
Language detector with Unicode range heuristics for Indian languages.
Falls back to Amazon Comprehend for ambiguous text.
"""
import re
import boto3
import logging

logger = logging.getLogger(__name__)

DEVANAGARI_RANGE = ("\u0900", "\u097F")

class LanguageDetector:
    def __init__(self):
        self.comprehend = boto3.client("comprehend", region_name="ap-south-1")

    def detect(self, text: str, hint: str = "auto") -> str:
        if hint in ("hi", "en"):
            return hint
        if not text or len(text.strip()) < 3:
            return "hi"  # Default to Hindi for Sahayak

        # Fast heuristic: Devanagari char ratio
        deva_count = sum(1 for c in text if DEVANAGARI_RANGE[0] <= c <= DEVANAGARI_RANGE[1])
        ratio = deva_count / len(text)

        if ratio > 0.3:
            return "hi"
        elif ratio < 0.05:
            return "en"
        else:
            # Ambiguous: use Comprehend
            return self._comprehend_detect(text)

    def _comprehend_detect(self, text: str) -> str:
        try:
            response = self.comprehend.detect_dominant_language(Text=text[:300])
            languages = response.get("Languages", [])
            if languages:
                top = languages[0]["LanguageCode"]
                return "hi" if top == "hi" else "en"
        except Exception as e:
            logger.warning(f"Comprehend detection failed: {e}")
        return "hi"
