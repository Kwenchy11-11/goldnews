"""
Tests for Polymarket Client

Tests all client methods with mocked HTTP responses.
No real API calls are made.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.integrations.polymarket.client import (
    PolymarketClient,
    MarketData,
    TokenPrice,
    PricePoint,
    SimpleCache,
    CacheEntry,
    GAMMA_API_BASE,
    CLOB_API_BASE,
)


class TestSimpleCache:
    """Test the in-memory cache with TTL."""
    
    def test_set_and_get(self):
        """Basic set and get."""
        cache = SimpleCache()
        cache.set("key1", "value1", ttl=60)
        
        result = cache.get("key1")
        assert result == "value1"
    
    def test_expired_entry(self):
        """Expired entries should return None."""
        cache = SimpleCache()
        cache.set("key1", "value1", ttl=0)  # Expired immediately
        
        result = cache.get("key1")
        assert result is None
    
    def test_clear(self):
        """Clear should remove all entries."""
        cache = SimpleCache()
        cache.set("key1", "value1", ttl=60)
        cache.set("key2", "value2", ttl=60)
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None
    
    def test_cleanup(self):
        """Cleanup should remove only expired entries."""
        cache = SimpleCache()
        cache.set("key1", "value1", ttl=0)  # Expired
        cache.set("key2", "value2", ttl=3600)  # Not expired
        
        cache.cleanup()
        
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"


class TestPolymarketClientInitialization:
    """Test client initialization."""
    
    def test_default_initialization(self):
        """Client should initialize with defaults."""
        client = PolymarketClient()
        
        assert client.gamma_base == GAMMA_API_BASE
        assert client.clob_base == CLOB_API_BASE
        assert client.timeout == 15
    
    def test_custom_base_urls(self):
        """Client should accept custom base URLs."""
        client = PolymarketClient(
            gamma_base="https://custom-gamma.com",
            clob_base="https://custom-clob.com",
            timeout=30,
        )
        
        assert client.gamma_base == "https://custom-gamma.com"
        assert client.clob_base == "https://custom-clob.com"
        assert client.timeout == 30
    
    def test_custom_ttl(self):
        """Client should accept custom TTL values."""
        client = PolymarketClient(
            default_ttl={"market": 600, "price": 30}
        )
        
        assert client.ttl["market"] == 600
        assert client.ttl["price"] == 30


class TestSearchMarkets:
    """Test search_markets method."""
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_search_returns_markets(self, mock_request):
        """Search should return parsed market data."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "market_001",
                "question": "Will gold hit $3000?",
                "description": "Gold price prediction",
                "condition_id": "cond_001",
                "outcomes": ["Yes", "No"],
                "volume": "100000",
                "liquidity": "50000",
                "closed": False,
                "category": "Economics",
                "tags": ["gold", "commodities"],
            }
        ]
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        results = client.search_markets("gold", limit=5)
        
        assert len(results) == 1
        assert isinstance(results[0], MarketData)
        assert results[0].market_id == "market_001"
        assert results[0].question == "Will gold hit $3000?"
        assert results[0].volume == 100000.0
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_search_empty_result(self, mock_request):
        """Empty search should return empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        results = client.search_markets("nonexistent", limit=5)
        
        assert results == []
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_search_http_error(self, mock_request):
        """HTTP error should return empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        results = client.search_markets("gold", limit=5)
        
        assert results == []
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_search_timeout(self, mock_request):
        """Timeout should return empty list."""
        import requests
        mock_request.side_effect = requests.exceptions.Timeout()
        
        client = PolymarketClient()
        results = client.search_markets("gold", limit=5)
        
        assert results == []
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_search_malformed_json(self, mock_request):
        """Malformed JSON should return empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        results = client.search_markets("gold", limit=5)
        
        assert results == []
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_search_caching(self, mock_request):
        """Search results should be cached."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "market_001",
                "question": "Test",
                "description": "",
                "condition_id": "cond_001",
                "outcomes": ["Yes", "No"],
                "volume": "100",
                "liquidity": "50",
                "closed": False,
            }
        ]
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        
        # First call
        results1 = client.search_markets("gold", limit=5)
        
        # Second call (should use cache)
        results2 = client.search_markets("gold", limit=5)
        
        # Should only make one HTTP request
        assert mock_request.call_count == 1
        assert len(results1) == 1
        assert len(results2) == 1


