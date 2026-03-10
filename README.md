# Anima

A persistent AI entity with genuine memory, inner life, and autonomous presence.

## Quick Start

```bash
chmod +x start.sh
./start.sh
```

Then open **http://localhost:5173**. The setup wizard will guide you through first-time configuration.

## Architecture

```
backend/          Python + FastAPI
  llm/            Unified adapter: Ollama, OpenAI, Anthropic, OpenAI-compatible
  core/           Tick engine, Prompter, Conversation handler, Message bus, Persona assembler
  memory/         Memory bank manager, context window, bank switching
  tools/          Tool registry (all Main LLM tools)
  connectors/     Web (active) + Discord (stub)
  users/          Multi-user session and profile management

frontend/         React + Vite + Tailwind
  panels/         Chat, Inner Thoughts, Memory Browser, Diary, Tick Log
  components/     Status bar, Setup wizard, Message bubble
```

## Memory Bank Structure

```
memory_banks/
└── [bank_name]/
    ├── static/self.md       ← Identity (seeded + AI-evolved)
    ├── static/favorites.md
    ├── people/[Name].md     ← Per-person profiles
    ├── days/[date]_[title].md
    ├── diary/[date].md
    ├── images/              ← VLM only
    └── index.md
```

## Config

Edit `config.yaml` to change models, providers, tick interval, etc.

All changes to model config take effect on next message (adapters are lazy-loaded).

## Adding a New Tool

1. Open `backend/tools/registry.py`
2. Call `register_tool(ToolDefinition(...), async_handler)` inside `setup_tools()`
3. Add it to `get_main_llm_tools()` or `get_prompter_tools()` as appropriate
4. Done — no other files need touching

## Adding a New LLM Provider

1. Create `backend/llm/myprovider.py` extending `LLMAdapter`
2. Implement `complete()` and `stream()`
3. Add a case in `backend/llm/__init__.py`'s `create_adapter()`
4. Done

## Discord Integration (Stub)

Set `connectors.discord.enabled: true` in `config.yaml` and implement `_start_bot()` in `backend/connectors/discord.py`.

## Requirements

- Python 3.11+
- Node.js 18+
- Ollama running locally (or API keys for cloud providers)
