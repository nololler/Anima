import asyncio
import json
from typing import Dict, Set, Callable, Any, Optional
from fastapi import WebSocket
from datetime import datetime
import uuid


class MessageBus:
    """
    Central event bus. All panels subscribe here.
    Events flow: backend → bus → WebSocket → frontend panels.
    """

    def __init__(self):
        self._connections: Set[WebSocket] = set()
        self._subscribers: Dict[str, list] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.add(ws)

    def disconnect(self, ws: WebSocket):
        self._connections.discard(ws)

    async def broadcast(self, event_type: str, data: Any):
        """Send event to all connected WebSocket clients."""
        payload = json.dumps({
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        })
        dead = set()
        for ws in self._connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections.discard(ws)

        # Also notify internal subscribers
        for handler in self._subscribers.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception:
                pass

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    # ── Convenience emitters ──────────────────────────────────────────

    async def emit_chat_message(
        self,
        role: str,
        content: str,
        msg_id: str,
        culled: bool = False,
        ai_initiated: bool = False,
    ):
        await self.broadcast("chat_message", {
            "id": msg_id,
            "role": role,
            "content": content,
            "culled": culled,
            "ai_initiated": ai_initiated,
        })

    async def emit_chat_stream(self, chunk: str, msg_id: str):
        await self.broadcast("chat_stream", {"id": msg_id, "chunk": chunk})

    async def emit_chat_stream_end(self, msg_id: str, full_content: str):
        await self.broadcast("chat_stream_end", {"id": msg_id, "content": full_content})

    async def emit_inner_thought(self, thought: str, kind: str = "thought"):
        """kind: 'thought' | 'kernel'"""
        await self.broadcast("inner_thought", {
            "id": str(uuid.uuid4()),
            "kind": kind,
            "content": thought,
        })

    async def emit_tick(self, tick_number: int, mode: str, summary: str):
        """mode: 'idle' | 'active'"""
        await self.broadcast("tick", {
            "number": tick_number,
            "mode": mode,
            "summary": summary,
        })

    async def emit_mood_update(self, mood: str, intensity: int):
        await self.broadcast("mood_update", {"mood": mood, "intensity": intensity})

    async def emit_memory_update(self, path: str, action: str):
        """action: 'write' | 'append' | 'delete'"""
        await self.broadcast("memory_update", {"path": path, "action": action})

    async def emit_context_cull(self, message_ids: list):
        await self.broadcast("context_cull", {"message_ids": message_ids})

    async def emit_bank_switch(self, old_bank: str, new_bank: str):
        await self.broadcast("bank_switch", {"old_bank": old_bank, "new_bank": new_bank})

    async def emit_tool_call(self, tool_name: str, args: dict, result: Any):
        await self.broadcast("tool_call", {
            "tool": tool_name,
            "args": args,
            "result": str(result)[:200],
        })

    async def emit_error(self, message: str, source: str = "system"):
        await self.broadcast("error", {"message": message, "source": source})

    async def emit_tick_countdown(self, seconds_remaining: int):
        await self.broadcast("tick_countdown", {"seconds": seconds_remaining})

    def connection_count(self) -> int:
        return len(self._connections)


# Global instance
_bus: Optional[MessageBus] = None


def get_bus() -> MessageBus:
    global _bus
    if _bus is None:
        _bus = MessageBus()
    return _bus
