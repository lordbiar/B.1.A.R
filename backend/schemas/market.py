"""BIAR Protocol - Pydantic schemas for request/response validation."""
import json
import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from core.config import settings

# Ethereum address pattern (basic sanity; checksum validation happens on-chain)
ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


class MarketCreate(BaseModel):
    """Request to create a new prediction market."""

    title: str = Field(..., min_length=5, max_length=settings.MAX_TITLE_LENGTH)
    description: str = Field("", max_length=settings.MAX_DESCRIPTION_LENGTH)
    outcomes: list[str] = Field(..., min_length=2, max_length=settings.MAX_OUTCOMES)
    category: str = Field("other", max_length=50)
    creator: str = Field("anonymous", max_length=42)
    end_time: Optional[str] = None  # ISO 8601

    @field_validator("outcomes")
    @classmethod
    def validate_outcomes(cls, v: list[str]) -> list[str]:
        cleaned = []
        for o in v:
            o = o.strip()
            if not o or len(o) > 50:
                raise ValueError("Each outcome must be 1-50 characters")
            if o.lower() in (x.lower() for x in cleaned):
                raise ValueError("Outcome names must be unique")
            cleaned.append(o)
        return cleaned

    @field_validator("creator")
    @classmethod
    def validate_creator(cls, v: str) -> str:
        if v != "anonymous" and not ETH_ADDRESS_RE.match(v):
            raise ValueError("creator must be a valid Ethereum address or 'anonymous'")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        allowed = {"crypto", "politics", "sports", "finance", "other"}
        if v not in allowed:
            raise ValueError(f"category must be one of {sorted(allowed)}")
        return v


class OrderRequest(BaseModel):
    """Request to place a trade against the AMM."""

    trader: str = Field("anonymous", max_length=42)
    outcome_index: int = Field(..., ge=0)
    side: str = Field(..., pattern="^(buy|sell)$")
    shares: float = Field(..., gt=0)
    max_slippage: Optional[float] = Field(None, ge=0, le=1.0)

    @field_validator("trader")
    @classmethod
    def validate_trader(cls, v: str) -> str:
        if v != "anonymous" and not ETH_ADDRESS_RE.match(v):
            raise ValueError("trader must be a valid Ethereum address or 'anonymous'")
        return v

    @field_validator("shares")
    @classmethod
    def validate_shares(cls, v: float) -> float:
        if v < settings.MIN_TRADE_AMOUNT:
            raise ValueError(f"shares must be >= {settings.MIN_TRADE_AMOUNT}")
        if v > settings.MAX_TRADE_AMOUNT:
            raise ValueError(f"shares must be <= {settings.MAX_TRADE_AMOUNT}")
        return v


class ResolveRequest(BaseModel):
    """Request to resolve a market (oracle-authorized callers only)."""

    resolver: str = Field(..., max_length=42)
    winning_outcome: int = Field(..., ge=0)

    @field_validator("resolver")
    @classmethod
    def validate_resolver(cls, v: str) -> str:
        if not ETH_ADDRESS_RE.match(v):
            raise ValueError("resolver must be a valid Ethereum address")
        return v


class TradeResponse(BaseModel):
    id: int
    market_id: int
    trader: str
    outcome_index: int
    side: str
    shares: float
    amount: float
    price: float
    created_at: str


class MarketResponse(BaseModel):
    id: int
    title: str
    description: str
    category: str
    outcomes: list[str]
    creator: str
    created_at: str
    end_time: Optional[str] = None
    resolved: bool
    winning_outcome: Optional[int] = None
    total_volume: float
    prices: list[float]
    liquidity_b: float

    @classmethod
    def from_model(cls, m, prices: list[float]) -> "MarketResponse":
        return cls(
            id=m.id,
            title=m.title,
            description=m.description,
            category=m.category,
            outcomes=json.loads(m.outcomes),
            creator=m.creator,
            created_at=m.created_at.isoformat() if m.created_at else "",
            end_time=m.end_time.isoformat() if m.end_time else None,
            resolved=m.resolved,
            winning_outcome=m.winning_outcome,
            total_volume=m.total_volume,
            prices=prices,
            liquidity_b=m.liquidity_b,
        )


class OrderBookResponse(BaseModel):
    market_id: int
    outcomes: list[str]
    prices: list[float]
    depth: list[dict]  # per-outcome depth ladder


class StatsResponse(BaseModel):
    active_markets: int
    total_markets: int
    total_volume: float
    total_trades: int


# ---------- auth ----------


class NonceRequest(BaseModel):
    """Request a sign-in challenge nonce for a wallet address."""

    address: str = Field(..., max_length=42)

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not ETH_ADDRESS_RE.match(v):
            raise ValueError("address must be a valid Ethereum address")
        return v


class VerifyRequest(BaseModel):
    """Submit a signed challenge to obtain a JWT session token."""

    address: str = Field(..., max_length=42)
    signature: str = Field(..., max_length=132)
    nonce: str = Field(..., max_length=64)

    @field_validator("address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not ETH_ADDRESS_RE.match(v):
            raise ValueError("address must be a valid Ethereum address")
        return v


class SessionResponse(BaseModel):
    token: str
    address: str
    expires_in: int


# ---------- limit orders ----------


class LimitOrderRequest(BaseModel):
    """Request to place a resting limit order."""

    outcome_index: int = Field(..., ge=0)
    side: str = Field(..., pattern="^(buy|sell)$")
    quantity: float = Field(..., gt=0)
    limit_price: float = Field(..., gt=0, lt=1)
    expires_at: Optional[str] = None  # ISO 8601

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, v: float) -> float:
        if v > settings.MAX_TRADE_AMOUNT:
            raise ValueError(f"quantity must be <= {settings.MAX_TRADE_AMOUNT}")
        return v


class LimitOrderResponse(BaseModel):
    order_ref: str
    market_id: int
    trader: str
    outcome_index: int
    side: str
    quantity: float
    limit_price: float
    filled_quantity: float
    status: str
    created_at: str
    expires_at: Optional[str] = None

    @classmethod
    def from_model(cls, o) -> "LimitOrderResponse":
        return cls(
            order_ref=o.order_ref,
            market_id=o.market_id,
            trader=o.trader,
            outcome_index=o.outcome_index,
            side=o.side,
            quantity=o.quantity,
            limit_price=o.limit_price,
            filled_quantity=o.filled_quantity,
            status=o.status,
            created_at=o.created_at.isoformat() if o.created_at else "",
            expires_at=o.expires_at.isoformat() if o.expires_at else None,
        )


# ---------- portfolio ----------


class PositionResponse(BaseModel):
    market_id: int
    market_title: str
    outcome_index: int
    outcome_name: str
    shares: float
    cost_basis: float
    avg_price: float
    current_price: float
    value: float
    unrealized_pnl: float
    realized_pnl: float
    resolved: bool
    winning: bool
    claimable: float


class PortfolioResponse(BaseModel):
    trader: str
    positions: list[PositionResponse]
    total_value: float
    total_cost_basis: float
    total_unrealized_pnl: float
    total_realized_pnl: float


# ---------- pagination ----------


class PaginatedMarkets(BaseModel):
    items: list[MarketResponse]
    total: int
    page: int
    page_size: int
    pages: int
