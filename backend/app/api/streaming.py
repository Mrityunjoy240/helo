from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import asyncio
import json
import logging

from app.services.streaming.pipeline import get_pipeline, VoicePipeline
from app.services.streaming.websocket_manager import ws_manager
from app.services.llm import OllamaLLM
from app.services.tools import get_tool_registry

logger = logging.getLogger(__name__)
router = APIRouter()


class QueryRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    intent: str
    source: str
    confidence: float


@router.websocket("/stream")
async def voice_stream_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice streaming.
    Supports:
    - Text queries with streaming response
    - Interrupt/barge-in
    - Session management
    """
    session_id = await ws_manager.connect(websocket)
    pipeline = get_pipeline()

    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)

            msg_type = message_data.get("type")

            if msg_type == "query":
                query = message_data.get("text", "")
                if not query.strip():
                    continue

                await ws_manager.send(session_id, {
                    "type": "processing",
                    "status": "started"
                })

                try:
                    async for result in pipeline.process(query, session_id):
                        if ws_manager.is_interrupted(session_id):
                            ws_manager.clear_interrupt(session_id)
                            await ws_manager.send(session_id, {
                                "type": "interrupted"
                            })
                            break

                        await ws_manager.send(session_id, result)

                except Exception as e:
                    logger.error(f"Pipeline error: {e}")
                    await ws_manager.send(session_id, {
                        "type": "error",
                        "message": str(e)
                    })

            elif msg_type == "interrupt":
                await ws_manager.interrupt(session_id)
                await ws_manager.send(session_id, {
                    "type": "interrupt_ack"
                })

            elif msg_type == "ping":
                await ws_manager.send(session_id, {
                    "type": "pong"
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await ws_manager.disconnect(session_id)


@router.post("/query", response_model=QueryResponse)
async def streaming_query(request: QueryRequest):
    """
    HTTP endpoint for simple query-response.
    Use WebSocket for streaming responses.
    """
    pipeline = get_pipeline()
    
    response_text = ""
    intent_info = {"intent": "unknown", "source": "unknown", "confidence": 0.0}

    try:
        async for result in pipeline.process(request.message, request.session_id or "http"):
            if result["type"] == "intent":
                intent_info = {
                    "intent": result.get("intent", "unknown"),
                    "source": result.get("source", "unknown"),
                    "confidence": result.get("confidence", 0.0)
                }
            elif result["type"] == "answer_chunk":
                response_text += result.get("text", "")
            elif result["type"] == "done":
                response_text = result.get("full_text", response_text)

    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return QueryResponse(
        answer=response_text,
        intent=intent_info["intent"],
        source=intent_info["source"],
        confidence=intent_info["confidence"]
    )


@router.get("/health")
async def streaming_health():
    """Health check for streaming services"""
    llm = OllamaLLM()
    
    return {
        "status": "healthy",
        "ollama": llm.is_available(),
        "active_sessions": ws_manager.get_active_count()
    }


@router.post("/interrupt/{session_id}")
async def interrupt_session(session_id: str):
    """Manually interrupt a session"""
    await ws_manager.interrupt(session_id)
    return {"status": "interrupted", "session_id": session_id}


@router.get("/sessions")
async def list_sessions():
    """List all active sessions"""
    return {
        "active_count": ws_manager.get_active_count(),
        "sessions": list(ws_manager._sessions.keys())
    }
