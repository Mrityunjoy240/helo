"""
Main Hybrid Query Service
Ties together cache, LLM classification, KB lookup, and response generation.
"""
import json
import logging
import re
import time
from typing import Dict, Any, Optional, List

from app.services.llm import OllamaLLM
from app.services.hybrid_query import get_bcrec_tool, get_cache, SimpleCache, HybridQueryProcessor

logger = logging.getLogger(__name__)


class HybridQueryService:
    """
    Main service for processing queries using hybrid approach:
    1. Check cache
    2. Classify intent via LLM
    3. Route to appropriate handler
    4. Generate response
    """
    
    def __init__(self):
        self.llm = OllamaLLM(model="qwen3.5:latest")
        self.tool = get_bcrec_tool()
        self.cache = get_cache()
        
        # Pre-defined responses for common queries (instant)
        self._init_quick_responses()
    
    def _init_quick_responses(self):
        """Fast responses for very common queries"""
        self.quick_responses = {
            "hello": "Hello! How can I help you today? I can answer questions about BCREC admissions, fees, placements, hostel, and more.",
            "hi": "Hi there! How can I assist you with BCREC today?",
            "hey": "Hey! What would you like to know about Dr. B.C. Roy Engineering College?",
            "namaste": "Namaste! Main aapki kaise madad kar sakta hoon? (How can I help you?)",
        }
    
    def _is_greeting(self, query: str) -> bool:
        greetings = ["hello", "hi", "hey", "namaste", "good morning", "good afternoon", "good evening"]
        q = query.lower().strip()
        return q in greetings or q.startswith("hello ") or q.startswith("hi ")
    
    async def _classify_intent(self, query: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        Use LLM to classify intent and extract entities.
        """
        history_context = ""
        if conversation_history:
            recent = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
            history_context = "\n\nConversation history:\n"
            for msg in recent:
                role = "User" if msg.get("role") == "user" else "Assistant"
                history_context += f"- {role}: {msg.get('content', '')[:100]}\n"
        
        prompt = f"""Classify this query and extract entities.

Query: "{query}"
{history_context}

Respond with valid JSON only:"""

        try:
            response = await self.llm.chat_complete(
                messages=[
                    {"role": "system", "content": HybridQueryProcessor.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,
                max_tokens=500
            )
            
            # Parse JSON response
            try:
                result = json.loads(response.strip())
                return result
            except json.JSONDecodeError:
                # Try to extract JSON from response
                json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                    return result
                else:
                    logger.warning(f"Failed to parse LLM response: {response[:100]}")
                    return {"intent": "conversational", "entities": {}, "conversation_summary": None}
        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            return {"intent": "conversational", "entities": {}, "conversation_summary": None}
    
    async def _generate_response(
        self, 
        query: str, 
        intent: str, 
        entities: Dict[str, Any],
        conversation_history: List[Dict] = None
    ) -> str:
        """
        Generate response based on intent and entities.
        """
        kb = self.tool.data
        
        # Build context from conversation
        context = ""
        if conversation_history:
            recent = conversation_history[-3:]
            context = "Previous conversation:\n"
            for msg in recent:
                role = "User" if msg.get("role") == "user" else "Assistant"
                context += f"- {role}: {msg.get('content', '')}\n"
        
        # Build knowledge context
        knowledge_context = self._build_knowledge_context(entities)
        
        prompt = f"""{context}

Knowledge Base:
{knowledge_context}

User Query: {query}

Instructions:
1. Answer ONLY using the knowledge base above
2. Keep responses short and conversational (2-3 sentences max)
3. If the exact information is not available, suggest contacting the college: 0343-2501353
4. Use natural language, no bullet points or markdown
5. If user asks for branch recommendation with rank, suggest based on cutoff data
6. Handle follow-up questions using context
7. If user says "I hate coding" or similar, recommend non-coding branches (ME, CE, ECE)

Answer:"""

        try:
            response = await self.llm.chat_complete(
                messages=[
                    {"role": "system", "content": "You are a helpful college information assistant. Answer questions about Dr. B.C. Roy Engineering College based only on the provided knowledge base."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            return response.strip()
        except Exception as e:
            logger.error(f"LLM response generation error: {e}")
            return "I apologize, I'm having trouble processing your request. Please contact the college directly at 0343-2501353."
    
    def _build_knowledge_context(self, entities: Dict[str, Any]) -> str:
        """Build relevant knowledge context based on entities"""
        kb = self.tool.data
        context_parts = []
        
        # College overview
        college = kb.get("college", {})
        context_parts.append(f"""College Info:
- Name: {college.get('name', 'Dr. B.C. Roy Engineering College')}
- Location: Durgapur, West Bengal
- Established: {college.get('established', '2000')}
- NAAC Grade: {college.get('naac', {}).get('grade', 'B+')}
- NBA Accredited: CSE, IT, ECE, EE, ME
- Affiliation: MAKAUT""")
        
        # Courses
        courses = kb.get("courses", {}).get("btech", {})
        course_lines = ["Courses & Fees:"]
        for code, info in courses.items():
            fees = info.get("fees", {}).get("total", 0)
            placement = info.get("placement", {}).get("2024-25", "N/A")
            cutoff = info.get("cutoff", {}).get("2025", "N/A")
            course_lines.append(f"- {code} ({info.get('full_name', '')}): Fee Rs.{fees:,}, Placement {placement}, Cutoff {cutoff}")
        context_parts.append("\n".join(course_lines))
        
        # Placements
        placements = kb.get("placements", {})
        context_parts.append(f"""Placement Info:
- Overall: {placements.get('overall_rate_2025', '80%+')}
- Highest Package: Rs. {placements.get('highest_package', {}).get('amount', 30)} LPA ({placements.get('highest_package', {}).get('company', 'Cyberwissen')})
- Top Recruiters: TCS, Wipro, Cognizant, Celebal Technology""")
        
        # Admission
        admission = kb.get("admission", {})
        context_parts.append(f"""Admission:
- Eligibility: 10+2 with PCM, 50% marks
- Entrance: WBJEE (80%), JEE Main (10%), Management (10%)
- Counseling: WBJEEB at wbjeeb.nic.in""")
        
        # Scholarships
        scholarships = kb.get("scholarships", {})
        context_parts.append(f"""Scholarships:
- TFW (5% seats): Full tuition waiver
- SVMCM: Rs. 60,000/year for WB residents
- OASIS/Aikyashree: For SC/ST/OBC/Minority""")
        
        # Hostel
        hostel = kb.get("hostel", {})
        context_parts.append(f"""Hostel:
- Capacity: {hostel.get('total_capacity', 1500)} students
- Mess: Rs. 5000/month, 4 meals/day
- Room types: Single (Rs.30k/sem), Double/Triple (Rs.10k/sem)""")
        
        return "\n\n".join(context_parts)
    
    def _format_structured_response(self, query_type: str, entities: Dict[str, Any]) -> str:
        """Format response for structured (factual) queries"""
        course = entities.get("course", "").upper() if entities.get("course") else None
        kb = self.tool.data
        
        if query_type == "fee" or query_type == "fees":
            if course:
                result = self.tool.get_fee(course)
                if result.get("success"):
                    fees = result.get("fees", {})
                    return f"The total fee for {course} is Rs. {fees.get('total', 0):,}. First semester admission fee is Rs. {fees.get('admission', 0):,}."
            return f"B.Tech fees range from Rs. 4,37,700 to Rs. 5,98,300 depending on branch. Contact BCREC: 0343-2501353."
        
        if query_type == "placement":
            if course:
                result = self.tool.get_placement(course)
                if result.get("success"):
                    pl = result.get("placement", {})
                    return f"{course} placement rate: {pl.get('2024-25', 'N/A')}. Highest package: Rs. {pl.get('max_lpa', 'N/A')} LPA, Average: Rs. {pl.get('avg_lpa', 'N/A')} LPA."
            result = self.tool.get_placement()
            return f"Overall placement rate: {result.get('overall', '80%+')}. Highest package: Rs. {result.get('highest', {}).get('amount', 30)} LPA from {result.get('highest', {}).get('company', 'Cyberwissen')}."
        
        if query_type == "cutoff":
            if course:
                result = self.tool.get_cutoff(course)
                if result.get("success"):
                    cf = result.get("cutoff", {})
                    return f"{course} WBJEE 2025 cutoff: {cf.get('2025', 'N/A')}. Estimated 2026: {cf.get('2026_est', 'N/A')}."
            return "CSE cutoff: ~68K, ECE: ~93K, IT: ~97K, EE: ~93K. Contact BCREC for exact figures."
        
        if query_type == "admission":
            admission = kb.get("admission", {})
            return f"Admission through WBJEE counseling (wbjeeb.nic.in). Eligibility: 10+2 PCM with 50%. Seats: WBJEE 80%, JEE Main 10%, Management 10%."
        
        if query_type == "scholarship":
            scholarships = kb.get("scholarships", {})
            schemes = scholarships.get("schemes", {})
            parts = ["Available scholarships:"]
            if schemes.get("tfw"):
                parts.append(f"TFW: Full tuition waiver (5% seats)")
            if schemes.get("svmcm"):
                parts.append(f"SVMCM: Rs. 60,000/year for WB residents")
            return ". ".join(parts) + ". Contact BCREC: 0343-2501353."
        
        if query_type == "document":
            docs = kb.get("admission_documents", {})
            doc_list = []
            for cat, items in docs.items():
                if isinstance(items, list) and items:
                    doc_list.extend(items[:3])
            return f"Required documents: {', '.join(doc_list[:5])}. Contact BCREC: 0343-2501353."
        
        if query_type == "hostel":
            hostel = kb.get("hostel", {})
            return f"Hostel available for {hostel.get('total_capacity', 1500)} students. Mess: Rs. {hostel.get('mess', {}).get('monthly_charge', 5000)}/month. Rooms: Rs. 10,000-30,000/semester."
        
        if query_type == "faculty":
            academics = kb.get("academics", {})
            faculty = academics.get("faculty", {})
            return f"BCREC has {faculty.get('total', '150+')} faculty members. Student-teacher ratio: {academics.get('student_teacher_ratio', '15:1 to 20:1')}."
        
        if query_type == "infrastructure":
            infra = kb.get("infrastructure", {})
            return f"Campus has WiFi ({infra.get('wifi', {}).get('speed', '28 Mbps')}), Library ({infra.get('library', {}).get('books', '80,000+')} books), Well-equipped labs. AICTE IDEA Lab ranked #1 in India."
        
        return "Please contact BCREC at 0343-2501353 for more information."
    
    async def process_query(
        self, 
        query: str, 
        conversation_id: str = None,
        conversation_history: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for processing queries.
        
        Returns:
            Dict with: answer, source, intent, confidence
        """
        start_time = time.time()
        query_lower = query.lower().strip()
        
        # 1. Check for greeting
        if self._is_greeting(query):
            return {
                "answer": self.quick_responses.get(query_lower, self.quick_responses.get("hello")),
                "source": "greeting",
                "intent": "greeting",
                "confidence": 1.0,
                "processing_time": time.time() - start_time
            }
        
        # 2. Check cache
        cached = self.cache.get(query)
        if cached:
            return {
                "answer": cached,
                "source": "cache",
                "intent": "cached",
                "confidence": 1.0,
                "processing_time": time.time() - start_time
            }
        
        # 3. Classify intent
        classification = await self._classify_intent(query, conversation_history)
        intent = classification.get("intent", "conversational")
        entities = classification.get("entities", {})
        conversation_summary = classification.get("conversation_summary")
        
        logger.info(f"Classified: intent={intent}, entities={entities}")
        
        # 4. Route based on intent
        answer = None
        
        if intent == "structured":
            query_type = entities.get("query_type")
            if query_type:
                answer = self._format_structured_response(query_type, entities)
        
        if not answer:
            # 5. Generate response via LLM
            answer = await self._generate_response(
                query, 
                intent, 
                entities, 
                conversation_history
            )
        
        # 6. Cache the response
        self.cache.set(query, answer)
        
        return {
            "answer": answer,
            "source": "hybrid",
            "intent": intent,
            "confidence": entities.get("confidence", 0.8),
            "conversation_summary": conversation_summary,
            "processing_time": time.time() - start_time
        }


# Global instance
_hybrid_service = None


def get_hybrid_service() -> HybridQueryService:
    global _hybrid_service
    if _hybrid_service is None:
        _hybrid_service = HybridQueryService()
    return _hybrid_service
