"""
Discord Connector — STUB
========================
Not yet implemented. This is a placeholder that implements the MessageSource
interface. When Discord integration is ready, fill in the _start_bot() method
and wire it to the message pipeline in main.py.

To enable:
1. Set connectors.discord.enabled = true in config.yaml
2. Add your bot token
3. Implement _start_bot() using discord.py or nextcord
"""
from .base import MessageSource, IncomingMessage
from typing import Optional


class DiscordConnector(MessageSource):
    source_id = "discord"

    def __init__(self, config):
        self.config = config
        self._bot = None

    async def start(self):
        if not self.config.enabled:
            return
        # TODO: implement bot startup
        # import discord
        # self._bot = discord.Client(intents=discord.Intents.default())
        # await self._bot.start(self.config.token)
        print("[Discord] Connector stubbed — not started.")

    async def stop(self):
        if self._bot:
            pass  # await self._bot.close()

    def is_connected(self) -> bool:
        return False  # stub always returns False

    def get_status(self) -> dict:
        return {
            "connector": "discord",
            "status": "stub",
            "enabled": self.config.enabled,
            "note": "Not yet implemented",
        }
