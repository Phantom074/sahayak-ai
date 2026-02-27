"""
Bedrock Orchestrator — LLM response generation with RAG context injection.
Uses Claude 3 Sonnet for balanced quality/cost/speed.
Anti-hallucination: responses grounded strictly in retrieved context.
"""
import boto3
import json
import logging
import os
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")


class BedrockOrchestrator:
    def __init__(self):
        self.bedrock = boto3.client("bedrock-runtime", region_name="ap-south-1")

    def generate_response(
        self,
        user_query: str,
        language: str,
        retrieval_results: List[Dict],
        conversation_history: List[Dict],
        user_context: Dict,
    ) -> Dict:
        system_prompt = self._build_system_prompt(language, user_context)
        rag_context = self._format_rag_context(retrieval_results)
        messages = self._build_messages(conversation_history, user_query, rag_context)

        try:
            response = self.bedrock.invoke_model(
                modelId=MODEL_ID,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1024,
                    "system": system_prompt,
                    "messages": messages,
                    "temperature": 0.1,
                    "top_p": 0.9,
                }),
            )
            raw = json.loads(response["body"].read())["content"][0]["text"]
            return self._parse_response(raw)
        except Exception as e:
            logger.error(f"Bedrock invocation failed: {e}")
            return self._fallback_response(language)

    def _build_system_prompt(self, language: str, user_context: Dict) -> str:
        lang_instruction = (
            "Respond ONLY in Hindi (Devanagari). Use simple language a rural citizen can understand."
            if language == "hi"
            else "Respond in clear, simple English."
        )
        return f"""You are Sahayak AI, a trusted government scheme assistant for Indian citizens.

CRITICAL ANTI-HALLUCINATION RULES:
1. Answer ONLY from the <context> provided. Never invent facts.
2. If info is absent from context, say: "मुझे इस बारे में पक्की जानकारी नहीं है" (hi) or "I don't have verified information on this" (en).
3. Never guess benefit amounts, deadlines, or eligibility criteria.
4. Always name the specific scheme you are referencing.
5. If asked about non-government topics, politely redirect.

LANGUAGE: {lang_instruction}

USER PROFILE:
- State: {user_context.get("state", "Unknown")}
- Occupation: {user_context.get("occupation", "Unknown")}  
- Age: {user_context.get("age", "Unknown")}
- Income: {user_context.get("annual_income", "Unknown")}

OUTPUT FORMAT (strict JSON):
{{
  "response_text": "<your response>",
  "schemes_mentioned": ["scheme_id_1"],
  "action_items": ["Step 1: ...", "Step 2: ..."],
  "needs_more_info": ["field_needed_1"],
  "confidence": 0.95
}}"""

    def _format_rag_context(self, results: List[Dict]) -> str:
        if not results:
            return "<context>No verified scheme information found for this query.</context>"
        parts = ["<context>"]
        for i, r in enumerate(results[:5], 1):
            scheme_name = r.get("scheme_name", "Unknown Scheme")
            text = r.get("text", r.get("content", ""))
            source = r.get("source_url", "")
            parts.append(f'<scheme id="{i}" name="{scheme_name}" source="{source}">{text}</scheme>')
        parts.append("</context>")
        return "\n".join(parts)

    def _build_messages(self, history: List[Dict], query: str, rag_context: str) -> List[Dict]:
        messages = []
        for turn in history[-5:]:
            if turn.get("user_input"):
                messages.append({"role": "user", "content": turn["user_input"]})
            if turn.get("bot_response"):
                messages.append({"role": "assistant", "content": turn["bot_response"]})
        messages.append({"role": "user", "content": f"{rag_context}\n\nQuestion: {query}"})
        return messages

    def _parse_response(self, raw: str) -> Dict:
        try:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except json.JSONDecodeError:
            pass
        return {"response_text": raw, "schemes_mentioned": [], "action_items": [], "needs_more_info": [], "confidence": 0.5}

    def _fallback_response(self, language: str) -> Dict:
        text = (
            "माफ़ करें, अभी जवाब देने में समस्या हो रही है। कृपया कुछ देर बाद पुनः प्रयास करें।"
            if language == "hi"
            else "Sorry, I'm having trouble responding right now. Please try again shortly."
        )
        return {"response_text": text, "schemes_mentioned": [], "action_items": [], "needs_more_info": [], "confidence": 0.0}
