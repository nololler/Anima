import json
from typing import AsyncGenerator, Optional, List, Dict
from .base import LLMAdapter, Message, ToolDefinition, LLMResponse


class OpenAIAdapter(LLMAdapter):

    def _get_client(self):
        from openai import AsyncOpenAI
        kwargs = {"api_key": self.config.api_key or "sk-placeholder"}
        if hasattr(self.config, "base_url") and self.config.base_url:
            # For openai_compatible providers
            if "openai.com" not in self.config.base_url:
                kwargs["base_url"] = self.config.base_url
        return AsyncOpenAI(**kwargs)

    def _build_messages(self, messages: List[Message], system: Optional[str]) -> List[Dict]:
        result = []
        if system:
            result.append({"role": "system", "content": system})
        for m in messages:
            msg = {"role": m.role}
            if m.tool_calls:
                msg["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                msg["tool_call_id"] = m.tool_call_id
            if m.name:
                msg["name"] = m.name
            msg["content"] = m.content or ""
            result.append(msg)
        return result

    async def complete(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        system: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        client = self._get_client()
        kwargs = {
            "model": self.config.model,
            "messages": self._build_messages(messages, system),
            "temperature": self.config.temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = self.format_tools_openai(tools)

        resp = await client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        msg = choice.message

        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]

        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            input_tokens=resp.usage.prompt_tokens if resp.usage else 0,
            output_tokens=resp.usage.completion_tokens if resp.usage else 0,
        )

    async def stream(
        self,
        messages: List[Message],
        tools: Optional[List[ToolDefinition]] = None,
        system: Optional[str] = None,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        kwargs = {
            "model": self.config.model,
            "messages": self._build_messages(messages, system),
            "temperature": self.config.temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = self.format_tools_openai(tools)

        async with await client.chat.completions.create(**kwargs) as stream:
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content
