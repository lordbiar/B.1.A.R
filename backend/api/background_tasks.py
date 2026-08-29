"""BIAR Protocol - Background tasks for real-time updates.

Periodically broadcasts live prices for all active markets to WebSocket
subscribers and refreshes global platform statistics.
"""
import asyncio
import json
from datetime import datetime

from models.database import MarketModel, engine
from api.websocket import manager

# Broadcast cadence
MARKET_UPDATE_INTERVAL = 0.5  # seconds between price broadcasts
STATS_UPDATE_INTERVAL = 5.0  # seconds between stats broadcasts


async def broadcast_market_updates() -> None:
    """Continuously broadcast current prices for every active market."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from services.market_service import MarketService

    while True:
        db = Session(bind=engine)
        try:
            service = MarketService(db)
            markets = service.list_markets(active_only=True)
            for market in markets:
                try:
                    prices = service.get_prices(market)
                    await manager.broadcast_market(
                        market.id,
                        {
                            "type": "prices",
                            "market_id": market.id,
                            "prices": [round(p, 4) for p in prices],
                        },
                    )
                    await manager.broadcast_feed(
                        {
                            "type": "prices",
                            "market_id": market.id,
                            "prices": [round(p, 4) for p in prices],
                        }
                    )
                except Exception as e:  # never kill the loop for one market
                    print(f"Error broadcasting update for market {market.id}: {e}")
        except Exception as e:
            print(f"Background market update error: {e}")
        finally:
            db.close()

        await asyncio.sleep(MARKET_UPDATE_INTERVAL)


async def periodic_stats_update() -> None:
    """Periodically compute and broadcast platform statistics."""
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from models.database import TradeModel

    while True:
        db = Session(bind=engine)
        try:
            active_markets = db.execute(
                select(func.count(MarketModel.id)).where(MarketModel.resolved.is_(False))
            ).scalar_one()
            total_trades = db.execute(select(func.count(TradeModel.id))).scalar_one()
            stats = {
                "type": "stats",
                "active_markets": active_markets,
                "total_trades": total_trades,
                "timestamp": datetime.utcnow().isoformat(),
            }
            await manager.broadcast_feed(stats)
        except Exception as e:
            print(f"Background stats update error: {e}")
        finally:
            db.close()

        await asyncio.sleep(STATS_UPDATE_INTERVAL)


async def start_background_tasks() -> None:
    """Start all background tasks for real-time updates."""
    print("Starting background tasks for real-time updates...")
    tasks = [
        asyncio.create_task(broadcast_market_updates()),
        asyncio.create_task(periodic_stats_update()),
    ]
    await asyncio.gather(*tasks)


def start_update_server() -> None:
    """Helper to run background tasks in a standalone event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_background_tasks())