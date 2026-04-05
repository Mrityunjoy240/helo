import logging
import io
import re
import os
import tempfile
import asyncio
from typing import Optional
from pathlib import Path

from gtts import gTTS
import pyttsx3
import wave
from app.config import settings

class TTSAPIError(Exception):
    """Exception raised for TTS API errors"""
    pass

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self):
        """Initialize TTS service with Piper (Phase 2) and fallback support"""
        self.piper_voice = None
        self.cache_dir = os.path.join(settings.temp_audio_dir, "cache")
        os.makedirs(self.cache_dir, exist_ok=True)
        
        # Priority 1: Piper (Local Real-time) - Using Amy (Female Voice)
        try:
            from piper.voice import PiperVoice
            model_name = "en_US-amy-medium.onnx"
            model_path = Path("models") / model_name
            
            if model_path.exists():
                logger.info(f"Initializing Piper with female voice model: {model_path}")
                self.piper_voice = PiperVoice.load(str(model_path))
                logger.info("Piper TTS status: ENABLED (Amy)")
            else:
                # Fallback to lessac if amy not found
                alt_model = Path("models/en_US-lessac-medium.onnx")
                if alt_model.exists():
                    logger.info(f"Amy model not found. Using fallback: {alt_model}")
                    self.piper_voice = PiperVoice.load(str(alt_model))
                else:
                    logger.info("No Piper models found. Performance will rely on gTTS.")
        except Exception as e:
            logger.error(f"Piper failed to load: {e}")

    async def text_to_speech(self, text: str) -> bytes:
        """Main entry point for TTS. Supports caching and multiple backends."""
        clean_text = self._strip_markdown(text)
        processed_text = self._expand_acronyms(clean_text)
        
        # 1. Performance Hack: Cache check (using .wav for Piper native compatibility)
        text_hash = str(hash(processed_text))
        cache_file = os.path.join(self.cache_dir, f"{text_hash}.wav")
        if os.path.exists(cache_file):
            with open(cache_file, "rb") as f:
                return f.read()

        # 2. Priority execution
        audio_bytes = None
        try:
            if self.piper_voice:
                audio_bytes = await self._generate_piper(processed_text)
            else:
                audio_bytes = await self._generate_gtts(processed_text)
        except Exception as e:
            logger.warning(f"Primary TTS generator failed: {e}. Using pyttsx3 fallback.")
            audio_bytes = await self._generate_pyttsx3(processed_text)
        
        # Store in cache if successful
        if audio_bytes:
            try:
                with open(cache_file, "wb") as f:
                    f.write(audio_bytes)
            except Exception as cache_err:
                logger.debug(f"Cache write failed: {cache_err}")
                
        return audio_bytes

    def _strip_markdown(self, text: str) -> str:
        """Clean markdown symbols for clearer speech"""
        text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^\*]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)
        text = re.sub(r'^[\s]*[•\-\*]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        return text.strip()
    
    def _expand_acronyms(self, text: str) -> str:
        """Improve pronunciation of college-specific terms"""
        text = text.replace('₹', 'rupees ')
        acronyms = {
            r'\bIT\b': 'I T',
            r'\bCSE\b': 'C S E',
            r'\bAIML\b': 'A I M L',
            r'\bECE\b': 'E C E',
            r'\bEE\b': 'E E',
            r'\bME\b': 'M E',
            r'\bCE\b': 'C E',
            r'\bCS\b': 'C S',
            r'\bDS\b': 'D S',
            r'\bCSD\b': 'C S D',
            r'\bBTech\b': 'B Tech',
            r'\bB\.Tech\b': 'B Tech',
            r'\bMTech\b': 'M Tech',
            r'\bM\.Tech\b': 'M Tech'
        }
        for pattern, replacement in acronyms.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text

    async def _generate_piper(self, text: str) -> bytes:
        """Local high-speed Piper synthesis"""
        def _run():
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                temp_filename = tmp.name
            try:
                # Piper's synthesize_wav requires a wave.Wave_write object
                with wave.open(temp_filename, "wb") as wav_file:
                    self.piper_voice.synthesize_wav(text, wav_file)
                
                with open(temp_filename, "rb") as f:
                    return f.read()
            finally:
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
        return await asyncio.to_thread(_run)

    async def _generate_gtts(self, text: str) -> bytes:
        """Google Cloud TTS generation"""
        def _run():
            tts = gTTS(text=text, lang='en', tld='co.in', slow=False)
            buffer = io.BytesIO()
            tts.write_to_fp(buffer)
            return buffer.getvalue()
        return await asyncio.to_thread(_run)

    async def _generate_pyttsx3(self, text: str) -> bytes:
        """Native OS fallback"""
        def _run():
            engine = pyttsx3.init()
            engine.setProperty('rate', 160)
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                temp_filename = tmp.name
            try:
                engine.save_to_file(text, temp_filename)
                engine.runAndWait()
                with open(temp_filename, 'rb') as f:
                    return f.read()
            finally:
                if os.path.exists(temp_filename):
                    os.unlink(temp_filename)
        return await asyncio.to_thread(_run)
