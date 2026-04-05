import asyncio
import json
import logging
from typing import Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass

from app.services.llm import OllamaLLM
from app.services.router import IntentRouter
from app.services.tools import ToolRegistry, get_tool_registry
from app.services.memory import ShortTermMemory, LongTermMemory, short_term_memory, long_term_memory
from app.services.stt.faster_whisper_stt import FasterWhisperSTT, stt_service
from app.services.tts import TTSService

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for voice pipeline"""
    llm_model: str = "qwen3.5:latest"
    stt_model: str = "base"
    college_name: str = "Dr. B.C. Roy Engineering College"
    admissions_phone: str = "+91-9333928874"
    support_email: str = "info@bcrec.ac.in"


class VoicePipeline:
    """
    Main voice processing pipeline.
    Orchestrates STT -> Intent -> Tools/RAG -> LLM -> TTS
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        
        self.llm = OllamaLLM(model=self.config.llm_model)
        self.router = IntentRouter(llm=self.llm)
        self.tools = get_tool_registry()
        self.short_term = short_term_memory
        self.long_term = long_term_memory
        self.stt = stt_service
        self._tts = None

    @property
    def tts(self) -> TTSService:
        """Lazy load TTS"""
        if self._tts is None:
            self._tts = TTSService()
        return self._tts

    async def process(
        self,
        query: str,
        session_id: str,
        language: str = "en"
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process a query and yield streaming responses.
        
        Yields:
            - {"type": "transcript", "text": str} - Confirmed transcription
            - {"type": "intent", "intent": str, "confidence": float}
            - {"type": "tool_call", "tool": str, "result": dict}
            - {"type": "answer_chunk", "text": str} - LLM token chunks
            - {"type": "audio_chunk", "data": bytes} - TTS audio chunks
            - {"type": "done", "full_text": str} - Final response
            - {"type": "error", "message": str}
        """
        try:
            yield {"type": "transcript", "text": query}

            intent_result = await self.router.classify(query)
            yield {
                "type": "intent",
                "intent": intent_result.intent,
                "confidence": intent_result.confidence,
                "source": intent_result.source
            }

            response_text = ""

            if intent_result.intent == "greeting":
                response_text = "Hello! How can I help you today? I can provide information about admissions, fees, courses, placements, and more."
            
            elif intent_result.source == "tool":
                response_text = await self._handle_tool_query(query, intent_result)
            
            elif intent_result.source == "structured":
                response_text = await self._handle_structured_query(query, intent_result)
            
            else:
                response_text = await self._handle_llm_query(query, session_id, intent_result)

            self.short_term.add_message(session_id, "user", query)
            self.short_term.add_message(session_id, "assistant", response_text)

            async for chunk in self._stream_response(response_text):
                yield chunk

            yield {"type": "done", "full_text": response_text}

        except asyncio.CancelledError:
            logger.info(f"Pipeline cancelled for session {session_id}")
            raise
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            yield {"type": "error", "message": str(e)}

    async def _handle_tool_query(self, query: str, intent) -> str:
        """Handle query using unified BCREC tool"""
        entities = intent.entities
        query_type = None
        course_param = None
        dept_param = None

        intent_detail = entities.get("intent_detail", "")

        if intent.intent == "fee" or "hostel" in intent_detail:
            if "hostel" in query.lower():
                query_type = "hostel"
            else:
                course_param = entities.get("course") or entities.get("department") or "CSE"
                query_type = "fee"
        
        elif intent.intent == "admission":
            query_type = "admission"
        
        elif intent.intent == "contact":
            query_type = "contact"
        
        elif intent.intent == "course":
            query_type = "course"
            course_param = entities.get("department") or entities.get("course")
        
        elif intent.intent == "placement":
            query_type = "placement"
            course_param = entities.get("course")
        
        elif intent.intent == "cutoff" or "cutoff" in intent_detail:
            query_type = "cutoff"
            course_param = entities.get("course") or entities.get("department") or "CSE"
        
        elif intent.intent == "hod" or "hod" in intent_detail:
            query_type = "department"
            dept_param = entities.get("department") or entities.get("course") or "CSE"
        
        elif intent.intent == "facility" or intent.intent == "hod":
            if "hostel" in query.lower():
                query_type = "hostel"
            elif intent.intent == "hod":
                query_type = "department"
                dept_param = entities.get("department") or entities.get("course")
            else:
                query_type = "infrastructure"
        
        else:
            return "I couldn't find specific information. Please contact the college directly."

        result = self.tools.execute("get_bcrec_info", query_type=query_type, course=course_param, department=dept_param)
        return self._format_bcrec_result(result)

    async def _handle_structured_query(self, query: str, intent) -> str:
        """Handle structured data queries"""
        return await self._handle_tool_query(query, intent)

    async def _handle_llm_query(
        self, 
        query: str, 
        session_id: str, 
        intent
    ) -> str:
        """Handle complex queries using LLM"""
        context = self.short_term.get_context(session_id, last_k=5)
        memories = self.long_term.search(query, limit=3)
        
        system_prompt = f"""You are a helpful assistant for {self.config.college_name}.
College Contact: {self.config.admissions_phone}
Email: {self.config.support_email}

Guidelines:
1. Be concise and helpful
2. Provide accurate information about the college
3. For specific data (fees, cutoff), suggest using tools
4. Be friendly and professional
5. Answer in the same language as the user"""

        if memories:
            context_info = "\n".join([m["content"] for m in memories])
            system_prompt += f"\n\nRelevant past information:\n{context_info}"

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(context)
        messages.append({"role": "user", "content": query})

        response = await self.llm.chat_complete(
            messages,
            temperature=0.3,
            max_tokens=300
        )

        return response

    def _format_tool_result(self, result: Dict[str, Any]) -> str:
        """Format tool result for display"""
        return self._format_bcrec_result(result)

    def _format_bcrec_result(self, result: Dict[str, Any]) -> str:
        """Format BCREC tool result for display"""
        if not result:
            return "Information not available. Please contact the college directly."
        
        if not result.get("success", True):
            return result.get("error", "An error occurred")

        if result.get("total_fees") and result.get("course"):
            parts = []
            if result.get("course_name"):
                parts.append(f"{result['course_name']}:")
            parts.append(f"Fees: Total {result['total_fees']}, Admission {result.get('admission_fee', 'N/A')}")
            if result.get("duration"):
                parts.append(f"Duration: {result['duration']}")
            return ". ".join(parts)

        if result.get("full_name") and result.get("course"):
            parts = [f"{result['full_name']} ({result['course']}):"]
            if result.get("total_fees"):
                parts.append(f"Fees: {result['total_fees']}")
            if result.get("admission_fee"):
                parts.append(f"Admission: {result['admission_fee']}")
            if result.get("intake"):
                parts.append(f"Intake: {result['intake']} students")
            if result.get("nba_accredited"):
                parts.append("NBA Accredited")
            if result.get("placement"):
                p = result["placement"]
                if isinstance(p, dict):
                    rate = p.get("2024-25") or p.get("2025-26")
                    if rate:
                        parts.append(f"Placement: {rate}")
            return ". ".join(parts)

        if "cutoff" in result:
            c = result.get("cutoff", {})
            if isinstance(c, dict):
                course = result.get("course", "")
                parts = [f"{course} WBJEE Cutoff:"]
                for year, rank in c.items():
                    parts.append(f"{year}: {rank}")
                return ", ".join(parts)
            return str(c)

        if "admission" in result:
            a = result.get("admission")
            if not isinstance(a, dict):
                return str(a) if a else "Admission information not available."
            parts = ["Admission:"]
            elig = a.get("eligibility")
            if elig:
                if isinstance(elig, dict):
                    btech_elig = elig.get("btech") or elig.get("B.Tech")
                    if btech_elig:
                        parts.append(f"B.Tech: {btech_elig}")
                else:
                    parts.append(str(elig))
            if a.get("counseling"):
                parts.append(f"Counseling: {a['counseling']}")
            if a.get("scholarships"):
                parts.append("Scholarships available")
            if a.get("seat_distribution"):
                sd = a["seat_distribution"]
                if isinstance(sd, dict):
                    parts.append(f"Seat distribution: WBJEE {sd.get('wbjee', 'N/A')}, JEE Main {sd.get('jee_main', 'N/A')}")
            return ". ".join(parts)

        if "courses" in result:
            courses = result.get("courses", [])
            parts = ["Available courses:"]
            for c in courses[:5]:
                if isinstance(c, dict):
                    parts.append(f"{c.get('code')}: {c.get('name')} (Intake: {c.get('intake')})")
                else:
                    parts.append(str(c).upper())
            return ". ".join(parts)

        if "overall_rate" in result:
            parts = [f"Placement rate: {result['overall_rate']}"]
            if result.get("highest_package"):
                hp = result["highest_package"]
                if isinstance(hp, dict):
                    parts.append(f"Highest package: Rs. {hp.get('amount')} LPA from {hp.get('company')}")
                else:
                    parts.append(f"Highest package: {hp}")
            if result.get("top_companies"):
                companies = [c.get("company") for c in result["top_companies"][:3] if isinstance(c, dict)]
                parts.append(f"Top recruiters: {', '.join(companies)}")
            return ". ".join(parts)

        if "hostel" in result:
            h = result["hostel"]
            if isinstance(h, dict):
                parts = [f"Hostel available. Capacity: {h.get('total_capacity')} students."]
                if h.get("mess"):
                    mess = h["mess"]
                    if isinstance(mess, dict):
                        parts.append(f"Mess: Rs. {mess.get('monthly_charge')}/month")
                if h.get("room_types"):
                    types = [f"{r.get('type')} (Rs. {r.get('rent_per_sem')}/sem)" for r in h["room_types"] if isinstance(r, dict)]
                    parts.append(f"Room types: {', '.join(types)}")
                return ". ".join(parts)
            return str(h)

        if "contact" in result:
            c = result["contact"]
            if isinstance(c, dict):
                parts = []
                if c.get("email"):
                    parts.append(f"Email: {c['email']}")
                if c.get("phones"):
                    phones = c["phones"] if isinstance(c["phones"], list) else [c["phones"]]
                    parts.append(f"Phone: {', '.join(phones[:2])}")
                if c.get("website"):
                    parts.append(f"Website: {c['website']}")
                return ". ".join(parts)
            return str(c)

        if "admission" in result:
            a = result.get("admission")
            if not isinstance(a, dict):
                return str(a) if a else "Admission information not available."
            parts = ["Admission:"]
            elig = a.get("eligibility")
            if elig:
                if isinstance(elig, dict):
                    btech_elig = elig.get("btech") or elig.get("B.Tech")
                    if btech_elig:
                        parts.append(f"B.Tech: {btech_elig}")
                else:
                    parts.append(str(elig))
            if a.get("counseling"):
                parts.append(f"Counseling: {a['counseling']}")
            if a.get("scholarships"):
                parts.append("Scholarships available")
            if a.get("seat_distribution"):
                sd = a["seat_distribution"]
                if isinstance(sd, dict):
                    parts.append(f"Seat distribution: WBJEE {sd.get('wbjee', 'N/A')}, JEE Main {sd.get('jee_main', 'N/A')}")
            return ". ".join(parts)

        if "cutoff" in result:
            c = result.get("cutoff", {})
            if isinstance(c, dict):
                course = result.get("course", "")
                parts = [f"{course} WBJEE Cutoff:"]
                for year, rank in c.items():
                    parts.append(f"{year}: {rank}")
                return ", ".join(parts)
            return str(c)

        if "info" in result and "hod" in result["info"]:
            hod = result["info"]["hod"]
            if isinstance(hod, dict):
                parts = [f"HOD: {hod.get('name', 'N/A')}"]
                if hod.get("email"):
                    parts.append(f"Email: {hod['email']}")
                if hod.get("mobile"):
                    parts.append(f"Phone: {hod['mobile']}")
                return ". ".join(parts)

        return str(result)

    async def _stream_response(self, text: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream response with TTS audio chunks"""
        words = text.split()
        buffer = ""
        
        for word in words:
            buffer += word + " "
            
            if len(buffer) >= 20 or word.endswith("."):
                yield {"type": "answer_chunk", "text": buffer}
                buffer = ""

        if buffer:
            yield {"type": "answer_chunk", "text": buffer}

    async def shutdown(self):
        """Cleanup resources"""
        logger.info("Pipeline shutdown")


_global_pipeline: Optional[VoicePipeline] = None


def get_pipeline() -> VoicePipeline:
    """Get or create global pipeline"""
    global _global_pipeline
    if _global_pipeline is None:
        _global_pipeline = VoicePipeline()
    return _global_pipeline
