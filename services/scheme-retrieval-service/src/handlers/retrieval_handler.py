"""Lambda handler for scheme retrieval service."""
import json
import logging
from ..rag.hybrid_retriever import HybridRetriever

logger = logging.getLogger(__name__)
_retriever = None

def lambda_handler(event: dict, context) -> dict:
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    try:
        body = json.loads(event.get("body", "{}"))
        results = _retriever.hybrid_retrieve(
            query=body["query"],
            language=body.get("language", "hi"),
            user_context=body.get("user_context"),
            top_k=body.get("top_k", 5),
        )
        return {
            "statusCode": 200,
            "body": json.dumps({
                "results": [
                    {"chunk_id": r.chunk_id, "scheme_id": r.scheme_id,
                     "scheme_name": r.scheme_name, "text": r.text,
                     "score": r.score, "source_url": r.source_url}
                    for r in results
                ],
                "total": len(results),
            }),
        }
    except Exception as e:
        logger.exception(f"Retrieval error: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e), "results": []})}
