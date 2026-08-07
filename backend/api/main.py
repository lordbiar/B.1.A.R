"""
BIAR Protocol - FastAPI Main Application
REST API for prediction markets
"""

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

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
from core.amm import LMSR, ConstantProductAMM, SimulationEngine

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


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "BIAR Protocol API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
