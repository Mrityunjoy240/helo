import json
import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from app.services.llm import OllamaLLM

logger = logging.getLogger(__name__)


class IntentResult(BaseModel):
    """Structured intent classification result"""
    intent: str
    confidence: float
    source: str  # "structured", "rag", "tool"
    entities: Dict[str, Any] = {}
    language: str = "en"


class IntentRouter:
    """
    LLM-based intent classifier using structured output.
    Classifies user queries and routes to appropriate handler.
    """

    SYSTEM_PROMPT = """You are an intelligent college information assistant classifier.
Classify the user's query into one of these intents:

1. fee - Questions about fees, costs, payments
2. admission - Questions about admission process, eligibility, documents
3. course - Questions about courses, branches, departments, programs
4. contact - Questions about phone numbers, addresses, offices
5. placement - Questions about placements, jobs, packages, recruiters
6. facility - Questions about hostel, library, labs, sports
7. scholarship - Questions about scholarships, financial aid
8. general - General questions about the college
9. greeting - Greetings, small talk
10. comparison - Questions comparing options or asking for advice

Respond ONLY with valid JSON matching this schema:
{
    "intent": "string",
    "confidence": 0.0-1.0,
    "source": "structured|rag|tool",
    "entities": {"course": "...", "department": "..."},
    "language": "en|hi|bn"
}

Rules:
- Fee, contact, admission eligibility, course details -> source: "structured"
- Comparisons, advice, open questions -> source: "rag"
- Specific data lookups -> source: "tool"
- Default to "en" unless clearly Bengali or Hindi"""

    GREETING_PATTERNS = [
        "hello", "hi", "hey", "good morning", "good afternoon", 
        "good evening", "how are you", "namaste", "namoshkar"
    ]

    def __init__(self, llm: Optional[OllamaLLM] = None):
        self.llm = llm or OllamaLLM()

    async def classify(self, query: str) -> IntentResult:
        """Classify user query and return structured result"""
        query_lower = query.lower().strip()

        # Check for greetings FIRST (only if query IS a greeting, not contains greeting words)
        if self._is_greeting(query_lower):
            # Only treat as greeting if it's purely a greeting
            words = query_lower.split()
            greeting_words = set(self.GREETING_PATTERNS)
            if set(words).intersection(greeting_words) and len(words) <= 5:
                return IntentResult(
                    intent="greeting",
                    confidence=1.0,
                    source="structured",
                    entities={},
                    language=self._detect_language(query)
                )

        # Check for structured data queries (keyword-based fast path)
        structured_intent = self._keyword_classify(query_lower)
        if structured_intent:
            return structured_intent

        # Use LLM for complex classification
        return await self._llm_classify(query)

    def _is_greeting(self, query: str) -> bool:
        """Check if query is a greeting"""
        return any(greet in query for greet in self.GREETING_PATTERNS)

    def _detect_language(self, query: str) -> str:
        """Detect query language"""
        bengali_chars = set("অ আ ই ঈ উ ঊ ঋ এ ঐ ও ঔ ক খ গ ঘ ঙ চ ছ জ ঝ ঞ ট ঠ ড ঢ ণ ত থ দ ধ ন প ফ ব ভ ম য র ল শ ষ স হ ড় ঢ় য়")
        hindi_chars = set("अ आ इ ई उ ऊ ऋ ए ऐ ओ औ क ख ग घ ङ च छ ज झ ञ ट ठ ड ढ ण त थ द ध न प फ ब भ म य र ल व श ष स ह")

        query_chars = set(query)
        if query_chars & bengali_chars:
            return "bn"
        if query_chars & hindi_chars:
            return "hi"
        return "en"

    def _detect_detail_level(self, query: str) -> str:
        """Detect how much detail the user wants"""
        query_lower = query.lower()
        
        # Contact only keywords - HIGHEST priority
        contact_keywords = ["email", "phone", "mobile", "number", "contact", "reach", "call", "mail"]
        if any(kw in query_lower for kw in contact_keywords):
            return "contact"
        
        # Full info keywords
        full_info_keywords = ["about", "details", "info", "information", "tell me about", "what is", "describe", "everything", "complete", "full info"]
        if any(kw in query_lower for kw in full_info_keywords):
            return "full"
        
        # Just name keywords
        just_name_keywords = ["who is", "who's", "name of", "which is"]
        if any(kw in query_lower for kw in just_name_keywords):
            return "name"
        
        # Simple questions starting with who/what
        words = query_lower.split()[:4]
        if words and words[0] in ["who", "what", "which"] and len(query_lower) < 50:
            return "name"
        
        return "name"  # Default to just name

    def _keyword_classify(self, query: str) -> Optional[IntentResult]:
        """Fast keyword-based classification for simple queries"""
        fee_keywords = ["fee", "fees", "cost", "price", "payment", "rupee", "lakh"]
        contact_keywords = ["phone", "contact", "number", "email", "address", "call"]
        admission_keywords = ["admission", "apply", "eligible", "eligibility", "document", "process"]
        course_keywords = ["course", "branch", "department", "program", "seat", "intake", "about", "info", "details"]
        placement_keywords = ["placement", "job", "package", "salary", "recruit", "company"]
        cutoff_keywords = ["cutoff", "wbjee", "closing"]
        hostel_keywords = ["hostel", "room", "accommodation", "dormitory", "mess"]
        hod_keywords = ["hod", "head of department", "faculty", "professor", "faculty"]
        principal_keywords = ["principal", "director", "mam", "sir"]
        
        eligibility_keywords = ["eligible", "eligibility", "can i get", "will i get", "my rank", "i have rank", "rank in", "am i eligible", "which branch am i", "can i get admission", "get admission", "take admission", "join college"]
        recommendation_keywords = ["which branch", "which course", "should i take", "recommend", "suggest", "better branch", "best branch", "which one should", "branch should i", "branch is better", "branch is best", "choose", "career", "future"]
        salary_keywords = ["salary", "package", "highest salary", "highest package", "best salary", "money", "earn", "income", "average salary", "ctc"]
        comparison_keywords = ["compare", "vs", "versus", "difference between", "which is better", "comparision"]
        easiest_keywords = ["easiest", "easy", "simple", "light", "less workload", "less difficult"]
        general_info_keywords = ["everything", "all about", "complete info", "overview", "general info", "about college", "tell me about college", "college details"]
        
        document_keywords = ["document", "documents", "required docs", "what documents", "need for admission", "papers needed", "documents required"]
        refund_keywords = ["refund", "fee refund", "cancel admission", "money back", "if i cancel", "withdraw admission"]
        installment_keywords = ["installment", "monthly payment", "pay in parts", "pay in installment", "easy payment", " EMI"]
        scholarship_eligibility_keywords = ["who get scholarship", "scholarship eligibility", "can i get scholarship", "eligible for scholarship", "scholarship criteria"]
        food_quality_keywords = ["food quality", "mess food", "canteen food", "food", "taste", "meal quality"]
        ragging_keywords = ["ragging", "rag", "hazing", "freshers pressure", "senior junior issue"]
        placement_training_keywords = ["placement training", "mock interview", "aptitude training", "soft skills", "interview preparation", "resume building"]
        faculty_keywords = ["faculty", "professor", "teacher quality", "teaching", "faculty experience", "lecturer"]
        exam_pattern_keywords = ["exam pattern", "how exams", "assessment", "internal marks", "continuous assessment", "mid sem"]
        branch_change_keywords = ["change branch", "switch branch", "branch transfer", "change stream", "shift branch"]
        infrastructure_keywords = ["infrastructure", "campus", "building", "campus life", "premises"]
        student_life_keywords = ["activity", "club", "event", "fest", "cultural", "sports", "extracurricular", "nss", "hackathon"]
        
        lang = self._detect_language(query)
        
        # Check for document queries
        for kw in document_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "documents"
                return IntentResult(
                    intent="admission",
                    confidence=0.9,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        # Check for refund queries
        for kw in refund_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "refund"
                return IntentResult(
                    intent="fee",
                    confidence=0.9,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        # Check for installment queries
        for kw in installment_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "installment"
                return IntentResult(
                    intent="fee",
                    confidence=0.9,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        # Check for scholarship eligibility queries
        for kw in scholarship_eligibility_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "scholarship_eligibility"
                return IntentResult(
                    intent="scholarship",
                    confidence=0.9,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        # Check for food quality queries
        for kw in food_quality_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "food"
                return IntentResult(
                    intent="hostel",
                    confidence=0.85,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        # Check for ragging queries
        for kw in ragging_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "ragging"
                return IntentResult(
                    intent="general",
                    confidence=0.95,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        # Check for placement training queries
        for kw in placement_training_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "placement_training"
                return IntentResult(
                    intent="placement",
                    confidence=0.9,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        # Check for faculty queries
        for kw in faculty_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "faculty"
                return IntentResult(
                    intent="general",
                    confidence=0.85,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        # Check for exam pattern queries
        for kw in exam_pattern_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "exam_pattern"
                return IntentResult(
                    intent="general",
                    confidence=0.9,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        # Check for branch change queries
        for kw in branch_change_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "branch_change"
                return IntentResult(
                    intent="admission",
                    confidence=0.9,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        # Check for infrastructure queries
        for kw in infrastructure_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "infrastructure"
                return IntentResult(
                    intent="facility",
                    confidence=0.85,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        # Check for student life queries
        for kw in student_life_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "student_life"
                return IntentResult(
                    intent="general",
                    confidence=0.85,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        # Check for general info queries
        for kw in general_info_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "general_info"
                return IntentResult(
                    intent="general",
                    confidence=0.9,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        # Check for rank-based queries first
        rank_patterns = ["rank", "i have", "my rank is", "got rank"]
        for kw in rank_patterns:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "eligibility"
                return IntentResult(
                    intent="eligibility",
                    confidence=0.95,
                    source="rag",
                    entities=entities,
                    language=lang
                )

        for kw in cutoff_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "cutoff"
                return IntentResult(
                    intent="cutoff",
                    confidence=0.95,
                    source="tool",
                    entities=entities,
                    language=lang
                )

        for kw in hostel_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "hostel"
                return IntentResult(
                    intent="facility",
                    confidence=0.9,
                    source="tool",
                    entities=entities,
                    language=lang
                )

        for kw in hod_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "hod"
                entities["detail_level"] = self._detect_detail_level(query)
                return IntentResult(
                    intent="hod",
                    confidence=0.9,
                    source="tool",
                    entities=entities,
                    language=lang
                )
        
        for kw in principal_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "principal"
                entities["detail_level"] = self._detect_detail_level(query)
                return IntentResult(
                    intent="principal",
                    confidence=0.9,
                    source="tool",
                    entities=entities,
                    language=lang
                )

        for kw in easiest_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "easiest"
                return IntentResult(
                    intent="recommendation",
                    confidence=0.9,
                    source="rag",
                    entities=entities,
                    language=lang
                )

        for kw in recommendation_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "recommendation"
                return IntentResult(
                    intent="recommendation",
                    confidence=0.9,
                    source="rag",
                    entities=entities,
                    language=lang
                )

        for kw in salary_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "salary"
                return IntentResult(
                    intent="placement",
                    confidence=0.9,
                    source="tool",
                    entities=entities,
                    language=lang
                )

        for kw in comparison_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "comparison"
                return IntentResult(
                    intent="recommendation",
                    confidence=0.85,
                    source="rag",
                    entities=entities,
                    language=lang
                )

        for kw in eligibility_keywords:
            if kw in query:
                entities = self._extract_entities(query)
                entities["intent_detail"] = "eligibility"
                return IntentResult(
                    intent="eligibility",
                    confidence=0.9,
                    source="rag",
                    entities=entities,
                    language=lang
                )

        for kw in fee_keywords:
            if kw in query:
                return IntentResult(
                    intent="fee",
                    confidence=0.9,
                    source="tool",
                    entities=self._extract_entities(query),
                    language=lang
                )

        for kw in contact_keywords:
            if kw in query:
                return IntentResult(
                    intent="contact",
                    confidence=0.9,
                    source="tool",
                    entities=self._extract_entities(query),
                    language=lang
                )

        for kw in admission_keywords:
            if kw in query:
                return IntentResult(
                    intent="admission",
                    confidence=0.9,
                    source="tool",
                    entities=self._extract_entities(query),
                    language=lang
                )

        for kw in course_keywords:
            if kw in query:
                return IntentResult(
                    intent="course",
                    confidence=0.85,
                    source="tool",
                    entities=self._extract_entities(query),
                    language=lang
                )

        for kw in placement_keywords:
            if kw in query:
                return IntentResult(
                    intent="placement",
                    confidence=0.9,
                    source="tool",
                    entities=self._extract_entities(query),
                    language=lang
                )

        return None

    def _extract_entities(self, query: str) -> Dict[str, Any]:
        """Extract entities from query"""
        entities = {}

        query_lower = query.lower()
        
        course_patterns = {
            "btech": ["btech", "b.tech", "b.e", "bachelor of technology"],
            "mba": ["mba", "master of business administration"],
            "mca": ["mca", "master of computer applications"],
            "mtech": ["mtech", "m.tech", "m.e", "master of technology"]
        }
        for course, patterns in course_patterns.items():
            if any(p in query_lower for p in patterns):
                entities["course"] = course
                break

        dept_patterns = {
            "cse": ["cse", "computer science", "computerscience"],
            "it": ["it", "information technology"],
            "ece": ["ece", "electronics", "electronics and communication"],
            "ee": ["ee", "electrical"],
            "me": ["me", "mechanical"],
            "ce": ["ce", "civil"],
            "aiml": ["aiml", "ai ml", "artificial intelligence", "machine learning"],
            "ds": ["ds", "data science", "datascience"],
            "csd": ["csd", "computer science and design"]
        }
        for dept, patterns in dept_patterns.items():
            if any(p in query_lower for p in patterns):
                entities["department"] = dept
                break

        if "cutoff" in query_lower:
            entities["intent_detail"] = "cutoff"
        if "hostel" in query_lower or "room" in query_lower:
            entities["intent_detail"] = "hostel"
        if "hod" in query_lower or "head of department" in query_lower:
            entities["intent_detail"] = "hod"

        return entities

    async def _llm_classify(self, query: str) -> IntentResult:
        """Use LLM for complex classification"""
        if not self.llm.is_available():
            logger.warning("LLM not available, using keyword fallback")
            return IntentResult(
                intent="general",
                confidence=0.3,
                source="rag",
                entities={},
                language=self._detect_language(query)
            )

        try:
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": query}
            ]

            response = await self.llm.chat_complete(messages, temperature=0.0, max_tokens=500)

            result = json.loads(response.strip())
            return IntentResult(
                intent=result.get("intent", "general"),
                confidence=result.get("confidence", 0.5),
                source=result.get("source", "rag"),
                entities=result.get("entities", {}),
                language=result.get("language", "en")
            )
        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            return IntentResult(
                intent="general",
                confidence=0.3,
                source="rag",
                entities={},
                language=self._detect_language(query)
            )


_global_router: Optional[IntentRouter] = None


def get_intent_router() -> IntentRouter:
    """Get or create global intent router"""
    global _global_router
    if _global_router is None:
        _global_router = IntentRouter()
    return _global_router
