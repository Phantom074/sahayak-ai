"""
Intent Classifier — Fast pattern + embedding-based classification.
Classifies user queries into scheme intents without a full LLM call.
Target: < 100ms classification latency.
"""
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class Intent:
    name: str
    confidence: float
    entities: Dict = field(default_factory=dict)


INTENT_PATTERNS = {
    "scheme_information_query": {
        "hi": [r"योजना", r"स्कीम", r"बताओ", r"क्या है", r"जानकारी", r"किसान", r"आवास", r"पेंशन"],
        "en": [r"scheme", r"tell me", r"what is", r"about", r"information", r"benefit"],
    },
    "eligibility_check": {
        "hi": [r"पात्र", r"योग्य", r"हकदार", r"मिलेगा", r"लाभ मिलेगा", r"पात्रता"],
        "en": [r"eligible", r"qualify", r"entitled", r"can i get", r"am i", r"eligibility"],
    },
    "scheme_application": {
        "hi": [r"आवेदन", r"अप्लाई", r"फ़ॉर्म", r"रजिस्ट्रेशन", r"कैसे करें"],
        "en": [r"apply", r"application", r"register", r"how to", r"form", r"enroll"],
    },
    "document_query": {
        "hi": [r"दस्तावेज़", r"कागज़", r"आधार", r"प्रमाण", r"सर्टिफिकेट"],
        "en": [r"document", r"proof", r"aadhaar", r"certificate", r"id"],
    },
    "status_check": {
        "hi": [r"स्टेटस", r"स्थिति", r"कब", r"कहाँ तक", r"आवेदन का"],
        "en": [r"status", r"track", r"where", r"when", r"update"],
    },
    "scheme_list": {
        "hi": [r"कौन सी योजनाएं", r"सभी योजनाएं", r"और कौन सी", r"क्या क्या योजनाएं"],
        "en": [r"list", r"all schemes", r"what schemes", r"available schemes"],
    },
}

SCHEME_ENTITIES = {
    "PM-KISAN": [r"किसान", r"pm.?kisan", r"kisan samman"],
    "PMAY": [r"आवास", r"घर", r"pmay", r"awas yojana", r"housing"],
    "PMJDY": [r"जन.?धन", r"बैंक खाता", r"jan dhan", r"bank account"],
    "PMJJBY": [r"बीमा", r"insurance", r"jeevan jyoti"],
    "MGNREGS": [r"मनरेगा", r"mnrega", r"mgnregs", r"रोज़गार गारंटी"],
    "PMSYM": [r"श्रम योगी", r"shram yogi", r"असंगठित", r"unorganized worker"],
    "NPS": [r"पेंशन", r"pension", r"nps", r"national pension"],
    "PMSBY": [r"सुरक्षा बीमा", r"suraksha bima", r"accident"],
}


class IntentClassifier:
    """
    Rule-based intent classifier with regex patterns.
    Fast path: no LLM calls required.
    """

    def classify(self, text: str, language: str, history: list = None) -> Intent:
        text_lower = text.lower()
        best_intent = "general_query"
        best_score = 0.0
        entities = {}

        # Pattern matching for intent
        for intent_name, lang_patterns in INTENT_PATTERNS.items():
            patterns = lang_patterns.get(language, lang_patterns.get("en", []))
            matches = sum(1 for p in patterns if re.search(p, text_lower, re.IGNORECASE))
            score = matches / max(len(patterns), 1)
            if score > best_score:
                best_score = score
                best_intent = intent_name

        # Entity extraction (scheme names)
        for scheme_id, patterns in SCHEME_ENTITIES.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    entities["scheme_id"] = scheme_id
                    entities["scheme_name"] = scheme_id
                    break

        # Context carry-forward from previous turns
        if best_score < 0.2 and history:
            last_intent = history[-1].get("intent", "") if history else ""
            if last_intent:
                best_intent = last_intent
                best_score = 0.4

        confidence = min(best_score * 2, 0.99) if best_score > 0 else 0.5

        logger.info(f"Intent: {best_intent} (confidence={confidence:.2f}, entities={entities})")

        return Intent(name=best_intent, confidence=confidence, entities=entities)
