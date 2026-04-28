"""Tests for news_fetcher module."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json


def _future_date(days_ahead=0):
    """Return a date string in MM/DD/YYYY format for today + days_ahead."""
    d = datetime.utcnow() + timedelta(days=days_ahead)
    return d.strftime('%m/%d/%Y')


def _future_time(hours=8, minutes=30):
    """Return a time string like '8:30am' for a future time today."""
    return f"{hours}:{minutes:02d}am" if hours < 12 else f"{hours-12}:{minutes:02d}pm"


def test_fetch_forex_factory_events_returns_list():
    """fetch_forex_factory_events should return a list of event dicts."""
    from news_fetcher import fetch_forex_factory_events
    
    today_str = _future_date(0)
    time_str = _future_time(23, 59)  # Late today so it's not past
    
    mock_data = [
        {
            'title': 'CPI m/m',
            'country': 'USD',
            'date': today_str,
            'time': time_str,
            'impact': 'High',
            'forecast': '0.3%',
            'previous': '0.4%',
        },
        {
            'title': 'Unemployment Claims',
            'country': 'USD',
            'date': today_str,
            'time': time_str,
            'impact': 'Medium',
            'forecast': '220K',
            'previous': '215K',
        },
    ]
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data
    mock_response.raise_for_status = MagicMock()
    
    with patch('news_fetcher.requests.get', return_value=mock_response), \
         patch('news_fetcher.datetime') as mock_dt:
        mock_dt.utcnow.return_value = datetime.utcnow()
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs) if args else datetime.utcnow()
        events = fetch_forex_factory_events()
    
    assert isinstance(events, list)
    assert len(events) == 2
    assert events[0].title == 'CPI m/m'
    assert events[0].impact == 'High'
    assert events[0].country == 'USD'


def test_fetch_forex_factory_events_filters_relevant():
    """Should filter events to only gold-relevant ones."""
    from news_fetcher import fetch_forex_factory_events
    
    today_str = _future_date(0)
    time_str = _future_time(23, 59)
    
    mock_data = [
        {
            'title': 'CPI m/m',
            'country': 'USD',
            'date': today_str,
            'time': time_str,
            'impact': 'High',
            'forecast': '0.3%',
            'previous': '0.4%',
        },
        {
            'title': 'NZ Business Confidence',
            'country': 'NZD',
            'date': today_str,
            'time': '',
            'impact': 'Low',
            'forecast': '',
            'previous': '-14',
        },
    ]
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data
    mock_response.raise_for_status = MagicMock()
    
    with patch('news_fetcher.requests.get', return_value=mock_response), \
         patch('news_fetcher.datetime') as mock_dt:
        mock_dt.utcnow.return_value = datetime.utcnow()
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs) if args else datetime.utcnow()
        events = fetch_forex_factory_events()
    
    # Should include CPI (USD, High impact) but not NZ Business Confidence
    assert any(e.title == 'CPI m/m' for e in events)
    # NZ event should be filtered out (low impact, non-USD)
    assert not any(e.title == 'NZ Business Confidence' for e in events)


def test_fetch_forex_factory_events_handles_error():
    """Should return empty list on network error."""
    from news_fetcher import fetch_forex_factory_events
    
    with patch('news_fetcher.requests.get', side_effect=Exception('Network error')):
        events = fetch_forex_factory_events()
    
    assert events == []


def test_fetch_polymarket_gold_returns_list():
    """fetch_polymarket_gold should return a list of market dicts."""
    from news_fetcher import fetch_polymarket_gold
    
    mock_data = {
        'markets': [
            {
                'question': 'Will gold close above $3000 this week?',
                'description': 'Gold price prediction market',
                'probability': 0.68,
                'volume': 150000,
                'slug': 'gold-above-3000',
            },
            {
                'question': 'Will the Fed raise rates?',
                'description': 'Federal reserve interest rate decision',
                'probability': 0.25,
                'volume': 500000,
                'slug': 'fed-rate-hike',
            },
        ]
    }
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data
    mock_response.raise_for_status = MagicMock()
    
    with patch('news_fetcher.requests.get', return_value=mock_response):
        markets = fetch_polymarket_gold()
    
    assert isinstance(markets, list)
    # Should include gold market
    assert any('gold' in m.title.lower() or 'xau' in m.title.lower() for m in markets)


def test_fetch_polymarket_gold_handles_error():
    """Should return empty list on network error."""
    from news_fetcher import fetch_polymarket_gold
    
    with patch('news_fetcher.requests.get', side_effect=Exception('Network error')):
        markets = fetch_polymarket_gold()
    
    assert markets == []


def test_is_relevant_event_identifies_gold_news():
    """is_relevant_event should identify gold-related events."""
    from news_fetcher import is_relevant_event
    
    assert is_relevant_event({'title': 'CPI m/m', 'country': 'USD', 'impact': 'High'}) is True
    assert is_relevant_event({'title': 'FOMC Statement', 'country': 'USD', 'impact': 'High'}) is True
    assert is_relevant_event({'title': 'Gold Demand Report', 'country': 'CHN', 'impact': 'Medium'}) is True
    assert is_relevant_event({'title': 'NZ Business Confidence', 'country': 'NZD', 'impact': 'Low'}) is False