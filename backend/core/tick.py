"""
TickEngine — Three-state scheduler
====================================
States:
  ACTIVE  — user sent a message in the last 2 minutes.
             Prompter runs for context maintenance. Main LLM not interrupted.

  IDLE    — no activity for 2+ minutes.
             Full tick: Prompter runs → Main LLM gets idle reflection prompt.
             Entity reflects, tends memory, may reach out.

  SLEEP   — no activity for 30+ minutes.
             Slow ticks for memory consolidation only.
             Tick interval doubles.

Transitions:
  any message          → ACTIVE (also wakes from SLEEP)
  2 min no message     → IDLE
  30 min no message    → SLEEP
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from backend.config import get_config
from backend.core.message_bus import get_bus

IDLE_AFTER_SECONDS = 120
SLEEP_AFTER_SECONDS = 1800     # 30 minutes
TICK_INTERVAL_SECONDS = 60
SLEEP_TICK_MULTIPLIER = 2
COUNTDOWN_BROADCAST_SECONDS = 10


class EntityState(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    SLEEP = "sleep"


class TickEngine:
    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._tick_count = 0
        self._is_running = False
        self._countdown_task: Optional[asyncio.Task] = None
        self._last_tick_time: Optional[datetime] = None
        self._next_tick_time: Optional[datetime] = None
        self._entity_state = EntityState.IDLE
        self._last_message_time: Optional[datetime] = None

        self._prompter = None
        self._conversation = None
        self._context = None
        self._persona_state: Optional[dict] = None

    def setup(self, prompter, conversation_handler, context_manager, persona_state: dict):
        self._prompter = prompter
        self._conversation = conversation_handler
        self._context = context_manager
        self._persona_state = persona_state

    # ── Lifecycle ─────────────────────────────────────────────────────

    def start(self):
        cfg = get_config()
        if not cfg.tick.enabled:
            return
        self._scheduler.add_job(
            self._tick,
            "interval",
            seconds=TICK_INTERVAL_SECONDS,
            id="main_tick",
            replace_existing=True,
        )
        self._scheduler.start()
        self._is_running = True
        self._update_next_tick(TICK_INTERVAL_SECONDS)
        self._countdown_task = asyncio.create_task(self._countdown_loop())

    def stop(self):
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
        self._is_running = False
        if self._countdown_task:
            self._countdown_task.cancel()

    def reschedule(self, seconds: int):
        if self._scheduler.running:
            self._scheduler.reschedule_job(
                "main_tick", trigger="interval", seconds=max(30, seconds)
            )
        self._update_next_tick(seconds)

    # ── State management ──────────────────────────────────────────────

    def record_user_message(self):
        """Called by main.py whenever a user sends a message."""
        was_sleeping = self._entity_state == EntityState.SLEEP
        self._last_message_time = datetime.now()
        self._entity_state = EntityState.ACTIVE
        if self._persona_state:
            self._persona_state["entity_state"] = EntityState.ACTIVE
            self._persona_state["user_is_active"] = True
            self._persona_state["last_message_time"] = self._last_message_time
        if was_sleeping:
            # Restore normal tick speed
            self.reschedule(TICK_INTERVAL_SECONDS)
            asyncio.create_task(self._on_wake())

    def _compute_state(self) -> EntityState:
        if self._last_message_time is None:
            return EntityState.IDLE
        elapsed = (datetime.now() - self._last_message_time).total_seconds()
        if elapsed < IDLE_AFTER_SECONDS:
            return EntityState.ACTIVE
        if elapsed < SLEEP_AFTER_SECONDS:
            return EntityState.IDLE
        return EntityState.SLEEP

    def _update_next_tick(self, seconds: int):
        self._next_tick_time = datetime.now() + timedelta(seconds=seconds)

    # ── Main tick ─────────────────────────────────────────────────────

    async def _tick(self):
        self._tick_count += 1
        self._last_tick_time = datetime.now()
        bus = get_bus()

        new_state = self._compute_state()
        old_state = self._entity_state

        # Handle transitions
        if old_state != new_state:
            self._entity_state = new_state
            if self._persona_state:
                self._persona_state["entity_state"] = new_state
            if new_state == EntityState.IDLE and old_state == EntityState.ACTIVE:
                await self._on_enter_idle()
            elif new_state == EntityState.SLEEP:
                await self._on_enter_sleep()

        if self._persona_state:
            self._persona_state["tick_count"] = self._tick_count
            self._persona_state["user_is_active"] = (new_state == EntityState.ACTIVE)
            if self._context:
                self._persona_state["context_pressure"] = self._context.estimate_pressure()

        tick_interval = TICK_INTERVAL_SECONDS * (SLEEP_TICK_MULTIPLIER if new_state == EntityState.SLEEP else 1)
        self._update_next_tick(tick_interval)

        await bus.emit_tick(self._tick_count, new_state.value, f"Tick #{self._tick_count} ({new_state.value})")

        if not self._prompter:
            return

        try:
            if new_state == EntityState.ACTIVE:
                await self._tick_active()
            elif new_state == EntityState.IDLE:
                await self._tick_idle()
            else:
                await self._tick_sleep()
        except Exception as e:
            await bus.emit_error(f"Tick #{self._tick_count} error: {e}", source="tick_engine")

    async def _tick_active(self):
        """Context maintenance only — don't interrupt the main LLM."""
        status = await self._prompter.run_tick()
        bus = get_bus()
        await bus.emit_inner_thought(
            f"[active] context {status['context_pressure']:.0%} — "
            f"{status['context_counts']['active']} active msgs",
            kind="kernel",
        )

    async def _tick_idle(self):
        """Full idle cycle: Prompter → Main LLM reflection."""
        status = await self._prompter.run_tick()
        tick_summary = self._prompter.build_tick_summary(status)
        if self._conversation:
            await self._conversation.handle_idle_tick(tick_summary)

    async def _tick_sleep(self):
        """Sleep consolidation: Prompter + minimal Main LLM only if context is full."""
        bus = get_bus()
        status = await self._prompter.run_tick()
        await bus.emit_inner_thought("(sleeping — minimal tick)", kind="kernel")
        if self._conversation and self._context and self._context.estimate_pressure() > 0.5:
            tick_summary = self._prompter.build_tick_summary(status)
            await self._conversation.handle_idle_tick(
                tick_summary + "\n\nYou are resting. Consolidate quietly. No need to reach out."
            )

    # ── Transition hooks ──────────────────────────────────────────────

    async def _on_enter_idle(self):
        await get_bus().emit_inner_thought("(entering idle — user quiet)", kind="kernel")

    async def _on_enter_sleep(self):
        await get_bus().emit_inner_thought("(entering sleep — long inactivity)", kind="kernel")
        self.reschedule(TICK_INTERVAL_SECONDS * SLEEP_TICK_MULTIPLIER)

    async def _on_wake(self):
        await get_bus().emit_inner_thought("(waking — user returned)", kind="kernel")

    # ── Countdown ─────────────────────────────────────────────────────

    async def _countdown_loop(self):
        bus = get_bus()
        while self._is_running:
            try:
                if self._next_tick_time:
                    remaining = int((self._next_tick_time - datetime.now()).total_seconds())
                    await bus.emit_tick_countdown(max(0, remaining))
                await asyncio.sleep(COUNTDOWN_BROADCAST_SECONDS)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(COUNTDOWN_BROADCAST_SECONDS)

    # ── Status ────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "tick_count": self._tick_count,
            "is_running": self._is_running,
            "entity_state": self._entity_state.value,
            "last_tick": self._last_tick_time.isoformat() if self._last_tick_time else None,
            "next_tick": self._next_tick_time.isoformat() if self._next_tick_time else None,
        }


_engine: Optional[TickEngine] = None


def get_tick_engine() -> TickEngine:
    global _engine
    if _engine is None:
        _engine = TickEngine()
    return _engine
