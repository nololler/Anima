"""
Anima — FastAPI Application
============================
Wiring order:
  1. Config loaded
  2. AppState container built (single source of truth for all live objects)
  3. Tools registered against AppState references
  4. TickEngine wired to AppState
  5. WebSocket and REST handlers read from AppState

All mutable global state lives in AppState. No bare module-level globals
except the single `state` instance and the FastAPI `app`.
"""
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import get_config, reload_config
from backend.core.message_bus import get_bus
from backend.core.tick import get_tick_engine
from backend.core.prompter import Prompter
from backend.core.conversation import ConversationHandler
from backend.memory.banks import get_bank_manager
from backend.memory.context import ContextManager
from backend.tools.registry import setup_tools
from backend.users.manager import get_user_manager
from backend.connectors.discord import DiscordConnector


# ── AppState ──────────────────────────────────────────────────────────────────

class AppState:
    """
    Single container for all live application objects.
    Passed by reference so bank-switch rebuilds are reflected everywhere.
    """
    def __init__(self):
        cfg = get_config()
        self.persona: dict = {
            "name": cfg.anima.name,
            "mood": "neutral",
            "mood_intensity": 5,
            "tick_count": 0,
            "bank": cfg.anima.active_memory_bank,
            "context_pressure": 0.0,
            "entity_state": "idle",
            "user_is_active": False,
            "setup_complete": False,
        }

        self.bank_manager = get_bank_manager()
        self.context = ContextManager()

        # These three get rebuilt on bank switch
        self.memory = self.bank_manager.get_manager()
        self.prompter = Prompter(self.memory, self.context, self.persona)
        self.conversation = ConversationHandler(self.context, self.memory, self.persona)

    def rebuild_for_bank(self, bank_name: str):
        """Rebuild memory-dependent objects after a bank switch."""
        self.persona["bank"] = bank_name
        self.memory = self.bank_manager.get_manager()
        self.prompter = Prompter(self.memory, self.context, self.persona)
        self.conversation = ConversationHandler(self.context, self.memory, self.persona)
        # Re-wire tools with new memory manager
        setup_tools(self.memory, self.context, get_bus(), self.persona)
        # Re-wire tick engine
        tick = get_tick_engine()
        tick.setup(self.prompter, self.conversation, self.context, self.persona)


# Singleton AppState
state = AppState()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup complete check
    self_content = await state.memory.read_self()
    state.persona["setup_complete"] = (
        len(self_content.strip()) > 50
        and "No identity configured yet" not in self_content
        and "Not yet defined" not in self_content
    )

    # Register tools
    setup_tools(state.memory, state.context, get_bus(), state.persona)

    # Wire and start tick engine
    tick = get_tick_engine()
    tick.setup(state.prompter, state.conversation, state.context, state.persona)
    tick.start()

    # Discord stub
    cfg = get_config()
    discord = DiscordConnector(cfg.connectors.discord)
    asyncio.create_task(discord.start())

    yield

    tick.stop()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Anima", lifespan=lifespan)

cfg = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.server.cors_origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    bus = get_bus()
    await bus.connect(ws)
    try:
        await ws.send_text(json.dumps({
            "type": "init",
            "data": {
                "persona": state.persona,
                "tick_status": get_tick_engine().get_status(),
                "banks": state.bank_manager.list_banks(),
                "messages": [m.model_dump() for m in state.context.get_all_messages()],
                "setup_complete": state.persona["setup_complete"],
            },
        }))
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            await _handle_ws(data, ws)

    except WebSocketDisconnect:
        bus.disconnect(ws)
        state.persona["user_is_active"] = False
    except Exception as e:
        bus.disconnect(ws)
        state.persona["user_is_active"] = False


async def _handle_ws(data: dict, ws: WebSocket):
    bus = get_bus()
    msg_type = data.get("type")

    if msg_type == "chat":
        content = data.get("content", "").strip()
        if not content:
            return

        user_id = data.get("user_id", "user")
        username = data.get("username", "User")

        # Update tick engine state
        get_tick_engine().record_user_message()

        # Ensure user profile exists
        user_mgr = get_user_manager()
        user_mgr.get_or_create_session(user_id, username)
        user_profile = await user_mgr.ensure_profile(username, state.memory)

        # Build a lightweight prompter status for active messages
        # (not a full tick — just context pressure info)
        pressure = state.context.estimate_pressure()
        injected = state.context.get_injected_paths()
        prompter_status = (
            f"Context: {pressure:.0%} full. "
            f"Injected memories: {injected if injected else 'none'}."
        )

        await state.conversation.handle_user_message(
            content=content,
            username=username,
            user_profile=user_profile,
            prompter_status=prompter_status,
        )
        user_mgr.record_message(user_id)

    elif msg_type == "ping":
        await ws.send_text(json.dumps({"type": "pong"}))


