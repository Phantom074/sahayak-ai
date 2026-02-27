"""
voice-service/tests/test_language_detector.py

Unit tests for the language detection utility.
No AWS calls — pure Python logic testing.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.processors.language_detector import LanguageDetector, LanguageDetectionResult


@pytest.fixture
def detector():
    return LanguageDetector()


class TestLanguageDetector:

    def test_devanagari_detected_as_hindi(self, detector):
        """Pure Devanagari text should detect as Hindi with high confidence."""
        text = "मुझे पीएम किसान योजना के बारे में जानकारी चाहिए"
        result = detector.detect(text)

        assert result.language == "hi"
        assert result.confidence >= 0.85
        assert result.script == "devanagari"
        assert result.hint_used is False

    def test_english_text_detected(self, detector):
        """English text should detect as English."""
        text = "Tell me about PM Kisan scheme eligibility criteria"
        result = detector.detect(text)

        assert result.language == "en"
        assert result.confidence >= 0.7

    def test_explicit_hint_overrides_detection(self, detector):
        """Explicit language hint should always win."""
        text = "Tell me about schemes"  # English text
        result = detector.detect(text, hint="hi")

        assert result.language == "hi"
        assert result.confidence == 1.0
        assert result.hint_used is True

    def test_explicit_english_hint(self, detector):
        """Explicit English hint overrides Hindi text."""
        text = "मुझे जानकारी चाहिए"  # Hindi text
        result = detector.detect(text, hint="en")

        assert result.language == "en"
        assert result.hint_used is True

    def test_transliterated_hindi_detected(self, detector):
        """Hindi written in Latin script should detect as Hindi."""
        text = "mujhe PM Kisan yojana ke bare mein batao"
        result = detector.detect(text)

        assert result.language == "hi"

    def test_code_mixed_leans_hindi(self, detector):
        """Code-mixed Hindi-English should lean Hindi."""
        text = "PM Kisan yojana mein apply kaise karen"
        result = detector.detect(text)

        # Should detect Hindi due to markers
        assert result.language == "hi"

    def test_empty_string_defaults_hindi(self, detector):
        """Empty input should default to Hindi (India-first)."""
        result = detector.detect("")

        assert result.language == "hi"
        assert result.confidence == 0.5

    def test_mixed_script_high_devanagari(self, detector):
        """Text with majority Devanagari should be Hindi."""
        text = "क्या मुझे PM Kisan scheme का लाभ मिलेगा?"
        result = detector.detect(text)

        assert result.language == "hi"

    def test_confidence_range_valid(self, detector):
        """Confidence should always be 0.0 to 1.0."""
        test_texts = [
            "Hello",
            "नमस्ते",
            "mujhe batao",
            "PM Kisan yojana",
            "Tell me about MGNREGA scheme"
        ]
        for text in test_texts:
            result = detector.detect(text)
            assert 0.0 <= result.confidence <= 1.0, f"Confidence out of range for: {text}"

    def test_result_has_required_fields(self, detector):
        """LanguageDetectionResult must have all required fields."""
        result = detector.detect("test text")

        assert hasattr(result, "language")
        assert hasattr(result, "confidence")
        assert hasattr(result, "script")
        assert hasattr(result, "hint_used")
        assert result.language in ("hi", "en")
