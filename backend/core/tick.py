import asyncio
from datetime import datetime
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.config import get_config
from backend.core.message_bus import get_bus


class TickEngine:
    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._tick_count = 0
        self._job = None
        self._prompter = None
        self._main_llm_handler = None
        self._context_manager = None
        self._persona_state = None
        self._last_tick_time: Optional[datetime] = None
        self._next_tick_time: Optional[datetime] = None
        self._is_running = False
        self._countdown_task = None

    def setup(self, prompter, main_llm_handler, context_manager, persona_state):
        self._prompter = prompter
        self._main_llm_handler = main_llm_handler
        self._context_manager = context_manager
        self._persona_state = persona_state

    def start(self):
        cfg = get_config()
        interval = cfg.tick.interval_minutes
        if not cfg.tick.enabled:
            return
        self._scheduler.add_job(
            self._tick,
            "interval",
            minutes=interval,
            id="main_tick",
            replace_existing=True,
        )
        self._scheduler.start()
        self._is_running = True
        self._update_next_tick(interval)
        asyncio.create_task(self._countdown_loop())

    def stop(self):
        self._scheduler.shutdown(wait=False)
        self._is_running = False

    def reschedule(self, minutes: int):
        if self._scheduler.running:
            self._scheduler.reschedule_job("main_tick", trigger="interval", minutes=minutes)
            self._update_next_tick(minutes)

    def _update_next_tick(self, minutes: int):
        from datetime import timedelta
        self._next_tick_time = datetime.now().replace(microsecond=0)
        self._next_tick_time = self._next_tick_time.replace(
            second=0
        ) + timedelta(minutes=minutes)

    async def _countdown_loop(self):
        """Emit countdown every 10 seconds."""
        bus = get_bus()
        while self._is_running:
            if self._next_tick_time:
                remaining = int((self._next_tick_time - datetime.now()).total_seconds())
                remaining = max(0, remaining)
                await bus.emit_tick_countdown(remaining)
            await asyncio.sleep(10)

    async def _tick(self):
        self._tick_count += 1
        self._last_tick_time = datetime.now()
        bus = get_bus()
        cfg = get_config()
        self._update_next_tick(cfg.tick.interval_minutes)

        if self._persona_state:
            self._persona_state["tick_count"] = self._tick_count
            if self._context_manager:
                self._persona_state["context_pressure"] = self._context_manager.estimate_pressure()

            # Auto-reset to idle if no message in last 2 minutes
            last_msg_time = self._persona_state.get("last_message_time")
            if last_msg_time:
                from datetime import timedelta
                elapsed = (datetime.now() - last_msg_time).total_seconds()
                if elapsed > 120:
                    self._persona_state["user_is_active"] = False

        # Determine mode
        is_active = self._persona_state.get("user_is_active", False) if self._persona_state else False
        mode = "active" if is_active else "idle"

        await bus.emit_tick(self._tick_count, mode, f"Tick #{self._tick_count} ({mode})")

        if not self._prompter:
            return

        try:
            recent_msgs = []
            if self._context_manager:
                recent_msgs = self._context_manager.get_messages_for_llm()

            if mode == "idle":
                prompter_result = await self._prompter.run_idle(recent_msgs)

                # Pass to Main LLM for idle reflection
                if self._main_llm_handler:
                    await self._main_llm_handler.handle_idle_tick(
                        prompter_result,
                        suggest_cull=prompter_result.get("suggest_cull", False),
                    )

                # Day titling only happens when conversation goes idle
                # (handled in main.py after user messages, not every tick)

        except Exception as e:
            await bus.emit_error(f"Tick error: {e}", source="tick_engine")

    def get_status(self) -> dict:
        return {
            "tick_count": self._tick_count,
            "is_running": self._is_running,
            "last_tick": self._last_tick_time.isoformat() if self._last_tick_time else None,
            "next_tick": self._next_tick_time.isoformat() if self._next_tick_time else None,
        }


_engine: Optional[TickEngine] = None


def get_tick_engine() -> TickEngine:
    global _engine
    if _engine is None:
        _engine = TickEngine()
    return _engine
