"""
BIAR Protocol - Limit Order Engine
Advanced order types with order matching and book management
"""

from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import heapq


class OrderType(Enum):
    """Order types supported by BIAR"""
    MARKET = "market"  # Execute immediately
    LIMIT = "limit"  # Execute at price or better
    CONDITIONAL = "conditional"  # Execute when condition met
    STOP_LOSS = "stop_loss"  # Sell if price drops below


class OrderSide(Enum):
    """Buy or Sell"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """Order status"""
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class Order:
    """Represents a single order"""
    order_id: str
    market_id: int
    outcome: str
    side: OrderSide
    quantity: float
    price: float  # Limit price
    order_type: OrderType
    status: OrderStatus
    filled_quantity: float = 0
    timestamp: datetime = None
    expires_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def get_remaining_quantity(self) -> float:
        """Get unfilled quantity"""
        return self.quantity - self.filled_quantity
    
    def is_expired(self) -> bool:
        """Check if order is expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_filled(self) -> bool:
        """Check if order is fully filled"""
        return self.filled_quantity >= self.quantity
    
    def __lt__(self, other):
        """For heap comparison (priority queue)"""
        # BUY orders: higher price has priority (max heap)
        # SELL orders: lower price has priority (min heap)
        if self.side == OrderSide.BUY:
            return self.price > other.price  # Reversed for max heap
        return self.price < other.price


class OrderBook:
    """
    Manages buy and sell orders for a specific market outcome
    Implements matching engine for order execution
    """
    
    def __init__(self, market_id: int, outcome: str):
        self.market_id = market_id
        self.outcome = outcome
        self.buy_orders: List[Order] = []  # Max heap (sorted by price)
        self.sell_orders: List[Order] = []  # Min heap (sorted by price)
        self.order_history: Dict[str, Order] = {}  # All orders by ID
    
    def add_order(self, order: Order) -> Dict:
        """
        Add order to book and attempt to match
        Returns execution summary
        """
        if order.is_expired():
            order.status = OrderStatus.EXPIRED
            return {
                "status": "rejected",
                "reason": "Order has expired",
                "order_id": order.order_id
            }
        
        self.order_history[order.order_id] = order
        
        # Try to match the order
        matched_orders = self._match_order(order)
        
        # If not fully filled, add to book
        if not order.is_filled():
            if order.side == OrderSide.BUY:
                heapq.heappush(self.buy_orders, order)
            else:
                heapq.heappush(self.sell_orders, order)
            
            if matched_orders:
                order.status = OrderStatus.PARTIAL
            else:
                order.status = OrderStatus.PENDING
        else:
            order.status = OrderStatus.FILLED
        
        return {
            "status": "accepted",
            "order_id": order.order_id,
            "filled": order.filled_quantity,
            "remaining": order.get_remaining_quantity(),
            "matched_orders": matched_orders
        }
    
    def _match_order(self, incoming_order: Order) -> List[Tuple[str, float, float]]:
        """
        Match incoming order against existing orders in book
        Returns list of (order_id, quantity_matched, price)
        """
        matched = []
        
        if incoming_order.side == OrderSide.BUY:
            # Try to match against sell orders
            while self.sell_orders and incoming_order.get_remaining_quantity() > 0:
                sell_order = self.sell_orders[0]
                
                # Check if prices match
                if incoming_order.price >= sell_order.price:
                    # Match orders
                    qty_matched = min(
                        incoming_order.get_remaining_quantity(),
                        sell_order.get_remaining_quantity()
                    )
                    
                    execution_price = sell_order.price  # Seller's price
                    
                    incoming_order.filled_quantity += qty_matched
                    sell_order.filled_quantity += qty_matched
                    
                    matched.append((sell_order.order_id, qty_matched, execution_price))
                    
                    # Remove if fully filled
                    if sell_order.is_filled():
                        heapq.heappop(self.sell_orders)
                else:
                    break
        else:
            # Try to match against buy orders
            while self.buy_orders and incoming_order.get_remaining_quantity() > 0:
                buy_order = self.buy_orders[0]
                
                # Check if prices match
                if incoming_order.price <= buy_order.price:
                    # Match orders
                    qty_matched = min(
                        incoming_order.get_remaining_quantity(),
                        buy_order.get_remaining_quantity()
                    )
                    
                    execution_price = buy_order.price  # Buyer's price
                    
                    incoming_order.filled_quantity += qty_matched
                    buy_order.filled_quantity += qty_matched
                    
                    matched.append((buy_order.order_id, qty_matched, execution_price))
                    
                    # Remove if fully filled
                    if buy_order.is_filled():
                        heapq.heappop(self.buy_orders)
                else:
                    break
        
        return matched
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        if order_id not in self.order_history:
            return False
        
        order = self.order_history[order_id]
        
        if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]:
            return False
        
        # Remove from active lists
        if order.side == OrderSide.BUY:
            self.buy_orders = [o for o in self.buy_orders if o.order_id != order_id]
        else:
            self.sell_orders = [o for o in self.sell_orders if o.order_id != order_id]
        
        order.status = OrderStatus.CANCELLED
        return True
    
    def get_best_bid_ask(self) -> Tuple[Optional[float], Optional[float]]:
        """Get best bid (buy) and ask (sell) prices"""
        best_bid = None
        best_ask = None
        
        if self.buy_orders:
            best_bid = max(o.price for o in self.buy_orders)
        
        if self.sell_orders:
            best_ask = min(o.price for o in self.sell_orders)
        
        return best_bid, best_ask
    
    def get_order_book_depth(self, levels: int = 5) -> Dict:
        """Get order book snapshot at specified depth"""
        bids = []
        asks = []
        
        # Get top buy orders
        sorted_buys = sorted(self.buy_orders, key=lambda x: x.price, reverse=True)[:levels]
        for order in sorted_buys:
            bids.append({
                "price": order.price,
                "quantity": order.get_remaining_quantity(),
                "orders": 1
            })
        
        # Get top sell orders
        sorted_sells = sorted(self.sell_orders, key=lambda x: x.price)[:levels]
        for order in sorted_sells:
            asks.append({
                "price": order.price,
                "quantity": order.get_remaining_quantity(),
                "orders": 1
            })
        
        return {
            "bids": bids,
            "asks": asks,
            "spread": (asks[0]["price"] - bids[0]["price"]) if asks and bids else None
        }
    
    def get_liquidity_for_price(self, price: float, side: OrderSide) -> float:
        """Get total liquidity available at or better than price"""
        liquidity = 0
        
        if side == OrderSide.BUY:
            # Need to buy, so look at sell orders at or below price
            liquidity = sum(o.get_remaining_quantity() for o in self.sell_orders if o.price <= price)
        else:
            # Need to sell, so look at buy orders at or above price
            liquidity = sum(o.get_remaining_quantity() for o in self.buy_orders if o.price >= price)
        
        return liquidity


