"""
Data masker for DPDP compliance.
Masks PII fields in logs and analytics outputs.
"""
import re
import hashlib

class DataMasker:
    @staticmethod
    def mask_aadhaar(aadhaar: str) -> str:
        """Show only last 4 digits: XXXX-XXXX-1234"""
        digits = re.sub(r"\D", "", aadhaar or "")
        if len(digits) == 12:
            return f"XXXX-XXXX-{digits[-4:]}"
        return "XXXX-XXXX-XXXX"

    @staticmethod
    def hash_aadhaar(aadhaar: str, salt: str) -> str:
        """One-way hash for deduplication without storing raw Aadhaar."""
        digits = re.sub(r"\D", "", aadhaar or "")
        return hashlib.sha256(f"{salt}{digits}".encode()).hexdigest()

    @staticmethod
    def mask_phone(phone: str) -> str:
        """Show only last 4 digits: +91-XXXXXX4567"""
        digits = re.sub(r"\D", "", phone or "")
        if len(digits) >= 10:
            return f"+91-XXXXXX{digits[-4:]}"
        return "+91-XXXXXXXXXX"

    @staticmethod
    def mask_name(name: str) -> str:
        """Mask name for logging: 'Raj Kumar' → 'R** K****'"""
        if not name:
            return "***"
        parts = name.split()
        return " ".join(p[0] + "*" * (len(p)-1) for p in parts)

    @staticmethod
    def safe_log_profile(profile: dict) -> dict:
        """Return profile dict safe for logging (no PII)."""
        return {
            "user_id": profile.get("user_id"),
            "state": profile.get("state"),
            "occupation": profile.get("occupation"),
            "age": profile.get("age"),
            "income_bracket": DataMasker._income_bracket(profile.get("annual_income")),
        }

    @staticmethod
    def _income_bracket(income) -> str:
        if income is None: return "unknown"
        income = int(income)
        if income < 100000: return "<1L"
        elif income < 300000: return "1-3L"
        elif income < 600000: return "3-6L"
        elif income < 1000000: return "6-10L"
        return ">10L"
