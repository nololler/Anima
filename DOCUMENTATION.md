## Anima – Full Project Documentation

### 1. Overview

Anima is a **persistent AI entity** with genuine memory, inner life, and an autonomous presence. It combines:
- **Backend**: Python + FastAPI, an internal tick engine, a prompter “subconscious” model, and a main LLM with tools.
- **Frontend**: React + Vite + Tailwind, providing panels for chat, inner thoughts, memory browsing, diary reading, and system logs.
- **Memory banks**: Markdown files on disk that model identity, relationships, daily experiences, and diary entries across named banks.

Users converse with Anima over WebSocket; the backend maintains conversational context, periodically runs reflective ticks, and stores long‑term memories in the active memory bank.

---

### 2. Project Structure

At a high level:

- **Backend**
  - `backend/main.py`: FastAPI app, WebSocket endpoint, REST endpoints, global persona state, and lifecycle wiring.
  - `backend/config.py`: Typed configuration using Pydantic, backed by `config.yaml`.
  - `backend/core/`:
    - `tick.py`: Tick engine for periodic idle reflection.
    - `prompter.py`: “Subconscious” kernel model, produces inner thoughts and memory hints.
    - `conversation.py`: Main LLM loop, tool execution, and context updates.
    - `persona.py`: Assembles system prompts from identity, mood, and memories.
    - `message_bus.py`: Event bus from backend to WebSocket clients.
  - `backend/memory/`:
    - `manager.py`: File‑backed memory manager per bank.
    - `context.py`: In‑RAM conversational context and token pressure tracking.
    - `banks.py`: Manages active memory bank and switching.
  - `backend/tools/registry.py`: Tool registry and handlers exposed to LLMs.
  - `backend/llm/`: Provider‑agnostic LLM adapters (Ollama, OpenAI, Anthropic, OpenAI‑compatible).
  - `backend/connectors/`: Common connector base and a stub Discord connector.
  - `backend/users/manager.py`: Simple per‑user session/profile manager.

- **Frontend**
  - `frontend/src/main.jsx`: React entry point.
  - `frontend/src/App.jsx`: Layout and state orchestration.
  - `frontend/src/hooks/`: `useWebSocket`, `useDragResize`.
  - `frontend/src/components/`: `StatusBar`, `SetupWizard`, `SettingsPanel`.
  - `frontend/src/panels/`: `ChatPanel`, `InnerThoughtsPanel`, `MemoryBrowser`, `DiaryViewer`, `TickLog`.

- **Memory & Config**
  - `config.yaml`: Runtime configuration for models, tick interval, server, and connectors.
  - `memory_banks/`: On‑disk representation of identity, people, days, diary, and images per bank.

---

### 3. Configuration & Runtime Settings

#### 3.1 `config.yaml` and `backend/config.py`

The **source of truth** for runtime behavior is `config.yaml`, mapped into Pydantic models in `backend/config.py`:

- **AnimaConfig**
  - `name`: Display name of the entity (also used by the Setup Wizard).
  - `active_memory_bank`: Which memory bank is active at startup.
  - `version`: Project version tag.

- **LLMConfig** (`main_llm`, `prompter_llm`)
  - `provider`: `"ollama" | "openai" | "anthropic" | "openai_compatible"`.
  - `model`: Model ID (e.g. `qwen2.5:7b`).
  - `base_url`: HTTP endpoint (Ollama, or OpenAI‑compatible gateway).
  - `api_key`: Secret for cloud providers / compatible backends.
  - `temperature`, `context_limit`, `vision`: Sampling and context tuning.

- **TickConfig**
  - `interval_minutes`: How often the idle tick fires.
  - `enabled`: Global on/off for ticking.

- **ServerConfig**
  - `host`, `port`: FastAPI bind address and port.
  - `cors_origins`: Frontend origins allowed for REST.

- **ConnectorsConfig**
  - `discord`: `enabled`, `token`, `guild_id`, `channel_ids` (currently used by stub).

`backend.config` provides:
- `get_config()`: Lazily loads and caches the config.
- `reload_config()`: Forces reload from disk.
- `Config.save()`: Persists updated configuration back to `config.yaml`.

Changes made by the frontend (via `/api/setup`) or backend tools flow through this layer and are effective on the next use of the LLM adapters.

---

### 4. Backend Architecture

