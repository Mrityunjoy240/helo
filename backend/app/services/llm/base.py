from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any


class BaseLLM(ABC):
    """Abstract base class for LLM clients"""

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 500,
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """Stream chat response as tokens"""
        pass

    @abstractmethod
    async def chat_complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 500
    ) -> str:
        """Get complete chat response"""
        pass

    @abstractmethod
    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """Get structured JSON output"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if LLM is available"""
        pass
