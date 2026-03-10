from typing import Optional, Dict
from backend.memory.manager import MemoryManager


class UserManager:
    def __init__(self):
        self._sessions: Dict[str, dict] = {}

    def get_or_create_session(self, user_id: str, username: str) -> dict:
        if user_id not in self._sessions:
            self._sessions[user_id] = {
                "user_id": user_id,
                "username": username,
                "message_count": 0,
            }
        return self._sessions[user_id]

    def record_message(self, user_id: str):
        if user_id in self._sessions:
            self._sessions[user_id]["message_count"] += 1

    async def get_profile(self, username: str, memory_manager: MemoryManager) -> Optional[str]:
        return await memory_manager.read_person(username)

    async def ensure_profile(self, username: str, memory_manager: MemoryManager) -> Optional[str]:
        profile = await memory_manager.read_person(username)
        if not profile:
            # Create a stub profile
            stub = f"# {username}\n\nNew contact. No information yet.\n"
            await memory_manager.update_person(username, stub)
            return stub
        return profile


_user_manager: Optional[UserManager] = None


def get_user_manager() -> UserManager:
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
    return _user_manager