class LimitOrderEngine:
    """
    Central order matching engine for all markets
    Manages multiple order books
    """
    
    def __init__(self):
        self.order_books: Dict[Tuple[int, str], OrderBook] = {}  # (market_id, outcome) -> OrderBook
        self.all_orders: Dict[str, Order] = {}  # order_id -> Order
        self.user_orders: Dict[str, List[str]] = {}  # user_id -> [order_ids]
    
    def get_order_book(self, market_id: int, outcome: str) -> OrderBook:
        """Get or create order book for market/outcome"""
        key = (market_id, outcome)
        if key not in self.order_books:
            self.order_books[key] = OrderBook(market_id, outcome)
        return self.order_books[key]
    
    def place_order(self, order: Order, user_id: str) -> Dict:
        """Place an order in the system"""
        book = self.get_order_book(order.market_id, order.outcome)
        result = book.add_order(order)
        
        self.all_orders[order.order_id] = order
        
        if user_id not in self.user_orders:
            self.user_orders[user_id] = []
        self.user_orders[user_id].append(order.order_id)
        
        return result
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        if order_id not in self.all_orders:
            return False
        
        order = self.all_orders[order_id]
        book = self.get_order_book(order.market_id, order.outcome)
        
        return book.cancel_order(order_id)
    
    def get_user_orders(self, user_id: str, status: Optional[OrderStatus] = None) -> List[Order]:
        """Get all orders for a user"""
        if user_id not in self.user_orders:
            return []
        
        orders = [self.all_orders[oid] for oid in self.user_orders[user_id] if oid in self.all_orders]
        
        if status:
            orders = [o for o in orders if o.status == status]
        
        return orders
    
    def get_orderbook_snapshot(self, market_id: int, outcome: str, depth: int = 5) -> Dict:
        """Get current order book snapshot"""
        book = self.get_order_book(market_id, outcome)
        return book.get_order_book_depth(depth)
    
    def get_best_bid_ask(self, market_id: int, outcome: str) -> Tuple[Optional[float], Optional[float]]:
        """Get best bid/ask prices"""
        book = self.get_order_book(market_id, outcome)
        return book.get_best_bid_ask()


# Global limit order engine instance
limit_order_engine = LimitOrderEngine()
