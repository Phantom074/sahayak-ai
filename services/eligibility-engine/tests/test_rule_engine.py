
"""Unit tests for the eligibility rule engine."""
import pytest
from unittest.mock import MagicMock, patch
from src.rules.rule_engine import EligibilityRuleEngine, EligibilityStatus

MOCK_RULES = {
    "scheme_id": "PM-KISAN-2024",
    "sk": "RULES#latest",
    "application_url": "https://pmkisan.gov.in",
    "required_documents": ["aadhaar", "bank_account", "land_records"],
    "criteria": [
        {"field": "occupation", "operator": "in", "value": ["farmer"], "weight": 2.5,
         "message_hi_pass": "किसान है", "message_hi_fail": "किसान नहीं है",
         "message_en_pass": "Is farmer", "message_en_fail": "Not a farmer"},
        {"field": "land_holdings_acres", "operator": "between", "value": [0.1, 5.0], "weight": 2.0,
         "message_hi_pass": "भूमि पात्र", "message_hi_fail": "भूमि अपात्र",
         "message_en_pass": "Land eligible", "message_en_fail": "Land ineligible"},
    ]
}


@pytest.fixture
def engine():
    with patch("boto3.resource") as mock_boto:
        mock_table = MagicMock()
        mock_table.get_item.return_value = {"Item": MOCK_RULES}
        mock_boto.return_value.Table.return_value = mock_table
        eng = EligibilityRuleEngine()
        eng._rules_cache = {}
        return eng


def test_eligible_farmer(engine):
    profile = {"user_id": "u1", "occupation": "farmer", "land_holdings_acres": 2.5}
    engine._rules_cache["PM-KISAN-2024"] = MOCK_RULES
    result = engine.evaluate("PM-KISAN-2024", profile)
    assert result.status == EligibilityStatus.ELIGIBLE
    assert result.score > 0.8


def test_ineligible_non_farmer(engine):
    profile = {"user_id": "u2", "occupation": "government_employee", "land_holdings_acres": 2.5}
    engine._rules_cache["PM-KISAN-2024"] = MOCK_RULES
    result = engine.evaluate("PM-KISAN-2024", profile)
    assert result.status == EligibilityStatus.INELIGIBLE


def test_more_info_needed(engine):
    profile = {"user_id": "u3", "occupation": "farmer"}  # No land_holdings
    engine._rules_cache["PM-KISAN-2024"] = MOCK_RULES
    result = engine.evaluate("PM-KISAN-2024", profile)
    assert result.status == EligibilityStatus.MORE_INFO_NEEDED


def test_too_much_land(engine):
    profile = {"user_id": "u4", "occupation": "farmer", "land_holdings_acres": 10.0}
    engine._rules_cache["PM-KISAN-2024"] = MOCK_RULES
    result = engine.evaluate("PM-KISAN-2024", profile)
    assert result.status == EligibilityStatus.INELIGIBLE


def test_dot_notation_extraction(engine):
    profile = {"employment": {"type": "farmer"}}
    result = engine._extract_value(profile, "employment.type")
    assert result == "farmer"


def test_missing_field_is_unknown(engine):
    profile = {"user_id": "u5"}
    rule = {"field": "occupation", "operator": "in", "value": ["farmer"], "weight": 1.0,
            "message_hi_pass": "", "message_hi_fail": "", "message_en_pass": "", "message_en_fail": ""}
    result = engine._evaluate_criterion(rule, profile)
    assert result.status == "unknown"
