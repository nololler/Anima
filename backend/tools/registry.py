import json
from typing import Dict, Any, List, Optional, Callable
from backend.llm.base import ToolDefinition

_handlers: Dict[str, Callable] = {}
_definitions: Dict[str, ToolDefinition] = {}


def register_tool(definition: ToolDefinition, handler: Callable):
    _definitions[definition.name] = definition
    _handlers[definition.name] = handler


def get_all_definitions() -> List[ToolDefinition]:
    return list(_definitions.values())


def get_main_llm_tools() -> List[ToolDefinition]:
    main_tools = [
        "read_memory", "write_memory", "append_memory", "list_memory", "search_memory",
        "write_diary", "read_diary",
        "update_person", "read_person",
        "update_self", "set_mood",
        "initiate_conversation", "set_tick_interval",
    ]
    return [_definitions[n] for n in main_tools if n in _definitions]


def get_prompter_tools() -> List[ToolDefinition]:
    prompter_tools = [
        "read_memory", "list_memory", "search_memory",
        "append_memory", "write_memory",
        "write_diary", "update_person", "set_mood",
    ]
    return [_definitions[n] for n in prompter_tools if n in _definitions]


async def execute_tool(name: str, args: Dict[str, Any]) -> Any:
    if name not in _handlers:
        return {"error": f"Unknown tool: {name}"}
    try:
        result = await _handlers[name](**args)
        return result
    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()[-400:]}


def setup_tools(memory_manager, context_manager, bus, persona_state):

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
        description="Read a file from long-term memory by path (e.g. 'static/favorites.md', 'people/Alice.md')",
        parameters={"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
    ), read_memory)

    register_tool(ToolDefinition(
        name="write_memory",
        description="Create or overwrite a memory file.",
        parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    ), write_memory)

    register_tool(ToolDefinition(
        name="append_memory",
        description="Append content to an existing memory file.",
        parameters={"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]},
    ), append_memory)

    register_tool(ToolDefinition(
        name="list_memory",
        description="List files and folders in a memory directory. Leave folder empty for root.",
        parameters={"type": "object", "properties": {"folder": {"type": "string"}}, "required": []},
    ), list_memory)

    register_tool(ToolDefinition(
        name="search_memory",
        description="Search across all memory files by keyword.",
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
        description="Write an entry in your personal diary for today.",
        parameters={"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]},
    ), write_diary)

    register_tool(ToolDefinition(
        name="read_diary",
        description="Read diary entries. Specify date as YYYY-MM-DD or omit for today.",
        parameters={"type": "object", "properties": {"date": {"type": "string"}}, "required": []},
    ), read_diary)

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
        description="Create or update a profile for a person you know.",
        parameters={"type": "object", "properties": {"name": {"type": "string"}, "content": {"type": "string"}}, "required": ["name", "content"]},
    ), update_person)

    register_tool(ToolDefinition(
        name="read_person",
        description="Read a person's profile by name.",
        parameters={"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
    ), read_person)

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
        description="Update your own identity file. Append new reflections or overwrite entirely.",
        parameters={"type": "object", "properties": {
            "content": {"type": "string"},
            "mode": {"type": "string", "enum": ["overwrite", "append"]},
        }, "required": ["content"]},
    ), update_self)

    register_tool(ToolDefinition(
        name="set_mood",
        description="Update your current mood and intensity (1-10).",
        parameters={"type": "object", "properties": {
            "mood": {"type": "string"},
            "intensity": {"type": "integer", "minimum": 1, "maximum": 10},
        }, "required": ["mood", "intensity"]},
    ), set_mood)

    # ── Conversation ──────────────────────────────────────────────────

    async def initiate_conversation(message: str, urgency: str = "low"):
        from backend.memory.context import ContextMessage
        msg = ContextMessage.create(role="assistant", content=message, ai_initiated=True)
        context_manager.add_message(msg)
        await bus.emit_chat_message(
            role="assistant", content=message, msg_id=msg.id, ai_initiated=True
        )
        return {"sent": True, "urgency": urgency}

    register_tool(ToolDefinition(
        name="initiate_conversation",
        description="Send a message to the user on your own initiative without being prompted. Use when you genuinely want to reach out.",
        parameters={"type": "object", "properties": {
            "message": {"type": "string"},
            "urgency": {"type": "string", "enum": ["low", "medium", "high"]},
        }, "required": ["message"]},
    ), initiate_conversation)

    # ── System ────────────────────────────────────────────────────────

    async def set_tick_interval(minutes: int):
        from backend.config import get_config
        from backend.core.tick import get_tick_engine
        cfg = get_config()
        cfg.tick.interval_minutes = max(1, min(60, minutes))
        cfg.save()
        get_tick_engine().reschedule(cfg.tick.interval_minutes)
        return {"interval_minutes": cfg.tick.interval_minutes}

    register_tool(ToolDefinition(
        name="set_tick_interval",
        description="Change how often your internal tick fires, in minutes (1-60).",
        parameters={"type": "object", "properties": {"minutes": {"type": "integer", "minimum": 1, "maximum": 60}}, "required": ["minutes"]},
    ), set_tick_interval)
