"""
Conversation Orchestrator — Main Lambda Handler
Orchestrates the complete voice-to-voice pipeline:
  Audio → STT → Intent → RAG → LLM → Eligibility → TTS → Response

Target latency: < 3s (text), < 5s (audio) at P95
"""

import boto3
import json
import uuid
import time
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from ..orchestration.intent_classifier import IntentClassifier
from ..orchestration.context_manager import ContextManager
from ..orchestration.response_generator import ResponseGenerator
from ..bedrock.bedrock_client import BedrockOrchestrator
from ..models.conversation_models import ConversationTurn, SessionContext

logger = logging.getLogger(__name__)
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Lazy-loaded clients (reused across warm Lambda invocations)
_context_mgr: Optional[ContextManager] = None
_intent_classifier: Optional[IntentClassifier] = None
_response_gen: Optional[ResponseGenerator] = None
_bedrock: Optional[BedrockOrchestrator] = None


def _get_clients():
    global _context_mgr, _intent_classifier, _response_gen, _bedrock
    if _context_mgr is None:
        _context_mgr = ContextManager()
        _intent_classifier = IntentClassifier()
        _response_gen = ResponseGenerator()
        _bedrock = BedrockOrchestrator()
    return _context_mgr, _intent_classifier, _response_gen, _bedrock


