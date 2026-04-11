from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api import qa
from app.api import conversations
import logging
import os
from uuid import uuid4

from app.logging_config import setup_logging
from app.config import settings
from app.database import init_db

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize Database
init_db()

# Create FastAPI app
app = FastAPI(title="College Voice Agent API", version="1.0.0")

# Add Session ID Middleware
@app.middleware("http")
async def add_session_id_middleware(request: Request, call_next):
    """Inject a unique session_id into request.state for every request"""
    if not hasattr(request.state, 'session_id'):
        request.state.session_id = str(uuid4())
    response = await call_next(request)
    return response

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.limiter import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure temp audio directory exists
os.makedirs(settings.temp_audio_dir, exist_ok=True)

# Mount static directory for audio files
app.mount("/audio", StaticFiles(directory=settings.temp_audio_dir), name="audio")

# Include API routes
app.include_router(qa.router, prefix="/qa", tags=["qa"])
app.include_router(conversations.router, prefix="/api", tags=["conversations"])
from app.api import tts, stt
app.include_router(tts.router, prefix="/qa", tags=["tts"])
app.include_router(stt.router, prefix="/qa", tags=["stt"])
from app.api import monitoring, auth_routes, admin
from app.api import health
app.include_router(monitoring.router, prefix="/monitoring", tags=["monitoring"])
app.include_router(health.router, prefix="/health", tags=["health"])
app.include_router(auth_routes.router, tags=["auth"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])

# Serve Frontend Static Files (if they exist)
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
logger.info(f"Searching for frontend at: {frontend_path}")
if os.path.exists(frontend_path):
    logger.info("Frontend directory found. Mounting static files.")
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    logger.warning(f"Frontend directory NOT found at {frontend_path}")
    @app.get("/")
    async def root():
        return {"message": "College Voice Agent API is running! (Frontend not built)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