# ── REST API ──────────────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    return {
        "persona": state.persona,
        "tick": get_tick_engine().get_status(),
        "banks": state.bank_manager.list_banks(),
        "active_bank": state.bank_manager.current_bank(),
        "context": state.context.message_count(),
        "context_pressure": state.context.estimate_pressure(),
    }


@app.get("/api/memory/list")
async def list_memory(folder: str = ""):
    return state.memory.list_files(folder)


@app.get("/api/memory/read")
async def read_memory(path: str):
    content = await state.memory.read(path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": content}


@app.get("/api/diary")
async def read_diary(date: Optional[str] = None):
    content = await state.memory.read_diary(date)
    return {"date": date, "content": content}


@app.get("/api/diary/list")
async def list_diary():
    return state.memory.list_files("diary")


@app.get("/api/config")
async def get_full_config():
    return get_config().model_dump()


# ── Setup ─────────────────────────────────────────────────────────────────────

class SetupPayload(BaseModel):
    name: str
    identity: str
    main_provider: str
    main_model: str
    main_base_url: str = "http://localhost:11434"
    main_api_key: str = ""
    main_vision: bool = False
    prompter_provider: str
    prompter_model: str
    prompter_base_url: str = "http://localhost:11434"
    prompter_api_key: str = ""
    tick_interval: int = 1


@app.post("/api/setup")
async def setup(payload: SetupPayload):
    cfg = get_config()
    cfg.anima.name = payload.name
    cfg.main_llm.provider = payload.main_provider
    cfg.main_llm.model = payload.main_model
    cfg.main_llm.base_url = payload.main_base_url
    cfg.main_llm.api_key = payload.main_api_key
    cfg.main_llm.vision = payload.main_vision
    cfg.prompter_llm.provider = payload.prompter_provider
    cfg.prompter_llm.model = payload.prompter_model
    cfg.prompter_llm.base_url = payload.prompter_base_url
    cfg.prompter_llm.api_key = payload.prompter_api_key
    cfg.tick.interval_minutes = payload.tick_interval
    cfg.save()

    await state.memory.write("static/self.md", f"# {payload.name}\n\n{payload.identity}\n")
    state.persona["name"] = payload.name
    state.persona["setup_complete"] = True

    state.conversation.invalidate_adapter()
    state.prompter.invalidate_adapter()

    await get_bus().broadcast("setup_complete", {"name": payload.name})
    return {"success": True}


# ── Bank management ───────────────────────────────────────────────────────────

class BankPayload(BaseModel):
    bank_name: str


@app.post("/api/bank/switch")
async def switch_bank(payload: BankPayload):
    async def summarize(msgs):
        from backend.llm import create_adapter, Message
        from backend.core.conversation import build_system_prompt
        adapter = create_adapter(get_config().main_llm)
        lines = [f"[{m['role']}]: {m['content'][:300]}" for m in msgs]
        prompt = (
            "Summarize this conversation in 2-3 paragraphs. "
            "First person, emotional tone, capture what matters.\n\n"
            + "\n".join(lines)
        )
        resp = await adapter.complete(
            [Message(role="user", content=prompt)], max_tokens=400
        )
        return resp.content

    history = state.context.get_messages_for_llm()
    result = await state.bank_manager.switch_bank(payload.bank_name, history, summarize)

    state.context.clear()
    state.rebuild_for_bank(payload.bank_name)

    await get_bus().emit_bank_switch(result["old_bank"], result["new_bank"])
    return result


@app.post("/api/bank/create")
async def create_bank(payload: BankPayload):
    success = state.bank_manager.create_bank(payload.bank_name)
    return {"success": success, "bank": payload.bank_name}


@app.get("/api/banks")
async def list_banks():
    return {
        "banks": state.bank_manager.list_banks(),
        "active": state.bank_manager.current_bank(),
    }