class TestGetActiveMarkets:
    """Test get_active_markets method."""
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_get_active_markets(self, mock_request):
        """Should return active markets."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "market_001",
                "question": "Market 1",
                "description": "",
                "condition_id": "cond_001",
                "outcomes": ["Yes", "No"],
                "volume": "1000",
                "liquidity": "500",
                "closed": False,
            },
            {
                "id": "market_002",
                "question": "Market 2",
                "description": "",
                "condition_id": "cond_002",
                "outcomes": ["Yes", "No"],
                "volume": "2000",
                "liquidity": "1000",
                "closed": False,
            }
        ]
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        results = client.get_active_markets(limit=100)
        
        assert len(results) == 2
        assert results[0].market_id == "market_001"
        assert results[1].market_id == "market_002"


class TestGetMarketById:
    """Test get_market_by_id method."""
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_get_market_by_id(self, mock_request):
        """Should return single market."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "market_001",
            "question": "Will CPI be above 3%?",
            "description": "CPI prediction",
            "condition_id": "cond_001",
            "outcomes": ["Yes", "No"],
            "volume": "50000",
            "liquidity": "25000",
            "closed": False,
            "end_date": "2024-12-31",
            "category": "Economics",
            "tags": ["cpi", "inflation"],
        }
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        result = client.get_market_by_id("market_001")
        
        assert result is not None
        assert result.market_id == "market_001"
        assert result.question == "Will CPI be above 3%?"
        assert result.end_date == "2024-12-31"
        assert result.category == "Economics"
        assert result.tags == ["cpi", "inflation"]
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_get_market_not_found(self, mock_request):
        """404 should return None."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        result = client.get_market_by_id("nonexistent")
        
        assert result is None


class TestGetTokenPrice:
    """Test get_token_price method."""
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_get_token_price(self, mock_request):
        """Should return token price."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"price": "0.65"}
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        result = client.get_token_price("token_001", side="BUY")
        
        assert result is not None
        assert isinstance(result, TokenPrice)
        assert result.token_id == "token_001"
        assert result.price == 0.65
        assert result.side == "BUY"
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_get_token_price_mid_field(self, mock_request):
        """Should handle 'mid' field instead of 'price'."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"mid": "0.72"}
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        result = client.get_token_price("token_001", side="BUY")
        
        assert result is not None
        assert result.price == 0.72
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_get_token_price_invalid(self, mock_request):
        """Invalid price should default to 0."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"price": "invalid"}
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        result = client.get_token_price("token_001", side="BUY")
        
        assert result is not None
        assert result.price == 0.0


