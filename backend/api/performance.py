"""
BIAR Protocol - Performance and Caching Utilities
Implements Redis caching and query optimization for speed
"""

from typing import Any, Optional, Dict
from datetime import datetime, timedelta
import json


class CacheManager:
    """
    In-memory cache manager for performance optimization
    Can be extended to use Redis for distributed caching
    """
    
    def __init__(self, ttl_seconds: int = 30):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if key in self.cache:
            entry = self.cache[key]
            if datetime.utcnow() < entry['expires_at']:
                return entry['value']
            else:
                # Expired, remove it
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with TTL"""
        ttl = ttl or self.ttl_seconds
        self.cache[key] = {
            'value': value,
            'expires_at': datetime.utcnow() + timedelta(seconds=ttl)
        }
    
    def delete(self, key: str) -> None:
        """Delete value from cache"""
        if key in self.cache:
            del self.cache[key]
    
    def clear(self) -> None:
        """Clear entire cache"""
        self.cache.clear()
    
    def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate cache entries matching pattern"""
        keys_to_delete = [k for k in self.cache.keys() if pattern in k]
        for key in keys_to_delete:
            del self.cache[key]


# Global cache instances
market_cache = CacheManager(ttl_seconds=5)  # Markets cache every 5 seconds
orderbook_cache = CacheManager(ttl_seconds=2)  # Orderbook cache every 2 seconds
stats_cache = CacheManager(ttl_seconds=10)  # Stats cache every 10 seconds


class QueryOptimizer:
    """
    Utility class for database query optimization
    Provides methods for efficient data retrieval
    """
    
    @staticmethod
    def get_market_with_cache(db_session, market_id: int, use_cache: bool = True):
        """Get market with optional caching"""
        cache_key = f"market_{market_id}"
        
        if use_cache:
            cached = market_cache.get(cache_key)
            if cached:
                return cached
        
        from models.database import Market
        market = db_session.query(Market).filter(Market.id == market_id).first()
        
        if market and use_cache:
            market_cache.set(cache_key, market)
        
        return market
    
    @staticmethod
    def get_markets_with_cache(db_session, limit: int = 50, offset: int = 0, use_cache: bool = True):
        """Get markets list with optional caching"""
        cache_key = f"markets_list_{limit}_{offset}"
        
        if use_cache:
            cached = market_cache.get(cache_key)
            if cached:
                return cached
        
        from models.database import Market
        markets = db_session.query(Market).limit(limit).offset(offset).all()
        
        if use_cache:
            market_cache.set(cache_key, markets)
        
        return markets
    
    @staticmethod
    def invalidate_market_cache(market_id: int):
        """Invalidate market cache when it's updated"""
        market_cache.delete(f"market_{market_id}")
        market_cache.invalidate_pattern("markets_list_")


class PerformanceMonitor:
    """
    Monitors and tracks performance metrics
    """
    
    metrics: Dict[str, list] = {}
    
    @classmethod
    def record_metric(cls, metric_name: str, value: float) -> None:
        """Record a performance metric"""
        if metric_name not in cls.metrics:
            cls.metrics[metric_name] = []
        
        cls.metrics[metric_name].append({
            'value': value,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Keep only last 100 entries
        if len(cls.metrics[metric_name]) > 100:
            cls.metrics[metric_name] = cls.metrics[metric_name][-100:]
    
    @classmethod
    def get_average(cls, metric_name: str) -> float:
        """Get average for a metric"""
        if metric_name not in cls.metrics or not cls.metrics[metric_name]:
            return 0.0
        
        values = [m['value'] for m in cls.metrics[metric_name]]
        return sum(values) / len(values)
    
    @classmethod
    def get_metrics_report(cls) -> Dict[str, float]:
        """Get a report of all metrics"""
        return {
            metric_name: cls.get_average(metric_name)
            for metric_name in cls.metrics.keys()
        }


# Middleware for tracking performance
def performance_tracking_middleware(request, call_next):
    """
    ASGI middleware for tracking request performance
    """
    import time
    start_time = time.time()
    
    response = call_next(request)
    
    process_time = time.time() - start_time
    PerformanceMonitor.record_metric(f"endpoint_{request.url.path}", process_time * 1000)
    
    response.headers["X-Process-Time"] = str(process_time)
    return response
