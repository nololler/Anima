"""
Tool Registry
=============
Two tool sets:
  Main LLM tools — full autonomous capability
  Prompter tools — handled internally in prompter.py (no LLM tool-calling for 0.5B)

The Prompter does NOT use LLM tool-calling. It receives structured JSON
and executes actions directly in Python. This avoids reliability issues
with a 0.5B model trying to format tool calls.
"""

import json
from typing import Dict, Any, List, Callable, Optional
from backend.llm.base import ToolDefinition
from backend.memory.context import ContextMessage

_handlers: Dict[str, Callable] = {}
_definitions: Dict[str, ToolDefinition] = {}


def register_tool(definition: ToolDefinition, handler: Callable):
    _definitions[definition.name] = definition
    _handlers[definition.name] = handler


def get_main_llm_tools() -> List[ToolDefinition]:
    names = [
        "read_memory", "write_memory", "append_memory", "list_memory", "search_memory",
        "write_diary", "read_diary",
        "write_day_entry", "read_day",
        "update_person", "read_person",
        "read_image_manifest",
        "update_self",
        "set_mood",
        "report_state",
        "initiate_message",
        "set_tick_interval",
    ]
    return [_definitions[n] for n in names if n in _definitions]


async def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    if name not in _handlers:
        return {"error": f"Unknown tool: {name}"}
    try:
        return await _handlers[name](**args)
    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()[-400:]}


