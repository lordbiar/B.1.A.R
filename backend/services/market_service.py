"""
BIAR Protocol - Market Service
Business logic for market operations
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from models.database import Market, Order, Position, OracleFeed, MarketStatus, MarketType
from schemas.market import MarketCreate, MarketUpdate, OrderCreate


class MarketService:
    """Service layer for market operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_market(self, market_data: MarketCreate) -> Market:
        """Create a new prediction market"""
        db_market = Market(
            title=market_data.title,
            description=market_data.description,
            category=market_data.category,
            market_type=market_data.market_type,
            outcomes=market_data.outcomes,
            resolution_source=market_data.resolution_source,
            start_time=market_data.start_time,
            end_time=market_data.end_time,
            initial_liquidity=market_data.initial_liquidity,
            status=MarketStatus.ACTIVE,
            # Initialize liquidity distribution
            current_liquidity={outcome: market_data.initial_liquidity / len(market_data.outcomes) 
                              for outcome in market_data.outcomes}
        )
        
        self.db.add(db_market)
        self.db.commit()
        self.db.refresh(db_market)
        
        return db_market
    
    def get_market(self, market_id: int) -> Optional[Market]:
        """Get a single market by ID"""
        return self.db.query(Market).filter(Market.id == market_id).first()
    
    def get_markets(self, status: Optional[MarketStatus] = None, 
                    category: Optional[str] = None,
                    limit: int = 50, offset: int = 0) -> List[Market]:
        """Get list of markets with optional filters"""
        query = select(Market)
        
        if status:
            query = query.where(Market.status == status)
        if category:
            query = query.where(Market.category == category)
        
        query = query.offset(offset).limit(limit)
        results = self.db.execute(query)
        return list(results.scalars().all())
    
    def update_market(self, market_id: int, update_data: MarketUpdate) -> Optional[Market]:
        """Update an existing market"""
        db_market = self.get_market(market_id)
        if not db_market:
            return None
        
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(db_market, field, value)
        
        self.db.commit()
        self.db.refresh(db_market)
        
        return db_market
    
    def resolve_market(self, market_id: int, winning_outcome: str, 
                       oracle_data: Optional[Dict] = None) -> Optional[Market]:
        """Resolve a market with the winning outcome"""
        db_market = self.get_market(market_id)
        if not db_market:
            return None
        
        if winning_outcome not in db_market.outcomes:
            raise ValueError(f"Invalid outcome. Must be one of: {db_market.outcomes}")
        
        db_market.status = MarketStatus.RESOLVED
        db_market.winning_outcome = winning_outcome
        db_market.oracle_data = oracle_data
        db_market.resolved_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(db_market)
        
        return db_market
    
    def get_market_orders(self, market_id: int) -> List[Order]:
        """Get all orders for a market"""
        return self.db.query(Order).filter(Order.market_id == market_id).all()
    
    def get_market_positions(self, market_id: int) -> List[Position]:
        """Get all positions for a market"""
        return self.db.query(Position).filter(Position.market_id == market_id).all()
    
    def get_user_positions(self, user_address: str, 
                           market_id: Optional[int] = None) -> List[Position]:
        """Get positions for a specific user"""
        query = self.db.query(Position).filter(Position.user_address == user_address)
        if market_id:
            query = query.filter(Position.market_id == market_id)
        return query.all()
    
    def calculate_payout(self, position: Position, market: Market) -> float:
        """Calculate payout for a position based on market resolution"""
        if market.status != MarketStatus.RESOLVED:
            return 0.0
        
        if position.outcome == market.winning_outcome:
            # Full payout - 1 token per share
            return position.shares
        else:
            # No payout for losing positions
            return 0.0
    
    def get_active_markets_count(self) -> int:
        """Get count of active markets"""
        return self.db.query(Market).filter(
            Market.status == MarketStatus.ACTIVE
        ).count()
    
    def get_total_volume(self) -> float:
        """Get total volume across all markets"""
        markets = self.db.query(Market).all()
        return sum(m.total_volume or 0 for m in markets)


