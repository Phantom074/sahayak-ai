"""Shared exceptions for all Sahayak services."""

class SahayakBaseError(Exception):
    def __init__(self, message: str, error_code: str = None, http_status: int = 500):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.http_status = http_status

class ValidationError(SahayakBaseError):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR", 400)

class AuthorizationError(SahayakBaseError):
    def __init__(self, message: str):
        super().__init__(message, "AUTHORIZATION_ERROR", 403)

class SchemeNotFoundError(SahayakBaseError):
    def __init__(self, scheme_id: str):
        super().__init__(f"Scheme not found: {scheme_id}", "SCHEME_NOT_FOUND", 404)

class RetrievalError(SahayakBaseError):
    def __init__(self, message: str):
        super().__init__(message, "RETRIEVAL_ERROR", 503)

class TranscriptionError(SahayakBaseError):
    def __init__(self, message: str):
        super().__init__(message, "TRANSCRIPTION_ERROR", 503)

class LLMError(SahayakBaseError):
    def __init__(self, message: str):
        super().__init__(message, "LLM_ERROR", 503)
