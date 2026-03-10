import json
from typing import AsyncGenerator, Optional, List, Dict
from .base import LLMAdapter, Message, ToolDefinition, LLMResponse


class AnthropicAdapter(LLMAdapter):

    def _get_client(self):
        import anthropic
        return anthropic.AsyncAnthropic(api_key=self.config.api_key)

    def _build_messages(self, messages: List[Message]) -> List[Dict]:
        result = []
        for m in messages:
            if m.role == "system":
                continue  # system handled separately
            msg = {"role": m.role}
            if isinstance(m.content, list):
                msg["content"] = m.content
            elif m.tool_call_id:
                msg["content"] = [
                    {"type": "tool_result", "tool_use_id": m.tool_call_id, "content": m.content}
                ]
            elif m.tool_calls:
                blocks = []
                if m.content:
                    blocks.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": json.loads(tc["function"]["arguments"]),
                    })
                msg["content"] = blocks
            else:
                msg["content"] = m.content or ""
            result.append(msg)
        return result

    def _format_tools(self, tools: List[ToolDefinition]) -> List[Dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.parameters,
            }
            for t in tools
        ]

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
            "messages": self._build_messages(messages),
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._format_tools(tools)

        resp = await client.messages.create(**kwargs)

        content_text = ""
        tool_calls = None
        for block in resp.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append({
                    "id": block.id,
                    "type": "function",
                    "function": {"name": block.name, "arguments": json.dumps(block.input)},
                })

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            finish_reason=resp.stop_reason or "stop",
            input_tokens=resp.usage.input_tokens,
            output_tokens=resp.usage.output_tokens,
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
            "messages": self._build_messages(messages),
            "max_tokens": max_tokens,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = self._format_tools(tools)

        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield text
