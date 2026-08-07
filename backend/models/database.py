"""
BIAR Protocol - Database Models
SQLAlchemy models for markets, orders, and positions
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()


class MarketStatus(enum.Enum):
    ACTIVE = "active"
    PENDING_RESOLUTION = "pending_resolution"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class MarketType(enum.Enum):
    BINARY = "binary"
    MULTI_OUTCOME = "multi_outcome"


class OrderSide(enum.Enum):
    BUY = "buy"
    SELL = "sell"


class Market(Base):
    """Prediction market table"""
    __tablename__ = "markets"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(String(5000))
    category = Column(String(100), index=True)  # e.g., "crypto", "politics", "sports"
    
    market_type = Column(Enum(MarketType), default=MarketType.BINARY)
    outcomes = Column(JSON, nullable=False)  # List of possible outcomes
    
    status = Column(Enum(MarketStatus), default=MarketStatus.ACTIVE)
    resolution_source = Column(String(200))  # Oracle feed URL or contract address
    
    created_at = Column(DateTime, default=datetime.utcnow)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime)
    
    # AMM state
    initial_liquidity = Column(Float, default=1000.0)
    current_liquidity = Column(Float)
    total_volume = Column(Float, default=0.0)
    
    # Smart contract references
    contract_address = Column(String(66))
    chain_id = Column(Integer, default=11155111)  # Default Sepolia
    
    # Resolution
    winning_outcome = Column(String(200))
    oracle_data = Column(JSON)
    
    # Relationships
    orders = relationship("Order", back_populates="market", cascade="all, delete-orphan")
    positions = relationship("Position", back_populates="market", cascade="all, delete-orphan")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "market_type": self.market_type.value,
            "outcomes": self.outcomes,
            "status": self.status.value,
            "resolution_source": self.resolution_source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "initial_liquidity": self.initial_liquidity,
            "current_liquidity": self.current_liquidity,
            "total_volume": self.total_volume,
            "contract_address": self.contract_address,
            "chain_id": self.chain_id,
            "winning_outcome": self.winning_outcome,
            "probabilities": self.get_probabilities()
        }
    
    def get_probabilities(self) -> dict:
        """Calculate current probabilities based on liquidity distribution"""
        if not self.current_liquidity or not self.outcomes:
            n = len(self.outcomes) if self.outcomes else 2
            return {outcome: 1.0/n for outcome in (self.outcomes or ["YES", "NO"])}
        
        # Simplified probability calculation
        # In production, this would use the AMM engine
        total = sum(self.current_liquidity.values()) if isinstance(self.current_liquidity, dict) else self.current_liquidity
        if total == 0:
            return {outcome: 1.0/len(self.outcomes) for outcome in self.outcomes}
        
        if isinstance(self.current_liquidity, dict):
            return {k: v/total for k, v in self.current_liquidity.items()}
        
        # Default equal distribution
        return {outcome: 1.0/len(self.outcomes) for outcome in self.outcomes}


class Order(Base):
    """Order table for tracking trades"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(Integer, ForeignKey("markets.id"), nullable=False)
    user_address = Column(String(42), index=True)  # Ethereum wallet address
    
    side = Column(Enum(OrderSide), nullable=False)
    outcome = Column(String(100), nullable=False)
    
    amount = Column(Float, nullable=False)  # Amount in base currency (e.g., USDC)
    shares = Column(Float)  # Number of outcome tokens received
    price = Column(Float)  # Effective price per share
    
    slippage_tolerance = Column(Float, default=0.01)  # 1% default
    executed_slippage = Column(Float)
    
    status = Column(String(20), default="pending")  # pending, executed, cancelled, failed
    tx_hash = Column(String(66))  # Blockchain transaction hash
    
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime)
    
    # Relationships
    market = relationship("Market", back_populates="orders")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "market_id": self.market_id,
            "user_address": self.user_address,
            "side": self.side.value,
            "outcome": self.outcome,
            "amount": self.amount,
            "shares": self.shares,
            "price": self.price,
            "slippage_tolerance": self.slippage_tolerance,
            "executed_slippage": self.executed_slippage,
            "status": self.status,
            "tx_hash": self.tx_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None
        }


class Position(Base):
    """User positions in markets"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(Integer, ForeignKey("markets.id"), nullable=False)
    user_address = Column(String(42), index=True)
    
    outcome = Column(String(100), nullable=False)
    shares = Column(Float, default=0.0)
    average_cost = Column(Float, default=0.0)  # Average cost per share
    
    realized_pnl = Column(Float, default=0.0)
    unrealized_pnl = Column(Float, default=0.0)
    
    claimed = Column(Boolean, default=False)
    claim_tx_hash = Column(String(66))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    market = relationship("Market", back_populates="positions")
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "market_id": self.market_id,
            "user_address": self.user_address,
            "outcome": self.outcome,
            "shares": self.shares,
            "average_cost": self.average_cost,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "claimed": self.claimed,
            "claim_tx_hash": self.claim_tx_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class OracleFeed(Base):
    """Oracle feed configuration for market resolution"""
    __tablename__ = "oracle_feeds"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    feed_url = Column(String(500))
    feed_type = Column(String(50))  # "api", "chainlink", "custom"
    
    contract_address = Column(String(66))
    chain_id = Column(Integer, default=11155111)
    
    is_active = Column(Boolean, default=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    config = Column(JSON)  # Additional configuration
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "feed_url": self.feed_url,
            "feed_type": self.feed_type,
            "contract_address": self.contract_address,
            "chain_id": self.chain_id,
            "is_active": self.is_active,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "config": self.config
        }
