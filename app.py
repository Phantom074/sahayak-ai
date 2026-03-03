"""
Sahayak AI Main Application
Entry point for the voice-first, multilingual government scheme assistant.
"""

import os
import logging
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import Generator

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, CORSConfig
from aws_lambda_powertools.utilities.typing import LambdaContext

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = Logger(service="sahayak-ai")
tracer = Tracer(service="sahayak-ai")

# We'll initialize service handlers later when needed
conversation_handler = None
stt_handler = None
tts_handler = None
retrieval_handler = None
eligibility_handler = None
profile_handler = None
management_handler = None

# Define lifespan for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI) -> Generator:
    """Application lifespan manager."""
    logger.info("Starting Sahayak AI application...")
    
    # Initialize any required resources here
    # For example: database connections, caches, etc.
    
    yield  # Application runs during this period
    
    # Cleanup resources
    logger.info("Shutting down Sahayak AI application...")

# Create FastAPI application
app = FastAPI(
    title="Sahayak AI API",
    description="Voice-first, multilingual AI assistant helping Indian citizens access government schemes",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {
        "message": "Sahayak AI - Voice-first, multilingual government scheme assistant",
        "version": "1.0.0",
        "service": "conversation-orchestrator",
        "region": os.getenv("AWS_REGION", "ap-south-1"),
        "environment": os.getenv("ENVIRONMENT", "dev")
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
        "services": {
            "conversation": "available",
            "voice": "available",
            "retrieval": "available",
            "eligibility": "available",
            "user_profile": "available",
            "scheme_management": "available"
        }
    }

# Basic API routes will be added as needed
@app.get("/v1/conversation/start")
async def start_conversation():
    return {"session_id": "temp_session", "message": "Conversation started"}

@app.post("/v1/conversation/process")
async def process_conversation():
    return {"response_text": "This is a sample response for testing", "scheme_details": {}, "suggested_schemes": []}

@app.post("/v1/stt/transcribe")
async def transcribe_audio():
    return {"transcript": "sample transcript", "language": "hi"}

@app.post("/v1/tts/synthesize")
async def synthesize_text():
    return {"audio_url": "/sample/audio.mp3", "duration_seconds": 5}

@app.post("/v1/retrieval/search")
async def search_schemes():
    return {"results": [], "count": 0}

@app.post("/v1/eligibility/check")
async def check_eligibility():
    return {"eligible": True, "details": {}}

@app.get("/v1/profile/{profile_id}")
async def get_profile(profile_id: str):
    return {"profile_id": profile_id, "name": "Sample User"}

@app.get("/v1/schemes")
async def get_schemes():
    return {"schemes": [], "count": 0}

# Error handling
@app.exception_handler(500)
async def internal_exception_handler(request, exc):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {str(exc)}")
    return {
        "error": "internal_server_error",
        "message": "An internal server error occurred",
        "message_hi": "एक आंतरिक सर्वर त्रुटि हुई"
    }

@app.exception_handler(404)
async def not_found_handler(request, exc):
    """Handle not found errors."""
    return {
        "error": "not_found",
        "message": "The requested resource was not found",
        "message_hi": "अनुरोधित संसाधन नहीं मिला"
    }

# Additional utility endpoints
@app.get("/languages")
async def supported_languages():
    """Get supported languages."""
    return {
        "languages": [
            {"code": "hi", "name": "Hindi", "native_name": "हिंदी"},
            {"code": "en", "name": "English", "native_name": "अंग्रेज़ी"},
            {"code": "bn", "name": "Bengali", "native_name": "বাংলা"},
            {"code": "te", "name": "Telugu", "native_name": "తెలుగు"},
            {"code": "ta", "name": "Tamil", "native_name": "தமிழ்"},
            {"code": "mr", "name": "Marathi", "native_name": "मराठी"},
            {"code": "gu", "name": "Gujarati", "native_name": "ગુજરાતી"},
            {"code": "kn", "name": "Kannada", "native_name": "ಕನ್ನಡ"},
            {"code": "ml", "name": "Malayalam", "native_name": "മലയാളം"},
            {"code": "pa", "name": "Punjabi", "native_name": "ਪੰਜਾਬੀ"}
        ],
        "default_language": "hi"
    }

@app.get("/channels")
async def supported_channels():
    """Get supported communication channels."""
    return {
        "channels": [
            {"name": "web", "description": "Web interface"},
            {"name": "mobile", "description": "Mobile application"},
            {"name": "ivr", "description": "Interactive Voice Response"},
            {"name": "kiosk", "description": "Physical kiosks in rural areas"}
        ]
    }

# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", 8000)),
        log_level=os.getenv("LOG_LEVEL", "info").lower()
    )