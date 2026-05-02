"""
Tests for Historical Event Loader
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pytest

# Import the modules we're testing
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.historical_event_loader import (
    EventImpact,
    HistoricalEvent,
    HistoricalEventLoader,
    get_loader,
    load_events,
    load_sample_events
)


class TestEventImpact:
    """Test EventImpact enum"""
    
    def test_enum_values(self):
        """Test enum values are correct"""
        assert EventImpact.HIGH.value == "High"
        assert EventImpact.MEDIUM.value == "Medium"
        assert EventImpact.LOW.value == "Low"
        assert EventImpact.HOLIDAY.value == "Holiday"
    
    def test_from_string(self):
        """Test creating from string"""
        impact = EventImpact("High")
        assert impact == EventImpact.HIGH


class TestHistoricalEvent:
    """Test HistoricalEvent dataclass"""
    
    def test_creation(self):
        """Test creating a HistoricalEvent"""
        event = HistoricalEvent(
            title="CPI y/y",
            country="USD",
            date=datetime(2024, 1, 15, 8, 30),
            impact=EventImpact.HIGH,
            forecast="3.0%",
            previous="3.1%",
            actual="3.1%",
            event_id="test_001"
        )
        
        assert event.title == "CPI y/y"
        assert event.country == "USD"
        assert event.date == datetime(2024, 1, 15, 8, 30)
        assert event.impact == EventImpact.HIGH
        assert event.forecast == "3.0%"
        assert event.previous == "3.1%"
        assert event.actual == "3.1%"
        assert event.event_id == "test_001"
    
    def test_has_actual_true(self):
        """Test has_actual with actual value"""
        event = HistoricalEvent(
            title="CPI",
            country="USD",
            date=datetime.now(),
            impact=EventImpact.HIGH,
            actual="3.1%"
        )
        assert event.has_actual is True
    
    def test_has_actual_false(self):
        """Test has_actual without actual value"""
        event = HistoricalEvent(
            title="CPI",
            country="USD",
            date=datetime.now(),
            impact=EventImpact.HIGH,
            actual=None
        )
        assert event.has_actual is False
        
        event2 = HistoricalEvent(
            title="CPI",
            country="USD",
            date=datetime.now(),
            impact=EventImpact.HIGH,
            actual=""
        )
        assert event2.has_actual is False
        
        event3 = HistoricalEvent(
            title="CPI",
            country="USD",
            date=datetime.now(),
            impact=EventImpact.HIGH,
            actual="-"
        )
        assert event3.has_actual is False
    
    def test_is_usd_event(self):
        """Test USD event detection"""
        event_usd = HistoricalEvent(
            title="CPI",
            country="USD",
            date=datetime.now(),
            impact=EventImpact.HIGH
        )
        assert event_usd.is_usd_event is True
        
        event_eur = HistoricalEvent(
            title="CPI",
            country="EUR",
            date=datetime.now(),
            impact=EventImpact.HIGH
        )
        assert event_eur.is_usd_event is False
        
        event_us = HistoricalEvent(
            title="CPI",
            country="US",
            date=datetime.now(),
            impact=EventImpact.HIGH
        )
        assert event_us.is_usd_event is True
    
    def test_is_high_impact(self):
        """Test high impact detection"""
        event_high = HistoricalEvent(
            title="CPI",
            country="USD",
            date=datetime.now(),
            impact=EventImpact.HIGH
        )
        assert event_high.is_high_impact is True
        
        event_low = HistoricalEvent(
            title="CPI",
            country="USD",
            date=datetime.now(),
            impact=EventImpact.LOW
        )
        assert event_low.is_high_impact is False
    
    def test_to_dict(self):
        """Test conversion to dict"""
        date = datetime(2024, 1, 15, 8, 30)
        event = HistoricalEvent(
            title="CPI y/y",
            country="USD",
            date=date,
            impact=EventImpact.HIGH,
            forecast="3.0%",
            event_id="test_001"
        )
        
        result = event.to_dict()
        
        assert result['title'] == "CPI y/y"
        assert result['country'] == "USD"
        assert result['date'] == date.isoformat()
        assert result['impact'] == "High"
        assert result['forecast'] == "3.0%"
        assert result['event_id'] == "test_001"
    
    def test_from_dict(self):
        """Test creation from dict"""
        date = datetime(2024, 1, 15, 8, 30)
        data = {
            'title': 'CPI y/y',
            'country': 'USD',
            'date': date.isoformat(),
            'impact': 'High',
            'forecast': '3.0%',
            'event_id': 'test_001'
        }
        
        event = HistoricalEvent.from_dict(data)
        
        assert event.title == "CPI y/y"
        assert event.country == "USD"
        assert event.date == date
        assert event.impact == EventImpact.HIGH
        assert event.forecast == "3.0%"


class TestHistoricalEventLoader:
    """Test HistoricalEventLoader"""
    
    def test_initialization(self):
        """Test loader initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = HistoricalEventLoader(tmpdir)
            assert loader.cache_dir == tmpdir
            assert os.path.exists(tmpdir)
    
    def test_save_and_load_from_cache(self):
        """Test saving and loading from cache"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = HistoricalEventLoader(tmpdir)
            
            events = [
                HistoricalEvent(
                    title="CPI",
                    country="USD",
                    date=datetime(2024, 1, 15, 8, 30),
                    impact=EventImpact.HIGH,
                    actual="3.1%"
                ),
                HistoricalEvent(
                    title="NFP",
                    country="USD",
                    date=datetime(2024, 1, 16, 8, 30),
                    impact=EventImpact.HIGH,
                    actual="200K"
                )
            ]
            
            start = datetime(2024, 1, 1)
            end = datetime(2024, 1, 31)
            
            # Save
            loader._save_to_cache(events, start, end)
            
            # Load
            loaded = loader._load_from_cache(start, end)
            
            assert len(loaded) == 2
            assert loaded[0].title == "CPI"
            assert loaded[1].title == "NFP"
    
    def test_load_from_cache_not_found(self):
        """Test loading from cache when file doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = HistoricalEventLoader(tmpdir)
            
            start = datetime(2024, 1, 1)
            end = datetime(2024, 1, 31)
            
            result = loader._load_from_cache(start, end)
            assert result is None
    
    def test_parse_forexfactory_item_with_time(self):
        """Test parsing ForexFactory item with time"""
        loader = HistoricalEventLoader()
        
        item = {
            'title': 'CPI y/y',
            'country': 'USD',
            'date': '2024-01-15',
            'time': '08:30:00',
            'impact': 'High',
            'forecast': '3.0%',
            'previous': '3.1%',
            'actual': '3.1%',
            'id': '12345',
            'currency': 'USD'
        }
        
        event = loader._parse_forexfactory_item(item)
        
        assert event is not None
        assert event.title == "CPI y/y"
        assert event.country == "USD"
        assert event.date == datetime(2024, 1, 15, 8, 30)
        assert event.impact == EventImpact.HIGH
        assert event.forecast == "3.0%"
        assert event.previous == "3.1%"
        assert event.actual == "3.1%"
        assert event.event_id == "12345"
    
    def test_parse_forexfactory_item_without_time(self):
        """Test parsing ForexFactory item without time"""
        loader = HistoricalEventLoader()
        
        item = {
            'title': 'Bank Holiday',
            'country': 'US',
            'date': '2024-01-15',
            'time': '',
            'impact': 'Holiday'
        }
        
        event = loader._parse_forexfactory_item(item)
        
        assert event is not None
        assert event.title == "Bank Holiday"
        assert event.date == datetime(2024, 1, 15)
        assert event.impact == EventImpact.HOLIDAY
    
    def test_parse_forexfactory_item_invalid(self):
        """Test parsing invalid ForexFactory item"""
        loader = HistoricalEventLoader()
        
        # No date
        item = {'title': 'Test', 'country': 'USD'}
        event = loader._parse_forexfactory_item(item)
        assert event is None
    
    @patch('core.historical_event_loader.requests.get')
    def test_fetch_forexfactory_success(self, mock_get):
        """Test successful ForexFactory fetch"""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = [
            {
                'title': 'CPI y/y',
                'country': 'USD',
                'date': '2024-01-15',
                'time': '08:30:00',
                'impact': 'High',
                'forecast': '3.0%',
                'previous': '3.1%',
                'actual': '3.1%'
            }
        ]
        mock_get.return_value = mock_response
        
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = HistoricalEventLoader(tmpdir)
            
            start = datetime(2024, 1, 1)
            end = datetime(2024, 1, 31)
            
            events = loader.fetch_forexfactory(start, end, use_cache=False)
            
            assert len(events) == 1
            assert events[0].title == "CPI y/y"
    
    @patch('core.historical_event_loader.requests.get')
    def test_fetch_forexfactory_request_error(self, mock_get):
        """Test ForexFactory with request error"""
        from requests.exceptions import RequestException
        mock_get.side_effect = RequestException("Network error")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = HistoricalEventLoader(tmpdir)
            
            start = datetime(2024, 1, 1)
            end = datetime(2024, 1, 31)
            
            events = loader.fetch_forexfactory(start, end, use_cache=False)
            
            assert events == []
    
    def test_load_from_file(self):
        """Test loading from JSON file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "events.json")
            
            data = [
                {
                    'title': 'CPI',
                    'country': 'USD',
                    'date': '2024-01-15T08:30:00',
                    'impact': 'High',
                    'actual': '3.1%'
                }
            ]
            
            with open(filepath, 'w') as f:
                json.dump(data, f)
            
            loader = HistoricalEventLoader(tmpdir)
            events = loader.load_from_file(filepath)
            
            assert len(events) == 1
            assert events[0].title == "CPI"
    
    def test_load_from_file_single_event(self):
        """Test loading single event from JSON file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "event.json")
            
            data = {
                'title': 'CPI',
                'country': 'USD',
                'date': '2024-01-15T08:30:00',
                'impact': 'High',
                'actual': '3.1%'
            }
            
            with open(filepath, 'w') as f:
                json.dump(data, f)
            
            loader = HistoricalEventLoader(tmpdir)
            events = loader.load_from_file(filepath)
            
            assert len(events) == 1
            assert events[0].title == "CPI"
    
    def test_save_to_file(self):
        """Test saving to JSON file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "events.json")
            
            events = [
                HistoricalEvent(
                    title="CPI",
                    country="USD",
                    date=datetime(2024, 1, 15, 8, 30),
                    impact=EventImpact.HIGH,
                    actual="3.1%"
                )
            ]
            
            loader = HistoricalEventLoader(tmpdir)
            loader.save_to_file(events, filepath)
            
            assert os.path.exists(filepath)
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            assert len(data) == 1
            assert data[0]['title'] == "CPI"
    
    def test_create_sample_events(self):
        """Test creating sample events"""
        loader = HistoricalEventLoader()
        events = loader.create_sample_events()
        
        assert len(events) > 0
        assert all(isinstance(e, HistoricalEvent) for e in events)
        assert all(e.has_actual for e in events)
    
    def test_filter_events_by_country(self):
        """Test filtering events by country"""
        loader = HistoricalEventLoader()
        
        events = [
            HistoricalEvent(title="CPI", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="3.1%"),
            HistoricalEvent(title="CPI", country="EUR", date=datetime.now(), impact=EventImpact.HIGH, actual="2.5%"),
            HistoricalEvent(title="NFP", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="200K"),
        ]
        
        filtered = loader.filter_events(events, countries=['USD'])
        
        assert len(filtered) == 2
        assert all(e.country == "USD" for e in filtered)
    
    def test_filter_events_by_impact(self):
        """Test filtering events by impact"""
        loader = HistoricalEventLoader()
        
        events = [
            HistoricalEvent(title="CPI", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="3.1%"),
            HistoricalEvent(title="GDP", country="USD", date=datetime.now(), impact=EventImpact.MEDIUM, actual="2.5%"),
            HistoricalEvent(title="NFP", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="200K"),
        ]
        
        filtered = loader.filter_events(events, impacts=[EventImpact.HIGH])
        
        assert len(filtered) == 2
        assert all(e.impact == EventImpact.HIGH for e in filtered)
    
    def test_filter_events_by_keywords(self):
        """Test filtering events by keywords"""
        loader = HistoricalEventLoader()
        
        events = [
            HistoricalEvent(title="CPI y/y", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="3.1%"),
            HistoricalEvent(title="NFP", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="200K"),
            HistoricalEvent(title="PPI m/m", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="0.2%"),
        ]
        
        filtered = loader.filter_events(events, keywords=['CPI', 'PPI'])
        
        assert len(filtered) == 2
        assert all('CPI' in e.title or 'PPI' in e.title for e in filtered)
    
    def test_filter_events_has_actual(self):
        """Test filtering events by has_actual"""
        loader = HistoricalEventLoader()
        
        events = [
            HistoricalEvent(title="CPI", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="3.1%"),
            HistoricalEvent(title="NFP", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual=None),
            HistoricalEvent(title="PPI", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="0.2%"),
        ]
        
        filtered = loader.filter_events(events, has_actual=True)
        
        assert len(filtered) == 2
        assert all(e.has_actual for e in filtered)
    
    def test_get_high_impact_usd_events(self):
        """Test getting high impact USD events"""
        loader = HistoricalEventLoader()
        
        events = [
            HistoricalEvent(title="CPI", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="3.1%"),
            HistoricalEvent(title="CPI", country="EUR", date=datetime.now(), impact=EventImpact.HIGH, actual="2.5%"),
            HistoricalEvent(title="NFP", country="USD", date=datetime.now(), impact=EventImpact.MEDIUM, actual="200K"),
            HistoricalEvent(title="GDP", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual=None),
        ]
        
        filtered = loader.get_high_impact_usd_events(events)
        
        assert len(filtered) == 1
        assert filtered[0].title == "CPI"
    
    def test_get_events_by_category_inflation(self):
        """Test getting events by inflation category"""
        loader = HistoricalEventLoader()
        
        events = [
            HistoricalEvent(title="CPI y/y", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="3.1%"),
            HistoricalEvent(title="PPI m/m", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="0.2%"),
            HistoricalEvent(title="NFP", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="200K"),
        ]
        
        filtered = loader.get_events_by_category(events, 'inflation')
        
        assert len(filtered) == 2
    
    def test_get_events_by_category_labor(self):
        """Test getting events by labor category"""
        loader = HistoricalEventLoader()
        
        events = [
            HistoricalEvent(title="NFP", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="200K"),
            HistoricalEvent(title="Unemployment Rate", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="3.7%"),
            HistoricalEvent(title="CPI", country="USD", date=datetime.now(), impact=EventImpact.HIGH, actual="3.1%"),
        ]
        
        filtered = loader.get_events_by_category(events, 'labor')
        
        assert len(filtered) == 2
    
    def test_get_events_by_category_all(self):
        """Test getting all events"""
        loader = HistoricalEventLoader()
        
        events = [
            HistoricalEvent(title="CPI", country="USD", date=datetime.now(), impact=EventImpact.HIGH),
            HistoricalEvent(title="NFP", country="USD", date=datetime.now(), impact=EventImpact.HIGH),
        ]
        
        filtered = loader.get_events_by_category(events, 'all')
        
        assert len(filtered) == 2


class TestConvenienceFunctions:
    """Test convenience module-level functions"""
    
    def test_get_loader_singleton(self):
        """Test that get_loader returns singleton"""
        loader1 = get_loader()
        loader2 = get_loader()
        
        assert loader1 is loader2
    
    @patch('core.historical_event_loader.HistoricalEventLoader')
    def test_load_events(self, mock_loader_class):
        """Test load_events convenience function"""
        mock_loader = MagicMock()
        mock_events = [
            HistoricalEvent(title="CPI", country="USD", date=datetime.now(), impact=EventImpact.HIGH)
        ]
        mock_loader.fetch_forexfactory.return_value = mock_events
        mock_loader_class.return_value = mock_loader
        
        # Reset singleton
        import core.historical_event_loader as hel
        hel._loader = mock_loader
        
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 31)
        
        events = load_events(start, end)
        
        assert len(events) == 1
        assert events[0].title == "CPI"
        mock_loader.fetch_forexfactory.assert_called_once_with(start, end, True)
    
    @patch('core.historical_event_loader.HistoricalEventLoader')
    def test_load_sample_events(self, mock_loader_class):
        """Test load_sample_events convenience function"""
        mock_loader = MagicMock()
        mock_events = [
            HistoricalEvent(title="CPI", country="USD", date=datetime.now(), impact=EventImpact.HIGH)
        ]
        mock_loader.create_sample_events.return_value = mock_events
        mock_loader_class.return_value = mock_loader
        
        # Reset singleton
        import core.historical_event_loader as hel
        hel._loader = mock_loader
        
        events = load_sample_events()
        
        assert len(events) == 1
        mock_loader.create_sample_events.assert_called_once()
