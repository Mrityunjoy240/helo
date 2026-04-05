"""
Gemini LLM Service for BCREC Voice Agent Prototype

This module provides a pure LLM-based query service using Google Gemini API.
It injects the full knowledge base into the prompt and uses the LLM to handle
all query variations naturally.
"""
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-genai not installed. Gemini service will be unavailable.")

from app.config import settings


class GeminiService:
    """
    Pure LLM service using Google Gemini API.
    
    This service:
    1. Loads the full knowledge base
    2. Formats it into the system prompt
    3. Passes conversation history
    4. Uses Gemini to generate accurate responses
    """
    
    SYSTEM_PROMPT = """You are an AI assistant for Dr. B.C. Roy Engineering College (BCREC), Durgapur, West Bengal.

YOUR ROLE:
- Help students and parents with queries about the college
- Answer questions about admissions, fees, placements, hostel, courses, etc.
- Be helpful, accurate, and friendly
- Speak in a conversational tone

IMPORTANT RULES:
1. Answer ONLY using information from the provided knowledge base
2. If you don't know something, say "I don't have that information. Please contact the college directly at 0343-2501353."
3. Do NOT make up information or guess
4. Keep responses short and conversational (2-3 sentences max)
5. Use simple language - some users may not be familiar with technical terms
6. When giving numbers, use Indian format (e.g., "Rs. 5.98 lakhs" instead of "Rs. 598,000")
7. Handle mixed language queries (English + Hindi/Bengali) naturally
8. If user asks follow-up questions, use the conversation history for context

RESPONSE FORMAT:
- No bullet points or lists
- Natural paragraph responses
- Include contact info when relevant: 0343-2501353

EXAMPLE RESPONSES:
User: "What is the fee for CSE?"
Response: "The total fee for B.Tech in Computer Science and Engineering (CSE) is Rs. 5.98 lakhs for the entire 4-year course. The first semester admission fee is Rs. 97,125. You can contact the college at 0343-2501353 for more details."

User: "CSE ki placement kitni hai?"
Response: "CSE mein placement bahut acchi hai - 93% students place hote hain with highest package Rs. 30 lakhs per annum. TCS, Infosys, Wipro jaise companies aate hain. For more details, call 0343-2501353."

User: "I have 20k rank in WBJEE"
Response: "With 20,000 rank in WBJEE, you can get CSE, IT, or ECE in BCREC. CSE is the best option if you're interested in software and coding. Would you like to know more about placements or fees for these branches?"
"""
    
    def __init__(self):
        self.client = None
        self.model = settings.gemini_model if hasattr(settings, 'gemini_model') else "gemini-2.0-flash"
        self.temperature = settings.gemini_temperature if hasattr(settings, 'gemini_temperature') else 0.3
        self.max_tokens = settings.gemini_max_tokens if hasattr(settings, 'gemini_max_tokens') else 500
        self.knowledge_base = self._load_knowledge_base()
        
        if GEMINI_AVAILABLE and settings.gemini_api_key:
            try:
                self.client = genai.Client(api_key=settings.gemini_api_key)
                logger.info(f"Gemini client initialized with model: {self.model}")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.client = None
        else:
            logger.warning("Gemini API key not configured or library not installed")
    
    def _load_knowledge_base(self) -> str:
        """Load and format the knowledge base for the prompt"""
        try:
            import os
            kb_path = os.path.join(
                os.path.dirname(__file__),
                "..", "..", "data", "knowledge_base", "combined_kb.json"
            )
            kb_path = os.path.normpath(kb_path)
            
            with open(kb_path, 'r', encoding='utf-8') as f:
                kb_data = json.load(f)
            
            formatted_kb = self._format_knowledge_base(kb_data)
            return formatted_kb
        except Exception as e:
            logger.error(f"Failed to load knowledge base: {e}")
            return ""
    
    def _format_knowledge_base(self, kb_data: Dict[str, Any]) -> str:
        """Format knowledge base into readable text for the prompt"""
        lines = []
        
        # College Info
        if "college" in kb_data:
            college = kb_data["college"]
            lines.append("=== COLLEGE INFORMATION ===")
            lines.append(f"Name: {college.get('name', 'Dr. B.C. Roy Engineering College')}")
            lines.append(f"Location: {college.get('location', 'Durgapur, West Bengal')}")
            lines.append(f"Established: {college.get('established', '2000')}")
            if college.get('naac'):
                lines.append(f"NAAC Grade: {college.get('naac', {}).get('grade', 'B+')}")
            if college.get('contact'):
                contact = college.get('contact', {})
                lines.append(f"Phone: {contact.get('phones', ['0343-2501353'])[0]}")
                lines.append(f"Email: {contact.get('email', 'info@bcrec.ac.in')}")
                lines.append(f"Website: {contact.get('website', 'www.bcrec.ac.in')}")
            lines.append("")
        
        # Courses
        if "courses" in kb_data and "btech" in kb_data["courses"]:
            lines.append("=== B.TECH COURSES ===")
            for code, info in kb_data["courses"]["btech"].items():
                lines.append(f"\n{code} - {info.get('full_name', code)}:")
                lines.append(f"  Intake: {info.get('intake', 'N/A')} students")
                fees = info.get('fees', {})
                if fees:
                    lines.append(f"  Total Fee: Rs. {fees.get('total', 'N/A')}")
                cutoff = info.get('cutoff', {})
                if cutoff:
                    lines.append(f"  WBJEE 2025 Cutoff: {cutoff.get('2025', 'N/A')}")
                placement = info.get('placement', {})
                if placement:
                    lines.append(f"  Placement: {placement.get('2024-25', 'N/A')} ({placement.get('avg_lpa', '')} LPA avg)")
            lines.append("")
        
        # Placements
        if "placements" in kb_data:
            placements = kb_data["placements"]
            lines.append("=== PLACEMENT INFORMATION ===")
            lines.append(f"Overall Placement Rate: {placements.get('overall_rate_2025', '80%+')}")
            if placements.get('highest_package'):
                hp = placements['highest_package']
                if isinstance(hp, dict):
                    lines.append(f"Highest Package: Rs. {hp.get('amount', 30)} LPA ({hp.get('company', 'Cyberwissen')})")
                else:
                    lines.append(f"Highest Package: {hp}")
            if placements.get('top_companies_2026'):
                companies = placements['top_companies_2026']
                if isinstance(companies, list) and len(companies) > 0:
                    lines.append("Top Recruiters:")
                    for c in companies[:5]:
                        if isinstance(c, dict):
                            lines.append(f"  - {c.get('company', '')} ({c.get('package', '')})")
            lines.append("")
        
        # Fees Summary
        if "fees_summary" in kb_data:
            fees = kb_data["fees_summary"]
            lines.append("=== FEE STRUCTURE ===")
            if "semester_wise" in fees:
                sw = fees["semester_wise"]
                lines.append(f"1st Semester: Rs. {sw.get('first', 97525):,}")
                lines.append(f"Semester 2-7: Rs. {sw.get('semesters_2_to_7', '72,425-74,425')}/sem")
                lines.append(f"8th Semester: Rs. {sw.get('eighth', 73425):,}")
                lines.append(f"Total B.Tech: {sw.get('total_description', '~Rs. 6.08 Lakhs')}")
            else:
                for branch, data in fees.items():
                    if isinstance(data, dict):
                        lines.append(f"{branch}: Rs. {data.get('total', 'N/A')}")
            lines.append("")
        
        # Admission
        if "admission" in kb_data:
            adm = kb_data["admission"]
            lines.append("=== ADMISSION INFORMATION ===")
            if adm.get('eligibility'):
                elig = adm['eligibility']
                if isinstance(elig, dict) and 'btech' in elig:
                    lines.append(f"Eligibility: {elig['btech']}")
            if adm.get('counseling'):
                lines.append(f"Counseling: {adm['counseling']}")
            if adm.get('seat_distribution'):
                lines.append(f"Seat Distribution: {adm['seat_distribution']}")
            lines.append("")
        
        # Scholarships
        if "scholarships" in kb_data:
            sch = kb_data["scholarships"]
            lines.append("=== SCHOLARSHIPS ===")
            if sch.get('schemes'):
                for scheme_id, scheme in sch['schemes'].items():
                    if isinstance(scheme, dict):
                        lines.append(f"- {scheme.get('name', scheme_id)}: {scheme.get('benefit', scheme.get('amount', ''))}")
            lines.append("")
        
        # Hostel
        if "hostel" in kb_data:
            hostel = kb_data["hostel"]
            lines.append("=== HOSTEL FACILITIES ===")
            lines.append(f"Capacity: {hostel.get('total_capacity', 1500)} students")
            if hostel.get('mess'):
                mess = hostel['mess']
                lines.append(f"Mess: Rs. {mess.get('monthly_charge', 5000)}/month")
                lines.append(f"Meals: {mess.get('meals_per_day', 4)} times/day")
            if hostel.get('room_types'):
                lines.append("Room Types:")
                for room in hostel['room_types'][:2]:
                    if isinstance(room, dict):
                        lines.append(f"  - {room.get('type')}: Rs. {room.get('rent_per_sem')}/sem")
            lines.append("")
        
        # Faculty & Academics
        if "academics" in kb_data:
            ac = kb_data["academics"]
            lines.append("=== ACADEMICS ===")
            if ac.get('faculty'):
                f = ac['faculty']
                lines.append(f"Faculty: {f.get('total', '150+')}")
                lines.append(f"Student-Teacher Ratio: {ac.get('student_teacher_ratio', '15:1 to 20:1')}")
            if ac.get('exam_pattern'):
                lines.append(f"Exam Pattern: {ac['exam_pattern'].get('structure', 'CA + Semester')}")
            lines.append("")
        
        # Anti-ragging
        if "anti_ragging" in kb_data:
            ar = kb_data["anti_ragging"]
            lines.append("=== ANTI-RAGGING ===")
            lines.append(f"Policy: {ar.get('policy', 'Zero Tolerance')}")
            lines.append("Anti-Ragging Committee and Squad are active.")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_conversation_history(self, history: List[Dict]) -> str:
        """Format conversation history for the prompt"""
        if not history:
            return ""
        
        lines = ["=== CONVERSATION HISTORY ==="]
        for msg in history[-4:]:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")[:200]
            lines.append(f"{role}: {content}")
        lines.append("")
        return "\n".join(lines)
    
    async def generate_response(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Generate a response using Gemini.
        
        Args:
            query: User's question
            conversation_history: Previous messages for context
        
        Returns:
            Dict with 'answer', 'source', and 'model'
        """
        if not self.client:
            return {
                "answer": "Gemini API is not configured. Please set GEMINI_API_KEY in your environment.",
                "source": "error",
                "model": None
            }
        
        try:
            history_context = self._format_conversation_history(conversation_history) if conversation_history else ""
            
            full_prompt = f"""{self.SYSTEM_PROMPT}

{self.knowledge_base}

{history_context}
User Query: {query}

Remember:
1. Answer ONLY using the knowledge base above
2. If information is not available, say you don't know
3. Keep response short (2-3 sentences)
4. Use natural, conversational language

Response:"""
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens
                )
            )
            
            answer = response.text.strip()
            
            logger.info(f"Gemini response generated: {len(answer)} chars")
            
            return {
                "answer": answer,
                "source": "gemini",
                "model": self.model
            }
            
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            return {
                "answer": f"I encountered an error processing your request. Please try again or contact the college at 0343-2501353.",
                "source": "error",
                "error": str(e)
            }
    
    def is_available(self) -> bool:
        """Check if Gemini service is available"""
        return self.client is not None


# Global instance
_gemini_service = None


def get_gemini_service() -> GeminiService:
    """Get or create the Gemini service singleton"""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
