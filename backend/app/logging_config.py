
import logging
import logging.handlers
import json
import os
from datetime import datetime
from pathlib import Path

class JSONFormatter(logging.Formatter):
    """
    Formatter that dumps the log record as a JSON object.
    """
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_obj)

def setup_logging(log_dir: str = "logs", log_level: str = "INFO"):
    """
    Configure logging to write to console and rotating file.
    """
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    
    # Clear existing handlers
    logger.handlers = []
    
    # Console Handler (Human readable)
    console_handler = logging.StreamHandler()
    console_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File Handler (JSON structured for parsing)
    file_handler = logging.handlers.RotatingFileHandler(
        log_path / "app.log",
        maxBytes=10*1024*1024, # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(JSONFormatter())
    logger.addHandler(file_handler)
    
    # Error File Handler (Separate file for errors)
    error_handler = logging.handlers.RotatingFileHandler(
        log_path / "error.log",
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(JSONFormatter())
    logger.addHandler(error_handler)
    
    
    # Configure granular logging for Voice and TTS
    logging.getLogger("app.api.voice").setLevel(logging.DEBUG)
    logging.getLogger("app.services.tts").setLevel(logging.DEBUG)
    
    logging.info("Logging configured successfully")

