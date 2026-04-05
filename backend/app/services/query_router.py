from typing import Dict, List, Tuple, Optional
import re
import logging

logger = logging.getLogger(__name__)

class QueryRouter:
    """
    Keyword-based query classifier for BCREC chatbot.
    Routes queries to appropriate handler:
    - Simple structured queries → Fast lookup
    - Complex queries → RAG + LLM
    """
    
    # Intent patterns with keywords and weights
    INTENT_PATTERNS = {
        "fee": {
            "keywords": ["fee", "fees", "cost", "price", "payment", "pay", "charge", "amount", "rupee", "lakh", "semester"],
            "weight": 1.0,
            "topics": ["fees", "btech_fees", "mba_fees", "mca_fees", "hostel_fees", "scholarship"]
        },
        "contact": {
            "keywords": ["phone", "call", "contact", "number", "email", "address", "office", "timing", "hours", "locate", "reach"],
            "weight": 1.0,
            "topics": ["main_contact", "admission_contact", "placement_contact", "department_contact", "hod"]
        },
        "admission": {
            "keywords": ["admission", "admissions", "apply", "eligibility", "eligible", "criteria", "require", "required", "document", "documents", "process", "counseling", "wbjee", "jee", "entrance", "cutoff", "rank", "seat", "seats", "qualify", "qualification"],
            "weight": 1.0,
            "topics": ["eligibility", "process", "documents", "dates", "entrance_exams", "seat_distribution"]
        },
        "course": {
            "keywords": ["course", "courses", "branch", "branches", "department", "departments", "program", "programs", "stream", "streams", "specialization", "intake", "seat", "seats", "available"],
            "weight": 0.9,
            "topics": ["all_courses", "cse", "aiml", "it", "ds", "csd", "ece", "ee", "me", "ce", "mba", "mca", "mtech", "btech"]
        },
        "placement": {
            "keywords": ["placement", "placements", "job", "jobs", "package", "packages", "salary", "salaries", "recruit", "recruiter", "recruiters", "company", "companies", "placed", "hiring", "interview", "campus"],
            "weight": 1.0,
            "topics": ["stats", "recruiters", "highest", "average", "percentage", "rate"]
        },
        "facility": {
            "keywords": ["facility", "facilities", "infrastructure", "library", "lab", "labs", "laboratory", "laboratories", "hostel", "sports", "club", "clubs", "event", "events", "fest", "canteen", "wifi", "computer"],
            "weight": 0.9,
            "topics": ["infrastructure", "hostel", "sports", "clubs", "events", "library", "labs"]
        },
        "scholarship": {
            "keywords": ["scholarship", "scholarships", "waiver", "financial", "aid", "merit", "concession", "free", "tfw", "economically"],
            "weight": 1.0,
            "topics": ["tfw", "govt_schemes", "merit_based", "scholarship_types"]
        },
        "curriculum": {
            "keywords": ["syllabus", "curriculum", "subject", "subjects", "coursework", "learn", "teaching", "subjects", "paper", "papers"],
            "weight": 0.8,
            "topics": ["year1", "year2", "year3", "year4", "syllabus"]
        },
        "career": {
            "keywords": ["career", "careers", "job", "jobs", "future", "prospect", "prospects", "opportunity", "opportunities", "growth", "scope"],
            "weight": 0.8,
            "topics": ["paths", "options", "government", "psu", "entrepreneur"]
        },
        "general": {
            "keywords": ["college", "about", "history", "established", "accreditation", "accredited", "ranking", "ranked", "location", "campus", "naac", "nba", "aicte", "makaut", "autonomous"],
            "weight": 0.9,
            "topics": ["overview", "location", "accreditation", "ranking", "affiliation"]
        }
    }
    
    # Simple query patterns that should use structured lookup
    SIMPLE_PATTERNS = [
        r"(?i)^(what is|what are|tell me|give me|show me)?\s*(the )?(btech|mba|mca|mtech)?\s*(fee|fees|cost|price)",
        r"(?i)^(what is|what are|tell me|give me|show me)?\s*(the )?(phone number|telephone|contact number|email|address)",
        r"(?i)^(what is|what are|tell me|give me|show me)?\s*(the )?(eligibility|criteria|required documents)",
        r"(?i)^(what is|what are|tell me|give me|show me)?\s*(the )?(placement rate|highest package|average salary)",
        r"(?i)^(what is|what are|tell me|give me|show me)?\s*(the )?(btech|mba|mca|mtech)?\s*(cutoff|rank)",
        r"(?i)^(how (to|do i|can i|much))",
        r"(?i)^(is there|are there|do you have|does bcrec have)",
        r"(?i)^(can i|can we|should i|which|i have|i want|i need)",
    ]
    
    # Complex query patterns that should use RAG
    COMPLEX_PATTERNS = [
        r"(?i)(which is better|compare|comparison|vs|versus|difference between)",
        r"(?i)(should i choose|which one|what do you recommend|advice|guidance)",
        r"(?i)(tell me about|could you explain|what does|how is)",
        r"(?i)(why is|why should|why do)",
        r"(?i)(is it worth|is it good|is it better)",
    ]
    
    def __init__(self):
        self._build_keyword_index()
    
    def _build_keyword_index(self) -> None:
        """Build inverted index for fast keyword matching"""
        self.keyword_to_intent: Dict[str, List[str]] = {}
        
        for intent, pattern in self.INTENT_PATTERNS.items():
            for keyword in pattern["keywords"]:
                if keyword not in self.keyword_to_intent:
                    self.keyword_to_intent[keyword] = []
                self.keyword_to_intent[keyword].append(intent)
    
    def classify(self, query: str) -> Tuple[str, float, str]:
        """
        Classify query and return intent, confidence, and recommended handler.
        
        Returns:
            Tuple of (intent, confidence, handler_type)
            - intent: The detected intent (e.g., "fee", "placement")
            - confidence: 0.0 to 1.0 confidence score
            - handler_type: "structured" or "rag"
        """
        query_lower = query.lower().strip()
        query_words = set(re.findall(r'\b\w+\b', query_lower))
        
        # Check for complex patterns first
        for pattern in self.COMPLEX_PATTERNS:
            if re.search(pattern, query_lower):
                return ("complex", 0.9, "rag")
        
        # Score each intent based on keyword matches
        intent_scores: Dict[str, float] = {}
        matched_topics: Dict[str, List[str]] = {}
        
        for word in query_words:
            if word in self.keyword_to_intent:
                for intent in self.keyword_to_intent[word]:
                    if intent not in intent_scores:
                        intent_scores[intent] = 0.0
                        matched_topics[intent] = []
                    
                    # Weight based on pattern definition
                    weight = self.INTENT_PATTERNS[intent]["weight"]
                    intent_scores[intent] += weight
                    matched_topics[intent].append(word)
        
        # Check for simple patterns
        for pattern in self.SIMPLE_PATTERNS:
            if re.search(pattern, query_lower):
                if intent_scores:
                    best_intent = max(intent_scores, key=intent_scores.get)
                    confidence = min(intent_scores[best_intent] / len(query_words), 1.0)
                    return (best_intent, confidence, "structured")
                else:
                    return ("general", 0.5, "structured")
        
        # No patterns matched - determine based on scores
        if not intent_scores:
            return ("general", 0.3, "rag")
        
        # Find best matching intent
        best_intent = max(intent_scores, key=intent_scores.get)
        best_score = intent_scores[best_intent]
        
        # Calculate confidence (normalize by query length and max possible score)
        max_possible_score = len(query_words)
        confidence = min(best_score / max_possible_score, 1.0)
        
        # Determine handler type based on confidence and intent
        if confidence >= 0.15:
            handler = "structured"
        elif confidence >= 0.1:
            handler = "structured"  # Try structured first, fallback to RAG
        else:
            handler = "rag"
        
        # Some intents are always better with RAG
        if best_intent in ["career", "curriculum"]:
            if confidence < 0.6:
                handler = "rag"
        
        logger.info(f"Query: '{query}' -> Intent: {best_intent}, Confidence: {confidence:.2f}, Handler: {handler}")
        
        return (best_intent, confidence, handler)
    
    def get_topics_for_intent(self, intent: str) -> List[str]:
        """Get relevant topics for a given intent"""
        if intent in self.INTENT_PATTERNS:
            return self.INTENT_PATTERNS[intent]["topics"]
        return []
    
    def is_simple_query(self, query: str) -> bool:
        """Quick check if query is simple enough for structured lookup"""
        intent, confidence, handler = self.classify(query)
        return handler == "structured" and confidence >= 0.3


# Singleton instance
router = QueryRouter()


def classify_query(query: str) -> Tuple[str, float, str]:
    """
    Convenience function to classify a query.
    
    Args:
        query: User's question
        
    Returns:
        Tuple of (intent, confidence, handler_type)
    """
    return router.classify(query)


def is_simple_query(query: str) -> bool:
    """Quick check if query should use structured lookup"""
    return router.is_simple_query(query)
