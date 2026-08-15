"""
BIAR Protocol - WebSocket Server for Real-Time Updates
Provides live market data, price feeds, and order updates
"""

from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from typing import Set, Dict, List
import json
import asyncio
from datetime import datetime
from sqlalchemy.orm import Session

from models.database import Market, Order, Position
from core.amm import LMSR


class WebSocketManager:
    """Manages WebSocket connections and broadcasts real-time data"""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.market_subscribers: Dict[int, Set[str]] = {}  # market_id -> set of client_ids
    
    async def connect(self, websocket: WebSocket, client_id: str, market_id: int = None):
        """Register a new WebSocket connection"""
        await websocket.accept()
        
        if client_id not in self.active_connections:
            self.active_connections[client_id] = []
        self.active_connections[client_id].append(websocket)
        
        if market_id is not None:
            if market_id not in self.market_subscribers:
                self.market_subscribers[market_id] = set()
            self.market_subscribers[market_id].add(client_id)
    
    def disconnect(self, client_id: str, websocket: WebSocket):
        """Unregister a WebSocket connection"""
        if client_id in self.active_connections:
            self.active_connections[client_id].remove(websocket)
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
    
    async def broadcast_market_update(self, market_id: int, data: dict):
        """Broadcast market update to all subscribers of that market"""
        if market_id not in self.market_subscribers:
            return
        
        disconnected_clients = []
        for client_id in self.market_subscribers[market_id]:
            if client_id in self.active_connections:
                for websocket in self.active_connections[client_id]:
                    try:
                        await websocket.send_json({
                            "type": "market_update",
                            "market_id": market_id,
                            "data": data,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    except Exception as e:
                        disconnected_clients.append((client_id, websocket))
        
        # Cleanup disconnected clients
        for client_id, ws in disconnected_clients:
            self.disconnect(client_id, ws)
    
    async def broadcast_price_update(self, market_id: int, prices: Dict[str, float]):
        """Broadcast real-time price update"""
        data = {
            "type": "price_update",
            "market_id": market_id,
            "prices": prices,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast_market_update(market_id, data)
    
    async def broadcast_order_update(self, market_id: int, order: dict):
        """Broadcast order execution update"""
        data = {
            "type": "order_executed",
            "market_id": market_id,
            "order": order,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast_market_update(market_id, data)
    
    async def broadcast_probability_update(self, market_id: int, probabilities: Dict[str, float]):
        """Broadcast probability update to market subscribers"""
        data = {
            "type": "probability_update",
            "market_id": market_id,
            "probabilities": probabilities,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.broadcast_market_update(market_id, data)
    
    async def send_user_update(self, client_id: str, data: dict):
        """Send update to specific user"""
        if client_id in self.active_connections:
            for websocket in self.active_connections[client_id]:
                try:
                    await websocket.send_json({
                        "type": "user_update",
                        "data": data,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception:
                    pass
    
    async def broadcast_portfolio_update(self, wallet_address: str, positions: List[dict]):
        """Broadcast portfolio update to user"""
        data = {
            "type": "portfolio_update",
            "positions": positions,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_user_update(wallet_address, data)
    
    async def broadcast_notification(self, client_id: str, message: str, notification_type: str = "info"):
        """Send notification to user"""
        data = {
            "type": "notification",
            "message": message,
            "notification_type": notification_type,
            "timestamp": datetime.utcnow().isoformat()
        }
        await self.send_user_update(client_id, data)


# Global WebSocket manager instance
ws_manager = WebSocketManager()
