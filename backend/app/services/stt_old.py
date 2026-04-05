import asyncio
import base64
import io
import logging
from typing import Optional
import speech_recognition as sr
from pydub import AudioSegment

from app.config import settings

logger = logging.getLogger(__name__)

class STTService:
    def __init__(self):
        # Use Pydantic field, default to empty string if missing in .env
        self.api_key = settings.speechmatics_api_key
        self.base_url = "https://asr.api.speechmatics.com/v2"
        self.recognizer = sr.Recognizer()
    
    async def transcribe_audio(self, audio_data: str) -> str:
        """
        Transcribe audio using Google Speech Recognition (Free tier)
        audio_data: base64 encoded audio string
        """
        try:
            # Decode base64 audio data
            audio_bytes = base64.b64decode(audio_data)
            
            # Convert audio bytes to compatible format (WAV) using pydub if needed
            # Assuming input is likely webm/wav from browser
            # We explicitly convert to WAV for compatibility with SpeechRecognition
            try:
                # Assuming incoming is WebM/Ogg from browser, convert to WAV
                audio_segment = AudioSegment.from_file(io.BytesIO(audio_bytes))
                wav_io = io.BytesIO()
                audio_segment.export(wav_io, format="wav")
                wav_io.seek(0)
            except Exception as e:
                # If conversion fails, try direct WAV read
                logger.warning(f"Audio conversion failed, trying raw bytes: {e}")
                wav_io = io.BytesIO(audio_bytes)

            # Use SpeechRecognition
            with sr.AudioFile(wav_io) as source:
                audio_content = self.recognizer.record(source)
                
            # Perform transcription
            # Runs in thread executor to avoid blocking async loop
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                None, 
                lambda: self.recognizer.recognize_google(audio_content)
            )
            
            logger.info(f"Successfully transcribed audio: {text[:50]}...")
            return text

        except sr.UnknownValueError:
            logger.info("Speech Recognition could not understand audio")
            return ""
        except sr.RequestError as e:
            logger.error(f"Could not request results from Google Speech Recognition service; {e}")
            raise Exception(f"STT Error: {e}")
        except Exception as e:
            logger.error(f"Error in transcribe_audio: {e}")
            # If ffmpeg is missing for pydub, this might fail.
            # Fallback message?
            return ""
