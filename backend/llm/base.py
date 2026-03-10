from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, List, Dict, Any
from pydantic import BaseModel


class Message(BaseModel):
    role: str  # system | user | assistant | tool
    content: Any  # str or list of content blocks
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    name: Optional[str] = None


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema


class LLMResponse(BaseModel):
    content: str
    tool_calls: Optional[List[Dict]] = None
    finish_reason: str = "stop"
    input_tokens: int = 0
    output_tokens: int = 0


class LLMAdapter(ABC):
    """Abstract base for all LLM providers."""

    def __init__(self, config):
        self.config = config

    @abstractmethod
    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        system: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """Single completion, returns full response."""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        system: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """Streaming completion, yields text chunks."""
        pass

    def format_tools_openai(self, tools: List[ToolDefinition]) -> List[Dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]
