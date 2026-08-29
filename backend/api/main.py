"""BIAR Protocol - FastAPI application entry point."""
import json
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.auth import (
    build_challenge_message,
    create_session_token,
    get_current_user,
    nonce_store,
    require_auth,
    verify_signature,
)
from core.config import settings
from core.security import RateLimitMiddleware, SecurityHeadersMiddleware
from models.database import Base
from schemas.market import (
    LimitOrderRequest,
    MarketCreate,
    MarketResponse,
    NonceRequest,
    OrderRequest,
    ResolveRequest,
    VerifyRequest,
)
from services.market_service import (
    MarketNotFound,
    MarketResolvedError,
    MarketService,
)
from api.websocket import manager

# ---------- database setup ----------

sync_url = settings.DATABASE_URL.replace("+aiosqlite", "")
engine = create_engine(
    sync_url,
    connect_args={"check_same_thread": False} if "sqlite" in sync_url else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
)

# ---------- middleware ----------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)


# ---------- helpers ----------

def svc(db: Session = Depends(get_db)) -> MarketService:
    return MarketService(db)


def _market_response(service: MarketService, market) -> dict:
    prices = service.get_prices(market)
    resp = MarketResponse.from_model(market, prices)
    return resp.model_dump()


# ---------- REST endpoints ----------


@app.get("/health")
async def health():
    return {"status": "healthy", "version": settings.VERSION}