#### 4.1 Application Lifecycle (`backend/main.py`)

The FastAPI app is declared with a **lifespan context**:
- Loads `config.yaml` and initializes `persona_state` (name, active bank, mood, tick count, context pressure, setup flag).
- Creates a `ContextManager`, `BankManager` and its `MemoryManager`, `PersonaAssembler`, `Prompter`, and `ConversationHandler`.
- Registers all tools with the global `MessageBus` in `backend.tools.registry.setup_tools()`.
- Starts the **tick engine** (`TickEngine`) with references to the prompter, conversation handler, context manager, and persona state.
- Optionally starts the Discord connector (stub) if enabled.

On shutdown, the tick engine is stopped.

#### 4.2 WebSocket API

The WebSocket endpoint at **`/ws`**:
- On connect:
  - Registers the socket with the global `MessageBus`.
  - Immediately sends an `init` event: persona snapshot, tick status, available banks, full conversation history, and `setup_complete` flag.
- In the main loop:
  - Receives JSON messages from the frontend and dispatches them to `handle_ws_message`.

Supported message types:
- **`chat`**:
  - Fields: `content`, `user_id` (default `"user"`), `username` (default `"User"`).
  - Marks the user as active, updates `last_message_time`.
  - Ensures the user has a profile in memory via `UserManager`.
  - Runs the **Prompter** in active mode to produce kernel report, inner thought, and memory hints.
  - Passes everything to the **ConversationHandler**, which calls the main LLM and tools.
  - Updates user message counters and runs a **post‑pass** in the Prompter for day titling (if enough messages).

- **`ping`**: Responds with a `pong` event to keep the connection alive.

Errors and disconnections:
- On disconnect, the `MessageBus` is updated and `user_is_active` is reset.
- On errors, the bus disconnects the socket and logs an `error` event.

#### 4.3 REST API

Key REST endpoints:
- `GET /api/status`:
  - Returns persona state, tick status, banks list + active bank, context pressure, and message count.

- `GET /api/memory/list?folder=...`:
  - Lists files/folders in the active memory bank subtree.

- `GET /api/memory/read?path=...`:
  - Reads a markdown file from the active memory bank by relative path.

- `GET /api/diary?date=YYYY-MM-DD`:
  - Returns diary content for a given date (or today when omitted).

- `GET /api/diary/list`:
  - Lists diary entries as file metadata.

- `POST /api/setup`:
  - Takes `SetupPayload` (name, identity, providers, models, base URLs, API keys, tick interval).
  - Updates `config.yaml` accordingly.
  - Writes the identity markdown to `static/self.md`.
  - Refreshes persona state and invalidates LLM adapters so new settings apply.
  - Broadcasts `setup_complete`.

- `POST /api/bank/switch`:
  - Switches to another memory bank using `BankManager`, with auto‑summary of current conversation stored in the “old” bank.
  - Clears context, rebuilds memory/assembler/prompter/conversation handler for the new bank, and re‑wires tools.
  - Broadcasts `bank_switch`.

- `POST /api/bank/create`:
  - Creates a new memory bank folder structure.

- `GET /api/banks`:
  - Returns `{ banks: [...], active: "..." }`.

- `GET /api/config`:
  - Returns the current configuration as JSON.

---

### 5. Memory System

#### 5.1 On‑Disk Memory Banks

Each bank lives under `memory_banks/<bank_name>/` and follows the structure:

- `static/self.md`: Core identity of the AI.
- `static/favorites.md`: Optional favorites/preferences file.
- `people/*.md`: Per‑person profiles (`<Name>.md`).
- `days/*.md`: Day summaries (titles plus summaries of recent messages).
- `diary/*.md`: Daily diary entries (multi‑timestamp).
- `images/`: Placeholder for VLM‑backed image memory.
- `index.md`: A simple index that can be updated by tools.

`MemoryManager` is responsible for:
- Creating the necessary directory structure and stub files (`index.md`, `static/self.md`) if missing.
- Safe path resolution within the bank (prevents `..` traversal).
- Async read/write/append for arbitrary markdown paths.
- Listing files/folders with metadata (name, path, type, size, mtime).
- Full‑bank keyword search across `.md` files.
- Diary helpers: `write_diary()` and `read_diary()`.
- Person helpers: `update_person()` and `read_person()`.

