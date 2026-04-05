from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseTool(ABC):
    """Base class for all tools"""

    name: str = "base_tool"
    description: str = "A base tool"
    
    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool with given parameters"""
        pass

    @abstractmethod
    def get_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for this tool"""
        pass
