"""Lambda handler for eligibility engine."""
import json
import logging
from ..rules.rule_engine import EligibilityRuleEngine

logger = logging.getLogger(__name__)
_engine = None

def lambda_handler(event: dict, context) -> dict:
    global _engine
    if _engine is None:
        _engine = EligibilityRuleEngine()
    try:
        body = json.loads(event.get("body", "{}"))
        decision = _engine.evaluate(
            scheme_id=body["scheme_id"],
            user_profile=body.get("user_profile", {}),
        )
        return {
            "statusCode": 200,
            "body": json.dumps({
                "scheme_id": decision.scheme_id,
                "status": decision.status.value,
                "score": decision.score,
                "recommendation_hi": decision.recommendation_hi,
                "recommendation_en": decision.recommendation_en,
                "missing_documents": decision.missing_documents,
                "action_url": decision.action_url,
                "confidence": decision.confidence,
                "criteria_summary": [
                    {"name": r.criterion_name, "status": r.status, "weight": r.weight}
                    for r in decision.criterion_results
                ],
            }),
        }
    except KeyError as e:
        return {"statusCode": 400, "body": json.dumps({"error": f"Missing required field: {e}"})}
    except Exception as e:
        logger.exception(f"Eligibility error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