class TestGetTokenSpread:
    """Test get_token_spread method."""
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_get_token_spread(self, mock_request):
        """Should return bid/ask spread."""
        call_count = [0]
        
        def mock_request_side_effect(*args, **kwargs):
            call_count[0] += 1
            params = kwargs.get('params', {})
            response = MagicMock()
            response.status_code = 200
            if params.get('side') == 'BUY':
                response.json.return_value = {"price": "0.64"}
            else:
                response.json.return_value = {"price": "0.66"}
            return response
        
        mock_request.side_effect = mock_request_side_effect
        
        client = PolymarketClient()
        result = client.get_token_spread("token_001")
        
        assert result is not None
        assert result["bid"] == 0.64
        assert result["ask"] == 0.66
        assert result["spread"] == 0.02
        assert abs(result["spread_pct"] - 3.03) < 0.1
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_get_token_spread_error(self, mock_request):
        """Error should return None."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        result = client.get_token_spread("token_001")
        
        assert result is None


class TestGetPriceHistory:
    """Test get_price_history method."""
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_get_price_history(self, mock_request):
        """Should return price history."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "history": [
                {"t": 1700000000, "p": 0.65, "v": 1000},
                {"t": 1700003600, "p": 0.67, "v": 1500},
                {"t": 1700007200, "p": 0.63, "v": 800},
            ]
        }
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        results = client.get_price_history("token_001")
        
        assert len(results) == 3
        assert isinstance(results[0], PricePoint)
        assert results[0].timestamp == 1700000000
        assert results[0].price == 0.65
        assert results[0].volume == 1000
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_get_price_history_alt_format(self, mock_request):
        """Should handle alternative response format."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"timestamp": 1700000000, "price": 0.65},
            {"timestamp": 1700003600, "price": 0.67},
        ]
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        results = client.get_price_history("token_001")
        
        assert len(results) == 2
        assert results[0].price == 0.65
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_get_price_history_with_time_range(self, mock_request):
        """Should include time range in request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"history": []}
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        client.get_price_history(
            "token_001",
            start_ts=1700000000,
            end_ts=1700100000,
            interval="1d",
        )
        
        # Verify request params
        call_args = mock_request.call_args
        params = call_args.kwargs.get('params', {})
        assert params["start_ts"] == 1700000000
        assert params["end_ts"] == 1700100000
        assert params["interval"] == "1d"
    
    @patch('src.integrations.polymarket.client.requests.Session.request')
    def test_get_price_history_empty(self, mock_request):
        """Empty response should return empty list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = None
        mock_request.return_value = mock_response
        
        client = PolymarketClient()
        results = client.get_price_history("token_001")
        
        assert results == []


class TestUtilityMethods:
    """Test utility methods."""
    
    def test_clear_cache(self):
        """Clear cache should remove all entries."""
        client = PolymarketClient()
        client.cache.set("key1", "value1", ttl=60)
        
        client.clear_cache()
        
        assert client.cache.get("key1") is None
    
    def test_get_cache_stats(self):
        """Should return cache statistics."""
        client = PolymarketClient()
        client.cache.set("key1", "value1", ttl=60)
        client.cache.set("key2", "value2", ttl=60)
        
        stats = client.get_cache_stats()
        
        assert stats["entries"] == 2


class TestMarketDataParsing:
    """Test market data parsing."""
    
    def test_parse_market_full(self):
        """Should parse complete market data."""
        client = PolymarketClient()
        
        raw_data = {
            "id": "market_001",
            "question": "Will gold hit $3000?",
            "description": "Gold price prediction market",
            "condition_id": "cond_001",
            "outcomes": ["Yes", "No"],
            "volume": "100000",
            "liquidity": "50000",
            "closed": False,
            "end_date": "2024-12-31",
            "category": "Economics",
            "tags": ["gold", "commodities"],
        }
        
        result = client._parse_market(raw_data)
        
        assert result.market_id == "market_001"
        assert result.question == "Will gold hit $3000?"
        assert result.volume == 100000.0
        assert result.liquidity == 50000.0
        assert result.closed is False
        assert result.end_date == "2024-12-31"
        assert result.category == "Economics"
        assert result.tags == ["gold", "commodities"]
        assert len(result.tokens) == 2
        assert result.outcomes == ["Yes", "No"]
    
    def test_parse_market_minimal(self):
        """Should parse minimal market data."""
        client = PolymarketClient()
        
        raw_data = {
            "id": "market_001",
            "question": "Test",
            "description": "",
            "condition_id": "cond_001",
            "outcomes": ["Yes", "No"],
        }
        
        result = client._parse_market(raw_data)
        
        assert result.market_id == "market_001"
        assert result.volume == 0.0
        assert result.liquidity == 0.0
        assert result.closed is False
        assert result.end_date is None
        assert result.category is None
        assert result.tags == []
    
    def test_parse_market_invalid_numbers(self):
        """Should handle invalid numbers gracefully."""
        client = PolymarketClient()
        
        raw_data = {
            "id": "market_001",
            "question": "Test",
            "description": "",
            "condition_id": "cond_001",
            "outcomes": ["Yes", "No"],
            "volume": "invalid",
            "liquidity": "also_invalid",
        }
        
        result = client._parse_market(raw_data)
        
        assert result.volume == 0.0
        assert result.liquidity == 0.0
    
    def test_market_to_dict(self):
        """Should convert to dictionary."""
        market = MarketData(
            market_id="test_001",
            question="Test?",
            description="",
            condition_id="cond_001",
            tokens=[{"outcome": "Yes", "token_id": "t1"}],
            outcomes=["Yes", "No"],
            volume=1000.0,
            liquidity=500.0,
            closed=False,
        )
        
        data = market.to_dict()
        
        assert data["market_id"] == "test_001"
        assert data["volume"] == 1000.0
        assert data["closed"] is False


class TestConvenienceFunction:
    """Test convenience function."""
    
    def test_get_polymarket_client_singleton(self):
        """Should return singleton instance."""
        from src.integrations.polymarket.client import get_polymarket_client
        
        client1 = get_polymarket_client()
        client2 = get_polymarket_client()
        
        assert client1 is client2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
