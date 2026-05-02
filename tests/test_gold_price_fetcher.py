"""
Tests for Gold Price Fetcher
"""

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pytest

# Import the modules we're testing
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.gold_price_fetcher import (
    GoldPricePoint,
    GoldPriceCache,
    GoldPriceFetcher,
    get_fetcher,
    get_gold_price,
    get_price_change
)


class TestGoldPricePoint:
    """Test GoldPricePoint dataclass"""
    
    def test_creation(self):
        """Test creating a GoldPricePoint"""
        ts = datetime.now()
        point = GoldPricePoint(
            timestamp=ts,
            open_price=2000.50,
            high_price=2010.00,
            low_price=1995.00,
            close_price=2005.00,
            volume=1000
        )
        
        assert point.timestamp == ts
        assert point.open_price == 2000.50
        assert point.high_price == 2010.00
        assert point.low_price == 1995.00
        assert point.close_price == 2005.00
        assert point.volume == 1000
    
    def test_price_property(self):
        """Test price property returns close_price"""
        point = GoldPricePoint(
            timestamp=datetime.now(),
            open_price=2000.50,
            high_price=2010.00,
            low_price=1995.00,
            close_price=2005.00,
            volume=1000
        )
        
        assert point.price == 2005.00
    
    def test_to_dict(self):
        """Test conversion to dict"""
        ts = datetime(2024, 1, 15, 10, 30, 0)
        point = GoldPricePoint(
            timestamp=ts,
            open_price=2000.50,
            high_price=2010.00,
            low_price=1995.00,
            close_price=2005.00,
            volume=1000
        )
        
        result = point.to_dict()
        
        assert result["timestamp"] == ts.isoformat()
        assert result["open"] == 2000.50
        assert result["high"] == 2010.00
        assert result["low"] == 1995.00
        assert result["close"] == 2005.00
        assert result["volume"] == 1000


