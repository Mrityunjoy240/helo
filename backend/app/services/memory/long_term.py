import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class LongTermMemory:
    """
    Persistent memory using vector store for semantic search.
    Stores important facts and preferences across sessions.
    """

    def __init__(self, storage_path: str = "chroma_db/long_term_memory.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._memories: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        """Load memories from disk"""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load memories: {e}")
        return []

    def _save(self) -> None:
        """Save memories to disk"""
        try:
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(self._memories, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save memories: {e}")

    def add_memory(
        self, 
        session_id: str, 
        content: str, 
        memory_type: str = "fact",
        importance: float = 0.5
    ) -> None:
        """Add a new memory"""
        memory = {
            "session_id": session_id,
            "content": content,
            "type": memory_type,
            "importance": importance,
            "created_at": len(self._memories)
        }
        self._memories.append(memory)
        
        if len(self._memories) > 1000:
            self._memories = self._memories[-500:]
        
        self._save()

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Simple keyword-based search"""
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored = []
        for memory in self._memories:
            content_lower = memory["content"].lower()
            content_words = set(content_lower.split())
            
            overlap = len(query_words & content_words)
            if overlap > 0:
                score = overlap / max(len(query_words), len(content_words))
                scored.append((score, memory))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:limit]]

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most recent memories"""
        return self._memories[-limit:]

    def clear_session(self, session_id: str) -> None:
        """Remove memories for a specific session"""
        self._memories = [m for m in self._memories if m.get("session_id") != session_id]
        self._save()

    def get_memory_count(self) -> int:
        """Get total memory count"""
        return len(self._memories)


long_term_memory = LongTermMemory()
