"""
BIAR Protocol - Pydantic Schemas
Request/Response validation schemas for API
"""

from pydantic import BaseModel, Field, HttpUrl, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class MarketType(str, Enum):
    BINARY = "binary"
    MULTI_OUTCOME = "multi_outcome"


class MarketStatus(str, Enum):
    ACTIVE = "active"
    PENDING_RESOLUTION = "pending_resolution"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


# Market Schemas
class MarketBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    category: str = Field(..., min_length=1, max_length=100)
    market_type: MarketType = MarketType.BINARY
    outcomes: List[str] = Field(..., min_length=2)
    resolution_source: Optional[str] = None
    start_time: datetime
    end_time: datetime
    initial_liquidity: float = Field(default=1000.0, gt=0)


class MarketCreate(MarketBase):
    """Schema for creating a new market"""
    pass


class MarketUpdate(BaseModel):
    """Schema for updating an existing market"""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = Field(None, max_length=5000)
    status: Optional[MarketStatus] = None
    current_liquidity: Optional[Dict[str, float]] = None
    total_volume: Optional[float] = None


class MarketResponse(MarketBase):
    """Schema for market response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    status: MarketStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None
    current_liquidity: Optional[Any] = None
    total_volume: float = 0.0
    contract_address: Optional[str] = None
    chain_id: int = 11155111
    winning_outcome: Optional[str] = None
    probabilities: Dict[str, float]


# Order Schemas
class OrderBase(BaseModel):
    outcome: str
    side: OrderSide = OrderSide.BUY
    amount: float = Field(..., gt=0)
    slippage_tolerance: float = Field(default=0.01, ge=0, le=1)


class OrderCreate(OrderBase):
    """Schema for creating a new order"""
    user_address: str = Field(..., pattern="^0x[a-fA-F0-9]{40}$")


class OrderResponse(BaseModel):
    """Schema for order response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    market_id: int
    user_address: str
    side: OrderSide
    outcome: str
    amount: float
    shares: Optional[float] = None
    price: Optional[float] = None
    slippage_tolerance: float
    executed_slippage: Optional[float] = None
    status: str
    tx_hash: Optional[str] = None
    created_at: datetime
    executed_at: Optional[datetime] = None


# Position Schemas
class PositionResponse(BaseModel):
    """Schema for position response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    market_id: int
    user_address: str
    outcome: str
    shares: float
    average_cost: float
    realized_pnl: float
    unrealized_pnl: float
    claimed: bool
    claim_tx_hash: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# Oracle Schemas
class OracleFeedBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    feed_url: Optional[HttpUrl] = None
    feed_type: str = Field(default="api", pattern="^(api|chainlink|custom)$")
    contract_address: Optional[str] = Field(None, pattern="^0x[a-fA-F0-9]{40}$|^$")
    chain_id: int = 11155111
    config: Optional[Dict[str, Any]] = None


class OracleFeedCreate(OracleFeedBase):
    """Schema for creating oracle feed"""
    pass


class OracleFeedResponse(OracleFeedBase):
    """Schema for oracle feed response"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    is_active: bool = True
    last_updated: datetime


# Simulation Schemas
class SlippageSimulationRequest(BaseModel):
    """Schema for slippage simulation request"""
    market_id: int
    outcome: str
    amount: float = Field(..., gt=0)
    model_type: str = Field(default="lmsr", pattern="^(lmsr|cpmm)$")


class SlippageSimulationResponse(BaseModel):
    """Schema for slippage simulation response"""
    effective_price: float
    price_impact: float
    slippage_percentage: float
    cost: float
    shares_received: float
    model_used: str


class LiquidityDepthRequest(BaseModel):
    """Schema for liquidity depth simulation"""
    market_id: int
    outcome: str
    trade_sizes: List[float] = Field(default=[10, 50, 100, 500, 1000])


class LiquidityDepthResponse(BaseModel):
    """Schema for liquidity depth response"""
    trades: List[Dict[str, Any]]
    avg_slippage: float
    max_slippage: float


# Order Book Schema
class OrderBookEntry(BaseModel):
    """Single order book entry"""
    price: float
    quantity: float
    total: float


class OrderBookResponse(BaseModel):
    """Order book response"""
    market_id: int
    bids: List[OrderBookEntry]
    asks: List[OrderBookEntry]
    spread: float
    last_updated: datetime


# Generic Response
class ErrorResponse(BaseModel):
    """Error response schema"""
    error: str
    detail: Optional[str] = None
    code: Optional[int] = None


class SuccessResponse(BaseModel):
    """Generic success response"""
    message: str
    data: Optional[Any] = None