#### 5.2 Bank Manager & Switching

`BankManager` (`backend/memory/banks.py`) wraps `MemoryManager` to manage the active bank:
- Lazily constructs a `MemoryManager` based on `config.anima.active_memory_bank`.
- Exposes:
  - `get_manager()`: Returns the `MemoryManager` for the current bank.
  - `current_bank()`: Returns the current bank name.
  - `list_banks()`: Static enumeration of available banks.
  - `create_bank(name)`: Creates a new bank by constructing a new `MemoryManager`.
  - `switch_bank(new_bank, conversation_history, summarizer_fn)`:
    - Optionally builds a **summary** of the conversation via `PersonaAssembler.build_summarizer_prompt`.
    - Appends a pre‑switch summary note into the old bank’s `days` folder.
    - Updates `config.anima.active_memory_bank` and saves.
    - Replaces the internal `MemoryManager` instance.

The FastAPI layer ensures that after a bank switch, global references (memory manager, persona assembler, prompter, conversation handler) are rebuilt, and tools re‑registered.

#### 5.3 In‑Memory Conversation Context

`ContextManager` maintains in‑RAM conversation state:
- Stores a list of `ContextMessage` objects, each with:
  - `id`, `role`, `content`, `timestamp`, optional `culled` flag, `ai_initiated`, `tool_calls`, and `tool_call_id`.
- Provides:
  - `add_message()`, `get_active_messages()`, `get_all_messages()`.
  - Token‑pressure estimation:
    - `estimate_pressure()` returns \(0.0–1.0\) fraction of context limit.
    - `estimate_tokens_used()` returns an approximate token count.
  - Culling tools:
    - `get_summary_candidates(n)`: Returns the oldest active messages excluding the last 5, for potential summarization.
    - `cull_messages(ids)`: Marks messages as culled for LLM context while keeping them visible in the UI.
  - Serialization for LLM:
    - `get_messages_for_llm()` returns a list of dicts containing roles, content, and optional tool metadata.

This context is used both by the prompter and by the main LLM for conversation and idle ticks.

---

### 6. Tick Engine & Inner Life

#### 6.1 Tick Engine

The `TickEngine` (`backend/core/tick.py`) is responsible for:
- Scheduling periodic ticks using `apscheduler.AsyncIOScheduler`.
- Tracking:
  - `tick_count`
  - `last_tick_time`, `next_tick_time`
  - Running state and a separate countdown loop.
- On `start()`:
  - Reads the tick interval and enabled flag from `Config`.
  - Schedules `_tick` as an interval job.
  - Starts a countdown task that sends `tick_countdown` events every 10 seconds.

On each `_tick()`:
- Increments `tick_count` and updates persona state (`tick_count`, `context_pressure`).
- If there is no user activity for more than 2 minutes, auto‑resets `user_is_active` to `False`.
- Determines `mode`:
  - `"active"` if `persona_state.user_is_active` is true.
  - `"idle"` otherwise.
- Emits a `tick` event with number and mode.
- For idle mode:
  - Runs the **Prompter**’s `run_idle()` with recent messages.
  - Passes the promper’s result into `ConversationHandler.handle_idle_tick()` to allow the main LLM to reflect, use tools, or perform memory culling.

`reschedule()` and `get_status()` allow dynamic adjustment of tick frequency and status reporting.

#### 6.2 Prompter (“Subconscious Kernel”)

`Prompter` (`backend/core/prompter.py`) is a separate LLM (often smaller/faster) that:
- Maintains its own adapter configured via `prompter_llm`.
- Provides:
  - `_call()`: Helper that enforces JSON‑only responses and robustly handles errors.
  - `_parse_json()`: Multi‑strategy JSON extraction (handles fenced code, trailing prose, minor JSON errors, and falls back to structured extraction or plain inner thoughts).

Main workflows:
- **Idle mode (`run_idle`)**:
  - Builds a prompter prompt via `PersonaAssembler.build_prompter_prompt(mode="idle")`.
  - Expects strict JSON with `kernel_report`, `inner_thought`, `suggest_initiate`, `suggested_message`.
  - Emits `inner_thought` events for the kernel report and inner thought.
  - Adds context‑pressure‑based hints (and `suggest_cull`) if pressure exceeds a threshold.

