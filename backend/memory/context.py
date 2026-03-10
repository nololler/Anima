from typing import List, Dict, Optional, Any
from pydantic import BaseModel
from datetime import datetime
import uuid
import re


class InjectedMemory(BaseModel):
    path: str
    content: str
    injected_at: str
    tag: str = "memory"


class ContextMessage(BaseModel):
    id: str
    role: str
    content: str
    timestamp: str
    culled: bool = False
    ai_initiated: bool = False
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    think_content: Optional[str] = None

    @classmethod
    def create(cls, role: str, content: str, **kwargs) -> "ContextMessage":
        return cls(id=str(uuid.uuid4()), role=role, content=content, timestamp=datetime.now().isoformat(), **kwargs)


class ContextManager:
    def __init__(self, context_limit: int = 8192):
        self.context_limit = context_limit
        self.messages: List[ContextMessage] = []
        self.injected_memories: List[InjectedMemory] = []
        self.prompter_action_log: List[Dict] = []
        self.last_state_report: Dict[str, Any] = {}

    def add_message(self, msg: ContextMessage):
        self.messages.append(msg)

    def get_active_messages(self) -> List[ContextMessage]:
        return [m for m in self.messages if not m.culled]

    def get_all_messages(self) -> List[ContextMessage]:
        return self.messages

    def cull_messages(self, message_ids: List[str]) -> List[ContextMessage]:
        culled = []
        for msg in self.messages:
            if msg.id in message_ids and not msg.culled:
                msg.culled = True
                culled.append(msg)
        return culled

    def get_cull_candidates(self, n: int = 10) -> List[Dict]:
        """Score and return cull candidates. Never culls last 6. Returns [{id, role, preview, score}]."""
        date_pat = re.compile(r'\b\d{4}-\d{2}-\d{2}\b|\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', re.I)
        name_pat = re.compile(r'\b[A-Z][a-z]{2,}\b')
        active = self.get_active_messages()
        if len(active) <= 6:
            return []
        candidates = active[:-6]
        result = []
        for msg in candidates:
            score = 0.0
            score += min(len(msg.content) / 500, 1.0) * 0.4
            if date_pat.search(msg.content): score += 0.3
            if name_pat.search(msg.content): score += 0.2
            if msg.ai_initiated: score += 0.1
            result.append({"id": msg.id, "role": msg.role, "preview": msg.content[:80].replace("\n", " "), "score": round(score, 2)})
        result.sort(key=lambda x: x["score"])
        return result[:n]

    def inject_memory(self, path: str, content: str):
        self.injected_memories = [m for m in self.injected_memories if m.path != path]
        self.injected_memories.append(InjectedMemory(path=path, content=content, injected_at=datetime.now().isoformat()))

    def clear_injections(self):
        self.injected_memories = []

    def get_injections_block(self) -> Optional[str]:
        if not self.injected_memories:
            return None
        lines = ["[INJECTED MEMORIES — loaded by subconscious kernel]"]
        for m in self.injected_memories:
            ts = m.injected_at[11:16]
            lines.append(f"\n### {m.path} (injected {ts})\n{m.content[:1200]}")
        return "\n".join(lines)

    def get_messages_for_llm(self) -> List[Dict]:
        active = self.get_active_messages()
        if not active:
            return []
        injection_block = self.get_injections_block()
        if not injection_block:
            return [{"role": m.role, "content": m.content} for m in active]
        last_user_idx = next((i for i in range(len(active)-1, -1, -1) if active[i].role == "user"), None)
        result = []
        for i, m in enumerate(active):
            if i == last_user_idx:
                result.append({"role": "user", "content": f"{injection_block}\n\n---\n{m.content}"})
            else:
                result.append({"role": m.role, "content": m.content})
        return result

    def estimate_pressure(self) -> float:
        active = self.get_active_messages()
        tokens = sum(self._tok(m.content) for m in active) + sum(self._tok(m.content) for m in self.injected_memories)
        return min(tokens / self.context_limit, 1.0)

    def estimate_tokens_used(self) -> int:
        return sum(self._tok(m.content) for m in self.get_active_messages())

    def log_prompter_action(self, action: str, detail: str = ""):
        entry = {"time": datetime.now().strftime("%H:%M"), "action": action, "detail": detail[:60]}
        self.prompter_action_log = self.prompter_action_log[-9:] + [entry]

    def get_prompter_log_summary(self) -> str:
        if not self.prompter_action_log:
            return "none"
        return "; ".join(f"{e['time']} {e['action']}({e['detail']})" for e in self.prompter_action_log[-5:])

    def update_state_report(self, report: Dict[str, Any]):
        self.last_state_report = {**report, "reported_at": datetime.now().isoformat()}

    def get_state_summary(self) -> str:
        r = self.last_state_report
        if not r:
            return "no state reported yet"
        mood = r.get("mood", "unknown")
        energy = r.get("energy", "?")
        note = r.get("note", "")
        age_str = ""
        if "reported_at" in r:
            try:
                delta = int((datetime.now() - datetime.fromisoformat(r["reported_at"])).total_seconds() // 60)
                age_str = f" ({delta}m ago)"
            except Exception:
                pass
        return f"mood={mood} energy={energy}{age_str} — {note}"[:200]

    def clear(self):
        self.messages = []
        self.injected_memories = []
        self.prompter_action_log = []
        self.last_state_report = {}

    @staticmethod
    def _tok(text: str) -> int:
        return max(1, len(text) // 4) if text else 0
