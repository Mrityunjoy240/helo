import asyncio
import json
import logging
from typing import AsyncGenerator, List, Dict, Any, Optional
from .base import BaseLLM

logger = logging.getLogger(__name__)


class OllamaLLM(BaseLLM):
    """
    Local LLM client using Ollama API.
    Supports streaming responses and structured output.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3.5:latest",
        timeout: int = 120
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._available = None

    def is_available(self) -> bool:
        """Check if Ollama server is running"""
        if self._available is not None:
            return self._available
        
        try:
            import httpx
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            self._available = response.status_code == 200
            return self._available
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            self._available = False
            return False

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 500,
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response from Ollama.
        Yields tokens one by one for real-time response.
        """
        import httpx

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as response:
                if response.status_code != 200:
                    raise Exception(f"Ollama API error: Status {response.status_code}")

                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            if "message" in data:
                                content = data["message"].get("content", "")
                                if content:
                                    yield content
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

    async def chat_complete(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int = 500
    ) -> str:
        """Get complete chat response as single string"""
        tokens = []
        async for token in self.chat(messages, temperature, max_tokens, stream=True):
            tokens.append(token)
        return "".join(tokens)

    async def structured_output(
        self,
        messages: List[Dict[str, str]],
        schema: Dict[str, Any],
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        Get structured JSON output from LLM.
        Uses prompt engineering to guide JSON output.
        """
        schema_str = json.dumps(schema, indent=2)
        
        structured_messages = messages.copy()
        structured_messages.append({
            "role": "system",
            "content": f"""You must respond ONLY with valid JSON matching this schema.
Do not include any explanation, markdown, or text outside the JSON.
Schema: {schema_str}"""
        })

        response = await self.chat_complete(structured_messages, temperature=temperature, max_tokens=1000)
        
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            return json.loads(cleaned)

    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using Ollama"""
        import httpx

        payload = {
            "model": "nomic-embed-text:latest",
            "prompt": text
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.base_url}/api/embeddings", json=payload)
            if response.status_code == 200:
                data = response.json()
                return data.get("embedding", [])
            else:
                raise Exception(f"Embedding error: {response.text}")


llm_client = OllamaLLM()
