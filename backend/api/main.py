"""
BIAR Protocol - FastAPI Main Application
REST API for prediction markets
"""

from fastapi import FastAPI, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json

from models.database import Base, Market, Order, Position, OracleFeed, MarketStatus
from schemas.market import (
    MarketCreate, MarketResponse, MarketUpdate,
    OrderCreate, OrderResponse,
    PositionResponse,
    OracleFeedCreate, OracleFeedResponse,
    SlippageSimulationRequest, SlippageSimulationResponse,
    LiquidityDepthRequest, LiquidityDepthResponse,
    SuccessResponse, ErrorResponse
)
from services.market_service import MarketService, OrderService, OracleService
from services.rewards import rewards_manager
from core.amm import LMSR, ConstantProductAMM, SimulationEngine
from core.limit_orders import limit_order_engine
from api.websocket import ws_manager

# Database setup
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./biar.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
Base.metadata.create_all(bind=engine)

# Initialize AMM engine (using LMSR as default)
amm_engine = LMSR(b=100.0, fee_rate=0.003)
simulation_engine = SimulationEngine(amm_engine)

# FastAPI app
app = FastAPI(
    title="BIAR Protocol API",
    description="Decentralized Prediction Market API with AMM-based pricing",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== Market Endpoints ====================

@app.post("/api/v1/markets", response_model=MarketResponse, tags=["Markets"])
async def create_market(market: MarketCreate, db: Session = Depends(get_db)):
    """Create a new prediction market"""
    service = MarketService(db)
    
    # Validate outcomes
    if len(market.outcomes) < 2:
        raise HTTPException(status_code=400, detail="Market must have at least 2 outcomes")
    
    if market.start_time >= market.end_time:
        raise HTTPException(status_code=400, detail="Start time must be before end time")
    
    db_market = service.create_market(market)
    return db_market


@app.get("/api/v1/markets", response_model=List[MarketResponse], tags=["Markets"])
async def get_markets(
    status: Optional[MarketStatus] = None,
    category: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """Get list of active prediction markets"""
    service = MarketService(db)
    markets = service.get_markets(status=status, category=category, limit=limit, offset=offset)
    return markets


@app.get("/api/v1/markets/{market_id}", response_model=MarketResponse, tags=["Markets"])
async def get_market(market_id: int, db: Session = Depends(get_db)):
    """Get details of a specific market"""
    service = MarketService(db)
    market = service.get_market(market_id)
    
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    return market


@app.put("/api/v1/markets/{market_id}", response_model=MarketResponse, tags=["Markets"])
async def update_market(market_id: int, market_update: MarketUpdate, db: Session = Depends(get_db)):
    """Update an existing market"""
    service = MarketService(db)
    market = service.update_market(market_id, market_update)
    
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    return market


@app.post("/api/v1/markets/{market_id}/resolve", response_model=MarketResponse, tags=["Markets"])
async def resolve_market(
    market_id: int,
    winning_outcome: str,
    oracle_data: Optional[dict] = None,
    db: Session = Depends(get_db)
):
    """Resolve a market with the winning outcome"""
    service = MarketService(db)
    
    try:
        market = service.resolve_market(market_id, winning_outcome, oracle_data)
        if not market:
            raise HTTPException(status_code=404, detail="Market not found")
        return market
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Order Endpoints ====================

@app.post("/api/v1/markets/{market_id}/order", response_model=dict, tags=["Orders"])
async def place_order(market_id: int, order: OrderCreate, db: Session = Depends(get_db)):
    """Place an order for outcome tokens"""
    service = OrderService(db, amm_engine)
    
    try:
        result = service.create_order(market_id, order)
        
        if result["status"] == "rejected":
            raise HTTPException(status_code=400, detail=result["reason"])
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/markets/{market_id}/orderbook", tags=["Orders"])
async def get_orderbook(market_id: int, db: Session = Depends(get_db)):
    """Get market order book (simulated from AMM state)"""
    market_service = MarketService(db)
    market = market_service.get_market(market_id)
    
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    # Generate synthetic order book from AMM state
    quantities = market.current_liquidity or {}
    if isinstance(quantities, str):
        import json
        quantities = json.loads(quantities)
    
    bids = []
    asks = []
    
    for outcome in market.outcomes:
        price = amm_engine.get_price(quantities, outcome)
        qty = quantities.get(outcome, 0)
        
        # Simulate bid/ask around current price
        spread = 0.01  # 1% spread
        
        bids.append({
            "outcome": outcome,
            "price": round(price * (1 - spread/2), 4),
            "quantity": round(qty * 0.5, 2),
            "total": round(qty * 0.5 * price, 2)
        })
        
        asks.append({
            "outcome": outcome,
            "price": round(price * (1 + spread/2), 4),
            "quantity": round(qty * 0.5, 2),
            "total": round(qty * 0.5 * price, 2)
        })
    
    return {
        "market_id": market_id,
        "bids": sorted(bids, key=lambda x: x["price"], reverse=True),
        "asks": sorted(asks, key=lambda x: x["price"]),
        "spread": spread,
        "last_updated": datetime.utcnow().isoformat()
    }


@app.get("/api/v1/users/{user_address}/positions", response_model=List[PositionResponse], tags=["Positions"])
async def get_user_positions(
    user_address: str,
    market_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get positions for a specific user"""
    service = MarketService(db)
    return service.get_user_positions(user_address, market_id)


# ==================== Oracle Endpoints ====================

@app.get("/api/v1/oracles", response_model=List[OracleFeedResponse], tags=["Oracles"])
async def get_oracle_feeds(active_only: bool = True, db: Session = Depends(get_db)):
    """Get all configured oracle feeds"""
    service = OracleService(db)
    return service.get_oracle_feeds(active_only=active_only)


@app.post("/api/v1/oracles", response_model=OracleFeedResponse, tags=["Oracles"])
async def create_oracle_feed(oracle: OracleFeedCreate, db: Session = Depends(get_db)):
    """Create a new oracle feed configuration"""
    service = OracleService(db)
    return service.create_oracle_feed(
        name=oracle.name,
        feed_url=str(oracle.feed_url) if oracle.feed_url else None,
        feed_type=oracle.feed_type,
        contract_address=oracle.contract_address,
        chain_id=oracle.chain_id,
        config=oracle.config
    )


# ==================== Simulation Endpoints ====================

@app.post("/api/v1/simulation/slippage", response_model=SlippageSimulationResponse, tags=["Simulation"])
async def simulate_slippage(request: SlippageSimulationRequest, db: Session = Depends(get_db)):
    """Simulate slippage for a potential trade"""
    market_service = MarketService(db)
    market = market_service.get_market(request.market_id)
    
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    quantities = market.current_liquidity or {}
    if isinstance(quantities, str):
        import json
        quantities = json.loads(quantities)
    
    # Use appropriate AMM model
    if request.model_type == "cpmm":
        sim_amm = ConstantProductAMM()
    else:
        sim_amm = LMSR(b=100.0)
    
    cost = sim_amm.calculate_cost(quantities, request.outcome, request.amount)
    eff_price, price_impact, slippage_pct = sim_amm.calculate_slippage(
        quantities, request.outcome, request.amount
    )
    
    shares = request.amount / eff_price if eff_price > 0 else 0
    
    return {
        "effective_price": round(eff_price, 6),
        "price_impact": round(price_impact, 6),
        "slippage_percentage": round(slippage_pct, 4),
        "cost": round(cost, 4),
        "shares_received": round(shares, 4),
        "model_used": request.model_type
    }


@app.post("/api/v1/simulation/liquidity-depth", response_model=LiquidityDepthResponse, tags=["Simulation"])
async def simulate_liquidity_depth(request: LiquidityDepthRequest, db: Session = Depends(get_db)):
    """Simulate liquidity depth analysis"""
    market_service = MarketService(db)
    market = market_service.get_market(request.market_id)
    
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    quantities = market.current_liquidity or {}
    if isinstance(quantities, str):
        import json
        quantities = json.loads(quantities)
    
    result = simulation_engine.simulate_liquidity_depth(
        quantities, request.outcome, request.trade_sizes
    )
    
    return {
        "trades": result["trades"],
        "avg_slippage": round(result["avg_slippage"], 4),
        "max_slippage": round(result["max_slippage"], 4)
    }


# ==================== WebSocket Endpoints ====================

@app.websocket("/ws/market/{market_id}/{client_id}")
async def websocket_market_endpoint(websocket: WebSocket, market_id: int, client_id: str, db: Session = Depends(get_db)):
    """
    WebSocket endpoint for real-time market updates.
    Provides live price updates, probability changes, and order notifications.
    """
    await ws_manager.connect(websocket, client_id, market_id)
    
    try:
        while True:
            # Receive client messages (e.g., subscribe/unsubscribe)
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                # Respond to ping to keep connection alive
                await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
            
            elif message.get("type") == "get_market_state":
                # Send current market state on demand
                service = MarketService(db)
                market = service.get_market(market_id)
                
                if market:
                    quantities = market.current_liquidity or {}
                    if isinstance(quantities, str):
                        quantities = json.loads(quantities)
                    
                    prices = {}
                    probabilities = {}
                    
                    for outcome in market.outcomes:
                        price = amm_engine.get_price(quantities, outcome)
                        prices[outcome] = round(price, 4)
                        probabilities[outcome] = round(price * 100, 2)  # Convert to percentage
                    
                    await websocket.send_json({
                        "type": "market_state",
                        "market_id": market_id,
                        "market": {
                            "id": market.id,
                            "title": market.title,
                            "description": market.description,
                            "outcomes": market.outcomes,
                            "prices": prices,
                            "probabilities": probabilities,
                            "total_volume": round(market.total_volume, 2),
                            "status": market.status.value if market.status else "active",
                            "end_time": market.end_time.isoformat() if market.end_time else None
                        },
                        "timestamp": datetime.utcnow().isoformat()
                    })
    
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id, websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        ws_manager.disconnect(client_id, websocket)


@app.websocket("/ws/user/{wallet_address}")
async def websocket_user_endpoint(websocket: WebSocket, wallet_address: str, db: Session = Depends(get_db)):
    """
    WebSocket endpoint for user-specific updates.
    Provides portfolio updates, order confirmations, and notifications.
    """
    await ws_manager.connect(websocket, wallet_address)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
            
            elif message.get("type") == "get_portfolio":
                # Send current portfolio state
                service = MarketService(db)
                positions = service.get_user_positions(wallet_address)
                
                portfolio_data = {
                    "positions": [
                        {
                            "market_id": pos.market_id,
                            "outcome": pos.outcome,
                            "shares": pos.shares,
                            "average_cost": pos.average_cost,
                            "current_value": round(pos.shares * pos.average_cost, 2)
                        }
                        for pos in positions
                    ],
                    "total_value": sum(pos.shares * pos.average_cost for pos in positions)
                }
                
                await websocket.send_json({
                    "type": "portfolio_state",
                    "data": portfolio_data,
                    "timestamp": datetime.utcnow().isoformat()
                })
    
    except WebSocketDisconnect:
        ws_manager.disconnect(wallet_address, websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        ws_manager.disconnect(wallet_address, websocket)


@app.websocket("/ws/feed")
async def websocket_feed_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for global market feed.
    Provides updates on all markets (price ticks, new markets, settlements).
    """
    client_id = "feed_" + datetime.utcnow().isoformat()
    await ws_manager.connect(websocket, client_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.utcnow().isoformat()})
    
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id, websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        ws_manager.disconnect(client_id, websocket)


# ==================== Stats Endpoints ====================

@app.get("/api/v1/stats", tags=["Stats"])
async def get_stats(db: Session = Depends(get_db)):
    """Get platform statistics"""
    market_service = MarketService(db)
    
    return {
        "active_markets": market_service.get_active_markets_count(),
        "total_volume": round(market_service.get_total_volume(), 2),
        "timestamp": datetime.utcnow().isoformat()
    }


# ==================== Limit Order Endpoints ====================

@app.post("/api/v1/orders", tags=["Limit Orders"])
async def place_limit_order(
    market_id: int,
    outcome: str,
    side: str,
    quantity: float,
    price: float,
    order_type: str = "LIMIT",
    user_address: str = None
):
    """
    Place a limit order for an outcome token
    
    - **market_id**: Market to trade on
    - **outcome**: Outcome to trade
    - **side**: BUY or SELL
    - **quantity**: Number of shares
    - **price**: Limit price
    - **order_type**: LIMIT, MARKET, STOP_LOSS, CONDITIONAL
    """
    try:
        order = limit_order_engine.place_order(
            market_id=market_id,
            outcome=outcome,
            side=side,
            quantity=quantity,
            price=price,
            order_type=order_type,
            user_address=user_address
        )
        
        # Broadcast order update via WebSocket
        await ws_manager.broadcast_order_update(market_id, {
            "order_id": order.order_id,
            "market_id": order.market_id,
            "outcome": order.outcome,
            "side": order.side,
            "quantity": order.quantity,
            "price": order.price,
            "status": order.status.value,
            "timestamp": order.created_at.isoformat()
        })
        
        return {
            "success": True,
            "order_id": order.order_id,
            "status": order.status.value,
            "message": "Order placed successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/orders/{order_id}", tags=["Limit Orders"])
async def get_order(order_id: str):
    """Get details of a specific order"""
    try:
        # Find order in engine
        all_orders = limit_order_engine.get_all_orders()
        order = next((o for o in all_orders if o.order_id == order_id), None)
        
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return {
            "order_id": order.order_id,
            "market_id": order.market_id,
            "outcome": order.outcome,
            "side": order.side,
            "quantity": order.quantity,
            "price": order.price,
            "status": order.status.value,
            "filled_quantity": order.filled_quantity,
            "created_at": order.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/v1/orders/{order_id}", tags=["Limit Orders"])
async def cancel_order(order_id: str, market_id: int = None):
    """Cancel a pending order"""
    try:
        success = limit_order_engine.cancel_order(order_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Order not found or already cancelled")
        
        # Broadcast cancellation via WebSocket
        if market_id:
            await ws_manager.broadcast_order_update(market_id, {
                "order_id": order_id,
                "status": "CANCELLED",
                "timestamp": datetime.utcnow().isoformat()
            })
        
        return {"success": True, "message": "Order cancelled successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/users/{user_address}/orders", tags=["Limit Orders"])
async def get_user_orders(user_address: str, market_id: int = None):
    """Get all orders for a user"""
    try:
        orders = limit_order_engine.get_user_orders(user_address)
        
        # Filter by market if specified
        if market_id:
            orders = [o for o in orders if o.market_id == market_id]
        
        return {
            "user_address": user_address,
            "orders": [
                {
                    "order_id": o.order_id,
                    "market_id": o.market_id,
                    "outcome": o.outcome,
                    "side": o.side,
                    "quantity": o.quantity,
                    "price": o.price,
                    "status": o.status.value,
                    "filled_quantity": o.filled_quantity
                }
                for o in orders
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/markets/{market_id}/orderbook", tags=["Limit Orders"])
async def get_market_orderbook(market_id: int):
    """Get order book for a market"""
    try:
        outcomes = ["YES", "NO"]  # Default outcomes, should come from market
        
        orderbooks = {}
        for outcome in outcomes:
            best_bid, best_ask = limit_order_engine.get_best_bid_ask(market_id, outcome)
            depth = limit_order_engine.get_order_book_depth(market_id, outcome, 5)
            
            orderbooks[outcome] = {
                "best_bid": best_bid,
                "best_ask": best_ask,
                "bids": depth.get("bids", []),
                "asks": depth.get("asks", [])
            }
        
        return {
            "market_id": market_id,
            "orderbooks": orderbooks,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Analytics Endpoints ====================

@app.get("/api/v1/markets/{market_id}/analytics", tags=["Analytics"])
async def get_market_analytics(market_id: int, timeframe: str = "24h", db: Session = Depends(get_db)):
    """Get advanced analytics for a market"""
    try:
        service = MarketService(db)
        market = service.get_market(market_id)
        
        if not market:
            raise HTTPException(status_code=404, detail="Market not found")
        
        # Generate mock analytics data
        # In production, this would query a time-series database
        prices = [0.45 + (i * 0.001) for i in range(96)]  # 24h of 15-min data
        volumes = [1000 + (i * 10) for i in range(96)]
        
        return {
            "market_id": market_id,
            "title": market.title,
            "prices": prices,
            "volumes": volumes,
            "timeframe": timeframe,
            "current_price": prices[-1],
            "high_24h": max(prices),
            "low_24h": min(prices),
            "volume_24h": sum(volumes),
            "change_24h": round((prices[-1] - prices[0]) / prices[0] * 100, 2),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Leaderboard Endpoints ====================

@app.get("/api/v1/leaderboard", tags=["Leaderboard"])
async def get_leaderboard(
    timeframe: str = "24h",
    category: str = "profit",
    limit: int = 100
):
    """
    Get trader leaderboard
    
    - **timeframe**: 24h, 7d, 30d, all
    - **category**: profit, roi, volume, winrate, followers
    - **limit**: Max number of traders to return (1-100)
    """
    try:
        # Use rewards manager to get leaderboard data
        leaderboard = rewards_manager.get_leaderboard_by_rewards(limit=min(limit, 100))
        
        return {
            "timeframe": timeframe,
            "category": category,
            "traders": leaderboard,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/traders/{user_address}/stats", tags=["Leaderboard"])
async def get_trader_stats(user_address: str):
    """Get detailed stats for a specific trader"""
    try:
        summary = rewards_manager.get_reward_summary(user_address)
        
        return {
            "user_address": user_address,
            "stats": summary,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ==================== Rewards Endpoints ====================

@app.post("/api/v1/rewards/claim", tags=["Rewards"])
async def claim_rewards(user_address: str):
    """Claim all pending rewards for a user"""
    try:
        success, amount = rewards_manager.claim_all_rewards(user_address)
        
        if not success:
            return {"success": False, "message": "No pending rewards to claim"}
        
        return {
            "success": True,
            "user_address": user_address,
            "amount_claimed": round(amount, 2),
            "message": f"Successfully claimed ${amount:.2f}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/rewards/{user_address}", tags=["Rewards"])
async def get_user_rewards(user_address: str):
    """Get reward summary for a user"""
    try:
        summary = rewards_manager.get_reward_summary(user_address)
        
        return {
            "user_address": user_address,
            "rewards": summary,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/rewards/referral-link", tags=["Rewards"])
async def create_referral_link(user_address: str):
    """Create or get referral link for a user"""
    try:
        code = rewards_manager.create_referral_link(user_address)
        
        return {
            "user_address": user_address,
            "referral_code": code,
            "referral_link": f"https://biar.protocol/ref?code={code}",
            "message": "Share this link to earn rewards when friends trade"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "BIAR Protocol API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
