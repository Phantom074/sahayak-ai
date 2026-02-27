
"""Unit tests for intent classifier."""
import pytest
from src.orchestration.intent_classifier import IntentClassifier, Intent


@pytest.fixture
def classifier():
    return IntentClassifier()


def test_scheme_info_hindi(classifier):
    result = classifier.classify("पीएम किसान योजना के बारे में बताओ", "hi")
    assert result.name == "scheme_information_query"
    assert result.confidence > 0.0


def test_eligibility_check_english(classifier):
    result = classifier.classify("Am I eligible for PM KISAN scheme?", "en")
    assert result.name in ("eligibility_check", "scheme_information_query")


def test_application_intent(classifier):
    result = classifier.classify("How do I apply for this scheme?", "en")
    assert result.name in ("scheme_application", "scheme_information_query")


def test_entity_extraction_pm_kisan(classifier):
    result = classifier.classify("PM Kisan scheme ke baare mein batao", "hi")
    assert result.entities.get("scheme_id") == "PM-KISAN"


def test_empty_text_fallback(classifier):
    result = classifier.classify("", "hi")
    assert result.name is not None
    assert 0.0 <= result.confidence <= 1.0
