"""
Polymarket Client

Deterministic client for Polymarket public APIs:
- Gamma API: Market/event discovery
- CLOB API: Prices, spreads, price history

No authentication required. Uses caching with TTL to avoid excessive API calls.
"""

import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import requests

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"

# Default TTL values (seconds)
DEFAULT_MARKET_TTL = 300      # 5 minutes for market data
DEFAULT_PRICE_TTL = 60        # 1 minute for prices
DEFAULT_HISTORY_TTL = 600     # 10 minutes for price history
DEFAULT_SEARCH_TTL = 120      # 2 minutes for search results

# Request timeout (seconds)
REQUEST_TIMEOUT = 15


@dataclass
class MarketData:
    """Normalized market data from Polymarket."""
    market_id: str
    question: str
    description: str
    condition_id: str
    tokens: List[Dict[str, Any]]
    outcomes: List[str]
    volume: float
    liquidity: float
    closed: bool
    end_date: Optional[str] = None
    category: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "market_id": self.market_id,
            "question": self.question,
            "description": self.description,
            "condition_id": self.condition_id,
            "tokens": self.tokens,
            "outcomes": self.outcomes,
            "volume": self.volume,
            "liquidity": self.liquidity,
            "closed": self.closed,
            "end_date": self.end_date,
            "category": self.category,
            "tags": self.tags,
        }


@dataclass
class TokenPrice:
    """Price data for a market token."""
    token_id: str
    price: float
    side: str  # "BUY" or "SELL"
    timestamp: float
    spread: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_id": self.token_id,
            "price": self.price,
            "side": self.side,
            "timestamp": self.timestamp,
            "spread": self.spread,
            "bid": self.bid,
            "ask": self.ask,
        }


@dataclass
class PricePoint:
    """Single point in price history."""
    timestamp: float
    price: float
    volume: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "price": self.price,
            "volume": self.volume,
        }


class CacheEntry:
    """Single cache entry with TTL."""
    
    def __init__(self, data: Any, ttl: int):
        self.data = data
        self.expires_at = time.time() + ttl
    
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class SimpleCache:
    """In-memory cache with TTL support."""
    
    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        entry = self._cache.get(key)
        if entry and not entry.is_expired():
            return entry.data
        # Remove expired entry
        if key in self._cache:
            del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int):
        """Set cached value with TTL."""
        self._cache[key] = CacheEntry(value, ttl)
    
    def clear(self):
        """Clear all cached entries."""
        self._cache.clear()
    
    def cleanup(self):
        """Remove expired entries."""
        expired_keys = [
            k for k, v in self._cache.items() if v.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]


