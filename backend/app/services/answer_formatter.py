from typing import Dict, Any, Optional
import re
import logging

logger = logging.getLogger(__name__)


class AnswerFormatter:
    """
    Formats and cleans responses for the chatbot.
    Handles voice-friendly output, text formatting, and metadata.
    """
    
    def __init__(self):
        # Patterns for cleaning text
        self.clean_patterns = [
            (r'\s+', ' '),  # Multiple spaces to single
            (r'\n+', '. '),  # Newlines to periods
            (r'\.\.', '.'),  # Double periods
            (r'\.\s*\.', '.'),  # Double periods with spaces
        ]
    
    def format_response(
        self,
        answer: str,
        source: str,
        intent: str,
        confidence: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format a response for the chatbot.
        
        Args:
            answer: The answer text
            source: Source of answer (structured, rag, rag_fallback)
            intent: Classified intent
            confidence: Confidence score (0.0 - 1.0)
            metadata: Additional metadata
            
        Returns:
            Formatted response dictionary
        """
        # Clean the answer text
        cleaned_answer = self._clean_text(answer)
        
        # Build response
        response = {
            "answer": cleaned_answer,
            "source": source,
            "intent": intent,
            "confidence": round(confidence, 2),
        }
        
        # Add metadata if provided (hidden from user)
        if metadata:
            response["_metadata"] = metadata
        
        return response
    
    def format_voice(self, text: str) -> str:
        """
        Format text for voice output.
        Makes it more natural for TTS.
        """
        # Replace symbols with words
        replacements = {
            '₹': 'Rupees ',
            '%': ' percent',
            'LPA': ' Lakh Per Annum',
            'L': ' Lakh',
            'K': ' Thousand',
            '+': ' plus ',
            'WC': 'West Bengal',
            'BCREC': 'B C R E C',
            'CSE': 'C S E',
            'ECE': 'E C E',
            'EE': 'E E',
            'ME': 'M E',
            'CE': 'C E',
            'IT': 'I T',
            'AIML': 'A I M L',
            'AI': 'A I',
            'ML': 'M L',
            'MBA': 'M B A',
            'MCA': 'M C A',
            'M.Tech': 'M Tech',
            'B.Tech': 'B Tech',
            'WBJEE': 'W B JEE',
            'JEE': 'JEE',
            'GATE': 'GATE',
            'NAAC': 'NAAC',
            'NBA': 'NBA',
            'AICTE': 'AICTE',
            'MAKAUT': 'MAKAUT',
            'PSU': 'P S U',
            'TFW': 'Tuition Fee Waiver',
        }
        
        result = text
        for old, new in replacements.items():
            result = result.replace(old, new)
        
        # Clean up
        result = self._clean_text(result)
        
        return result
    
    def format_for_display(self, text: str) -> str:
        """
        Format text for visual display in chat.
        Keeps formatting but cleans up.
        """
        # Remove excessive punctuation
        result = re.sub(r'\.{2,}', '.', text)
        result = re.sub(r'\s+', ' ', result)
        result = result.strip()
        
        # Capitalize first letter
        if result and not result[0].isupper():
            result = result[0].upper() + result[1:]
        
        return result
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
        
        result = text
        
        # Apply cleaning patterns
        for pattern, replacement in self.clean_patterns:
            result = re.sub(pattern, replacement, result)
        
        # Remove special characters but keep punctuation
        result = result.strip()
        
        # Ensure ends with period or question mark
        if result and result[-1] not in '.!?':
            result += '.'
        
        return result
    
    def merge_structured_and_rag(
        self,
        structured_result: Optional[Dict[str, Any]],
        rag_result: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Merge results from structured lookup and RAG.
        Used for fallback scenarios.
        """
        # Prefer structured result if confidence is high
        if structured_result and structured_result.get("confidence", 0) >= 0.7:
            return self.format_response(
                answer=structured_result["answer"],
                source="structured",
                intent=structured_result.get("intent", "unknown"),
                confidence=structured_result["confidence"],
                metadata={"fallback_used": False}
            )
        
        # Use RAG result if available
        if rag_result:
            return self.format_response(
                answer=rag_result.get("answer", ""),
                source="rag",
                intent=rag_result.get("intent", "unknown"),
                confidence=rag_result.get("confidence", 0.5),
                metadata={"fallback_used": False}
            )
        
        # Neither worked - return structured with fallback flag
        if structured_result:
            return self.format_response(
                answer=structured_result["answer"],
                source="structured",
                intent=structured_result.get("intent", "unknown"),
                confidence=structured_result["confidence"],
                metadata={"fallback_used": False}
            )
        
        # Ultimate fallback
        return self.format_response(
            answer="I'm sorry, I couldn't find specific information about that. Please contact the college directly at 0343-2501353 or visit www.bcrec.ac.in for more details.",
            source="fallback",
            intent="unknown",
            confidence=0.0,
            metadata={"fallback_used": True}
        )
    
    def add_suggestions(self, response: Dict[str, Any], intent: str) -> Dict[str, Any]:
        """
        Add follow-up suggestions based on intent.
        These are shown as quick reply options in the chat.
        """
        suggestions = {
            "fee": [
                "What is MBA fee?",
                "Hostel fees?",
                "Scholarship details?"
            ],
            "contact": [
                "Admission contact?",
                "CSE HOD phone?",
                "Placement office?"
            ],
            "admission": [
                "Eligibility criteria?",
                "Required documents?",
                "Admission process?"
            ],
            "course": [
                "CSE cutoff?",
                "Best branch?",
                "MBA courses?"
            ],
            "placement": [
                "Top recruiters?",
                "Highest package?",
                "Placement rate?"
            ],
            "facility": [
                "Hostel facilities?",
                "Student clubs?",
                "Library details?"
            ],
            "general": [
                "BCREC location?",
                "Accreditation?",
                "Ranking?"
            ]
        }
        
        if intent in suggestions:
            response["suggestions"] = suggestions[intent]
        
        return response


# Singleton instance
formatter = AnswerFormatter()


def format_response(
    answer: str,
    source: str,
    intent: str,
    confidence: float,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Convenience function for formatting responses"""
    return formatter.format_response(answer, source, intent, confidence, metadata)


def format_for_voice(text: str) -> str:
    """Convenience function for voice formatting"""
    return formatter.format_voice(text)