@app.post("/api/v1/markets")
def create_market(
    data: MarketCreate,
    service: MarketService = Depends(svc),
    user: str = Depends(get_current_user),
):
    try:
        if user != "anonymous":
            data.creator = user
        market = service.create_market(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _market_response(service, market)


@app.get("/api/v1/markets")
def list_markets(
    category: str | None = Query(None),
    include_resolved: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: MarketService = Depends(svc),
):
    markets, total, page, page_size = service.list_markets(
        category=category,
        active_only=not include_resolved,
        page=page,
        page_size=page_size,
    )
    return {
        "items": [_market_response(service, m) for m in markets],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@app.get("/api/v1/markets/{market_id}")
def get_market(market_id: int, service: MarketService = Depends(svc)):
    try:
        market = service.get_market(market_id)
    except MarketNotFound:
        raise HTTPException(status_code=404, detail="Market not found")
    return _market_response(service, market)


@app.post("/api/v1/markets/{market_id}/order")
async def place_order(
    market_id: int,
    order: OrderRequest,
    service: MarketService = Depends(svc),
    user: str = Depends(get_current_user),
):
    if settings.AUTH_REQUIRED and user == "anonymous":
        raise HTTPException(status_code=401, detail="Authentication required")
    if user != "anonymous":
        order.trader = user
    try:
        trade = service.place_order(market_id, order)
    except MarketNotFound:
        raise HTTPException(status_code=404, detail="Market not found")
    except MarketResolvedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        # AMMError and validation errors -> 400
        raise HTTPException(status_code=400, detail=str(e))

    trade_data = {
        "id": trade.id,
        "trader": trade.trader,
        "outcome_index": trade.outcome_index,
        "side": trade.side,
        "shares": trade.shares,
        "amount": round(trade.amount, 6),
        "price": round(trade.price, 6),
        "created_at": trade.created_at.isoformat() if trade.created_at else "",
    }
    # Real-time broadcast to market room + global feed
    await manager.broadcast_trade(market_id, trade_data)
    market = service.get_market(market_id)
    await manager.broadcast_market(
        market_id,
        {"type": "prices", "market_id": market_id, "prices": service.get_prices(market)},
    )
    return trade_data


@app.get("/api/v1/markets/{market_id}/orderbook")
def get_orderbook(market_id: int, service: MarketService = Depends(svc)):
    try:
        return service.get_orderbook(market_id)
    except MarketNotFound:
        raise HTTPException(status_code=404, detail="Market not found")


@app.post("/api/v1/markets/{market_id}/resolve")
async def resolve_market(
    market_id: int,
    req: ResolveRequest,
    service: MarketService = Depends(svc),
):
    """Resolve a market. In production this is triggered by the oracle contract
    event, not by arbitrary API callers. Restricted here to DEBUG mode."""
    if not settings.DEBUG:
        raise HTTPException(
            status_code=403,
            detail="Resolution is oracle-only in production. Enable DEBUG for testing.",
        )
    try:
        market = service.resolve_market(market_id, req.winning_outcome)
    except MarketNotFound:
        raise HTTPException(status_code=404, detail="Market not found")
    except MarketResolvedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await manager.broadcast_market(
        market_id,
        {
            "type": "resolved",
            "market_id": market_id,
            "winning_outcome": market.winning_outcome,
        },
    )
    return _market_response(service, market)


@app.get("/api/v1/stats")
def get_stats(service: MarketService = Depends(svc)):
    return service.get_stats()


# ---------- auth endpoints ----------


@app.post("/api/v1/auth/nonce")
def auth_nonce(req: NonceRequest):
    """Issue a sign-in challenge nonce for a wallet address."""
    nonce = nonce_store.issue(req.address)
    return {
        "address": req.address,
        "nonce": nonce,
        "message": build_challenge_message(req.address, nonce),
        "expires_in": settings.NONCE_TTL_SECONDS,
    }


@app.post("/api/v1/auth/verify")
def auth_verify(req: VerifyRequest):
    """Verify a signed challenge and issue a JWT session token."""
    if not nonce_store.consume(req.address, req.nonce):
        raise HTTPException(status_code=400, detail="Invalid or expired nonce")
    message = build_challenge_message(req.address, req.nonce)
    if not verify_signature(req.address, message, req.signature):
        raise HTTPException(status_code=401, detail="Signature verification failed")
    token = create_session_token(req.address)
    return {
        "token": token,
        "address": req.address.lower(),
        "expires_in": settings.JWT_EXPIRY_SECONDS,
    }


@app.get("/api/v1/auth/me")
def auth_me(user: str = Depends(get_current_user)):
    return {"address": user}


# ---------- limit order endpoints ----------


@app.post("/api/v1/markets/{market_id}/limit-order")
async def place_limit_order(
    market_id: int,
    req: LimitOrderRequest,
    service: MarketService = Depends(svc),
    user: str = Depends(require_auth),
):
    try:
        order = service.place_limit_order(market_id, user, req)
    except MarketNotFound:
        raise HTTPException(status_code=404, detail="Market not found")
    except MarketResolvedError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    from schemas.market import LimitOrderResponse

    data = LimitOrderResponse.from_model(order).model_dump()
    await manager.broadcast_market(
        market_id,
        {"type": "limit_order", "market_id": market_id, "order": data},
    )
    return data


@app.get("/api/v1/markets/{market_id}/limit-orders")
def list_limit_orders(
    market_id: int,
    mine_only: bool = Query(False),
    service: MarketService = Depends(svc),
    user: str = Depends(get_current_user),
):
    try:
        orders = service.list_limit_orders(
            market_id, trader=user if mine_only and user != "anonymous" else None
        )
    except MarketNotFound:
        raise HTTPException(status_code=404, detail="Market not found")
    from schemas.market import LimitOrderResponse

    return [LimitOrderResponse.from_model(o).model_dump() for o in orders]


@app.delete("/api/v1/limit-orders/{order_ref}")
def cancel_limit_order(
    order_ref: str,
    service: MarketService = Depends(svc),
    user: str = Depends(require_auth),
):
    if not service.cancel_limit_order(order_ref, user):
        raise HTTPException(
            status_code=404, detail="Order not found, not cancellable, or not yours"
        )
    return {"order_ref": order_ref, "status": "cancelled"}


@app.post("/api/v1/markets/{market_id}/match")
def match_limit_orders(market_id: int, service: MarketService = Depends(svc)):
    """Run the limit-order matching loop (also invoked after each trade)."""
    try:
        filled = service.match_limit_orders(market_id)
    except MarketNotFound:
        raise HTTPException(status_code=404, detail="Market not found")
    return {"market_id": market_id, "filled": filled}


# ---------- portfolio endpoints ----------


@app.get("/api/v1/portfolio")
def get_portfolio(
    service: MarketService = Depends(svc),
    user: str = Depends(require_auth),
):
    return service.get_portfolio(user)


@app.post("/api/v1/markets/{market_id}/claim")
def claim_winnings(
    market_id: int,
    service: MarketService = Depends(svc),
    user: str = Depends(require_auth),
):
    try:
        return service.claim_winnings(user, market_id)
    except MarketNotFound:
        raise HTTPException(status_code=404, detail="Market not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------- WebSocket endpoints ----------


@app.websocket("/ws/market/{market_id}")
async def ws_market(websocket: WebSocket, market_id: int):
    try:
        await manager.connect_market(market_id, websocket)
        # Send current state on connect
        db = SessionLocal()
        try:
            service = MarketService(db)
            market = service.get_market(market_id)
            await websocket.send_json(
                {
                    "type": "prices",
                    "market_id": market_id,
                    "prices": service.get_prices(market),
                }
            )
        finally:
            db.close()
        while True:
            # Keep connection alive; ignore client messages except ping
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect_market(market_id, websocket)
    except Exception:
        await manager.disconnect_market(market_id, websocket)


@app.websocket("/ws/feed")
async def ws_feed(websocket: WebSocket):
    try:
        await manager.connect_feed(websocket)
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await manager.disconnect_feed(websocket)
    except Exception:
        await manager.disconnect_feed(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)