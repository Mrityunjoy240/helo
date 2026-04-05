from fastapi import APIRouter
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/tts")
async def tts_health_check():
    """Check which TTS providers are working"""
    gtts_available = False
    pyttsx3_available = False
    
    
    def check_providers():
        gtts_ok = False
        pyttsx3_ok = False
        
        # Test gTTS
        try:
            from gtts import gTTS
            gTTS(text="test", lang='en')
            gtts_ok = True
        except:
            gtts_ok = False
            
        # Test pyttsx3
        try:
            import pyttsx3
            # Just check import for health check to avoid COM overhead/hanging
            # engine = pyttsx3.init() 
            pyttsx3_ok = True
        except:
            pyttsx3_ok = False
            
        return gtts_ok, pyttsx3_ok

    import asyncio
    gtts_available, pyttsx3_available = await asyncio.to_thread(check_providers)
    
    active_provider = "pyttsx3" if pyttsx3_available and not gtts_available else ("gtts" if gtts_available else "none")
    if gtts_available and pyttsx3_available:
        active_provider = "gtts (with fallback)"

    logger.info(f"TTS Health: gTTS={gtts_available}, pyttsx3={pyttsx3_available}, active={active_provider}")
    
    return {
        "gtts_available": gtts_available,
        "pyttsx3_available": pyttsx3_available,
        "active_provider": active_provider,
        "status": "healthy" if (gtts_available or pyttsx3_available) else "degraded"
    }
