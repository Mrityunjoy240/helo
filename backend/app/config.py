from pydantic_settings import BaseSettings
from typing import List, Optional, Any
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Try to load local.env first, then .env
if os.path.exists("local.env"):
    load_dotenv("local.env")
    logger.info("Loaded configuration from local.env")
else:
    load_dotenv(".env")
    logger.info("Loaded configuration from .env")

# Try to import Groq, gracefully degrade if not available
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    Groq = None
    logger.warning("groq package not installed. Groq features will be unavailable.")

class Settings(BaseSettings):
    # API Keys
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    sarvam_api_key: str = os.getenv("SARVAM_API_KEY", "")

    # Auth Settings
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "admin")
    secret_key: str = os.getenv("SECRET_KEY", "supersecretkey")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # Direct Groq client initialization
    groq_client: Optional[Any] = None
    
    # Gemini settings
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
    gemini_temperature: float = float(os.getenv("GEMINI_TEMPERATURE", "0.3"))
    gemini_max_tokens: int = int(os.getenv("GEMINI_MAX_TOKENS", "500"))
    
    # Directories
    chroma_persist_dir: str = os.getenv("CHROMA_PERSIST_DIR", "chroma_db")
    upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")
    temp_audio_dir: str = os.getenv("TEMP_AUDIO_DIR", "temp_audio")
    
    # CORS settings
    cors_origins: List[str] = ["*"]  # In production, specify exact origins
    
    # College information
    college_name: str = os.getenv("COLLEGE_NAME", "Dr. B.C. Roy Engineering College")
    admissions_phone: str = os.getenv("ADMISSIONS_PHONE", "0343-2501353")
    support_email: str = os.getenv("SUPPORT_EMAIL", "info@bcrec.ac.in")
    
    class Config:
        env_file = ".env"
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Initialize Groq client if API key is available and library is installed
        if GROQ_AVAILABLE and self.groq_api_key:
            try:
                self.groq_client = Groq(api_key=self.groq_api_key)
                logger.info("Groq client initialized from API key")
            except Exception as e:
                logger.error(f"Failed to initialize Groq client: {e}")
                self.groq_client = None
        else:
            self.groq_client = None

# Create settings instance
settings = Settings()
