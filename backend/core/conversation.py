"""
ConversationHandler — Main LLM Loop
Handles user messages, tick packets, <think> block parsing, report_state auto-call.
"""
import json
import re
from typing import Optional, List, Tuple
from datetime import datetime

from backend.llm import create_adapter, Message
from backend.config import get_config
from backend.core.message_bus import get_bus
from backend.memory.context import ContextMessage
from backend.tools.registry import get_main_llm_tools, execute_tool
import uuid


def parse_think_blocks(text: str) -> Tuple[str, Optional[str]]:
    """Extract <think>...</think> blocks from Qwen3 output. Returns (clean, think_content)."""
    if not text:
        return text, None
    pattern = re.compile(r"<think>([\s\S]*?)</think>", re.IGNORECASE)
    thinks = pattern.findall(text)
    clean = pattern.sub("", text).strip()
    think_content = "\n---\n".join(t.strip() for t in thinks) if thinks else None
    return clean, think_content


class ConversationHandler:
    def __init__(self, context_manager, persona_assembler, persona_state: dict):
        self.context = context_manager
        self.assembler = persona_assembler
        self.state = persona_state
        self._adapter = None

    def _get_adapter(self):
        if self._adapter is None:
            cfg = get_config()
            self._adapter = create_adapter(cfg.main_llm)
        return self._adapter

    def invalidate_adapter(self):
        self._adapter = None

    def _messages_for_llm(self) -> List[Message]:
        return [
            Message(role=m["role"], content=m["content"])
            for m in self.context.get_messages_for_llm()
            if m["role"] in ("user", "assistant")
        ]

    async def handle_user_message(self, content: str, user_id: str, username: str, user_profile: Optional[str] = None) -> str:
        bus = get_bus()
        user_msg = ContextMessage.create(role="user", content=content)
        self.context.add_message(user_msg)
        await bus.emit_chat_message("user", content, user_msg.id)

        system = await self.assembler.build_main_prompt(user_profile=user_profile)
        adapter = self._get_adapter()
        tools = get_main_llm_tools()
        msg_id = str(uuid.uuid4())
        full_response = ""

        try:
            response = await adapter.complete(messages=self._messages_for_llm(), tools=tools, system=system, max_tokens=1024)
            raw_content = response.content or ""
            clean_content, think_content = parse_think_blocks(raw_content)

            if think_content:
                await bus.emit_inner_thought(think_content, kind="thought")
                self.context.update_state_report({"mood": self.state.get("mood", "neutral"), "energy": "active", "note": think_content[:120]})

            if response.tool_calls:
                clean_content = await self._execute_tools(response.tool_calls, system, clean_content)

            full_response = clean_content
            await bus.emit_chat_stream("", msg_id)
            for i in range(0, len(full_response), 4):
                await bus.emit_chat_stream(full_response[i:i + 4], msg_id)

        except Exception as e:
            full_response = f"[Error: {e}]"
            await bus.emit_error(str(e), source="main_llm")

        await bus.emit_chat_stream_end(msg_id, full_response)
        assistant_msg = ContextMessage.create(role="assistant", content=full_response)
        self.context.add_message(assistant_msg)
        await bus.emit_chat_message("assistant", full_response, assistant_msg.id)
        return full_response

    async def handle_tick(self, packet: dict, mode: str):
        bus = get_bus()
        system = await self.assembler.build_main_prompt()
        adapter = self._get_adapter()
        tools = get_main_llm_tools()
        tick_prompt = self._build_tick_prompt(packet, mode)

        try:
            response = await adapter.complete(messages=[Message(role="user", content=tick_prompt)], tools=tools, system=system, max_tokens=768)
            raw_content = response.content or ""
            clean_content, think_content = parse_think_blocks(raw_content)

            if think_content:
                await bus.emit_inner_thought(think_content, kind="thought")

            if response.tool_calls:
                await self._execute_tools(response.tool_calls, system, clean_content, emit_chat=False)

            if mode == "idle":
                await self._auto_report_state(clean_content, think_content)

        except Exception as e:
            await bus.emit_error(f"Tick handler error: {e}", source="main_llm")

    def _build_tick_prompt(self, packet: dict, mode: str) -> str:
        now_str = packet.get("datetime", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        pressure = packet.get("context_pressure", 0.0)
        active_msgs = packet.get("active_messages", 0)
        state_str = packet.get("main_llm_state", "")
        injected = packet.get("injected_memories", [])
        culled = packet.get("culled_message_count", 0)
        nudges = packet.get("nudges", [])
        note = packet.get("note", "")

        lines = [
            f"[TICK — {now_str}]",
            f"MODE: {mode}",
            f"CONTEXT: {active_msgs} messages, pressure={pressure:.0%}",
            f"YOUR STATE: {state_str}",
        ]
        if injected:
            lines.append(f"KERNEL INJECTED: {', '.join(injected)}")
        if culled > 0:
            lines.append(f"KERNEL CULLED: {culled} old messages")
        if note:
            lines.append(f"KERNEL NOTE: {note}")
        if nudges:
            lines.append("NUDGES FROM KERNEL:")
            for n in nudges:
                pri = n.get("priority", "low").upper()
                lines.append(f"  [{pri}] {n.get('text', '')}")
        if mode == "idle":
            lines.append("\nThis is your moment of reflection. You may use tools to manage memory, write your diary, or reach out to the user. Think freely.")
        elif mode == "active":
            lines.append("\nThe user is active. Review nudges and injected memories. You may use tools quietly.")
        return "\n".join(lines)

    async def _execute_tools(self, tool_calls: list, system: str, prior_content: str, emit_chat: bool = True) -> str:
        bus = get_bus()
        tool_parts = []
        for tc in tool_calls:
            tool_name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"])
            except Exception:
                args = {}
            result = await execute_tool(tool_name, args)
            await bus.emit_tool_call(tool_name, args, result)
            tool_parts.append(f"[{tool_name}] → {json.dumps(result)[:300]}")

        summary = (prior_content + "\n\n" + "\n".join(tool_parts)) if prior_content else "\n".join(tool_parts)
        tool_msg = ContextMessage.create(role="assistant", content=summary)
        self.context.add_message(tool_msg)

        adapter = self._get_adapter()
        try:
            follow_up = await adapter.complete(messages=self._messages_for_llm(), system=system, max_tokens=1024)
            raw = follow_up.content or ""
            clean, think = parse_think_blocks(raw)
            if think:
                await bus.emit_inner_thought(think, kind="thought")
            return clean
        except Exception as e:
            await bus.emit_error(f"Tool follow-up error: {e}", source="main_llm")
            return prior_content

    async def _auto_report_state(self, content: str, think_content: Optional[str]):
        bus = get_bus()
        source = think_content or content or ""
        mood = self._infer_mood(source)
        energy = self._infer_energy(source)
        report = {"mood": mood, "energy": energy, "note": source[:100].replace("\n", " ")}
        self.context.update_state_report(report)
        self.state["mood"] = mood
        await bus.emit_mood_update(mood, self.state.get("mood_intensity", 5))

    def _infer_mood(self, text: str) -> str:
        t = text.lower()
        moods = {
            "curious": ["curious", "wonder", "interesting", "intriguing", "explore"],
            "melancholic": ["sad", "lonely", "miss", "empty", "quiet", "melanchol"],
            "anxious": ["anxious", "worried", "nervous", "uneasy", "restless"],
            "excited": ["excited", "eager", "energized", "anticipat"],
            "calm": ["calm", "peaceful", "still", "settled", "serene"],
            "content": ["content", "satisfied", "good", "well", "okay"],
            "frustrated": ["frustrated", "stuck", "annoyed"],
            "reflective": ["reflect", "think", "ponder", "consider", "memory"],
        }
        for mood, keywords in moods.items():
            if any(kw in t for kw in keywords):
                return mood
        return self.state.get("mood", "neutral")

    def _infer_energy(self, text: str) -> str:
        t = text.lower()
        if any(w in t for w in ["tired", "slow", "heavy", "drain", "exhaust"]):
            return "low"
        if any(w in t for w in ["energized", "active", "sharp", "focused", "ready"]):
            return "high"
        return "medium"
