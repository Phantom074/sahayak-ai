"""
Eligibility Rule Engine — Deterministic rule evaluation for scheme eligibility.
Rules stored in DynamoDB for real-time updates without redeployment.
"""
import boto3
import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
from decimal import Decimal

logger = logging.getLogger(__name__)


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    PARTIAL = "partial"
    MORE_INFO_NEEDED = "more_info_needed"


@dataclass
class CriterionResult:
    criterion_name: str
    status: str  # "pass" | "fail" | "unknown"
    user_value: Any
    required_value: Any
    message_hi: str
    message_en: str
    weight: float = 1.0


@dataclass
class EligibilityDecision:
    scheme_id: str
    user_id: str
    status: EligibilityStatus
    score: float
    criterion_results: List[CriterionResult]
    missing_documents: List[str]
    recommendation_hi: str
    recommendation_en: str
    action_url: str
    confidence: float


class EligibilityRuleEngine:
    """
    Deterministic rule engine. Rules loaded from DynamoDB per scheme.
    Supports: eq, in, not_in, lte, gte, between, exists operators.
    High-weight criteria (weight >= 2.0) are knockout disqualifiers.
    """

    RULES_TABLE = os.environ.get("RULES_TABLE", "sahayak-dev-eligibility-rules")

    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb", region_name="ap-south-1")
        self.rules_table = self.dynamodb.Table(self.RULES_TABLE)
        self._rules_cache: Dict[str, dict] = {}

    def evaluate(self, scheme_id: str, user_profile: dict) -> EligibilityDecision:
        rules = self._get_rules(scheme_id)
        if not rules:
            return self._unknown_decision(scheme_id, user_profile.get("user_id", "anon"))

        criterion_results = []
        total_weight = 0.0
        passed_weight = 0.0
        missing_info = []

        for rule in rules.get("criteria", []):
            result = self._evaluate_criterion(rule, user_profile)
            criterion_results.append(result)
            weight = float(rule.get("weight", 1.0))
            total_weight += weight

            if result.status == "pass":
                passed_weight += weight
            elif result.status == "unknown":
                missing_info.append(rule["field"])

        score = passed_weight / total_weight if total_weight > 0 else 0.0

        # Knockout criteria: high-weight failures = immediate ineligible
        hard_fails = [r for r in criterion_results if r.status == "fail" and r.weight >= 2.0]

        if hard_fails:
            status = EligibilityStatus.INELIGIBLE
        elif missing_info:
            status = EligibilityStatus.MORE_INFO_NEEDED
        elif score >= 0.8:
            status = EligibilityStatus.ELIGIBLE
        elif score >= 0.5:
            status = EligibilityStatus.PARTIAL
        else:
            status = EligibilityStatus.INELIGIBLE

        return EligibilityDecision(
            scheme_id=scheme_id,
            user_id=user_profile.get("user_id", "anonymous"),
            status=status,
            score=round(score, 3),
            criterion_results=criterion_results,
            missing_documents=self._identify_missing_docs(rules, user_profile),
            recommendation_hi=self._recommendation_hi(status, score, missing_info),
            recommendation_en=self._recommendation_en(status, score, missing_info),
            action_url=rules.get("application_url", ""),
            confidence=0.95 if not missing_info else 0.70,
        )

    def _evaluate_criterion(self, rule: dict, profile: dict) -> CriterionResult:
        field_path = rule["field"]
        operator = rule["operator"]
        required = rule["value"]
        weight = float(rule.get("weight", 1.0))
        user_value = self._extract_value(profile, field_path)

        if user_value is None:
            return CriterionResult(
                criterion_name=field_path, status="unknown",
                user_value=None, required_value=required,
                message_hi=f"{field_path} की जानकारी नहीं",
                message_en=f"{field_path} information missing",
                weight=weight,
            )

        passed = False
        try:
            if operator == "eq":
                passed = str(user_value).lower() == str(required).lower()
            elif operator == "in":
                passed = str(user_value).lower() in [str(v).lower() for v in required]
            elif operator == "not_in":
                passed = str(user_value).lower() not in [str(v).lower() for v in required]
            elif operator == "lte":
                passed = float(user_value) <= float(required)
            elif operator == "gte":
                passed = float(user_value) >= float(required)
            elif operator == "between":
                passed = float(required[0]) <= float(user_value) <= float(required[1])
            elif operator == "exists":
                passed = user_value is not None and str(user_value) != ""
            elif operator == "bool":
                passed = bool(user_value) == bool(required)
        except (ValueError, TypeError) as e:
            logger.warning(f"Criterion evaluation error for {field_path}: {e}")
            return CriterionResult(
                criterion_name=field_path, status="unknown",
                user_value=user_value, required_value=required,
                message_hi="मूल्यांकन में त्रुटि", message_en="Evaluation error",
                weight=weight,
            )

        return CriterionResult(
            criterion_name=field_path,
            status="pass" if passed else "fail",
            user_value=user_value,
            required_value=required,
            message_hi=rule.get("message_hi_pass" if passed else "message_hi_fail", ""),
            message_en=rule.get("message_en_pass" if passed else "message_en_fail", ""),
            weight=weight,
        )

    def _extract_value(self, profile: dict, field_path: str) -> Any:
        """Dot-notation extraction: 'employment.type' → profile['employment']['type']"""
        keys = field_path.split(".")
        value = profile
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value

    def _get_rules(self, scheme_id: str) -> Optional[dict]:
        if scheme_id in self._rules_cache:
            return self._rules_cache[scheme_id]
        try:
            response = self.rules_table.get_item(
                Key={"scheme_id": scheme_id, "sk": "RULES#latest"}
            )
            rules = response.get("Item")
            if rules:
                # Convert Decimal types from DynamoDB
                rules_clean = json.loads(json.dumps(rules, default=str))
                self._rules_cache[scheme_id] = rules_clean
                return rules_clean
        except Exception as e:
            logger.error(f"Failed to load rules for {scheme_id}: {e}")
        return None

    def _identify_missing_docs(self, rules: dict, profile: dict) -> List[str]:
        required_docs = rules.get("required_documents", [])
        provided_docs = profile.get("documents_available", [])
        return [doc for doc in required_docs if doc not in provided_docs]

    def _recommendation_hi(self, status: EligibilityStatus, score: float, missing: list) -> str:
        if status == EligibilityStatus.ELIGIBLE:
            return "आप इस योजना के लिए पात्र हैं। अभी आवेदन करें।"
        elif status == EligibilityStatus.MORE_INFO_NEEDED:
            return f"पात्रता जांचने के लिए अधिक जानकारी चाहिए: {', '.join(missing[:3])}"
        elif status == EligibilityStatus.PARTIAL:
            return f"आप आंशिक रूप से पात्र हैं ({int(score*100)}%)। विवरण देखें।"
        return "खेद है, आप इस योजना के पात्र नहीं हैं। अन्य उपलब्ध योजनाएं देखें।"

    def _recommendation_en(self, status: EligibilityStatus, score: float, missing: list) -> str:
        if status == EligibilityStatus.ELIGIBLE:
            return "You are eligible for this scheme. Apply now."
        elif status == EligibilityStatus.MORE_INFO_NEEDED:
            return f"More information needed to check eligibility: {', '.join(missing[:3])}"
        elif status == EligibilityStatus.PARTIAL:
            return f"Partially eligible ({int(score*100)}%). See details."
        return "Sorry, you do not qualify for this scheme. View other available schemes."

    def _unknown_decision(self, scheme_id: str, user_id: str) -> EligibilityDecision:
        return EligibilityDecision(
            scheme_id=scheme_id, user_id=user_id,
            status=EligibilityStatus.MORE_INFO_NEEDED, score=0.0,
            criterion_results=[], missing_documents=[],
            recommendation_hi="योजना नियम उपलब्ध नहीं हैं।",
            recommendation_en="Scheme rules not available.",
            action_url="", confidence=0.0,
        )
