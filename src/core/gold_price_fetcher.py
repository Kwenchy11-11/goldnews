"""
Gold Price Data Fetcher - XAU/USD Historical Data

Provides historical gold price data from free APIs:
- Yahoo Finance (primary)
- Twelve Data (fallback if API key available)
- Alpha Vantage (fallback if API key available)
"""

import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import json
import sqlite3
import logging

import requests
from config import DATA_DIR

logger = logging.getLogger(__name__)

# Constants
GOLD_SYMBOL = "XAUUSD"
GOLD_YAHOO_SYMBOL = "GC=F"  # Gold Futures on Yahoo Finance
CACHE_DB_PATH = os.path.join(DATA_DIR, "gold_prices.db")


@dataclass
class GoldPricePoint:
    """Single gold price data point"""
    timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: int
    
    @property
    def price(self) -> float:
        """Alias for close price"""
        return self.close_price
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open_price,
            "high": self.high_price,
            "low": self.low_price,
            "close": self.close_price,
            "volume": self.volume
        }


class GoldPriceCache:
    """SQLite cache for gold price data to avoid repeated API calls"""
    
    def __init__(self, db_path: str = CACHE_DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gold_prices (
                    timestamp TEXT PRIMARY KEY,
                    open_price REAL,
                    high_price REAL,
                    low_price REAL,
                    close_price REAL,
                    volume INTEGER,
                    source TEXT
                )
            """)
            
            # Create index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON gold_prices(timestamp)
            """)
            
            conn.commit()
    
    def save_prices(self, prices: List[GoldPricePoint], source: str = "yahoo"):
        """Save price data to cache"""
        with sqlite3.connect(self.db_path) as conn:
            for price in prices:
                conn.execute(
                    """INSERT OR REPLACE INTO gold_prices 
                       (timestamp, open_price, high_price, low_price, close_price, volume, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        price.timestamp.isoformat(),
                        price.open_price,
                        price.high_price,
                        price.low_price,
                        price.close_price,
                        price.volume,
                        source
                    )
                )
            conn.commit()
    
    def get_prices(self, start: datetime, end: datetime) -> List[GoldPricePoint]:
        """Get cached prices for date range"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """SELECT timestamp, open_price, high_price, low_price, close_price, volume 
                   FROM gold_prices 
                   WHERE timestamp >= ? AND timestamp <= ?
                   ORDER BY timestamp""",
                (start.isoformat(), end.isoformat())
            )
            
            prices = []
            for row in cursor.fetchall():
                prices.append(GoldPricePoint(
                    timestamp=datetime.fromisoformat(row[0]),
                    open_price=row[1],
                    high_price=row[2],
                    low_price=row[3],
                    close_price=row[4],
                    volume=row[5]
                ))
            
            return prices
    
    def get_price_at(self, timestamp: datetime) -> Optional[GoldPricePoint]:
        """Get price closest to given timestamp"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """SELECT timestamp, open_price, high_price, low_price, close_price, volume 
                   FROM gold_prices 
                   ORDER BY ABS(JULIANDAY(timestamp) - JULIANDAY(?))
                   LIMIT 1""",
                (timestamp.isoformat(),)
            )
            
            row = cursor.fetchone()
            if row:
                return GoldPricePoint(
                    timestamp=datetime.fromisoformat(row[0]),
                    open_price=row[1],
                    high_price=row[2],
                    low_price=row[3],
                    close_price=row[4],
                    volume=row[5]
                )
            return None


class GoldPriceFetcher:
    """Fetch historical gold price data from multiple sources"""
    
    def __init__(self):
        self.cache = GoldPriceCache()
    
    def fetch_yahoo_finance(
        self, 
        start: datetime, 
        end: datetime,
        interval: str = "1m"
    ) -> List[GoldPricePoint]:
        """
        Fetch gold prices from Yahoo Finance (free, no API key needed)
        
        Args:
            start: Start date
            end: End date
            interval: Data interval (1m, 5m, 15m, 1h, 1d)
        """
        # Convert to Unix timestamps
        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())
        
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{GOLD_YAHOO_SYMBOL}"
        params = {
            "period1": start_ts,
            "period2": end_ts,
            "interval": interval,
            "events": "history"
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if "chart" not in data or "result" not in data["chart"] or not data["chart"]["result"]:
                logger.error(f"Invalid Yahoo Finance response: {data}")
                return []
            
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            ohlc = result["indicators"]["quote"][0]
            
            prices = []
            for i, ts in enumerate(timestamps):
                try:
                    prices.append(GoldPricePoint(
                        timestamp=datetime.fromtimestamp(ts),
                        open_price=ohlc["open"][i],
                        high_price=ohlc["high"][i],
                        low_price=ohlc["low"][i],
                        close_price=ohlc["close"][i],
                        volume=ohlc["volume"][i]
                    ))
                except (KeyError, TypeError, IndexError):
                    # Skip incomplete data points
                    continue
            
            logger.info(f"Fetched {len(prices)} price points from Yahoo Finance")
            
            # Cache the results
            self.cache.save_prices(prices, "yahoo")
            
            return prices
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching from Yahoo Finance: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing Yahoo Finance data: {e}")
            return []
    
    def fetch_twelve_data(
        self,
        start: datetime,
        end: datetime,
        interval: str = "1min",
        api_key: Optional[str] = None
    ) -> List[GoldPricePoint]:
        """
        Fetch from Twelve Data (requires API key)
        
        Args:
            start: Start date
            end: End date
            interval: Data interval (1min, 5min, 15min, 1h, 1day)
            api_key: Twelve Data API key (or from env TWELVE_DATA_API_KEY)
        """
        if not api_key:
            api_key = os.getenv("TWELVE_DATA_API_KEY")
        
        if not api_key:
            logger.error("Twelve Data API key not found")
            return []
        
        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": "XAU/USD",
            "interval": interval,
            "start_date": start.strftime("%Y-%m-%d %H:%M:%S"),
            "end_date": end.strftime("%Y-%m-%d %H:%M:%S"),
            "apikey": api_key,
            "format": "JSON"
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if "values" not in data:
                logger.error(f"Invalid Twelve Data response: {data}")
                return []
            
            prices = []
            for item in data["values"]:
                try:
                    prices.append(GoldPricePoint(
                        timestamp=datetime.strptime(item["datetime"], "%Y-%m-%d %H:%M:%S"),
                        open_price=float(item["open"]),
                        high_price=float(item["high"]),
                        low_price=float(item["low"]),
                        close_price=float(item["close"]),
                        volume=int(item.get("volume", 0))
                    ))
                except (KeyError, ValueError) as e:
                    logger.warning(f"Skipping invalid data point: {e}")
                    continue
            
            # Reverse to chronological order
            prices.reverse()
            
            logger.info(f"Fetched {len(prices)} price points from Twelve Data")
            
            # Cache the results
            self.cache.save_prices(prices, "twelve_data")
            
            return prices
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching from Twelve Data: {e}")
            return []
    
    def get_prices(
        self,
        start: datetime,
        end: datetime,
        interval: str = "5m",
        use_cache: bool = True
    ) -> List[GoldPricePoint]:
        """
        Get gold prices with caching
        
        Args:
            start: Start date/time
            end: End date/time
            interval: Data interval (1m, 5m, 15m, 1h, 1d)
            use_cache: Whether to use cached data
        
        Returns:
            List of GoldPricePoint
        """
        # Check cache first
        if use_cache:
            cached = self.cache.get_prices(start, end)
            if cached and len(cached) > 0:
                # Verify we have enough data points
                time_span = (end - start).total_seconds() / 60  # minutes
                expected_points = time_span / self._interval_minutes(interval)
                
                if len(cached) >= expected_points * 0.8:  # 80% threshold
                    logger.info(f"Using {len(cached)} cached price points")
                    return cached
        
        # Fetch from Yahoo Finance (free)
        prices = self.fetch_yahoo_finance(start, end, interval)
        
        if not prices:
            # Try Twelve Data as fallback
            prices = self.fetch_twelve_data(start, end, interval)
        
        return prices
    
    def get_price_at(self, timestamp: datetime) -> Optional[float]:
        """Get gold price at specific timestamp"""
        # Check cache first
        cached = self.cache.get_price_at(timestamp)
        if cached:
            return cached.close_price
        
        # Fetch surrounding data
        start = timestamp - timedelta(hours=1)
        end = timestamp + timedelta(hours=1)
        
        prices = self.get_prices(start, end, interval="1m")
        
        # Find closest price
        if prices:
            closest = min(prices, key=lambda p: abs((p.timestamp - timestamp).total_seconds()))
            return closest.close_price
        
        return None
    
    def get_price_change(
        self,
        start: datetime,
        end: datetime
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate price change between two times
        
        Returns:
            Dict with start_price, end_price, change, change_pct, high, low
        """
        # Get prices in the range
        prices = self.get_prices(start - timedelta(minutes=5), end + timedelta(minutes=5))
        
        if not prices:
            return None
        
        # Find closest prices to start and end times
        start_price_point = min(prices, key=lambda p: abs((p.timestamp - start).total_seconds()))
        end_price_point = min(prices, key=lambda p: abs((p.timestamp - end).total_seconds()))
        
        start_price = start_price_point.close_price
        end_price = end_price_point.close_price
        
        # Calculate high/low in the period
        period_prices = [p for p in prices if start <= p.timestamp <= end]
        if period_prices:
            high = max(p.high_price for p in period_prices)
            low = min(p.low_price for p in period_prices)
        else:
            high = max(start_price, end_price)
            low = min(start_price, end_price)
        
        change = end_price - start_price
        change_pct = (change / start_price) * 100
        
        return {
            "start_price": round(start_price, 2),
            "end_price": round(end_price, 2),
            "change": round(change, 2),
            "change_pct": round(change_pct, 3),
            "high": round(high, 2),
            "low": round(low, 2),
            "start_time": start_price_point.timestamp.isoformat(),
            "end_time": end_price_point.timestamp.isoformat()
        }
    
    def _interval_minutes(self, interval: str) -> int:
        """Convert interval string to minutes"""
        mapping = {
            "1m": 1, "1min": 1,
            "5m": 5, "5min": 5,
            "15m": 15, "15min": 15,
            "1h": 60, "1hour": 60, "60min": 60,
            "1d": 1440, "1day": 1440
        }
        return mapping.get(interval, 5)


# Convenience functions
_fetcher = None

def get_fetcher() -> GoldPriceFetcher:
    """Get singleton GoldPriceFetcher instance"""
    global _fetcher
    if _fetcher is None:
        _fetcher = GoldPriceFetcher()
    return _fetcher


def get_gold_price(timestamp: datetime) -> Optional[float]:
    """Get gold price at specific timestamp"""
    return get_fetcher().get_price_at(timestamp)


def get_price_change(start: datetime, end: datetime) -> Optional[Dict[str, Any]]:
    """Calculate price change between two times"""
    return get_fetcher().get_price_change(start, end)
