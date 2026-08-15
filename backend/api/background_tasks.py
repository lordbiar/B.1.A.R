"""
BIAR Protocol - Background Tasks for Real-Time Updates
Handles periodic market updates, price feeds, and broadcasts
"""

import asyncio
from datetime import datetime
from typing import Dict
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.database import Market
from core.amm import LMSR
from api.websocket import ws_manager

# Database connection
SQLALCHEMY_DATABASE_URL = "sqlite:///./biar.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize AMM
amm_engine = LMSR(b=100.0, fee_rate=0.003)


async def broadcast_market_updates():
    """
    Periodically broadcast market updates to all connected WebSocket clients
    """
    db = SessionLocal()
    
    try:
        while True:
            # Get all active markets
            markets = db.query(Market).filter(Market.status.in_(['active', 'pending'])).all()
            
            for market in markets:
                try:
                    # Parse liquidity
                    quantities = market.current_liquidity or {}
                    if isinstance(quantities, str):
                        import json
                        quantities = json.loads(quantities)
                    
                    # Calculate current prices and probabilities
                    prices = {}
                    probabilities = {}
                    
                    for outcome in market.outcomes:
                        price = amm_engine.get_price(quantities, outcome)
                        prices[outcome] = round(price, 4)
                        probabilities[outcome] = round(price * 100, 2)
                    
                    # Broadcast price update
                    await ws_manager.broadcast_price_update(market.id, prices)
                    
                    # Broadcast probability update
                    await ws_manager.broadcast_probability_update(market.id, probabilities)
                    
                except Exception as e:
                    print(f"Error broadcasting update for market {market.id}: {e}")
            
            # Wait before next broadcast (100ms for near-real-time)
            await asyncio.sleep(0.1)
    
    finally:
        db.close()


async def periodic_stats_update():
    """
    Periodically update and broadcast platform statistics
    """
    db = SessionLocal()
    
    try:
        while True:
            # Calculate current stats
            active_markets = db.query(Market).filter(Market.status == 'active').count()
            
            # Could add more stats calculations here
            stats = {
                "active_markets": active_markets,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Broadcast to all connected clients
            # (Implementation would iterate through ws_manager.active_connections)
            
            # Wait before next update (5 seconds)
            await asyncio.sleep(5)
    
    finally:
        db.close()


async def start_background_tasks():
    """
    Start all background tasks for real-time updates
    """
    print("Starting background tasks for real-time updates...")
    
    # Create tasks
    tasks = [
        asyncio.create_task(broadcast_market_updates()),
        asyncio.create_task(periodic_stats_update())
    ]
    
    # Run all tasks concurrently
    await asyncio.gather(*tasks)


def start_update_server():
    """
    Helper to start the background update server
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_background_tasks())
