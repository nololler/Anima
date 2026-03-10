import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from backend.config import get_config, reload_config
from backend.core.message_bus import get_bus
from backend.core.tick import get_tick_engine
from backend.core.persona import PersonaAssembler
from backend.core.prompter import Prompter
from backend.core.conversation import ConversationHandler
from backend.memory.banks import get_bank_manager
from backend.memory.context import ContextManager
from backend.tools.registry import setup_tools
from backend.users.manager import get_user_manager
from backend.connectors.discord import DiscordConnector


# ── Global state ──────────────────────────────────────────────────────────────

persona_state: dict = {
    "name": "Anima",
    "mood": "neutral",
    "mood_intensity": 5,
    "tick_count": 0,
    "bank": "default",
    "context_pressure": 0.0,
    "user_is_active": False,
    "setup_complete": False,
}

context_manager = ContextManager()
bank_manager = get_bank_manager()
memory_manager = bank_manager.get_manager()
persona_assembler = PersonaAssembler(memory_manager, persona_state)
prompter = Prompter(memory_manager, persona_assembler, persona_state)
conversation_handler = ConversationHandler(context_manager, persona_assembler, persona_state)

# Wire tools
setup_tools(memory_manager, context_manager, get_bus(), persona_state)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = get_config()
    persona_state["name"] = cfg.anima.name
    persona_state["bank"] = cfg.anima.active_memory_bank

    # Setup is complete if the config name has been changed from default
    # AND the self.md has real content (not the stub)
    self_content = await memory_manager.read_self()
    has_real_identity = (
        len(self_content.strip()) > 50 and
        "No identity configured yet" not in self_content and
        "Not yet defined" not in self_content
    )
    persona_state["setup_complete"] = has_real_identity

    # Start tick engine
    tick = get_tick_engine()
    tick.setup(prompter, conversation_handler, context_manager, persona_state)
    tick.start()

    # Start Discord connector (stub)
    discord = DiscordConnector(cfg.connectors.discord)
    asyncio.create_task(discord.start())

    yield

    tick.stop()


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
        # Send initial state
        await ws.send_text(json.dumps({
            "type": "init",
            "data": {
                "persona": persona_state,
                "tick_status": get_tick_engine().get_status(),
                "banks": bank_manager.list_banks(),
                "messages": [m.model_dump() for m in context_manager.get_all_messages()],
                "setup_complete": persona_state["setup_complete"],
            },
        }))

        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            await handle_ws_message(data, ws)

    except WebSocketDisconnect:
        bus.disconnect(ws)
        persona_state["user_is_active"] = False
    except Exception as e:
        bus.disconnect(ws)
        persona_state["user_is_active"] = False


async def handle_ws_message(data: dict, ws: WebSocket):
    bus = get_bus()
    msg_type = data.get("type")

    if msg_type == "chat":
        content = data.get("content", "").strip()
        if not content:
            return
        user_id = data.get("user_id", "user")
        username = data.get("username", "User")

        persona_state["user_is_active"] = True
        persona_state["last_message_time"] = datetime.now()

        user_mgr = get_user_manager()
        user_mgr.get_or_create_session(user_id, username)
        user_profile = await user_mgr.ensure_profile(username, memory_manager)

        # Run prompter (active mode)
        recent_msgs = context_manager.get_messages_for_llm()
        prompter_result = await prompter.run_active(recent_msgs, content)

        # Handle conversation
        await conversation_handler.handle_user_message(
            content=content,
            user_id=user_id,
            username=username,
            prompter_result=prompter_result,
            user_profile=user_profile,
        )

        user_mgr.record_message(user_id)

        # Post pass — only title the day if we have enough messages
        recent = context_manager.get_messages_for_llm()
        await prompter.run_post(
            day_title_needed=len(recent) >= 4,
            recent_messages=recent,
        )

    elif msg_type == "ping":
        await ws.send_text(json.dumps({"type": "pong"}))


# ── REST API ──────────────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    return {
        "persona": persona_state,
        "tick": get_tick_engine().get_status(),
        "banks": bank_manager.list_banks(),
        "active_bank": bank_manager.current_bank(),
        "context_pressure": context_manager.estimate_pressure(),
        "message_count": len(context_manager.get_all_messages()),
    }


@app.get("/api/memory/list")
async def list_memory(folder: str = ""):
    return memory_manager.list_files(folder)


@app.get("/api/memory/read")
async def read_memory(path: str):
    content = await memory_manager.read(path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"path": path, "content": content}


@app.get("/api/diary")
async def read_diary(date: Optional[str] = None):
    content = await memory_manager.read_diary(date)
    return {"date": date, "content": content}


@app.get("/api/diary/list")
async def list_diary():
    entries = memory_manager.list_files("diary")
    return entries


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

    await memory_manager.write("static/self.md", f"# {payload.name}\n\n{payload.identity}\n")
    persona_state["name"] = payload.name
    persona_state["setup_complete"] = True

    conversation_handler.invalidate_adapter()
    prompter._invalidate_adapter()

    await get_bus().broadcast("setup_complete", {"name": payload.name})
    return {"success": True}


class BankSwitchPayload(BaseModel):
    bank_name: str


@app.post("/api/bank/switch")
async def switch_bank(payload: BankSwitchPayload):
    async def summarize(msgs):
        prompt = await persona_assembler.build_summarizer_prompt(msgs)
        from backend.llm import create_adapter, Message
        adapter = create_adapter(get_config().main_llm)
        resp = await adapter.complete([Message(role="user", content=prompt)], max_tokens=300)
        return resp.content

    history = context_manager.get_messages_for_llm()
    result = await bank_manager.switch_bank(payload.bank_name, history, summarize)

    # Reset context and reload memory
    context_manager.clear()
    global memory_manager, persona_assembler, prompter, conversation_handler
    memory_manager = bank_manager.get_manager()
    persona_state["bank"] = payload.bank_name
    persona_assembler = PersonaAssembler(memory_manager, persona_state)
    prompter = Prompter(memory_manager, persona_assembler, persona_state)
    conversation_handler = ConversationHandler(context_manager, persona_assembler, persona_state)
    setup_tools(memory_manager, context_manager, get_bus(), persona_state)

    await get_bus().emit_bank_switch(result["old_bank"], result["new_bank"])
    return result


@app.post("/api/bank/create")
async def create_bank(payload: BankSwitchPayload):
    success = bank_manager.create_bank(payload.bank_name)
    return {"success": success, "bank": payload.bank_name}


@app.get("/api/banks")
async def list_banks():
    return {"banks": bank_manager.list_banks(), "active": bank_manager.current_bank()}

@app.get("/api/config")
async def get_full_config():
    cfg = get_config()
    return cfg.model_dump()
