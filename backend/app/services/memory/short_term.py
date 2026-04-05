import time
from typing import List, Dict, Any, Optional
from collections import deque
import json
import logging

logger = logging.getLogger(__name__)


class ShortTermMemory:
    """
    In-memory session-based conversation memory.
    Stores recent messages for context.
    """

    def __init__(self, max_messages: int = 10, max_sessions: int = 1000):
        self.max_messages = max_messages
        self.max_sessions = max_sessions
        self._sessions: Dict[str, deque] = {}
        self._timestamps: Dict[str, float] = {}

    def add_message(self, session_id: str, role: str, content: str) -> None:
        """Add a message to session memory"""
        if session_id not in self._sessions:
            self._sessions[session_id] = deque(maxlen=self.max_messages)
            
            if len(self._sessions) > self.max_sessions:
                oldest = min(self._timestamps, key=self._timestamps.get)
                del self._sessions[oldest]
                del self._timestamps[oldest]
        
        message = {
            "role": role,
            "content": content,
            "timestamp": time.time()
        }
        self._sessions[session_id].append(message)
        self._timestamps[session_id] = time.time()

    def get_context(self, session_id: str, last_k: int = 5) -> List[Dict[str, str]]:
        """Get last K messages as context for LLM"""
        if session_id not in self._sessions:
            return []
        
        messages = list(self._sessions[session_id])[-last_k:]
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def get_full_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Get full session history"""
        if session_id not in self._sessions:
            return []
        return list(self._sessions[session_id])

    def clear_session(self, session_id: str) -> None:
        """Clear a session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
        if session_id in self._timestamps:
            del self._timestamps[session_id]

    def get_session_count(self) -> int:
        """Get number of active sessions"""
        return len(self._sessions)

    def cleanup_old_sessions(self, max_age_seconds: int = 3600) -> int:
        """Remove sessions older than max_age_seconds"""
        current_time = time.time()
        to_remove = []
        
        for session_id, last_time in self._timestamps.items():
            if current_time - last_time > max_age_seconds:
                to_remove.append(session_id)
        
        for session_id in to_remove:
            self.clear_session(session_id)
        
        return len(to_remove)


short_term_memory = ShortTermMemory()
