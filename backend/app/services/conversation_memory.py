import json
import time
from typing import Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ConversationMemory:
    def __init__(self, storage_file: str = "chroma_db/conversation_memory.json"):
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(exist_ok=True)
        self.sessions: Dict[str, List[Dict]] = self._load_memory()
        # Initialize user profiles for storing preferences like WBJEE rank, interests, etc.
        self.user_profiles: Dict[str, Dict] = self._load_user_profiles()
    
    def _load_memory(self) -> Dict[str, List[Dict]]:
        """Load conversation memory from file."""
        try:
            if self.storage_file.exists():
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            else:
                return {}
        except Exception as e:
            logger.error(f"Error loading conversation memory: {e}")
            return {}
    
    def _load_user_profiles(self) -> Dict[str, Dict]:
        """Load user profiles from a separate file."""
        profile_file = Path("chroma_db/user_profiles.json")
        try:
            if profile_file.exists():
                with open(profile_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, dict) else {}
            else:
                return {}
        except Exception as e:
            logger.error(f"Error loading user profiles: {e}")
            return {}
    
    def _save_user_profiles(self):
        """Save user profiles to file."""
        profile_file = Path("chroma_db/user_profiles.json")
        try:
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(self.user_profiles, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving user profiles: {e}")
    
    def _save_memory(self):
        """Save conversation memory to file."""
        try:
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(self.sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error saving conversation memory: {e}")
    
    def create_session(self, session_id: str):
        """Create a new conversation session."""
        if session_id not in self.sessions:
            self.sessions[session_id] = []
            self._save_memory()
    
    def add_interaction(self, session_id: str, user_message: str, bot_response: str):
        """Add a user-bot interaction to the conversation memory."""
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        
        interaction = {
            "timestamp": time.time(),
            "user_message": user_message,
            "bot_response": bot_response
        }
        
        self.sessions[session_id].append(interaction)
        self._save_memory()
    
    def get_session_history(self, session_id: str, limit: int = 5) -> List[Dict]:
        """Get recent conversation history for a session."""
        if session_id in self.sessions:
            # Return last 'limit' interactions
            return self.sessions[session_id][-limit:]
        return []
    
    def update_last_response(self, session_id: str, new_response: str):
        """Update the last bot response in the conversation."""
        if session_id in self.sessions and self.sessions[session_id]:
            last_interaction = self.sessions[session_id][-1]
            last_interaction["bot_response"] = new_response
            self._save_memory()
    
    def delete_session(self, session_id: str):
        """Delete a conversation session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save_memory()
        # Also delete user profile for this session if exists
        if session_id in self.user_profiles:
            del self.user_profiles[session_id]
            self._save_user_profiles()
    
    def get_all_sessions(self) -> Dict[str, List[Dict]]:
        """Get all conversation sessions."""
        return self.sessions.copy()
    
    def clear_memory(self):
        """Clear all conversation memory."""
        self.sessions = {}
        self.user_profiles = {}
        self._save_memory()
        self._save_user_profiles()
    
    def update_user_profile(self, session_id: str, key: str, value: any):
        """Update user profile with specific information like rank, interests, etc."""
        if session_id not in self.user_profiles:
            self.user_profiles[session_id] = {}
        
        self.user_profiles[session_id][key] = value
        self._save_user_profiles()
    
    def get_user_profile(self, session_id: str) -> Dict:
        """Get user profile for a session."""
        return self.user_profiles.get(session_id, {})
    
    def get_user_preference(self, session_id: str, key: str, default=None):
        """Get specific user preference from profile."""
        return self.user_profiles.get(session_id, {}).get(key, default)