- **Active mode (`run_active`)**:
  - Similar to idle but `mode="active"`, focusing on relevant memories for the current user message.
  - Yields:
    - `kernel_report`, `inner_thought`, and `relevant_memory_paths`.
    - Loads up to three memory files and attaches their content into `injected_memories`.

- **Post‑response (`run_post`)**:
  - Decides when to **title the day** based on message count since the last message.
  - Asks the prompter (or main LLM) for a short poetic title and writes a summary note into `days/<date>_<Title>.md`.
  - Emits a kernel thought about the new title and a memory update.

#### 6.3 Persona Assembler (System Prompt)

`PersonaAssembler` combines:
- Identity (`self.md`).
- Live persona state (mood, intensity, tick count, bank).
- User profile (per‑username markdown).
- Injected memories.
- Kernel report and inner thoughts.

Core methods:
- `build_main_prompt()`: Produces a rich Markdown system prompt for the main LLM, including:
  - Identity and user information.
  - Relevant memories.
  - Kernel report and an `<inner_thought>` section.
  - Core behavioral guidelines (Anima as an entity, not a helper).

- `build_prompter_prompt()`: Produces a concise view of recent conversation and mood tailored to the Prompter, with precise instructions to output strict JSON.

- `build_summarizer_prompt()`: Compresses a list of messages into a summarization prompt for cross‑bank summaries.

---

### 7. Conversation Loop & Tools

#### 7.1 ConversationHandler (Main LLM)

`ConversationHandler` coordinates the main message flow:
- Lazily constructs a main LLM adapter using `Config.main_llm`.
- Converts the active context into `Message` objects.

On user messages (`handle_user_message()`):
- Adds the user message to the context and emits a `chat_message` event.
- Uses `PersonaAssembler.build_main_prompt()` to construct a system prompt that includes:
  - Kernel report and inner thoughts from the Prompter.
  - Injected memories and user profile.
- Calls the main LLM with:
  - The message history from `ContextManager`.
  - Tool definitions from `get_main_llm_tools()`.
  - A maximum token limit for the response.

Tools are handled as follows:
- If the LLM returns `tool_calls`:
  - Each tool call’s arguments are parsed as JSON.
  - `execute_tool()` in `backend.tools.registry` is invoked with those arguments.
  - A `tool_call` event is emitted to the bus with truncated results.
  - Tool outputs are injected as an intermediate assistant message in context.
  - A **second completion** is performed without tools, letting the LLM craft a final user‑visible response that considers tool results.

The final response:
- Is streamed out via a simulated streaming mechanism (`chat_stream` events).
- Is then added as an assistant message to context.
- Is emitted as a permanent `chat_message`.

On idle ticks (`handle_idle_tick()`):
- Uses a simple user prompt describing quietness and optional context pressure or initiation suggestions from the Prompter.
- Allows the main LLM to:
  - Call tools autonomously to manage memory or mood.
  - Cull context messages if `suggest_cull` is true.
  - Emit `tool_call` and `context_cull` events as needed.

#### 7.2 Tool Registry

`backend/tools/registry.py` centralizes tools:
- Uses `ToolDefinition` to describe tools to the LLM (name, description, JSON‑schema parameters).
- Maintains:
  - `_definitions`: All tool metadata.
  - `_handlers`: Async callables implementing each tool.

Key categories:
- **Memory tools**
  - `read_memory(path)` – Read any memory file by path.
  - `write_memory(path, content)` – Create/overwrite a file; emits `memory_update`.
  - `append_memory(path, content)` – Append to a file; emits `memory_update`.
  - `list_memory(folder)` – Enumerate the bank’s directory tree.
  - `search_memory(query)` – Full‑text search across markdown.

- **Diary tools**
  - `write_diary(content)` – Appends a timestamped entry to today’s diary; emits `memory_update`.
  - `read_diary(date)` – Reads a specific day’s diary entry (or today).

- **People tools**
  - `update_person(name, content)` – Creates/updates a per‑person profile; emits `memory_update`.
  - `read_person(name)` – Reads a person profile by name.

- **Self tools**
  - `update_self(content, mode)` – Writes or appends to `static/self.md`; emits `memory_update`.
  - `set_mood(mood, intensity)` – Updates persona mood and intensity; emits `mood_update`.

