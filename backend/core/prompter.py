"""
Prompter — Subconscious Kernel (0.5B model)
============================================
Runs every 60s. Strictly mechanical — no personality, no prose.
Does NOT use LLM tool-calling. Produces JSON → executes actions in Python.

Output schema (strict):
{
  "inject_paths": [],       # memory paths to inject, max 3
  "cull_ids": [],           # message IDs to cull directly
  "nudges": [{"priority": "high|medium|low", "text": "..."}],  # max 3
  "note": "..."             # one sentence for Main LLM, max 80 chars
}
"""
import json
import re
from typing import Optional, List, Dict
from datetime import datetime

from backend.llm import create_adapter, Message
from backend.config import get_config
from backend.core.message_bus import get_bus
from backend.memory.manager import MemoryManager
from backend.memory.context import ContextManager


PROMPTER_SCHEMA = '{"inject_paths":[],"cull_ids":[],"nudges":[{"priority":"high|medium|low","text":"..."}],"note":"..."}'

SYSTEM_PROMPT = (
    "You are a mechanical scheduler. "
    "Output ONLY valid JSON. No prose. No explanation. No markdown. "
    "Start with { and end with }. "
    "Follow the schema exactly."
)


class Prompter:
    def __init__(self, memory_manager: MemoryManager, context_manager: ContextManager, persona_state: dict):
        self.memory = memory_manager
        self.context = context_manager
        self.state = persona_state
        self._adapter = None

    def _get_adapter(self):
        if self._adapter is None:
            cfg = get_config()
            self._adapter = create_adapter(cfg.prompter_llm)
        return self._adapter

    def invalidate_adapter(self):
        self._adapter = None

    async def _call(self, prompt: str) -> str:
        adapter = self._get_adapter()
        try:
            response = await adapter.complete(
                messages=[Message(role="user", content=prompt)],
                system=SYSTEM_PROMPT,
                max_tokens=300,
            )
            return (response.content or "").strip()
        except Exception as e:
            return json.dumps({"inject_paths": [], "cull_ids": [], "nudges": [], "note": f"error:{str(e)[:40]}"})

    def _parse(self, raw: str) -> dict:
        """Strict parse with complete fallback. Never raises."""
        default = {"inject_paths": [], "cull_ids": [], "nudges": [], "note": ""}
        if not raw:
            return default

        clean = re.sub(r"```(?:json)?|```", "", raw).strip()

        # Try direct parse
        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", clean)
            if not m:
                return default
            candidate = re.sub(r",\s*([}\]])", r"\1", m.group())
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                return default

        result = {}
        # inject_paths: list[str], max 3
        paths = data.get("inject_paths", [])
        result["inject_paths"] = [str(p) for p in (paths if isinstance(paths, list) else [])][:3]
        # cull_ids: list[str]
        cids = data.get("cull_ids", [])
        result["cull_ids"] = [str(c) for c in (cids if isinstance(cids, list) else [])]
        # nudges: list[{priority, text}], max 3
        nudges_raw = data.get("nudges", [])
        nudges = []
        for n in (nudges_raw if isinstance(nudges_raw, list) else [])[:3]:
            if isinstance(n, dict) and "text" in n:
                pri = n.get("priority", "low")
                nudges.append({"priority": pri if pri in ("high", "medium", "low") else "low", "text": str(n["text"])[:120]})
        result["nudges"] = nudges
        result["note"] = str(data.get("note", ""))[:80]
        return result

    def _build_prompt(self, mode: str, cull_candidates: List[Dict], memory_index: str, recent_messages: List[Dict]) -> str:
        now = datetime.now()
        pressure = self.context.estimate_pressure()
        state_summary = self.context.get_state_summary()
        action_log = self.context.get_prompter_log_summary()
        active_count = len(self.context.get_active_messages())
        total_count = len(self.context.get_all_messages())

        recent_lines = []
        for m in recent_messages[-4:]:
            content = str(m.get("content", ""))[:100].replace("\n", " ")
            recent_lines.append(f"[{m.get('role','?')[:8]}]: {content}")

        cull_lines = [f"  id={c['id'][:8]}... score={c['score']} role={c['role']} preview={c['preview'][:40]}" for c in cull_candidates[:6]]

        return f"""DATE: {now.strftime("%Y-%m-%d")}
TIME: {now.strftime("%H:%M")}
MODE: {mode}
CONTEXT: {active_count}/{total_count} msgs pressure={pressure:.0%}
MAIN_STATE: {state_summary}
LAST_ACTIONS: {action_log}

RECENT:
{chr(10).join(recent_lines) or "(none)"}

MEMORY_FILES:
{memory_index[:400] or "(empty)"}

CULL_CANDIDATES (low score=safe to cull):
{chr(10).join(cull_lines) or "  none"}

SCHEMA: {PROMPTER_SCHEMA}

RULES:
- inject_paths: only from MEMORY_FILES, max 3
- cull_ids: only from CULL_CANDIDATES IDs, only if pressure>0.6 or total>20
- nudges: max 3, only if needed
- note: max 80 chars

OUTPUT ONLY JSON:"""

    async def run_tick(self, mode: str) -> dict:
        """Run one prompter tick. Returns packet for Main LLM."""
        bus = get_bus()
        recent_msgs = self.context.get_messages_for_llm()
        cull_candidates = self.context.get_cull_candidates(n=8)
        memory_index = await self._get_memory_index()

        prompt = self._build_prompt(mode, cull_candidates, memory_index, recent_msgs)
        raw = await self._call(prompt)
        result = self._parse(raw)

        # Execute: inject memories
        injected = []
        for path in result["inject_paths"]:
            content = await self.memory.read(path)
            if content:
                self.context.inject_memory(path, content)
                self.context.log_prompter_action("inject", path)
                injected.append(path)
                await bus.emit_inner_thought(f"[kernel] injected: {path}", kind="kernel")

        # Execute: cull messages directly
        culled_ids = []
        if result["cull_ids"]:
            valid_ids = {c["id"] for c in cull_candidates}
            safe_ids = [cid for cid in result["cull_ids"] if cid in valid_ids]
            if safe_ids:
                self.context.cull_messages(safe_ids)
                self.context.log_prompter_action("cull", f"{len(safe_ids)}")
                culled_ids = safe_ids
                await bus.emit_context_cull(safe_ids)
                await bus.emit_inner_thought(f"[kernel] culled {len(safe_ids)} messages", kind="kernel")

        if result["note"]:
            await bus.emit_inner_thought(f"[kernel] {result['note']}", kind="kernel")

        self.context.log_prompter_action("tick", mode)

        return {
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "context_pressure": round(self.context.estimate_pressure(), 2),
            "active_messages": len(self.context.get_active_messages()),
            "main_llm_state": self.context.get_state_summary(),
            "injected_memories": injected,
            "culled_message_count": len(culled_ids),
            "nudges": result["nudges"],
            "note": result["note"],
        }

    async def _get_memory_index(self) -> str:
        files = self.memory.list_files("")
        lines = []
        for entry in files:
            if entry["type"] == "folder":
                for s in self.memory.list_files(entry["path"]):
                    if s["type"] == "file":
                        lines.append(f"{s['path']} ({s['size']}b)")
            else:
                lines.append(f"{entry['path']} ({entry['size']}b)")
        return "\n".join(lines[:30])
