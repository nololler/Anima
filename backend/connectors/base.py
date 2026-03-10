from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Optional


class IncomingMessage(BaseModel):
    user_id: str
    username: str
    content: str
    source: str  # "web" | "discord" | etc.
    channel_id: Optional[str] = None


class MessageSource(ABC):
    source_id: str

    @abstractmethod
    async def start(self): ...

    @abstractmethod
    async def stop(self): ...

    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    def get_status(self) -> dict: ...