- **Conversation/system tools**
  - `initiate_conversation(message, urgency)` – Allows the AI to proactively send a message to the user; inserts it into context and emits a chat event with `ai_initiated=true`.
  - `set_tick_interval(minutes)` – Updates the tick interval in config and reschedules the tick engine.

Visibility:
- `get_main_llm_tools()` selects a subset suitable for the main LLM.
- `get_prompter_tools()` selects tools for the Prompter’s use.

To **add a new tool**, see Section 10.2.

---

### 8. LLM Provider Adapters

The `backend/llm/` package abstracts different providers behind a common `LLMAdapter` interface:

- **Core types**
  - `Message`: Generic chat message with role, content, and tool metadata.
  - `ToolDefinition`: Name, description, JSON‑schema parameters.
  - `LLMResponse`: Output content, tool calls, finish reason, token counts.
  - `LLMAdapter`: Abstract base with:
    - `complete(messages, tools, system, max_tokens)` – single completion.
    - `stream(messages, tools, system, max_tokens)` – async generator for streaming.

- **OllamaAdapter**
  - Talks to `POST {base_url}/api/chat`.
  - Converts tool results into assistant messages, since Ollama lacks a dedicated tool role.
  - Maps Ollama’s `tool_calls` into OpenAI‑style function call descriptors.

- **OpenAIAdapter**
  - Wraps `openai.AsyncOpenAI`.
  - Optionally supports OpenAI‑compatible base URLs (LM Studio, vLLM, etc.).
  - Propagates tool calls via `tools` field and returns unified `LLMResponse`.

- **AnthropicAdapter**
  - Wraps `anthropic.AsyncAnthropic`.
  - Maps messages into Anthropic’s content blocks (text, tool_use, tool_result).
  - Adapts Anthropic tool use events into `tool_calls` for the registry.

A `create_adapter()` factory (in `backend/llm/__init__.py`) chooses the appropriate adapter based on `Config.main_llm.provider` or `Config.prompter_llm.provider`.

---

### 9. Frontend Architecture

#### 9.1 Application Shell (`App.jsx` and `main.jsx`)

- `main.jsx`:
  - Creates a React root and renders `<App />` (React StrictMode is disabled to avoid double WebSocket connections).

- `App.jsx`:
  - Imports global styles and panels/components.
  - Uses:
    - `useWebSocket(handleWsMessage)` to connect to `ws://<host>:8000/ws`.
    - `useDragResize()` to allow resizing between columns and rows.
  - Maintains React state for:
    - `setupComplete`, `showSettings`.
    - `persona`, `tickStatus`, `banks`, `activeBank`.
    - `messages`, `streamingMsg`, `thoughts`.
    - `tickMode`, `tickCountdown`, `ticks`.
    - `toolCalls`, `errors`.
    - `memoryUpdates` (to trigger refresh in memory/diary panels).
    - `username` (persisted to `localStorage`).
  - Handles WebSocket events:
    - `init`, `setup_complete`, `chat_message`, `chat_stream`, `chat_stream_end`.
    - `inner_thought`, `tick`, `tick_countdown`, `mood_update`, `memory_update`, `context_cull`, `bank_switch`, `tool_call`, `error`.
  - Sends:
    - Chat messages with `{ type: "chat", content, user_id, username }`.
  - Calls REST endpoints for:
    - Bank switching and creation.

The UI layout splits the screen into:
- Left: Chat panel.
- Center: Inner thoughts (top) and tick/tool/error log (bottom).
- Right: Memory browser (top) and diary viewer (bottom).

#### 9.2 WebSocket Hook (`useWebSocket`)

`useWebSocket` encapsulates:
- Connection lifecycle with automatic **reconnect** every 2.5 seconds if disconnected.
- Single global WebSocket per component tree.
- Ensures:
  - `onMessage` callback is always up to date via a ref.
  - Graceful cleanup of event handlers on unmount.

Exposes:
- `connected`: Boolean connection status.
- `send(data)`: JSON‑encoded message sender (if the socket is open).

#### 9.3 Layout & Resize Hook (`useDragResize`)

`useDragResize` manages panel sizes:
- Stores an array of sizes (pixels).
- `onMouseDown(handleIndex, event)` starts a drag session.
- Global mousemove/mouseup listeners update sizes and enforce a minimum size.
- Supports both horizontal and vertical resizing with different cursors.

