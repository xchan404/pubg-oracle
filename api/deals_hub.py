"""
Live Deals Hub
In-process broadcaster connecting the sniper bot (HTTP push) to
dashboard clients (WebSocket). Keeps a small replay buffer for late joiners.
"""

import asyncio
import os
from collections import deque
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket


class DealsHub:
    def __init__(self, buffer_size: int = 50):
        self.clients: set[WebSocket] = set()
        self.recent: deque[dict[str, Any]] = deque(maxlen=buffer_size)
        self._lock = asyncio.Lock()

    @staticmethod
    def token_required() -> bool:
        return bool(os.getenv("INTERNAL_TOKEN"))

    @staticmethod
    def token_valid(token: str | None) -> bool:
        expected = os.getenv("INTERNAL_TOKEN", "")
        return bool(expected) and token == expected

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self.clients.discard(ws)

    def publish(self, deal: dict[str, Any]) -> dict[str, Any]:
        """Stores the deal and schedules broadcast to all live clients."""
        deal = {"received_at": datetime.now(UTC).isoformat(), **deal}
        self.recent.appendleft(deal)
        asyncio.get_event_loop().create_task(self._broadcast(deal))
        return deal

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in list(self.clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)


hub = DealsHub()
