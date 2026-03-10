import json
import re
from typing import Optional, Dict, List
from backend.llm import create_adapter, Message
from backend.config import get_config
from backend.core.message_bus import get_bus


class Prompter:
    """
    The subconscious kernel. Runs before Main LLM on every tick and message.
    Handles: memory selection, context pressure, inner thoughts, kernel reports.
    """

    def __init__(self, memory_manager, persona_assembler, persona_state: dict):
        self.memory = memory_manager
        self.assembler = persona_assembler
        self.state = persona_state
        self._adapter = None

    def _get_adapter(self):
        if self._adapter is None:
            cfg = get_config()
            self._adapter = create_adapter(cfg.prompter_llm)
        return self._adapter

    def _invalidate_adapter(self):
        self._adapter = None

    async def _call(self, prompt: str, system: str = None) -> str:
        adapter = self._get_adapter()
        try:
            response = await adapter.complete(
                messages=[Message(role="user", content=prompt)],
                system=system,
                max_tokens=512,
            )
            return response.content.strip()
        except Exception as e:
            return json.dumps({
                "kernel_report": f"Prompter error: {e}",
                "inner_thought": "Something feels off in my mind...",
            })

    def _parse_json(self, text: str) -> dict:
        """
        Multi-strategy JSON extraction. Small models often wrap JSON in prose,
        add preamble, or produce slightly malformed output. We try every trick.
        """
        if not text:
            return self._fallback(text)

        # Strategy 1: direct parse after stripping fences
        clean = re.sub(r"```(?:json)?|```", "", text).strip()
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass

        # Strategy 2: find first { ... } block (greedy, handles trailing prose)
        match = re.search(r"\{[\s\S]*\}", clean)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                # Strategy 3: fix common small-model JSON mistakes
                candidate = match.group()
                # Remove trailing commas before } or ]
                candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
                # Replace single quotes with double quotes
                candidate = re.sub(r"(?<![\\])'", '"', candidate)
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass

        # Strategy 4: extract fields manually with regex
        result = {}
        for field in ["kernel_report", "inner_thought", "suggested_message"]:
            # Match "field": "value" or "field": null
            m = re.search(
                rf'"{field}"\s*:\s*(?:"((?:[^"\\]|\\.)*)"|null)',
                clean, re.DOTALL
            )
            if m:
                result[field] = m.group(1) if m.group(1) is not None else None

        suggest_m = re.search(r'"suggest_initiate"\s*:\s*(true|false)', clean)
        if suggest_m:
            result["suggest_initiate"] = suggest_m.group(1) == "true"

        paths_m = re.search(r'"relevant_memory_paths"\s*:\s*(\[.*?\])', clean, re.DOTALL)
        if paths_m:
            try:
                result["relevant_memory_paths"] = json.loads(paths_m.group(1))
            except Exception:
                result["relevant_memory_paths"] = []

        if result.get("kernel_report") or result.get("inner_thought"):
            return result

        # Strategy 5: treat the whole response as an inner thought
        return self._fallback(clean)

    def _fallback(self, text: str) -> dict:
        """Last resort — treat raw text as inner thought."""
        clean = text.strip()[:300] if text else "..."
        return {
            "kernel_report": "Kernel scan complete.",
            "inner_thought": clean,
            "suggest_initiate": False,
            "suggested_message": None,
        }

    async def run_idle(self, recent_messages: List[Dict]) -> dict:
        """Full idle tick: kernel + reflection + optional initiation suggestion."""
        bus = get_bus()
        tick_count = self.state.get("tick_count", 0)

        system = (
            "You are an AI's inner voice and subconscious kernel. "
            "You MUST respond with ONLY a valid JSON object — no prose, no explanation, no markdown. "
            "Start your response with { and end with }. Nothing else."
        )

        prompt = await self.assembler.build_prompter_prompt(
            recent_messages=recent_messages,
            tick_count=tick_count,
            mode="idle",
        )

        raw = await self._call(prompt, system=system)
        result = self._parse_json(raw)

        kernel_report = result.get("kernel_report", "")
        inner_thought = result.get("inner_thought", "")
        suggest_initiate = result.get("suggest_initiate", False)
        suggested_message = result.get("suggested_message", None)

        if kernel_report:
            await bus.emit_inner_thought(kernel_report, kind="kernel")
        if inner_thought:
            await bus.emit_inner_thought(inner_thought, kind="thought")

        context_pressure = self.state.get("context_pressure", 0.0)
        if context_pressure > 0.75:
            cull_note = f"Context at {context_pressure:.0%} — flagging for culling."
            await bus.emit_inner_thought(cull_note, kind="kernel")
            result["suggest_cull"] = True
        else:
            result["suggest_cull"] = False

        result["kernel_report"] = kernel_report
        result["inner_thought"] = inner_thought
        result["suggest_initiate"] = suggest_initiate
        result["suggested_message"] = suggested_message

        return result

    async def run_active(self, recent_messages: List[Dict], incoming_message: str) -> dict:
        """Pre-response pass: fast memory selection + nudge."""
        bus = get_bus()
        tick_count = self.state.get("tick_count", 0)

        system = (
            "You are an AI's inner voice and subconscious kernel. "
            "You MUST respond with ONLY a valid JSON object — no prose, no explanation, no markdown. "
            "Start your response with { and end with }. Nothing else."
        )

        prompt = await self.assembler.build_prompter_prompt(
            recent_messages=recent_messages,
            tick_count=tick_count,
            mode="active",
        )

        raw = await self._call(prompt, system=system)
        result = self._parse_json(raw)

        kernel_report = result.get("kernel_report", "")
        inner_thought = result.get("inner_thought", "")
        relevant_paths = result.get("relevant_memory_paths", [])
        if not isinstance(relevant_paths, list):
            relevant_paths = []

        if kernel_report:
            await bus.emit_inner_thought(kernel_report, kind="kernel")
        if inner_thought:
            await bus.emit_inner_thought(inner_thought, kind="thought")

        # Load relevant memory files
        injected_memories = []
        for path in relevant_paths[:3]:
            if isinstance(path, str):
                content = await self.memory.read(path)
                if content:
                    injected_memories.append(f"### {path}\n{content[:800]}")

        result["injected_memories"] = injected_memories
        result["kernel_report"] = kernel_report
        result["inner_thought"] = inner_thought

        return result

    async def run_post(self, day_title_needed: bool, recent_messages: List[Dict]) -> None:
        """Post-response housekeeping: day titling. Only fires once per calendar day."""
        bus = get_bus()
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        already_titled = self.state.get("day_titled_date") == today

        if day_title_needed and recent_messages and not already_titled:
            try:
                recent_text = " ".join(
                    m.get("content", "")[:100] for m in recent_messages[-4:]
                )
                title_prompt = (
                    f"Give this conversation a short poetic title, 3-6 words, no quotes, "
                    f"no punctuation, just the title itself:\n\n{recent_text}"
                )
                raw = await self._call(title_prompt)
                # Strip any quotes, punctuation, keep only the title line
                title = raw.strip().split("\n")[0]
                title = re.sub(r'["\'/\\:*?<>|]', "", title).strip()[:60]
                if not title:
                    title = "Untitled"
                today = datetime.now().strftime("%Y-%m-%d")
                safe_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "_")
                path = f"days/{today}_{safe_title}.md"
                summary = "\n".join(
                    f"[{m.get('role','?')}]: {m.get('content','')[:200]}"
                    for m in recent_messages[-10:]
                )
                await self.memory.write(path, f"# {title}\n\n{summary}\n")
                self.state["day_titled_date"] = today
                await bus.emit_inner_thought(f"Titled today's conversation: '{title}'", kind="kernel")
                await bus.emit_memory_update(path, "write")
            except Exception as e:
                await bus.emit_inner_thought(f"Day titling failed: {e}", kind="kernel")
