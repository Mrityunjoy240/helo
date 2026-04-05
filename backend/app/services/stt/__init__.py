from .faster_whisper_stt import FasterWhisperSTT

# Re-export old STTService for backward compatibility
try:
    from app.services.stt_old import STTService
    __all__ = ["FasterWhisperSTT", "STTService"]
except ImportError:
    __all__ = ["FasterWhisperSTT"]
