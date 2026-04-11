"""
Sarvam.ai Service for BCREC Voice Agent

Provides Text-to-Speech (TTS) and Speech-to-Text (STT) using Sarvam AI APIs.
- TTS: Bulbul v3 model with 30+ Indian voices
- STT: Saaras v3 model for 22 Indian languages
"""
import base64
import logging
import io
import json
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    from sarvamai import SarvamAI
    SARVAM_AVAILABLE = True
except ImportError:
    SARVAM_AVAILABLE = False
    logger.warning("sarvamai not installed. Sarvam service will be unavailable.")


class SarvamService:
    """
    Sarvam AI service for TTS and STT operations.
    """
    
    # Supported languages
    SUPPORTED_LANGUAGES = {
        "en-IN": "English (India)",
        "hi-IN": "Hindi",
        "hi": "Hindi",
        "bn-IN": "Bengali",
        "bn": "Bengali",
        "ta-IN": "Tamil",
        "te-IN": "Telugu",
        "kn-IN": "Kannada",
        "ml-IN": "Malayalam",
        "mr-IN": "Marathi",
        "gu-IN": "Gujarati",
        "pa-IN": "Punjabi",
        "od-IN": "Odia",
    }
    
    # Available TTS voices (Bulbul v3)
    VOICES = {
        # Male voices
        "shubh": "Shubh (Default Male)",
        "aditya": "Aditya",
        "rahul": "Rahul",
        "rohan": "Rohan",
        "amit": "Amit",
        "dev": "Dev",
        "ritu": "Ritu (Female)",
        "priya": "Priya (Female)",
        "neha": "Neha (Female)",
        "pooja": "Pooja (Female)",
        "roopa": "Roopa (Female)",
    }
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = None
        self.api_key = api_key
        
        if SARVAM_AVAILABLE and api_key:
            try:
                self.client = SarvamAI(api_subscription_key=api_key)
                logger.info("Sarvam client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Sarvam client: {e}")
                self.client = None
        else:
            if not api_key:
                logger.warning("Sarvam API key not provided")
            if not SARVAM_AVAILABLE:
                logger.warning("Sarvam library not installed")
    
    def is_available(self) -> bool:
        """Check if Sarvam service is available"""
        return self.client is not None
    
    async def text_to_speech(
        self,
        text: str,
        language: str = "en-IN",
        speaker: str = "shubh",
        pace: float = 1.0,
        model: str = "bulbul:v3"
    ) -> Dict[str, Any]:
        """
        Convert text to speech using Sarvam TTS API.
        
        Args:
            text: Text to convert to speech
            language: Language code (default: en-IN)
            speaker: Voice name (default: shubh)
            pace: Speech pace 0.5-2.0 (default: 1.0)
            model: TTS model (default: bulbul:v3)
        
        Returns:
            Dict with 'audio_bytes' (bytes) and 'format' (str)
        """
        if not self.client:
            return {
                "success": False,
                "error": "Sarvam client not initialized"
            }
        
        try:
            response = self.client.text_to_speech.convert(
                text=text,
                target_language_code=language,
                speaker=speaker,
                model=model,
                pace=pace,
                speech_sample_rate=24000
            )
            
            # Combine all audio chunks
            audio_base64 = "".join(response.audios)
            audio_bytes = base64.b64decode(audio_base64)
            
            logger.info(f"TTS generated: {len(audio_bytes)} bytes, lang={language}, speaker={speaker}")
            
            return {
                "success": True,
                "audio_bytes": audio_bytes,
                "format": "wav",
                "language": language,
                "speaker": speaker
            }
            
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def speech_to_text(
        self,
        audio_bytes: bytes,
        language: str = "en-IN",
        model: str = "saaras:v3"
    ) -> Dict[str, Any]:
        """
        Convert speech to text using Sarvam STT API.
        
        Args:
            audio_bytes: Audio data (wav/mp3 format)
            language: Language code (default: en-IN, use 'auto' for detection)
            model: STT model (default: saaras:v3)
        
        Returns:
            Dict with 'text', 'language', and 'success'
        """
        if not self.client:
            return {
                "success": False,
                "error": "Sarvam client not initialized"
            }
        
        try:
            # Create file-like object for upload
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "audio.wav"
            
            lang_param = None if language == "auto" else language
            
            logger.info(f"STT request: audio_size={len(audio_bytes)} bytes, model={model}, language={lang_param}")
            
            response = self.client.speech_to_text.transcribe(
                file=audio_file,
                model=model,
                language_code=lang_param
            )
            
            logger.info(f"Sarvam raw response type: {type(response)}")
            logger.info(f"Sarvam raw response: {response}")
            
            transcript = ""
            detected_language = language
            
            if hasattr(response, 'transcript'):
                transcript = response.transcript or ""
            elif hasattr(response, 'text'):
                transcript = response.text or ""
            elif isinstance(response, dict):
                transcript = response.get('transcript', '') or response.get('text', '') or ""
            else:
                transcript = str(response) or ""
            
            if hasattr(response, 'language_code') and response.language_code:
                detected_language = response.language_code
            
            logger.info(f"Extracted transcript: '{transcript[:100] if transcript else 'EMPTY'}'")
            
            logger.info(f"STT result: '{transcript[:100]}...' detected_lang={detected_language}")
            
            return {
                "success": True,
                "text": transcript,
                "language": detected_language
            }
            
        except Exception as e:
            logger.error(f"STT error: {e}")
            return {
                "success": False,
                "error": str(e),
                "text": ""
            }
    
    def get_available_voices(self) -> Dict[str, str]:
        """Get list of available TTS voices"""
        return self.VOICES.copy()
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages"""
        return self.SUPPORTED_LANGUAGES.copy()


# Global instance
_sarvam_service: Optional[SarvamService] = None


def get_sarvam_service(api_key: Optional[str] = None) -> SarvamService:
    """Get or create the Sarvam service singleton"""
    global _sarvam_service
    
    if _sarvam_service is None:
        _sarvam_service = SarvamService(api_key=api_key)
    return _sarvam_service


def init_sarvam_service(api_key: str) -> SarvamService:
    """Initialize Sarvam service with API key"""
    global _sarvam_service
    _sarvam_service = SarvamService(api_key=api_key)
    return _sarvam_service