class PolymarketClient:
    """
    Client for Polymarket public APIs.
    
    Uses Gamma API for market discovery and CLOB API for pricing data.
    Includes caching with configurable TTL to avoid excessive API calls.
    """
    
    def __init__(
        self,
        gamma_base: str = GAMMA_API_BASE,
        clob_base: str = CLOB_API_BASE,
        timeout: int = REQUEST_TIMEOUT,
        default_ttl: Optional[Dict[str, int]] = None,
    ):
        """
        Initialize the Polymarket client.
        
        Args:
            gamma_base: Gamma API base URL
            clob_base: CLOB API base URL
            timeout: Request timeout in seconds
            default_ttl: Optional TTL overrides for different data types
        """
        self.gamma_base = gamma_base.rstrip('/')
        self.clob_base = clob_base.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "GoldNews-Polymarket/1.0",
            "Accept": "application/json",
        })
        
        # Cache configuration
        self.ttl = default_ttl or {
            "market": DEFAULT_MARKET_TTL,
            "price": DEFAULT_PRICE_TTL,
            "history": DEFAULT_HISTORY_TTL,
            "search": DEFAULT_SEARCH_TTL,
        }
        
        # Initialize cache
        self.cache = SimpleCache()
    
    def _request(
        self,
        method: str,
        url: str,
        params: Optional[Dict] = None,
        cache_key: Optional[str] = None,
        ttl: Optional[int] = None,
    ) -> Any:
        """
        Make HTTP request with caching and error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Full URL to request
            params: Query parameters
            cache_key: Optional cache key
            ttl: Optional TTL override
            
        Returns:
            Parsed JSON response or None on error
        """
        # Check cache first
        if cache_key:
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached
        
        try:
            logger.debug(f"Request: {method} {url} params={params}")
            
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                timeout=self.timeout,
            )
            
            # Handle HTTP errors
            if response.status_code == 404:
                logger.warning(f"Resource not found: {url}")
                return None
            elif response.status_code == 429:
                logger.warning(f"Rate limited: {url}")
                return None
            elif response.status_code >= 400:
                logger.error(
                    f"HTTP error {response.status_code}: {url} - {response.text[:200]}"
                )
                return None
            
            # Parse JSON
            try:
                data = response.json()
            except ValueError as e:
                logger.error(f"Malformed JSON response: {url} - {e}")
                return None
            
            # Cache successful response
            if cache_key and ttl:
                self.cache.set(cache_key, data, ttl)
            
            return data
            
        except requests.exceptions.Timeout:
            logger.error(f"Request timeout: {url} (timeout={self.timeout}s)")
            return None
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error: {url} - {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {url} - {e}")
            return None
    
    # ─────────────────────────────────────────────────────────
    # Gamma API Methods (Market Discovery)
    # ─────────────────────────────────────────────────────────
    
    def search_markets(
        self,
        query: str,
        limit: int = 10,
    ) -> List[MarketData]:
        """
        Search for markets by query string.
        
        Args:
            query: Search query (e.g., "gold", "CPI", "Fed")
            limit: Maximum number of results
            
        Returns:
            List of MarketData objects
        """
        cache_key = f"search:{query}:{limit}"
        
        url = f"{self.gamma_base}/markets"
        params = {
            "search": query,
            "limit": limit,
            "closed": "false",
        }
        
        data = self._request(
            "GET", url, params=params,
            cache_key=cache_key, ttl=self.ttl.get("search")
        )
        
        if not data or not isinstance(data, list):
            return []
        
        return [self._parse_market(m) for m in data if isinstance(m, dict)]
    
    def get_active_markets(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[MarketData]:
        """
        Get active markets with pagination.
        
        Args:
            limit: Number of markets to retrieve
            offset: Pagination offset
            
        Returns:
            List of MarketData objects
        """
        cache_key = f"active:{limit}:{offset}"
        
        url = f"{self.gamma_base}/markets"
        params = {
            "limit": limit,
            "offset": offset,
            "closed": "false",
            "order": "volume",
            "ascending": "false",
        }
        
        data = self._request(
            "GET", url, params=params,
            cache_key=cache_key, ttl=self.ttl.get("market")
        )
        
        if not data or not isinstance(data, list):
            return []
        
        return [self._parse_market(m) for m in data if isinstance(m, dict)]
    
    def get_market_by_id(self, market_id: str) -> Optional[MarketData]:
        """
        Get a single market by its ID.
        
        Args:
            market_id: Market identifier
            
        Returns:
            MarketData object or None
        """
        cache_key = f"market:{market_id}"
        
        url = f"{self.gamma_base}/markets/{market_id}"
        
        data = self._request(
            "GET", url,
            cache_key=cache_key, ttl=self.ttl.get("market")
        )
        
        if not data or not isinstance(data, dict):
            return None
        
        return self._parse_market(data)
    
    def get_markets_by_condition(self, condition_id: str) -> List[MarketData]:
        """
        Get all markets for a condition.
        
        Args:
            condition_id: Condition identifier
            
        Returns:
            List of MarketData objects for the condition
        """
        cache_key = f"condition:{condition_id}"
        
        url = f"{self.gamma_base}/markets"
        params = {
            "condition_id": condition_id,
            "closed": "false",
        }
        
        data = self._request(
            "GET", url, params=params,
            cache_key=cache_key, ttl=self.ttl.get("market")
        )
        
        if not data or not isinstance(data, list):
            return []
        
        return [self._parse_market(m) for m in data if isinstance(m, dict)]
    
    # ─────────────────────────────────────────────────────────
    # CLOB API Methods (Pricing)
    # ─────────────────────────────────────────────────────────
    
    def get_token_price(
        self,
        token_id: str,
        side: str = "BUY",
    ) -> Optional[TokenPrice]:
        """
        Get current price for a market token.
        
        Args:
            token_id: Token identifier
            side: "BUY" or "SELL"
            
        Returns:
            TokenPrice object or None
        """
        cache_key = f"price:{token_id}:{side}"
        
        url = f"{self.clob_base}/price"
        params = {
            "token_id": token_id,
            "side": side,
        }
        
        data = self._request(
            "GET", url, params=params,
            cache_key=cache_key, ttl=self.ttl.get("price")
        )
        
        if not data or not isinstance(data, dict):
            return None
        
        price_str = data.get("price", data.get("mid", "0"))
        try:
            price = float(price_str)
        except (ValueError, TypeError):
            price = 0.0
        
        return TokenPrice(
            token_id=token_id,
            price=price,
            side=side,
            timestamp=time.time(),
        )
    
    def get_token_spread(self, token_id: str) -> Optional[Dict[str, float]]:
        """
        Get bid/ask spread for a market token.
        
        Args:
            token_id: Token identifier
            
        Returns:
            Dict with bid, ask, spread or None
        """
        cache_key = f"spread:{token_id}"
        
        # Get both buy and ask prices
        buy_url = f"{self.clob_base}/price"
        sell_url = f"{self.clob_base}/price"
        
        buy_data = self._request(
            "GET", buy_url,
            params={"token_id": token_id, "side": "BUY"},
            cache_key=f"price:{token_id}:BUY",
            ttl=self.ttl.get("price")
        )
        
        sell_data = self._request(
            "GET", sell_url,
            params={"token_id": token_id, "side": "SELL"},
            cache_key=f"price:{token_id}:SELL",
            ttl=self.ttl.get("price")
        )
        
        if not buy_data or not sell_data:
            return None
        
        try:
            bid = float(buy_data.get("price", buy_data.get("mid", "0")))
            ask = float(sell_data.get("price", sell_data.get("mid", "0")))
            spread = round(ask - bid, 4)
        except (ValueError, TypeError):
            return None
        
        return {
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "spread_pct": (spread / ask * 100) if ask > 0 else 0,
        }
    
    def get_price_history(
        self,
        token_id: str,
        start_ts: Optional[int] = None,
        end_ts: Optional[int] = None,
        interval: str = "60m",
    ) -> List[PricePoint]:
        """
        Get price history for a market token.
        
        Args:
            token_id: Token identifier
            start_ts: Start timestamp (Unix epoch seconds)
            end_ts: End timestamp (Unix epoch seconds)
            interval: Time interval (e.g., "60m", "1d")
            
        Returns:
            List of PricePoint objects
        """
        cache_key = f"history:{token_id}:{start_ts}:{end_ts}:{interval}"
        
        url = f"{self.clob_base}/prices-history"
        params = {
            "market": token_id,
            "interval": interval,
        }
        
        if start_ts:
            params["start_ts"] = start_ts
        if end_ts:
            params["end_ts"] = end_ts
        
        data = self._request(
            "GET", url, params=params,
            cache_key=cache_key, ttl=self.ttl.get("history")
        )
        
        if not data:
            return []
        
        # Handle different response formats
        if isinstance(data, list):
            history_data = data
        elif isinstance(data, dict):
            history_data = data.get("history", data)
            if not isinstance(history_data, list):
                return []
        else:
            return []
        
        points = []
        for item in history_data:
            if not isinstance(item, dict):
                continue
            
            try:
                timestamp = float(item.get("t", item.get("timestamp", 0)))
                price = float(item.get("p", item.get("price", 0)))
                volume = item.get("v", item.get("volume"))
                if volume is not None:
                    volume = float(volume)
                
                points.append(PricePoint(
                    timestamp=timestamp,
                    price=price,
                    volume=volume,
                ))
            except (ValueError, TypeError):
                continue
        
        return points
    
    # ─────────────────────────────────────────────────────────
    # Utility Methods
    # ─────────────────────────────────────────────────────────
    
    def clear_cache(self):
        """Clear all cached data."""
        self.cache.clear()
        logger.info("Cache cleared")
    
    def cleanup_cache(self):
        """Remove expired cache entries."""
        self.cache.cleanup()
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        return {
            "entries": len(self.cache._cache),
        }
    
    # ─────────────────────────────────────────────────────────
    # Internal Methods
    # ─────────────────────────────────────────────────────────
    
    def _parse_market(self, data: Dict[str, Any]) -> MarketData:
        """Parse raw market data into MarketData object."""
        # Extract tokens
        tokens = []
        outcomes = []
        for outcome in data.get("outcomes", []):
            tokens.append({
                "outcome": outcome,
                "token_id": data.get(f"{outcome.lower()}_token_id", ""),
            })
            outcomes.append(outcome)
        
        # Parse volume and liquidity
        try:
            volume = float(data.get("volume", 0))
        except (ValueError, TypeError):
            volume = 0.0
        
        try:
            liquidity = float(data.get("liquidity", 0))
        except (ValueError, TypeError):
            liquidity = 0.0
        
        # Parse tags
        tags = data.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]
        
        return MarketData(
            market_id=data.get("id", ""),
            question=data.get("question", ""),
            description=data.get("description", ""),
            condition_id=data.get("condition_id", ""),
            tokens=tokens,
            outcomes=outcomes,
            volume=volume,
            liquidity=liquidity,
            closed=data.get("closed", False),
            end_date=data.get("end_date"),
            category=data.get("category"),
            tags=tags,
        )


# ─────────────────────────────────────────────────────────────
# Convenience Function
# ─────────────────────────────────────────────────────────────
def get_polymarket_client() -> PolymarketClient:
    """Get a singleton Polymarket client instance."""
    if not hasattr(get_polymarket_client, '_instance'):
        get_polymarket_client._instance = PolymarketClient()
    return get_polymarket_client._instance