Used in `App.jsx` to:
- Adjust column widths (chat vs center vs right).
- Adjust row heights (inner thoughts vs tick log and memory vs diary).

---

### 10. Frontend Panels & Components

#### 10.1 StatusBar

`StatusBar` shows:
- **Identity**: Persona name and mood badge (color‑coded).
- **Tick status**: Current tick number and simple next‑tick hint.
- **Active bank**: Current memory bank name.
- **Bank selector**:
  - Dropdown listing existing banks (click to switch).
  - Inline creator for new banks (POST `/api/bank/create`, then refresh).
- **Connection**: An indicator for WebSocket connectivity (`live` vs `offline`).
- **Settings button**: Opens the SettingsPanel.

#### 10.2 SetupWizard

`SetupWizard` appears when `setupComplete` is false:
- Guides the user through:
  - Naming the entity.
  - Writing a core identity string.
  - Picking providers, models, base URLs, and API keys for main and prompter LLMs.
  - Choosing the tick interval.
- On submit:
  - Validates requirements for OpenAI‑compatible providers (base URLs).
  - Calls `POST /api/setup` with the filled form.
  - On success, invokes `onComplete()` (and the backend emits `setup_complete`).

#### 10.3 SettingsPanel

`SettingsPanel` is similar to the wizard but for **editing**:
- On mount:
  - Fetches `/api/config` for the current config.
  - Fetches `/api/memory/read?path=static/self.md` for the identity file.
  - Seeds the form.
- Provides fields for:
  - Identity name + full self description.
  - Main LLM (provider, model, base URL, key, vision flag).
  - Prompter LLM (provider, model, base URL, key).
  - Tick interval.
- On save:
  - Posts to `/api/setup` with current form.
  - Shows success or error banners.

#### 10.4 ChatPanel

`ChatPanel` handles:
- Displaying the chat history with distinct styling for user vs assistant messages.
- Streaming display of the current assistant message.
- An editable **username**:
  - Inline editing with small input and commit button.
  - Propagated up to `App` via `onUsernameChange`, which stores it in `localStorage`.
- Input box:
  - Multiline (Enter sends, Shift+Enter inserts newline).
  - Disabled send button if input is empty.

#### 10.5 InnerThoughtsPanel

`InnerThoughtsPanel` visualizes:
- A live feed of **inner thoughts** and **kernel reports**.
- Filters:
  - `all`, `thought`, `kernel`.
- Tick status:
  - Mode badge (`active` vs `idle`) and tick count.
  - A progress bar based on `tickCountdown` (time to next tick).

Each thought entry shows:
- Type (`thought` vs `kernel`).
- Time of emission.
- Content, with distinct styling for kernel/system vs emotional thoughts.

#### 10.6 MemoryBrowser

`MemoryBrowser` offers:
- A two‑pane layout:
  - Left: Tree view of the active bank (`/api/memory/list`).
  - Right: Content of the selected file (`/api/memory/read`).
- Behavior:
  - Auto‑reloads tree on startup and when `memoryUpdates` changes.
  - Default expanded folders: `static`, `people`, `days`.
  - Nested folder entries that lazily load their children only when expanded.

#### 10.7 DiaryViewer

`DiaryViewer`:
- Lists diary entries (`/api/diary/list`).
- Shows the most recent entry by default if none is selected.
- Lets the user:
  - Navigate by date using arrows or clicking date chips.
  - View content via `/api/diary?date=...`.
- Reacts to `memoryUpdates` to ensure fresh entries appear.

#### 10.8 TickLog

`TickLog` merges:
- `ticks`: Tick events from the backend.
- `toolCalls`: Tool call logs.
- `errors`: Error logs.

All events are merged and sorted by timestamp, then:
- Rendered with icons and minimal text describing:
  - Tick mode and number.
  - Tool name and truncated arguments.
  - Error message and source.

---

### 11. Connectors & Multi‑Source Inputs

`backend/connectors/base.py`:
- Defines a `MessageSource` interface for external connectors (e.g. Discord, future integrations).
- Defines `IncomingMessage` (user_id, username, content, source, channel).

`backend/connectors/discord.py`:
- Contains a stub `DiscordConnector`:
  - Respects `config.connectors.discord.enabled`.
  - Prints a stub message instead of starting a bot.
  - Implements `start`, `stop`, `is_connected`, and `get_status`.

