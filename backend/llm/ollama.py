import httpx
import json
from typing import AsyncGenerator, Optional, List, Dict
from .base import LLMAdapter, Message, ToolDefinition, LLMResponse


class OllamaAdapter(LLMAdapter):

    def _build_messages(self, messages: List[Message], system: Optional[str]) -> List[Dict]:
        result = []
        if system:
            result.append({"role": "system", "content": system})
        for m in messages:
            # Ollama doesn't support role="tool" — convert to assistant message
            if m.role == "tool":
                result.append({
                    "role": "assistant",
                    "content": f"[Tool result]: {m.content or ''}",
                })
            elif isinstance(m.content, list):
                result.append({"role": m.role, "content": m.content})
            else:
                result.append({"role": m.role, "content": m.content or ""})
        return result

    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        system: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        payload = {
            "model": self.config.model,
            "messages": self._build_messages(messages, system),
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": max_tokens,
            },
        }
        if tools:
            payload["tools"] = self.format_tools_openai(tools)

        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                f"{self.config.base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        msg = data.get("message", {})
        tool_calls = None
        if msg.get("tool_calls"):
            tool_calls = [
                {
                    "id": f"call_{i}",
                    "type": "function",
                    "function": {
                        "name": tc["function"]["name"],
                        "arguments": json.dumps(tc["function"].get("arguments", {})),
                    },
                }
                for i, tc in enumerate(msg["tool_calls"])
            ]

        return LLMResponse(
            content=msg.get("content") or "",
            tool_calls=tool_calls,
            finish_reason=data.get("done_reason", "stop"),
        )

    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        system: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.config.model,
            "messages": self._build_messages(messages, system),
            "stream": True,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": max_tokens,
            },
        }
        if tools:
            payload["tools"] = self.format_tools_openai(tools)

        async with httpx.AsyncClient(timeout=180) as client:
            async with client.stream(
                "POST",
                f"{self.config.base_url}/api/chat",
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            yield chunk
                    except json.JSONDecodeError:
                        continue