class OrderService:
    """Service layer for order operations"""
    
    def __init__(self, db: Session, amm_engine):
        self.db = db
        self.amm = amm_engine
    
    def create_order(self, market_id: int, order_data: OrderCreate) -> Dict[str, Any]:
        """
        Create and execute an order
        Returns order details including calculated shares and price
        """
        market = self.db.query(Market).filter(Market.id == market_id).first()
        if not market:
            raise ValueError("Market not found")
        
        if market.status != MarketStatus.ACTIVE:
            raise ValueError("Market is not active")
        
        if order_data.outcome not in market.outcomes:
            raise ValueError(f"Invalid outcome. Must be one of: {market.outcomes}")
        
        # Get current quantities from market state
        quantities = market.current_liquidity or {}
        if isinstance(quantities, str):
            import json
            quantities = json.loads(quantities)
        
        # Calculate cost and shares using AMM
        cost = self.amm.calculate_cost(quantities, order_data.outcome, order_data.amount)
        
        # Solve for shares (simplified - in production use proper root finding)
        price = self.amm.get_price(quantities, order_data.outcome)
        shares = order_data.amount / price if price > 0 else 0
        
        # Calculate slippage
        _, price_impact, slippage_pct = self.amm.calculate_slippage(
            quantities, order_data.outcome, shares
        )
        
        # Check slippage tolerance
        if slippage_pct > order_data.slippage_tolerance * 100:
            return {
                "status": "rejected",
                "reason": f"Slippage {slippage_pct:.2f}% exceeds tolerance {order_data.slippage_tolerance*100}%"
            }
        
        # Create order record
        db_order = Order(
            market_id=market_id,
            user_address=order_data.user_address,
            side=order_data.side,
            outcome=order_data.outcome,
            amount=order_data.amount,
            shares=shares,
            price=price,
            slippage_tolerance=order_data.slippage_tolerance,
            executed_slippage=slippage_pct / 100,
            status="executed"
        )
        
        # Update market state
        new_quantities = self.amm.get_quantities_after_trade(
            quantities, order_data.outcome, order_data.amount
        )
        market.current_liquidity = new_quantities
        market.total_volume = (market.total_volume or 0) + order_data.amount
        
        # Update or create position
        position = self.db.query(Position).filter(
            Position.market_id == market_id,
            Position.user_address == order_data.user_address,
            Position.outcome == order_data.outcome
        ).first()
        
        if position:
            # Update existing position
            total_shares = position.shares + shares
            total_cost = (position.shares * position.average_cost) + order_data.amount
            position.average_cost = total_cost / total_shares if total_shares > 0 else 0
            position.shares = total_shares
        else:
            # Create new position
            position = Position(
                market_id=market_id,
                user_address=order_data.user_address,
                outcome=order_data.outcome,
                shares=shares,
                average_cost=order_data.amount / shares if shares > 0 else 0
            )
            self.db.add(position)
        
        self.db.add(db_order)
        self.db.commit()
        self.db.refresh(db_order)
        
        return {
            "status": "executed",
            "order": db_order.to_dict(),
            "shares_received": shares,
            "effective_price": price,
            "slippage": slippage_pct
        }
    
    def cancel_order(self, order_id: int, user_address: str) -> bool:
        """Cancel an order"""
        order = self.db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return False
        
        if order.user_address != user_address:
            return False
        
        if order.status != "pending":
            return False
        
        order.status = "cancelled"
        self.db.commit()
        
        return True


class OracleService:
    """Service layer for oracle operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_oracle_feeds(self, active_only: bool = True) -> List[OracleFeed]:
        """Get all oracle feeds"""
        query = self.db.query(OracleFeed)
        if active_only:
            query = query.filter(OracleFeed.is_active == True)
        return query.all()
    
    def get_oracle_feed(self, feed_id: int) -> Optional[OracleFeed]:
        """Get a specific oracle feed"""
        return self.db.query(OracleFeed).filter(OracleFeed.id == feed_id).first()
    
    def create_oracle_feed(self, name: str, feed_url: str, 
                          feed_type: str = "api",
                          contract_address: Optional[str] = None,
                          chain_id: int = 11155111,
                          config: Optional[Dict] = None) -> OracleFeed:
        """Create a new oracle feed"""
        db_feed = OracleFeed(
            name=name,
            feed_url=feed_url,
            feed_type=feed_type,
            contract_address=contract_address,
            chain_id=chain_id,
            config=config or {},
            is_active=True
        )
        
        self.db.add(db_feed)
        self.db.commit()
        self.db.refresh(db_feed)
        
        return db_feed
    
    async def fetch_oracle_data(self, feed: OracleFeed) -> Optional[Any]:
        """Fetch data from oracle feed (async)"""
        import httpx
        
        if feed.feed_type == "api" and feed.feed_url:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(str(feed.feed_url), timeout=10.0)
                    response.raise_for_status()
                    return response.json()
            except Exception as e:
                print(f"Error fetching oracle data: {e}")
                return None
        
        # For Chainlink or custom oracles, integrate with web3
        # This is a simplified implementation
        return None
    
    def update_feed_timestamp(self, feed_id: int):
        """Update last_updated timestamp for a feed"""
        feed = self.get_oracle_feed(feed_id)
        if feed:
            feed.last_updated = datetime.utcnow()
            self.db.commit()
