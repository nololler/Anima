import yaml
import os
from pathlib import Path
from pydantic import BaseModel
from typing import Optional, List

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"  # project root
# If running from project root via uvicorn backend.main:app, __file__ is backend/config.py
# so parent.parent = project root. Correct.


class LLMConfig(BaseModel):
    provider: str = "ollama"
    model: str = "qwen2.5:7b"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    temperature: float = 0.8
    context_limit: int = 8192
    vision: bool = False


class PrompterConfig(BaseModel):
    provider: str = "ollama"
    model: str = "qwen2.5:3b"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    temperature: float = 1.1
    context_limit: int = 2048


class TickConfig(BaseModel):
    interval_minutes: int = 1
    enabled: bool = True


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["http://localhost:5173"]


class DiscordConfig(BaseModel):
    enabled: bool = False
    token: str = ""
    guild_id: str = ""
    channel_ids: List[str] = []


class ConnectorsConfig(BaseModel):
    discord: DiscordConfig = DiscordConfig()


class AnimaConfig(BaseModel):
    name: str = "Anima"
    active_memory_bank: str = "default"
    version: str = "0.1.0"


class Config(BaseModel):
    anima: AnimaConfig = AnimaConfig()
    main_llm: LLMConfig = LLMConfig()
    prompter_llm: PrompterConfig = PrompterConfig()
    tick: TickConfig = TickConfig()
    server: ServerConfig = ServerConfig()
    connectors: ConnectorsConfig = ConnectorsConfig()

    def save(self):
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False)


_config: Optional[Config] = None


def load_config() -> Config:
    global _config
    if not CONFIG_PATH.exists():
        _config = Config()
        return _config
    with open(CONFIG_PATH, "r") as f:
        data = yaml.safe_load(f)
    _config = Config(**data)
    return _config


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reload_config() -> Config:
    global _config
    _config = None
    return load_config()
