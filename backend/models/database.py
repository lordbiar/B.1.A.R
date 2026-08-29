"""BIAR Protocol - SQLAlchemy database models."""
import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship

from core.config import settings

# Engine for DDL and sessions. SQLite check_same_thread disabled for TestClient.
_engine_url = settings.DATABASE_URL.replace("+aiosqlite", "")
engine = create_engine(
    _engine_url,
    connect_args={"check_same_thread": False} if "sqlite" in _engine_url else {},
)

Base = declarative_base()


class MarketModel(Base):
    __tablename__ = "markets"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(2000), default="")
    category = Column(String(50), default="other", index=True)
    outcomes = Column(String(500), nullable=False)  # JSON-encoded list
    creator = Column(String(42), default="anonymous")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    resolved = Column(Boolean, default=False, index=True)
    winning_outcome = Column(Integer, nullable=True)
    total_volume = Column(Float, default=0.0)
    liquidity_b = Column(Float, default=200.0)
    # Outstanding shares per outcome (JSON-encoded list, mirrors AMM q vector)
    q_vector = Column(String(500), default="[0,0]")

    trades = relationship("TradeModel", back_populates="market")


class TradeModel(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(Integer, ForeignKey("markets.id"), nullable=False, index=True)
    trader = Column(String(42), index=True)
    outcome_index = Column(Integer, nullable=False)
    side = Column(String(4), nullable=False)  # "buy" or "sell"
    shares = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)  # collateral spent/received
    price = Column(Float, nullable=False)  # effective avg price
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)

    market = relationship("MarketModel", back_populates="trades")


class PositionModel(Base):
    """Net share balance per (trader, market, outcome).

    Maintained by the service layer on every fill so portfolio queries are
    O(1) instead of replaying the trade history.
    """

    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    trader = Column(String(42), nullable=False, index=True)
    market_id = Column(Integer, ForeignKey("markets.id"), nullable=False, index=True)
    outcome_index = Column(Integer, nullable=False)
    shares = Column(Float, default=0.0)  # net long shares (can be 0)
    cost_basis = Column(Float, default=0.0)  # total collateral still invested
    realized_pnl = Column(Float, default=0.0)
    claimed = Column(Boolean, default=False)  # winnings claimed after resolution
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    market = relationship("MarketModel")


class LimitOrderModel(Base):
    """Persisted limit order resting on the book.

    Matching is AMM-assisted: resting orders fill against the AMM when the
    LMSR price crosses their limit price (Polymarket-style hybrid).
    """

    __tablename__ = "limit_orders"

    id = Column(Integer, primary_key=True, index=True)
    order_ref = Column(String(64), unique=True, index=True)  # public order id
    market_id = Column(Integer, ForeignKey("markets.id"), nullable=False, index=True)
    trader = Column(String(42), nullable=False, index=True)
    outcome_index = Column(Integer, nullable=False)
    side = Column(String(4), nullable=False)  # "buy" or "sell"
    quantity = Column(Float, nullable=False)
    limit_price = Column(Float, nullable=False)
    filled_quantity = Column(Float, default=0.0)
    status = Column(String(16), default="open", index=True)  # open/partial/filled/cancelled/expired
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=True)

    market = relationship("MarketModel")
