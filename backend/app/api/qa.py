from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import logging
import os
import time
import sqlite3
from datetime import datetime

from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

from app.database import get_db

# Request/Response Models
class GroqQueryRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[str]
    session_id: str
    conversation_id: Optional[str] = None
    source: str = "groq"
    intent: str = "general"
    confidence: float = 0.95


# Helper Functions
async def _get_conversation_messages(conversation_id: str, limit: int = 10):
    """Get messages from a conversation"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
        (conversation_id, limit)
    )
    messages = cursor.fetchall()
    conn.close()
    return [{"role": m["role"], "content": m["content"]} for m in reversed(messages)]


async def _save_message(conversation_id: str, role: str, content: str):
    """Save a message to a conversation"""
    conn = get_db()
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
        (conversation_id, role, content, now)
    )
    cursor.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        (now, conversation_id)
    )
    conn.commit()
    conn.close()


async def _create_conversation() -> str:
    """Create a new conversation"""
    import uuid
    conn = get_db()
    cursor = conn.cursor()
    conv_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (conv_id, "New Chat", now, now)
    )
    conn.commit()
    conn.close()
    return conv_id


# ============== ENDPOINTS ==============

@router.post("/groq-query", response_model=QueryResponse)
async def groq_query_endpoint(request: Request, query_data: GroqQueryRequest):
    """
    Pure LLM Query Endpoint using Groq API (Llama 3.3 70B).
    """
    start_time = time.time()
    session_id = query_data.session_id or getattr(request.state, 'session_id', 'default')
    logger.info(f"[{session_id}] Groq Query: '{query_data.message[:60]}...'")
    
    try:
        from app.services.llm.groq_service import get_groq_service
        
        conversation_history = None
        if query_data.conversation_id:
            conversation_history = await _get_conversation_messages(query_data.conversation_id, limit=6)
        
        groq_service = get_groq_service()
        
        if not groq_service.is_available():
            return QueryResponse(
                answer="Groq API is not configured. Please check your .env file.",
                sources=[],
                session_id=session_id,
                conversation_id=query_data.conversation_id,
                source="error",
                intent="configuration_error",
                confidence=0.0
            )
        
        result = await groq_service.generate_response(
            query_data.message,
            conversation_history=conversation_history
        )
        
        if query_data.conversation_id:
            await _save_message(query_data.conversation_id, "user", query_data.message)
            await _save_message(query_data.conversation_id, "assistant", result["answer"])
        
        elapsed = time.time() - start_time
        logger.info(f"[{session_id}] Groq processed in {elapsed:.2f}s")
        
        return QueryResponse(
            answer=result["answer"],
            sources=[],
            session_id=session_id,
            conversation_id=query_data.conversation_id,
            source=result.get("source", "groq"),
            intent="llm_generated",
            confidence=0.95
        )
        
    except Exception as e:
        logger.error(f"Groq query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    groq_ok = False
    try:
        from app.services.llm.groq_service import get_groq_service
        groq_ok = get_groq_service().is_available()
    except Exception:
        pass
    
    return {
        'status': 'healthy',
        'groq_available': groq_ok,
        'groq_endpoint': '/qa/groq-query',
        'knowledge_base': 'combined_kb.json',
        'conversations_enabled': True
    }
