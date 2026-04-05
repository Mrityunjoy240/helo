import asyncio
import logging
import numpy as np
from typing import AsyncGenerator, Optional
from typing import List

logger = logging.getLogger(__name__)


class FasterWhisperSTT:
    """
    Local STT using Faster-Whisper.
    Optimized for real-time streaming transcription.
    """

    def __init__(
        self,
        model_size: str = "base",
        language: str = "en",
        compute_type: str = "int8"
    ):
        self.model_size = model_size
        self.language = language
        self.compute_type = compute_type
        self.model = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the model"""
        if self._initialized:
            return True

        try:
            from faster_whisper import WhisperModel
            
            logger.info(f"Loading Whisper model: {self.model_size}")
            self.model = WhisperModel(
                self.model_size,
                compute_type=self.compute_type,
                device="cpu"
            )
            self._initialized = True
            logger.info("Whisper model loaded successfully")
            return True
        except ImportError:
            logger.warning("faster-whisper not installed, using fallback")
            return False
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            return False

    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None
    ) -> str:
        """Transcribe audio bytes to text"""
        if not self._initialized:
            await self.initialize()

        if self.model is None:
            logger.warning("Using browser-based STT as fallback")
            return ""

        try:
            import io
            import wave
            
            audio_array = self._bytes_to_audio(audio_data)
            if audio_array is None:
                return ""

            segments, _ = self.model.transcribe(
                audio_array,
                language=language or self.language,
                beam_size=5,
                vad_filter=True
            )

            text = " ".join([segment.text for segment in segments])
            logger.info(f"Transcribed: {text[:50]}...")
            return text.strip()

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    async def transcribe_stream(
        self,
        audio_chunks: AsyncGenerator[bytes, None],
        language: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Stream transcription - yields partial results"""
        if not self._initialized:
            await self.initialize()

        if self.model is None:
            logger.warning("Streaming STT not available")
            return

        buffer = []
        
        async for chunk in audio_chunks:
            if not chunk:
                continue

            audio_array = self._bytes_to_audio(chunk)
            if audio_array is None:
                continue

            try:
                segments, _ = self.model.transcribe(
                    audio_array,
                    language=language or self.language,
                    beam_size=3,
                    vad_filter=True
                )

                for segment in segments:
                    if segment.text.strip():
                        yield segment.text.strip()

            except Exception as e:
                logger.error(f"Streaming transcription error: {e}")
                continue

    def _bytes_to_audio(self, audio_bytes: bytes) -> Optional[np.ndarray]:
        """Convert audio bytes to numpy array"""
        try:
            import io
            import wave
            
            wav_io = io.BytesIO(audio_bytes)
            
            with wave.open(wav_io, 'rb') as wav_file:
                sample_rate = wav_file.getframerate()
                num_frames = wav_file.getnframes()
                audio_data = wav_file.readframes(num_frames)
                
                audio_array = np.frombuffer(audio_data, dtype=np.int16)
                audio_array = audio_array.astype(np.float32) / 32768.0
                
                if sample_rate != 16000:
                    import scipy.signal
                    samples = int(len(audio_array) * 16000 / sample_rate)
                    audio_array = scipy.signal.resample(audio_array, samples)
                
                return audio_array

        except Exception as e:
            logger.error(f"Audio conversion error: {e}")
            return None

    async def detect_language(self, audio_data: bytes) -> str:
        """Detect language in audio"""
        if not self._initialized:
            await self.initialize()

        if self.model is None:
            return "en"

        try:
            audio_array = self._bytes_to_audio(audio_data)
            if audio_array is None:
                return "en"

            segments, info = self.model.transcribe(
                audio_array,
                beam_size=5
            )
            
            return info.language if hasattr(info, 'language') else "en"

        except Exception as e:
            logger.error(f"Language detection error: {e}")
            return "en"


class WebRTCVAD:
    """
    Voice Activity Detection using WebRTC VAD.
    Optimized for real-time barge-in detection.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        mode: int = 3
    ):
        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms
        self.mode = mode
        self.vad = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize VAD"""
        if self._initialized:
            return True

        try:
            import webrtcvad
            self.vad = webrtcvad.Vad(mode)
            self._initialized = True
            logger.info("WebRTC VAD initialized")
            return True
        except ImportError:
            logger.warning("webrtcvad not installed, using energy-based VAD")
            self._use_energy_vad = True
            return True
        except Exception as e:
            logger.error(f"VAD initialization error: {e}")
            return False

    async def is_speech(self, audio_chunk: bytes) -> bool:
        """Detect if chunk contains speech"""
        if not self._initialized:
            await self.initialize()

        if hasattr(self, '_use_energy_vad') and self._use_energy_vad:
            return self._energy_based_vad(audio_chunk)

        try:
            return self.vad.is_speech(
                audio_chunk,
                self.sample_rate
            )
        except Exception as e:
            logger.error(f"VAD error: {e}")
            return True

    def _energy_based_vad(self, audio_chunk: bytes) -> bool:
        """Fallback energy-based VAD"""
        try:
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16)
            energy = np.sqrt(np.mean(audio_array.astype(float) ** 2))
            threshold = 500
            return energy > threshold
        except:
            return True


stt_service = FasterWhisperSTT()
vad_service = WebRTCVAD()