class TestGoldPriceCache:
    """Test GoldPriceCache"""
    
    def test_save_and_get_prices(self):
        """Test saving and retrieving prices"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            cache = GoldPriceCache(db_path)
            
            # Create test prices
            prices = [
                GoldPricePoint(
                    timestamp=datetime(2024, 1, 15, 10, 0, 0),
                    open_price=2000.0,
                    high_price=2010.0,
                    low_price=1995.0,
                    close_price=2005.0,
                    volume=1000
                ),
                GoldPricePoint(
                    timestamp=datetime(2024, 1, 15, 10, 5, 0),
                    open_price=2005.0,
                    high_price=2015.0,
                    low_price=2000.0,
                    close_price=2010.0,
                    volume=1100
                )
            ]
            
            # Save
            cache.save_prices(prices, "test")
            
            # Retrieve
            start = datetime(2024, 1, 15, 9, 0, 0)
            end = datetime(2024, 1, 15, 11, 0, 0)
            retrieved = cache.get_prices(start, end)
            
            assert len(retrieved) == 2
            assert retrieved[0].close_price == 2005.0
            assert retrieved[1].close_price == 2010.0
            
        finally:
            os.unlink(db_path)
    
    def test_get_price_at(self):
        """Test getting price at specific timestamp"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            cache = GoldPriceCache(db_path)
            
            prices = [
                GoldPricePoint(
                    timestamp=datetime(2024, 1, 15, 10, 0, 0),
                    open_price=2000.0,
                    high_price=2010.0,
                    low_price=1995.0,
                    close_price=2000.0,
                    volume=1000
                ),
                GoldPricePoint(
                    timestamp=datetime(2024, 1, 15, 10, 5, 0),
                    open_price=2000.0,
                    high_price=2010.0,
                    low_price=1995.0,
                    close_price=2005.0,
                    volume=1000
                )
            ]
            
            cache.save_prices(prices)
            
            # Get exact match
            price = cache.get_price_at(datetime(2024, 1, 15, 10, 0, 0))
            assert price is not None
            assert price.close_price == 2000.0
            
            # Get closest
            price = cache.get_price_at(datetime(2024, 1, 15, 10, 2, 0))
            assert price is not None
            
        finally:
            os.unlink(db_path)
    
    def test_get_price_at_not_found(self):
        """Test getting price when none exists"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            cache = GoldPriceCache(db_path)
            price = cache.get_price_at(datetime.now())
            assert price is None
        finally:
            os.unlink(db_path)


class TestGoldPriceFetcher:
    """Test GoldPriceFetcher"""
    
    def test_interval_minutes(self):
        """Test interval conversion"""
        fetcher = GoldPriceFetcher()
        
        assert fetcher._interval_minutes("1m") == 1
        assert fetcher._interval_minutes("5m") == 5
        assert fetcher._interval_minutes("15m") == 15
        assert fetcher._interval_minutes("1h") == 60
        assert fetcher._interval_minutes("1d") == 1440
        assert fetcher._interval_minutes("invalid") == 5  # Default
    
    @patch("core.gold_price_fetcher.requests.get")
    def test_fetch_yahoo_finance_success(self, mock_get):
        """Test successful Yahoo Finance fetch"""
        # Mock response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "chart": {
                "result": [{
                    "timestamp": [1705312800, 1705313100],  # 2 timestamps
                    "indicators": {
                        "quote": [{
                            "open": [2000.0, 2005.0],
                            "high": [2010.0, 2015.0],
                            "low": [1995.0, 2000.0],
                            "close": [2005.0, 2010.0],
                            "volume": [1000, 1100]
                        }]
                    }
                }]
            }
        }
        mock_get.return_value = mock_response
        
        fetcher = GoldPriceFetcher()
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            fetcher.cache = GoldPriceCache(f.name)
        
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 11, 0, 0)
        
        prices = fetcher.fetch_yahoo_finance(start, end, "5m")
        
        assert len(prices) == 2
        assert prices[0].close_price == 2005.0
        assert prices[1].close_price == 2010.0
        
        os.unlink(fetcher.cache.db_path)
    
    @patch("core.gold_price_fetcher.requests.get")
    def test_fetch_yahoo_finance_empty_response(self, mock_get):
        """Test Yahoo Finance with empty response"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"chart": {"result": []}}
        mock_get.return_value = mock_response
        
        fetcher = GoldPriceFetcher()
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 11, 0, 0)
        
        prices = fetcher.fetch_yahoo_finance(start, end)
        
        assert prices == []
    
    @patch("core.gold_price_fetcher.requests.get")
    def test_fetch_yahoo_finance_request_error(self, mock_get):
        """Test Yahoo Finance with request error"""
        from requests.exceptions import RequestException
        mock_get.side_effect = RequestException("Network error")
        
        fetcher = GoldPriceFetcher()
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 11, 0, 0)
        
        prices = fetcher.fetch_yahoo_finance(start, end)
        
        assert prices == []
    
    @patch("core.gold_price_fetcher.requests.get")
    def test_fetch_twelve_data_success(self, mock_get):
        """Test successful Twelve Data fetch"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "values": [
                {
                    "datetime": "2024-01-15 10:05:00",
                    "open": "2005.0",
                    "high": "2015.0",
                    "low": "2000.0",
                    "close": "2010.0",
                    "volume": "1100"
                },
                {
                    "datetime": "2024-01-15 10:00:00",
                    "open": "2000.0",
                    "high": "2010.0",
                    "low": "1995.0",
                    "close": "2005.0",
                    "volume": "1000"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        fetcher = GoldPriceFetcher()
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            fetcher.cache = GoldPriceCache(f.name)
        
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 11, 0, 0)
        
        prices = fetcher.fetch_twelve_data(start, end, "5min", "test_api_key")
        
        assert len(prices) == 2
        assert prices[0].close_price == 2005.0  # Reversed to chronological
        assert prices[1].close_price == 2010.0
        
        os.unlink(fetcher.cache.db_path)
    
    def test_fetch_twelve_data_no_api_key(self):
        """Test Twelve Data without API key"""
        fetcher = GoldPriceFetcher()
        
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 11, 0, 0)
        
        # Ensure no env var
        with patch.dict(os.environ, {}, clear=True):
            prices = fetcher.fetch_twelve_data(start, end)
        
        assert prices == []
    
    def test_get_prices_from_cache(self):
        """Test getting prices from cache"""
        fetcher = GoldPriceFetcher()
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            fetcher.cache = GoldPriceCache(f.name)
        
        # Pre-populate cache
        prices = [
            GoldPricePoint(
                timestamp=datetime(2024, 1, 15, 10, 0, 0),
                open_price=2000.0,
                high_price=2010.0,
                low_price=1995.0,
                close_price=2000.0,
                volume=1000
            ),
            GoldPricePoint(
                timestamp=datetime(2024, 1, 15, 10, 5, 0),
                open_price=2000.0,
                high_price=2010.0,
                low_price=1995.0,
                close_price=2005.0,
                volume=1000
            ),
            GoldPricePoint(
                timestamp=datetime(2024, 1, 15, 10, 10, 0),
                open_price=2005.0,
                high_price=2015.0,
                low_price=2000.0,
                close_price=2010.0,
                volume=1100
            )
        ]
        fetcher.cache.save_prices(prices)
        
        # Get from cache
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 10, 10, 0)
        
        result = fetcher.get_prices(start, end, use_cache=True)
        
        assert len(result) == 3
        
        os.unlink(fetcher.cache.db_path)
    
    def test_get_price_at_with_cache(self):
        """Test getting single price from cache"""
        fetcher = GoldPriceFetcher()
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            fetcher.cache = GoldPriceCache(f.name)
        
        prices = [
            GoldPricePoint(
                timestamp=datetime(2024, 1, 15, 10, 0, 0),
                open_price=2000.0,
                high_price=2010.0,
                low_price=1995.0,
                close_price=2005.0,
                volume=1000
            )
        ]
        fetcher.cache.save_prices(prices)
        
        price = fetcher.get_price_at(datetime(2024, 1, 15, 10, 0, 0))
        
        assert price == 2005.0
        
        os.unlink(fetcher.cache.db_path)
    
    def test_get_price_change(self):
        """Test calculating price change"""
        fetcher = GoldPriceFetcher()
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            fetcher.cache = GoldPriceCache(f.name)
        
        # Populate cache with enough data (get_price_change adds buffer)
        # get_price_change calls get_prices(start-5min, end+5min)
        prices = [
            GoldPricePoint(
                timestamp=datetime(2024, 1, 15, 9, 55, 0),  # Buffer before
                open_price=1998.0,
                high_price=2000.0,
                low_price=1995.0,
                close_price=2000.0,
                volume=1000
            ),
            GoldPricePoint(
                timestamp=datetime(2024, 1, 15, 10, 0, 0),
                open_price=2000.0,
                high_price=2020.0,
                low_price=1995.0,
                close_price=2000.0,
                volume=1000
            ),
            GoldPricePoint(
                timestamp=datetime(2024, 1, 15, 10, 5, 0),
                open_price=2000.0,
                high_price=2010.0,
                low_price=1995.0,
                close_price=2005.0,
                volume=1000
            ),
            GoldPricePoint(
                timestamp=datetime(2024, 1, 15, 10, 10, 0),
                open_price=2005.0,
                high_price=2015.0,
                low_price=2000.0,
                close_price=2010.0,
                volume=1100
            ),
            GoldPricePoint(
                timestamp=datetime(2024, 1, 15, 10, 15, 0),  # Buffer after
                open_price=2010.0,
                high_price=2020.0,
                low_price=2008.0,
                close_price=2012.0,
                volume=1200
            )
        ]
        fetcher.cache.save_prices(prices)
        
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 10, 10, 0)
        
        result = fetcher.get_price_change(start, end)
        
        assert result is not None
        assert result["start_price"] == 2000.0
        assert result["end_price"] == 2010.0
        assert result["change"] == 10.0
        assert result["change_pct"] == 0.5
        assert result["high"] == 2020.0
        assert result["low"] == 1995.0
        
        os.unlink(fetcher.cache.db_path)
    
    def test_get_price_change_no_data(self):
        """Test price change with no data"""
        fetcher = GoldPriceFetcher()
        
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            fetcher.cache = GoldPriceCache(f.name)
        
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 10, 10, 0)
        
        result = fetcher.get_price_change(start, end)
        
        assert result is None
        
        os.unlink(fetcher.cache.db_path)


class TestConvenienceFunctions:
    """Test convenience module-level functions"""
    
    def test_get_fetcher_singleton(self):
        """Test that get_fetcher returns singleton"""
        fetcher1 = get_fetcher()
        fetcher2 = get_fetcher()
        
        assert fetcher1 is fetcher2
    
    @patch("core.gold_price_fetcher.GoldPriceFetcher")
    def test_get_gold_price(self, mock_fetcher_class):
        """Test get_gold_price convenience function"""
        mock_fetcher = MagicMock()
        mock_fetcher.get_price_at.return_value = 2005.50
        mock_fetcher_class.return_value = mock_fetcher
        
        # Reset singleton
        import core.gold_price_fetcher as gpf
        gpf._fetcher = mock_fetcher
        
        ts = datetime(2024, 1, 15, 10, 0, 0)
        price = get_gold_price(ts)
        
        assert price == 2005.50
        mock_fetcher.get_price_at.assert_called_once_with(ts)
    
    @patch("core.gold_price_fetcher.GoldPriceFetcher")
    def test_get_price_change_convenience(self, mock_fetcher_class):
        """Test get_price_change convenience function"""
        mock_fetcher = MagicMock()
        mock_fetcher.get_price_change.return_value = {"change": 10.0}
        mock_fetcher_class.return_value = mock_fetcher
        
        # Reset singleton
        import core.gold_price_fetcher as gpf
        gpf._fetcher = mock_fetcher
        
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 10, 10, 0)
        result = get_price_change(start, end)
        
        assert result == {"change": 10.0}
        mock_fetcher.get_price_change.assert_called_once_with(start, end)
