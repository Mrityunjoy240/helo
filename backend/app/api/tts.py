"""
TTS (Text-to-Speech) API endpoint using Sarvam.ai

POST /qa/tts - Generate speech from text
GET /qa/tts/voices - List available voices
GET /qa/tts/languages - List supported languages
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import logging
import os
import time
import uuid

from app.config import settings
from app.services.sarvam_service import get_sarvam_service, init_sarvam_service

logger = logging.getLogger(__name__)
router = APIRouter()


class TTSRequest(BaseModel):
    text: str
    language: Optional[str] = "en-IN"
    speaker: Optional[str] = "shubh"
    pace: Optional[float] = 1.0
    session_id: Optional[str] = None


class TTSResponse(BaseModel):
    audio_url: str
    format: str
    language: str
    speaker: str


def _init_sarvam():
    """Initialize Sarvam service if not already done"""
    if settings.sarvam_api_key:
        init_sarvam_service(settings.sarvam_api_key)
    return get_sarvam_service()


@router.post("/tts", response_model=TTSResponse)
async def text_to_speech(request_data: TTSRequest, request: Request):
    """
    Convert text to speech using Sarvam AI TTS API.
    """
    if not request_data.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    # Auto-select speaker based on language for better accent
    language = request_data.language or "en-IN"
    speaker = request_data.speaker or "shubh"
    
    # Map languages to natural-sounding native speakers
    language_speaker_map = {
        "hi-IN": "aditya",  # Clear Hindi male voice
        "hi": "aditya",
        "bn-IN": "ritu",    # Clear Bengali female voice
        "bn": "ritu",
        "en-IN": "shubh"    # Standard Indian English voice
    }
    
    if language in language_speaker_map and not request_data.speaker:
        speaker = language_speaker_map[language]

    sarvam = _init_sarvam()
    
    if not sarvam.is_available():
        raise HTTPException(
            status_code=503,
            detail="Sarvam TTS service not available. Please check SARVAM_API_KEY."
        )
    
    session_id = request_data.session_id or getattr(request.state, 'session_id', 'default')
    
    try:
        result = await sarvam.text_to_speech(
            text=request_data.text,
            language=language,
            speaker=speaker,
            pace=request_data.pace or 1.0
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "TTS generation failed"))
        
        audio_bytes = result["audio_bytes"]
        
        filename = f"tts_{session_id}_{int(time.time())}_{uuid.uuid4().hex[:8]}.wav"
        filepath = os.path.join(settings.temp_audio_dir, filename)
        
        os.makedirs(settings.temp_audio_dir, exist_ok=True)
        
        with open(filepath, "wb") as f:
            f.write(audio_bytes)
        
        logger.info(f"[{session_id}] TTS generated: {filename} ({len(audio_bytes)} bytes)")
        
        return TTSResponse(
            audio_url=f"/audio/{filename}",
            format=result.get("format", "wav"),
            language=result.get("language", request_data.language or "en-IN"),
            speaker=result.get("speaker", request_data.speaker or "shubh")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tts/voices")
async def list_voices():
    """List available TTS voices"""
    sarvam = _init_sarvam()
    return {
        "voices": sarvam.get_available_voices(),
        "default": "shubh"
    }


@router.get("/tts/languages")
async def list_languages():
    """List supported languages"""
    sarvam = _init_sarvam()
    return {
        "languages": sarvam.get_supported_languages(),
        "default": "en-IN"
    }
