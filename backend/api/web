"""BIAR Protocol - WebSocket connection manager for real-time updates."""
import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket


class WebSocketManager:
    """Manages WebSocket connections grouped by market and global feed."""

    def __init__(self):
        # market_id -> set of connected websockets
        self.market_connections: dict[int, set] = defaultdict(set)
        # global feed subscribers
        self.feed_connections: set = set()
        self._lock = asyncio.Lock()

    async def connect_market(self, market_id: int, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.market_connections[market_id].add(ws)

    async def connect_feed(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self.feed_connections.add(ws)

    async def disconnect_market(self, market_id: int, ws: WebSocket) -> None:
        async with self._lock:
            self.market_connections[market_id].discard(ws)

    async def disconnect_feed(self, ws: WebSocket) -> None:
        async with self._lock:
            self.feed_connections.discard(ws)

    async def _safe_send(self, ws: WebSocket, payload: str) -> bool:
        """Send to a socket; returns False if it should be dropped."""
        try:
            await ws.send_text(payload)
            return True
        except Exception:
            return False

    async def broadcast_market(self, market_id: int, message: dict) -> None:
        payload = json.dumps(message)
        async with self._lock:
            conns = set(self.market_connections.get(market_id, set()))
        dead = [ws for ws in conns if not await self._safe_send(ws, payload)]
        if dead:
            async with self._lock:
                for ws in dead:
                    self.market_connections[market_id].discard(ws)

    async def broadcast_feed(self, message: dict) -> None:
        payload = json.dumps(message)
        async with self._lock:
            conns = set(self.feed_connections)
        dead = [ws for ws in conns if not await self._safe_send(ws, payload)]
        if dead:
            async with self._lock:
                for ws in dead:
                    self.feed_connections.discard(ws)

    async def broadcast_trade(self, market_id: int, trade: dict) -> None:
        """Broadcast a trade to both the market room and the global feed."""
        await self.broadcast_market(market_id, {"type": "trade", "market_id": market_id, **trade})
        await self.broadcast_feed({"type": "trade", "market_id": market_id, **trade})


manager = WebSocketManager()