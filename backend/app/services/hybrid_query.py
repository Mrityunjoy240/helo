"""
Hybrid Query Processor
Combines LLM classification with structured KB lookup for optimal performance.
- Fast for structured queries (fees, courses, placements)
- Intelligent for conversational queries (recommendations, comparisons)
"""
import json
import time
import logging
import hashlib
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class SimpleCache:
    """Simple in-memory cache with TTL"""
    
    def __init__(self, ttl_seconds: int = 3600):
        self.cache: Dict[str, tuple] = {}  # {query_hash: (answer, timestamp)}
        self.ttl = ttl_seconds
    
    def _hash_query(self, query: str) -> str:
        normalized = query.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def get(self, query: str) -> Optional[str]:
        query_hash = self._hash_query(query)
        if query_hash in self.cache:
            answer, timestamp = self.cache[query_hash]
            if time.time() - timestamp < self.ttl:
                logger.info(f"Cache HIT: '{query[:50]}...'")
                return answer
            else:
                del self.cache[query_hash]
        return None
    
    def set(self, query: str, answer: str) -> None:
        query_hash = self._hash_query(query)
        self.cache[query_hash] = (answer, time.time())
        logger.info(f"Cache SET: '{query[:50]}...'")
    
    def clear(self) -> None:
        self.cache.clear()


class HybridQueryProcessor:
    """
    Hybrid approach combining:
    1. Cache for instant responses
    2. LLM for intent classification + entity extraction
    3. Structured KB lookup for factual queries
    4. LLM generation for conversational queries
    """
    
    SYSTEM_PROMPT = """You are an AI assistant for Dr. B.C. Roy Engineering College (BCREC), Durgapur.

Your task is to classify the user's query and extract relevant information.

CLASSIFICATION RULES:
1. STRUCTURED queries = factual lookups (fees, courses, placements, cutoff, contact, hostel, admission process, documents, scholarships, faculty, infrastructure)
2. CONVERSATIONAL queries = need reasoning (recommendations, comparisons, opinions, advice, "should I", "which is better", "tell me about")
3. FOLLOW_UP queries = refer to previous context (rank mentioned earlier, "it", "that branch", "what about")

Respond ONLY with valid JSON in this exact format:
{
    "intent": "structured|conversational|greeting|follow_up",
    "entities": {
        "rank": null or number,
        "course": null or string (CSE/IT/ECE/EE/ME/CE/AIML/DS/CSD/CY/MBA/MCA),
        "interest": null or string (ai/coding/electronics/mechanical/civil/management),
        "query_type": null or string (fee/cutoff/placement/hostel/admission/scholarship/document/faculty/infrastructure),
        "negation": false or true,
        "confidence": 0.0 to 1.0
    },
    "conversation_summary": "brief summary of what's being discussed (rank X, interested in Y, etc.) or null"
}

Examples:
- "What is the fee for CSE?" → {"intent": "structured", "entities": {"rank": null, "course": "CSE", "query_type": "fee", ...}, "conversation_summary": null}
- "My rank is 5000, suggest best branch" → {"intent": "conversational", "entities": {"rank": 5000, "course": null, "query_type": "recommendation", ...}, "conversation_summary": "User has rank 5000, seeking branch recommendation"}
- "What about placement?" (after discussing CSE) → {"intent": "follow_up", "entities": {"course": "CSE", "query_type": "placement", ...}, "conversation_summary": "Previously discussing CSE, now asking about placement"}
- "I hate coding" → {"intent": "conversational", "entities": {"negation": true, "interest": "non_coding", ...}, "conversation_summary": "User dislikes coding"}

IMPORTANT:
- Extract rank even from variations like "20k", "20000", "rank 500"
- Normalize course names to standard codes (CSE, IT, ECE, etc.)
- Mark negation if user says "hate", "don't want", "not interested"
- If previous context exists, note it in conversation_summary"""


