import json
import logging
from typing import Dict, Any, List, Optional, Callable
from .base import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry for managing and executing tools.
    Provides function calling interface for LLM.
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._schemas: List[Dict[str, Any]] = []

    def register(self, tool: BaseTool) -> None:
        """Register a tool"""
        self._tools[tool.name] = tool
        self._schemas.append(tool.get_schema())
        logger.info(f"Registered tool: {tool.name}")

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name"""
        return self._tools.get(name)

    def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a tool by name"""
        tool = self.get_tool(tool_name)
        if not tool:
            return {"error": f"Tool '{tool_name}' not found"}
        
        try:
            result = tool.execute(**kwargs)
            logger.info(f"Executed tool: {tool_name}")
            return result
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}

    def get_all_schemas(self) -> List[Dict[str, Any]]:
        """Get all tool schemas for LLM function calling"""
        return self._schemas

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """Get tools in OpenAI-compatible format"""
        return [
            {"type": "function", "function": schema}
            for schema in self._schemas
        ]

    def list_tools(self) -> List[str]:
        """List all registered tool names"""
        return list(self._tools.keys())

    def _register_default_tools(self):
        """Register all default tools"""
        from .bcrec_tool import BCRECTool

        self.register(BCRECTool())


_global_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get or create global tool registry"""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
        _global_registry._register_default_tools()
    return _global_registry
