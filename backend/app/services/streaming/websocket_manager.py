import asyncio
import json
import logging
from typing import Dict, Optional, Set
from fastapi import WebSocket
import uuid

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    Manages WebSocket connections for real-time voice communication.
    Handles connection pooling, session management, and interrupt handling.
    """

    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}
        self._sessions: Dict[str, Dict] = {}
        self._active_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket) -> str:
        """Accept connection and create session"""
        await websocket.accept()
        session_id = str(uuid.uuid4())
        
        self._connections[session_id] = websocket
        self._sessions[session_id] = {
            "connected": True,
            "interrupted": False,
            "last_activity": asyncio.get_event_loop().time()
        }
        
        logger.info(f"WebSocket connected: {session_id}")
        
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id
        })
        
        return session_id

    async def disconnect(self, session_id: str):
        """Disconnect and cleanup session"""
        if session_id in self._active_tasks:
            task = self._active_tasks[session_id]
            if not task.done():
                task.cancel()
            del self._active_tasks[session_id]

        if session_id in self._connections:
            del self._connections[session_id]

        if session_id in self._sessions:
            del self._sessions[session_id]

        logger.info(f"WebSocket disconnected: {session_id}")

    async def send(self, session_id: str, data: Dict):
        """Send data to client"""
        if session_id not in self._connections:
            logger.warning(f"Session not found: {session_id}")
            return False

        websocket = self._connections[session_id]
        
        try:
            await websocket.send_json(data)
            self._sessions[session_id]["last_activity"] = asyncio.get_event_loop().time()
            return True
        except Exception as e:
            logger.error(f"Send error: {e}")
            await self.disconnect(session_id)
            return False

    async def send_text(self, session_id: str, text: str):
        """Send text message"""
        await self.send(session_id, {"type": "text", "text": text})

    async def send_audio(self, session_id: str, audio_data: bytes):
        """Send audio data"""
        import base64
        audio_b64 = base64.b64encode(audio_data).decode()
        await self.send(session_id, {"type": "audio", "data": audio_b64})

    async def interrupt(self, session_id: str):
        """Interrupt current processing"""
        if session_id in self._sessions:
            self._sessions[session_id]["interrupted"] = True
            logger.info(f"Interrupted session: {session_id}")

    def is_interrupted(self, session_id: str) -> bool:
        """Check if session is interrupted"""
        if session_id not in self._sessions:
            return False
        return self._sessions[session_id].get("interrupted", False)

    def clear_interrupt(self, session_id: str):
        """Clear interrupt flag"""
        if session_id in self._sessions:
            self._sessions[session_id]["interrupted"] = False

    def register_task(self, session_id: str, task: asyncio.Task):
        """Register a background task for a session"""
        self._active_tasks[session_id] = task

    def cancel_task(self, session_id: str):
        """Cancel active task for session"""
        if session_id in self._active_tasks:
            task = self._active_tasks[session_id]
            if not task.done():
                task.cancel()
            del self._active_tasks[session_id]

    async def broadcast(self, data: Dict):
        """Broadcast to all connected clients"""
        for session_id in list(self._connections.keys()):
            await self.send(session_id, data)

    def get_active_count(self) -> int:
        """Get number of active connections"""
        return len(self._connections)

    def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get session information"""
        return self._sessions.get(session_id)


ws_manager = WebSocketManager()