class BCRECTool:
    """Unified BCREC Tool for answering all college-related queries."""
    
    def __init__(self, data_path: str = None):
        if data_path is None:
            import os
            module_dir = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.join(module_dir, "..", "..", "data", "knowledge_base", "combined_kb.json")
        self.data = self._load(data_path)
    
    def _load(self, path: str) -> Dict[str, Any]:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")
            return {}
    
    def get_fee(self, course: str = None) -> Dict[str, Any]:
        if not course:
            return {"success": True, "fees": self.data.get("fees_summary", {})}
        
        course_upper = course.upper()
        courses = self.data.get("courses", {}).get("btech", {})
        
        for code, info in courses.items():
            if code.upper() == course_upper or code.upper().replace("-", "") == course_upper:
                return {
                    "success": True,
                    "course": code,
                    "fees": info.get("fees", {}),
                    "total": f"Rs. {info.get('fees', {}).get('total', 0):,}"
                }
        
        return {"success": False, "error": f"Course {course} not found"}
    
    def get_placement(self, course: str = None) -> Dict[str, Any]:
        if course:
            course_upper = course.upper()
            courses = self.data.get("courses", {}).get("btech", {})
            
            for code, info in courses.items():
                if code.upper() == course_upper:
                    return {
                        "success": True,
                        "course": code,
                        "placement": info.get("placement", {})
                    }
        
        return {
            "success": True,
            "overall": self.data.get("placements", {}).get("overall_rate_2025", "N/A"),
            "highest": self.data.get("placements", {}).get("highest_package", {}),
            "companies": self.data.get("placements", {}).get("top_companies_2026", [])
        }
    
    def get_cutoff(self, course: str = None) -> Dict[str, Any]:
        if course:
            course_upper = course.upper()
            courses = self.data.get("courses", {}).get("btech", {})
            
            for code, info in courses.items():
                if code.upper() == course_upper:
                    return {
                        "success": True,
                        "course": code,
                        "cutoff": info.get("cutoff", {})
                    }
        
        cutoffs = {}
        courses = self.data.get("courses", {}).get("btech", {})
        for code, info in courses.items():
            if info.get("cutoff"):
                cutoffs[code] = info.get("cutoff")
        return {"success": True, "cutoffs": cutoffs}
    
    def get_course(self, course: str = None) -> Dict[str, Any]:
        if not course:
            courses_list = []
            for code, info in self.data.get("courses", {}).get("btech", {}).items():
                courses_list.append({
                    "code": code,
                    "name": info.get("full_name", ""),
                    "intake": info.get("intake", "N/A")
                })
            return {"success": True, "courses": courses_list}
        
        course_upper = course.upper()
        courses = self.data.get("courses", {}).get("btech", {})
        
        for code, info in courses.items():
            if code.upper() == course_upper:
                return {
                    "success": True,
                    "course": code,
                    "name": info.get("full_name", ""),
                    "intake": info.get("intake", "N/A"),
                    "fees": info.get("fees", {}),
                    "placement": info.get("placement", {}),
                    "cutoff": info.get("cutoff", {})
                }
        
        return {"success": False, "error": f"Course {course} not found"}
    
    def get_hostel(self) -> Dict[str, Any]:
        return {"success": True, "hostel": self.data.get("hostel", {})}
    
    def get_admission(self) -> Dict[str, Any]:
        return {"success": True, "admission": self.data.get("admission", {})}
    
    def get_documents(self) -> Dict[str, Any]:
        return {"success": True, "documents": self.data.get("admission_documents", {})}
    
    def get_scholarship(self) -> Dict[str, Any]:
        return {"success": True, "scholarships": self.data.get("scholarships", {})}
    
    def get_infrastructure(self) -> Dict[str, Any]:
        return {
            "success": True,
            "infrastructure": self.data.get("infrastructure", {}),
            "student_life": self.data.get("student_life", {})
        }
    
    def get_overview(self) -> Dict[str, Any]:
        college = self.data.get("college", {})
        return {
            "success": True,
            "name": college.get("name", "BCREC"),
            "established": college.get("established", ""),
            "type": college.get("type", ""),
            "naac": college.get("naac", {}),
            "affiliation": college.get("affiliation", ""),
            "contact": {
                "phone": college.get("phones", ["0343-2501353"])[0],
                "email": college.get("email", "info@bcrec.ac.in"),
                "website": college.get("website", "www.bcrec.ac.in")
            }
        }
    
    def get_all(self) -> Dict[str, Any]:
        return {"success": True, "data": self.data}


# Global instances
_cache = SimpleCache(ttl_seconds=3600)
_bcrec_tool = None


def get_bcrec_tool() -> BCRECTool:
    global _bcrec_tool
    if _bcrec_tool is None:
        _bcrec_tool = BCRECTool()
    return _bcrec_tool


def get_cache() -> SimpleCache:
    return _cache
