from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from groq import Groq

class Settings(BaseSettings):
    # API Keys
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    speechmatics_api_key: str = os.getenv("SPEECHMATICS_API_KEY", "")

    # Auth Settings
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin")
    secret_key: str = os.getenv("SECRET_KEY", "supersecretkey")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Default voice ID for ElevenLabs (Rachel's voice)
    # elevenlabs_voice_id: str = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
    
    # Direct Groq client initialization
    groq_client: Optional[Groq] = None
    
    # Directories
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "chroma_db")
    upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")
    temp_audio_dir: str = os.getenv("TEMP_AUDIO_DIR", "temp_audio")
    
    # CORS settings
    cors_origins: List[str] = ["*"]  # In production, specify exact origins
    
    # College information
    college_name: str = os.getenv("COLLEGE_NAME", "Dr. B.C. Roy Engineering College")
    admissions_phone: str = os.getenv("ADMISSIONS_PHONE", "+91-343-2567890")
    support_email: str = os.getenv("SUPPORT_EMAIL", "admissions@bcrec.ac.in")
    
    class Config:
        env_file = ".env"
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Initialize Groq client if API key is available
        # Groq is now optional - local Ollama is primary LLM
        if self.groq_api_key:
            self.groq_client = Groq(api_key=self.groq_api_key)
        else:
            self.groq_client = None

# Create settings instance
settings = Settings()