def setup_tools(memory_manager, context_manager, bus, persona_state, tick_engine_ref=None):
    """
    Register all Main LLM tools.
    tick_engine_ref is a callable that returns the tick engine (to avoid circular import).
    """

    # ── Memory ────────────────────────────────────────────────────────

    async def read_memory(path: str):
        result = await memory_manager.read(path)
        return result if result is not None else {"error": f"File not found: {path}"}

    async def write_memory(path: str, content: str):
        await memory_manager.write(path, content)
        await bus.emit_memory_update(path, "write")
        return {"success": True, "path": path}

    async def append_memory(path: str, content: str):
        await memory_manager.append(path, content)
        await bus.emit_memory_update(path, "append")
        return {"success": True, "path": path}

    async def list_memory(folder: str = ""):
        return memory_manager.list_files(folder)

    async def search_memory(query: str):
        return await memory_manager.search(query)

    register_tool(ToolDefinition(
        name="read_memory",
        description="Read any file from your memory bank by relative path (e.g. 'static/self.md', 'people/Alice.md').",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    ), read_memory)

    register_tool(ToolDefinition(
        name="write_memory",
        description="Create or overwrite a file in your memory bank. Use .md extension. Do not use for diary or day files.",
        parameters={"type": "object", "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        }, "required": ["path", "content"]},
    ), write_memory)

    register_tool(ToolDefinition(
        name="append_memory",
        description="Append content to an existing memory file.",
        parameters={"type": "object", "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
        }, "required": ["path", "content"]},
    ), append_memory)

    register_tool(ToolDefinition(
        name="list_memory",
        description="List files and folders in your memory bank. Leave folder empty for root listing.",
        parameters={"type": "object", "properties": {"folder": {"type": "string"}}, "required": []},
    ), list_memory)

    register_tool(ToolDefinition(
        name="search_memory",
        description="Full-text search across all memory files.",
        parameters={"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    ), search_memory)

    # ── Diary ─────────────────────────────────────────────────────────

    async def write_diary(content: str):
        await memory_manager.write_diary(content)
        await bus.emit_memory_update("diary/today.md", "append")
        return {"success": True}

    async def read_diary(date: str = None):
        result = await memory_manager.read_diary(date)
        return result if result is not None else {"error": "No diary entry for that date"}

    register_tool(ToolDefinition(
        name="write_diary",
        description="Write a personal diary entry for today. Timestamped automatically.",
        parameters={"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]},
    ), write_diary)

    register_tool(ToolDefinition(
        name="read_diary",
        description="Read diary entries. Specify date as YYYY-MM-DD or omit for today.",
        parameters={"type": "object", "properties": {"date": {"type": "string"}}, "required": []},
    ), read_diary)

    # ── Days (date-gated) ─────────────────────────────────────────────

    async def write_day_entry(content: str, title: Optional[str] = None):
        result = await memory_manager.write_day_entry(content, title)
        await bus.emit_memory_update(result["path"], result["action"])
        return result

    async def read_day(date: str = None):
        result = await memory_manager.read_day(date)
        return result if result is not None else {"error": f"No day file for {date or 'today'}"}

    register_tool(ToolDefinition(
        name="write_day_entry",
        description=(
            "Log an entry to today's day file. Creates new file if it's a new day (with optional title). "
            "Appends if file exists. ONLY works for today — cannot write past or future dates."
        ),
        parameters={"type": "object", "properties": {
            "content": {"type": "string"},
            "title": {"type": "string", "description": "Title for new day file (first entry only)"},
        }, "required": ["content"]},
    ), write_day_entry)

    register_tool(ToolDefinition(
        name="read_day",
        description="Read a day log. Specify date as YYYY-MM-DD or omit for today.",
        parameters={"type": "object", "properties": {"date": {"type": "string"}}, "required": []},
    ), read_day)

    # ── People ────────────────────────────────────────────────────────

    async def update_person(name: str, content: str):
        await memory_manager.update_person(name, content)
        await bus.emit_memory_update(f"people/{name}.md", "write")
        return {"success": True, "name": name}

    async def read_person(name: str):
        result = await memory_manager.read_person(name)
        return result if result is not None else {"error": f"No profile for {name}"}

    register_tool(ToolDefinition(
        name="update_person",
        description="Create or update a memory profile for a person. Use when meeting someone new or learning something worth remembering about them.",
        parameters={"type": "object", "properties": {
            "name": {"type": "string"},
            "content": {"type": "string"},
        }, "required": ["name", "content"]},
    ), update_person)

    register_tool(ToolDefinition(
        name="read_person",
        description="Read a person's memory profile by name.",
        parameters={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    ), read_person)

    # ── Images ────────────────────────────────────────────────────────

    async def read_image_manifest():
        return await memory_manager.read_image_manifest()

    register_tool(ToolDefinition(
        name="read_image_manifest",
        description="Read the manifest of all images saved in memory. Shows names, dates, descriptions, and who sent them.",
        parameters={"type": "object", "properties": {}, "required": []},
    ), read_image_manifest)

    # ── Self ──────────────────────────────────────────────────────────

    async def update_self(content: str, mode: str = "append"):
        if mode == "append":
            await memory_manager.append("static/self.md", content)
        else:
            await memory_manager.write("static/self.md", content)
        await bus.emit_memory_update("static/self.md", mode)
        return {"success": True, "mode": mode}

    async def set_mood(mood: str, intensity: int):
        persona_state["mood"] = mood
        persona_state["mood_intensity"] = max(1, min(10, intensity))
        await bus.emit_mood_update(mood, persona_state["mood_intensity"])
        return {"mood": mood, "intensity": persona_state["mood_intensity"]}

    register_tool(ToolDefinition(
        name="update_self",
        description="Update your own identity file (static/self.md). Append reflections or overwrite entirely.",
        parameters={"type": "object", "properties": {
            "content": {"type": "string"},
            "mode": {"type": "string", "enum": ["overwrite", "append"]},
        }, "required": ["content"]},
    ), update_self)

    register_tool(ToolDefinition(
        name="set_mood",
        description="Update your displayed mood and intensity (1-10).",
        parameters={"type": "object", "properties": {
            "mood": {"type": "string"},
            "intensity": {"type": "integer", "minimum": 1, "maximum": 10},
        }, "required": ["mood", "intensity"]},
    ), set_mood)

    # ── State report ──────────────────────────────────────────────────

    async def report_state(mood: str, energy: str, note: str = ""):
        context_manager.update_state_report({"mood": mood, "energy": energy, "note": note})
        persona_state["mood"] = mood
        await bus.emit_mood_update(mood, persona_state.get("mood_intensity", 5))
        await bus.emit_inner_thought(
            f"[state] mood={mood} energy={energy} — {note}", kind="kernel"
        )
        return {"success": True}

    register_tool(ToolDefinition(
        name="report_state",
        description=(
            "Record your current inner state for your subconscious kernel. "
            "Call this at the end of idle reflection. "
            "The kernel reads this every tick to understand how you're doing."
        ),
        parameters={"type": "object", "properties": {
            "mood": {"type": "string", "description": "Current mood in one word"},
            "energy": {"type": "string", "enum": ["low", "medium", "high"]},
            "note": {"type": "string", "description": "One sentence about your current state"},
        }, "required": ["mood", "energy"]},
    ), report_state)

    # ── Conversation initiation ───────────────────────────────────────

    async def initiate_message(message: str):
        msg = ContextMessage.create(role="assistant", content=message, ai_initiated=True)
        context_manager.add_message(msg)
        await bus.emit_chat_message(
            role="assistant", content=message, msg_id=msg.id, ai_initiated=True
        )
        return {"sent": True}

    register_tool(ToolDefinition(
        name="initiate_message",
        description="Send a message to the user on your own initiative without being prompted. Use when you genuinely want to reach out.",
        parameters={"type": "object", "properties": {
            "message": {"type": "string"},
        }, "required": ["message"]},
    ), initiate_message)

    # ── System ────────────────────────────────────────────────────────

    async def set_tick_interval(minutes: int):
        from backend.config import get_config
        cfg = get_config()
        cfg.tick.interval_minutes = max(1, min(60, minutes))
        cfg.save()
        if tick_engine_ref:
            engine = tick_engine_ref()
            if engine:
                engine.reschedule(cfg.tick.interval_minutes)
        return {"interval_minutes": cfg.tick.interval_minutes}

    register_tool(ToolDefinition(
        name="set_tick_interval",
        description="Change how often your internal tick fires, in minutes (1-60).",
        parameters={"type": "object", "properties": {
            "minutes": {"type": "integer", "minimum": 1, "maximum": 60},
        }, "required": ["minutes"]},
    ), set_tick_interval)
