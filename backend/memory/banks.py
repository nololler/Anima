from typing import Optional, List
from .manager import MemoryManager
from datetime import datetime


class BankManager:
    def __init__(self):
        self._current_bank: Optional[str] = None
        self._manager: Optional[MemoryManager] = None

    def get_manager(self) -> MemoryManager:
        if self._manager is None:
            from backend.config import get_config
            cfg = get_config()
            self._current_bank = cfg.anima.active_memory_bank
            self._manager = MemoryManager(self._current_bank)
        return self._manager

    def current_bank(self) -> str:
        return self._current_bank or "default"

    async def switch_bank(
        self,
        new_bank: str,
        conversation_history: List[dict],
        summarizer_fn=None,
    ) -> dict:
        """
        Switch to a new memory bank.
        Auto-summarizes current conversation before switching.
        Returns summary + switch result.
        """
        old_bank = self.current_bank()
        summary = None

        # Auto-summarize if there's conversation history and a summarizer
        if conversation_history and summarizer_fn:
            try:
                summary = await summarizer_fn(conversation_history)
                old_mgr = self.get_manager()
                today = datetime.now().strftime("%Y-%m-%d")
                await old_mgr.append(
                    f"days/{today}_pre_switch.md",
                    f"# Conversation before switching to bank '{new_bank}'\n\n{summary}\n"
                )
            except Exception as e:
                summary = f"[Summary failed: {e}]"

        # Create new bank if needed
        new_mgr = MemoryManager(new_bank)

        # Update config
        from backend.config import get_config
        cfg = get_config()
        cfg.anima.active_memory_bank = new_bank
        cfg.save()

        self._current_bank = new_bank
        self._manager = new_mgr

        return {
            "old_bank": old_bank,
            "new_bank": new_bank,
            "summary": summary,
            "success": True,
        }

    def list_banks(self) -> List[str]:
        return MemoryManager.list_banks()

    def create_bank(self, name: str) -> bool:
        try:
            MemoryManager(name)  # creates structure
            return True
        except Exception:
            return False


# Global instance
_bank_manager: Optional[BankManager] = None


def get_bank_manager() -> BankManager:
    global _bank_manager
    if _bank_manager is None:
        _bank_manager = BankManager()
    return _bank_manager