class ConversationOrchestrator:
    """
    Stateless orchestrator — all state in DynamoDB session store.
    Implements circuit breaker pattern for downstream service failures.
    """

    def __init__(self):
        self.s3 = boto3.client("s3", region_name="ap-south-1")
        self.lambda_client = boto3.client("lambda", region_name="ap-south-1")
        self.context_mgr, self.intent_clf, self.response_gen, self.bedrock = _get_clients()

    def process_turn(self, event: dict) -> dict:
        """Process a single conversation turn end-to-end."""
        start_time = time.time()

        try:
            session_id = event["pathParameters"]["session_id"]
            body = json.loads(event.get("body", "{}"))
            user_id = event.get("requestContext", {}).get("authorizer", {}).get("sub", "anonymous")
            channel = event.get("requestContext", {}).get("stage", "web")

            logger.info(f"Processing turn: session={session_id}, user={user_id}, channel={channel}")

            # Step 1: Resolve text input (audio → STT or use text directly)
            if body.get("input_type") == "audio" and body.get("audio_s3_key"):
                text, language = self._invoke_stt(body["audio_s3_key"], body.get("language_hint", "auto"), channel)
            else:
                text = body.get("text", "")
                language = self._detect_language(text, body.get("language_hint", "auto"))

            if not text.strip():
                return self._empty_input_response(language, session_id)

            # Step 2: Load session context (last 5 turns for memory)
            session_ctx = self.context_mgr.load_session(session_id, user_id)
            user_context = {**session_ctx.user_profile, **body.get("user_context", {})}

            # Step 3: Classify intent
            intent = self.intent_clf.classify(text, language, session_ctx.recent_turns)

            # Step 4: RAG retrieval from scheme-retrieval-service
            retrieval_results = self._invoke_retrieval(text, language, user_context, intent)

            # Step 5: LLM response generation with RAG context
            llm_response = self.bedrock.generate_response(
                user_query=text,
                language=language,
                retrieval_results=retrieval_results,
                conversation_history=session_ctx.recent_turns,
                user_context=user_context,
            )

            # Step 6: Eligibility check if applicable
            eligibility_result = None
            if intent.name in ("eligibility_check", "scheme_application") and llm_response.get("schemes_mentioned"):
                eligibility_result = self._invoke_eligibility(
                    user_id, llm_response["schemes_mentioned"][0], user_context
                )

            # Step 7: TTS synthesis
            audio_url = self._invoke_tts(llm_response["response_text"], language, session_id)

            # Step 8: Persist turn
            turn_number = self.context_mgr.save_turn(
                session_id=session_id,
                user_id=user_id,
                user_input=text,
                bot_response=llm_response["response_text"],
                language=language,
                intent=intent.name,
                schemes_referenced=llm_response.get("schemes_mentioned", []),
                channel=channel,
            )

            latency_ms = int((time.time() - start_time) * 1000)

            return self._build_success_response(
                session_id=session_id,
                turn_number=turn_number,
                text=text,
                language=language,
                llm_response=llm_response,
                audio_url=audio_url,
                retrieval_results=retrieval_results,
                eligibility_result=eligibility_result,
                intent=intent,
                latency_ms=latency_ms,
            )

        except SchemeRetrievalError:
            logger.error("RAG retrieval failed — using template fallback")
            return self._template_fallback_response(body.get("text", ""), language if "language" in dir() else "hi")
        except Exception as e:
            logger.exception(f"Orchestration error: {e}")
            return self._error_response(str(e))

    def _invoke_stt(self, s3_key: str, language_hint: str, channel: str) -> tuple:
        """Invoke voice-service STT Lambda."""
        response = self.lambda_client.invoke(
            FunctionName=os.environ["STT_FUNCTION_NAME"],
            InvocationType="RequestResponse",
            Payload=json.dumps({
                "body": json.dumps({
                    "audio_s3_key": s3_key,
                    "language_hint": language_hint,
                    "channel": channel,
                })
            }),
        )
        result = json.loads(json.loads(response["Payload"].read())["body"])
        return result["transcript"], result["language"]

    def _invoke_retrieval(self, text: str, language: str, user_context: dict, intent) -> list:
        """Invoke scheme-retrieval-service Lambda."""
        try:
            response = self.lambda_client.invoke(
                FunctionName=os.environ["RETRIEVAL_FUNCTION_NAME"],
                InvocationType="RequestResponse",
                Payload=json.dumps({
                    "body": json.dumps({
                        "query": text,
                        "language": language,
                        "user_context": user_context,
                        "intent": intent.name,
                        "top_k": 5,
                    })
                }),
            )
            result = json.loads(json.loads(response["Payload"].read())["body"])
            return result.get("results", [])
        except Exception as e:
            logger.error(f"Retrieval service error: {e}")
            raise SchemeRetrievalError(str(e))

    def _invoke_eligibility(self, user_id: str, scheme_id: str, user_context: dict) -> Optional[dict]:
        """Invoke eligibility-engine Lambda (fire-and-forget if not needed immediately)."""
        try:
            response = self.lambda_client.invoke(
                FunctionName=os.environ["ELIGIBILITY_FUNCTION_NAME"],
                InvocationType="RequestResponse",
                Payload=json.dumps({
                    "body": json.dumps({
                        "user_id": user_id,
                        "scheme_id": scheme_id,
                        "user_profile": user_context,
                    })
                }),
            )
            return json.loads(json.loads(response["Payload"].read())["body"])
        except Exception as e:
            logger.warning(f"Eligibility check failed (non-critical): {e}")
            return None

    def _invoke_tts(self, text: str, language: str, session_id: str) -> Optional[str]:
        """Invoke voice-service TTS Lambda."""
        try:
            response = self.lambda_client.invoke(
                FunctionName=os.environ["TTS_FUNCTION_NAME"],
                InvocationType="RequestResponse",
                Payload=json.dumps({
                    "body": json.dumps({
                        "text": text,
                        "language": language,
                        "session_id": session_id,
                    })
                }),
            )
            result = json.loads(json.loads(response["Payload"].read())["body"])
            return result.get("audio_url")
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return None

    def _detect_language(self, text: str, hint: str) -> str:
        if hint in ("hi", "en"):
            return hint
        deva_count = sum(1 for c in text if "\u0900" <= c <= "\u097F")
        return "hi" if deva_count > len(text) * 0.15 else "en"

    def _build_success_response(self, **kwargs) -> dict:
        session_id = kwargs["session_id"]
        llm_response = kwargs["llm_response"]
        eligibility = kwargs.get("eligibility_result")
        intent = kwargs["intent"]
        retrieval_results = kwargs.get("retrieval_results", [])

        body = {
            "session_id": session_id,
            "turn_number": kwargs["turn_number"],
            "detected_language": kwargs["language"],
            "intent": {
                "name": intent.name,
                "confidence": intent.confidence,
                "entities": intent.entities,
            },
            "response": {
                "text": llm_response.get("response_text", ""),
                "audio_url": kwargs.get("audio_url"),
                "audio_expires_in": 300,
            },
            "schemes_referenced": [
                {"scheme_id": r.get("scheme_id"), "name": r.get("scheme_name"), "score": r.get("score")}
                for r in retrieval_results[:3]
            ],
            "action_items": llm_response.get("action_items", []),
            "follow_up_suggestions": self._get_follow_ups(intent.name, kwargs["language"]),
            "metadata": {
                "latency_ms": kwargs["latency_ms"],
                "rag_sources": len(retrieval_results),
                "confidence": llm_response.get("confidence", 0.0),
            },
        }

        if eligibility:
            body["eligibility"] = eligibility

        return {"statusCode": 200, "body": json.dumps(body), "headers": {"Content-Type": "application/json"}}

    def _empty_input_response(self, language: str, session_id: str) -> dict:
        msg = "कृपया अपना प्रश्न बोलें या टाइप करें।" if language == "hi" else "Please speak or type your question."
        return {"statusCode": 200, "body": json.dumps({"response": {"text": msg}, "session_id": session_id})}

    def _template_fallback_response(self, query: str, language: str) -> dict:
        """Fallback when RAG is unavailable — safe template response."""
        msg = (
            "माफ़ करें, इस समय जानकारी प्राप्त नहीं हो पा रही। कृपया थोड़ी देर बाद पुनः प्रयास करें।"
            if language == "hi"
            else "Sorry, I'm unable to retrieve information right now. Please try again in a moment."
        )
        return {"statusCode": 200, "body": json.dumps({"response": {"text": msg}, "fallback": True})}

    def _error_response(self, error: str) -> dict:
        return {"statusCode": 500, "body": json.dumps({"error": "internal_error", "message": error})}

    def _get_follow_ups(self, intent: str, language: str) -> list:
        suggestions = {
            "scheme_information_query": {
                "hi": ["मैं कैसे आवेदन करूं?", "कौन से दस्तावेज़ चाहिए?", "मेरी पात्रता जांचें"],
                "en": ["How do I apply?", "What documents do I need?", "Check my eligibility"],
            },
            "eligibility_check": {
                "hi": ["आवेदन प्रक्रिया बताएं", "अन्य योजनाएं दिखाएं"],
                "en": ["Show application process", "Show other schemes"],
            },
        }
        return suggestions.get(intent, {}).get(language, [])


class SchemeRetrievalError(Exception):
    pass


def lambda_handler(event: dict, context) -> dict:
    """Lambda entry point."""
    orchestrator = ConversationOrchestrator()
    return orchestrator.process_turn(event)