To fully support Discord:
- Implement `_start_bot()` with your Discord client of choice.
- Bridge incoming messages into the same conversation pipeline used by WebSocket messages (e.g. call `ConversationHandler` and broadcast via `MessageBus`).

---

### 12. Users & Profiles

`backend/users/manager.py`:
- Tracks per‑user sessions by `user_id`:
  - Username, message count.
- Provides:
  - `get_or_create_session(user_id, username)`.
  - `record_message(user_id)`.
  - `get_profile(username, memory_manager)`.
  - `ensure_profile(username, memory_manager)`:
    - Creates a stub markdown profile if none exists yet.

When handling a chat:
- The backend ensures a user profile exists for the `username` and passes that profile into the system prompt via `PersonaAssembler` for personalized responses.

---

### 13. Running & Developing

#### 13.1 Prerequisites

- **Python**: 3.11+
- **Node.js**: 18+
- **LLM backend**:
  - Local Ollama installation (default), or
  - API keys + base URLs for OpenAI/Anthropic/OpenAI‑compatible services.

#### 13.2 Backend

- Install Python dependencies:
  - From the project root: `pip install -r requirements.txt` (or your preferred manager).
- Run the FastAPI app, e.g.:
  - `uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`

The backend will:
- Initialize global state and memory banks.
- Start the tick engine.
- Expose WebSocket and REST endpoints.

#### 13.3 Frontend

From `frontend/`:
- Install JS dependencies: `npm install` or `pnpm install`.
- Start the dev server: `npm run dev` (Vite, port 5173 by default).

Open `http://localhost:5173` to:
- Run the **Setup Wizard** and configure Anima.
- Start conversing and explore panels.

#### 13.4 Combined Start Script

`start.sh` (in the project root) is provided to:
- Make the script executable and run both backend and frontend (see README “Quick Start”).

---

### 14. Extensibility

#### 14.1 Adding a New LLM Provider

1. Create a new adapter in `backend/llm/myprovider.py` that subclasses `LLMAdapter` and implements:
   - `complete()` (single response).
   - `stream()` (async generator for chunks).
2. Wire it into `backend/llm/__init__.py`’s `create_adapter()` factory, keyed by a new `provider` string.
3. Update `config.yaml` (`main_llm.provider` and/or `prompter_llm.provider`) and use the Setup Wizard / SettingsPanel to select it.

#### 14.2 Adding a New Tool

1. Open `backend/tools/registry.py`.
2. Write an async handler that uses `memory_manager`, `context_manager`, `bus`, or other services as needed.
3. Register the tool:
   - Define a new `ToolDefinition` with:
     - `name`: Unique string.
     - `description`: Clear, user‑facing explanation.
     - `parameters`: JSON schema for arguments.
   - Call `register_tool(definition, handler)` inside `setup_tools()`.
4. Add the new tool’s name to:
   - `get_main_llm_tools()` and/or
   - `get_prompter_tools()`
   depending on where it should be available.

Once registered, the tool automatically becomes available to the LLM for function calling.

#### 14.3 Adding a New Panel or Frontend Feature

1. Create a new component under `frontend/src/panels/` or `frontend/src/components/`.
2. Extend `handleWsMessage` in `App.jsx` to handle new event types if you’re emitting them from the backend.
3. Hook into existing REST or WebSocket endpoints, or add new endpoints in `backend/main.py`.
4. Use `useWebSocket` and/or `useDragResize` to integrate into the layout.

---

### 15. Design Notes & Behaviors

- **Entity vs Assistant**:
  - The system prompt explicitly instructs Anima to behave as a persistent entity, not a generic assistant.
  - Mood, memory, and inner thoughts are first‑class; tools allow Anima to manage its own memories and diary.

- **Memory Pressure & Culling**:
  - Context pressure is computed from active messages and exposed in persona state.
  - When high, the Prompter hints at culling, and the main LLM may summarize and mark messages as culled.

- **Initiative**:
  - When idle, the Prompter can suggest initiating contact.
  - The main LLM can use `initiate_conversation` to send organic, AI‑initiated messages to the user.

- **Multi‑Bank Persona**:
  - `bank` is part of persona state and system prompt.
  - Each memory bank represents a different “life” or story arc, with its own identity and diary.

This document should be the primary reference for how Anima is structured, how data and events flow through the system, and how to extend or integrate with it.

