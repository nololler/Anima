from typing import List, Dict, Optional
from pydantic import BaseModel
from datetime import datetime
import uuid


class ContextMessage(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str
    culled: bool = False
    ai_initiated: bool = False
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None

    @classmethod
    def create(cls, role: str, content: str, **kwargs) -> "ContextMessage":
        return cls(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
            **kwargs
        )


class ContextManager:
    def __init__(self, context_limit: int = 8192):
        self.context_limit = context_limit
        self.messages: List[ContextMessage] = []
        self._estimated_tokens = 0

    def add_message(self, msg: ContextMessage):
        self.messages.append(msg)
        self._estimated_tokens += self._estimate_tokens(msg.content)

    def get_active_messages(self) -> List[ContextMessage]:
        """Return non-culled messages for LLM context."""
        return [m for m in self.messages if not m.culled]

    def get_all_messages(self) -> List[ContextMessage]:
        """Return all messages including culled (for frontend display)."""
        return self.messages

    def estimate_pressure(self) -> float:
        """Return context pressure as 0.0 - 1.0."""
        active = self.get_active_messages()
        tokens = sum(self._estimate_tokens(m.content) for m in active)
        return min(tokens / self.context_limit, 1.0)

    def estimate_tokens_used(self) -> int:
        active = self.get_active_messages()
        return sum(self._estimate_tokens(m.content) for m in active)

    def cull_messages(self, message_ids: List[str]) -> List[ContextMessage]:
        """Mark messages as culled. Returns the culled messages."""
        culled = []
        for msg in self.messages:
            if msg.id in message_ids and not msg.culled:
                msg.culled = True
                culled.append(msg)
        return culled

    def get_messages_for_llm(self) -> List[Dict]:
        """Format active messages for LLM consumption."""
        active = self.get_active_messages()
        result = []
        for m in active:
            entry = {"role": m.role, "content": m.content}
            if m.tool_calls:
                entry["tool_calls"] = m.tool_calls
            if m.tool_call_id:
                entry["tool_call_id"] = m.tool_call_id
            result.append(entry)
        return result

    def get_summary_candidates(self, n: int = 10) -> List[ContextMessage]:
        """Get oldest N active messages as cull candidates."""
        active = self.get_active_messages()
        # Keep last 5 always, suggest culling from the front
        if len(active) <= 5:
            return []
        return active[:-5][:n]

    def clear(self):
        self.messages = []
        self._estimated_tokens = 0

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate: ~4 chars per token."""
        if not text:
            return 0
        return max(1, len(text) // 4)
