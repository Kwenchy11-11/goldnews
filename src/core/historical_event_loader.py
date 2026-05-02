"""
Historical Event Loader

Loads historical economic events for backtesting from multiple sources:
- ForexFactory API (historical data)
- Local JSON/cache files
- Manually specified events (for testing)
"""

import json
import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Callable
from enum import Enum

import requests
from config import FOREX_FACTORY_URL, DATA_DIR

logger = logging.getLogger(__name__)


class EventImpact(str, Enum):
    """Event impact levels"""
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    HOLIDAY = "Holiday"


@dataclass
class HistoricalEvent:
    """
    Historical economic event for backtesting
    
    Matches ForexFactory format with additional backtest fields
    """
    title: str
    country: str
    date: datetime
    impact: EventImpact
    forecast: Optional[str] = None
    previous: Optional[str] = None
    actual: Optional[str] = None  # Filled after event occurs
    
    # Backtest-specific fields
    event_id: Optional[str] = None
    currency: Optional[str] = None  # USD, EUR, etc.
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = asdict(self)
        result['date'] = self.date.isoformat()
        result['impact'] = self.impact.value
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HistoricalEvent':
        """Create from dictionary"""
        data = data.copy()
        if isinstance(data.get('date'), str):
            data['date'] = datetime.fromisoformat(data['date'])
        if isinstance(data.get('impact'), str):
            data['impact'] = EventImpact(data['impact'])
        return cls(**data)
    
    @property
    def has_actual(self) -> bool:
        """Check if actual value is available"""
        return self.actual is not None and self.actual.strip() not in ['', '-']
    
    @property
    def is_usd_event(self) -> bool:
        """Check if this is a USD event (most impactful for gold)"""
        return self.country in ['USD', 'US', 'United States'] or self.currency == 'USD'
    
    @property
    def is_high_impact(self) -> bool:
        """Check if high impact event"""
        return self.impact == EventImpact.HIGH


class HistoricalEventLoader:
    """
    Load historical economic events from various sources
    """
    
    # High-priority event keywords for gold impact
    HIGH_PRIORITY_KEYWORDS = [
        'CPI', 'PPI', 'Inflation',
        'NFP', 'Non-Farm', 'Payrolls', 'Unemployment',
        'FOMC', 'Fed', 'Interest Rate',
        'GDP', 'Retail Sales'
    ]
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir or os.path.join(DATA_DIR, 'historical_events')
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def _get_cache_path(self, start: datetime, end: datetime) -> str:
        """Generate cache file path for date range"""
        filename = f"events_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}.json"
        return os.path.join(self.cache_dir, filename)
    
    def _load_from_cache(self, start: datetime, end: datetime) -> Optional[List[HistoricalEvent]]:
        """Load events from local cache"""
        cache_path = self._get_cache_path(start, end)
        
        if not os.path.exists(cache_path):
            return None
        
        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)
            
            events = [HistoricalEvent.from_dict(e) for e in data]
            logger.info(f"Loaded {len(events)} events from cache")
            return events
            
        except Exception as e:
            logger.error(f"Error loading from cache: {e}")
            return None
    
    def _save_to_cache(self, events: List[HistoricalEvent], start: datetime, end: datetime):
        """Save events to local cache"""
        cache_path = self._get_cache_path(start, end)
        
        try:
            with open(cache_path, 'w') as f:
                json.dump([e.to_dict() for e in events], f, indent=2)
            
            logger.info(f"Saved {len(events)} events to cache")
            
        except Exception as e:
            logger.error(f"Error saving to cache: {e}")
    
    def fetch_forexfactory(
        self,
        start: datetime,
        end: datetime,
        use_cache: bool = True
    ) -> List[HistoricalEvent]:
        """
        Fetch events from ForexFactory
        
        Note: ForexFactory's public API returns current week by default.
        For historical data, we rely on cached data or local files.
        
        Args:
            start: Start date
            end: End date
            use_cache: Whether to use cached data
        
        Returns:
            List of HistoricalEvent
        """
        # Try cache first
        if use_cache:
            cached = self._load_from_cache(start, end)
            if cached:
                return cached
        
        # For now, ForexFactory API only returns current week
        # We'll try to fetch and see what we get
        try:
            logger.info("Fetching from ForexFactory API...")
            response = requests.get(FOREX_FACTORY_URL, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            events = []
            
            for item in data:
                try:
                    event = self._parse_forexfactory_item(item)
                    if event and start <= event.date <= end:
                        events.append(event)
                except Exception as e:
                    logger.warning(f"Error parsing event: {e}")
                    continue
            
            # Save to cache
            if events:
                self._save_to_cache(events, start, end)
            
            logger.info(f"Fetched {len(events)} events from ForexFactory")
            return events
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching from ForexFactory: {e}")
            return []
    
    def _parse_forexfactory_item(self, item: Dict[str, Any]) -> Optional[HistoricalEvent]:
        """Parse a single ForexFactory event item"""
        try:
            # Parse date
            date_str = item.get('date', '')
            time_str = item.get('time', '')
            
            if not date_str:
                return None
            
            # Combine date and time
            if time_str and time_str not in ['', 'Tentative', 'All Day']:
                datetime_str = f"{date_str} {time_str}"
                date = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
            else:
                date = datetime.strptime(date_str, "%Y-%m-%d")
            
            # Parse impact
            impact_str = item.get('impact', 'Low')
            try:
                impact = EventImpact(impact_str)
            except ValueError:
                impact = EventImpact.LOW
            
            event = HistoricalEvent(
                title=item.get('title', 'Unknown'),
                country=item.get('country', ''),
                date=date,
                impact=impact,
                forecast=item.get('forecast') or None,
                previous=item.get('previous') or None,
                actual=item.get('actual') or None,
                event_id=item.get('id'),
                currency=item.get('currency')
            )
            
            return event
            
        except Exception as e:
            logger.warning(f"Failed to parse ForexFactory item: {e}")
            return None
    
    def load_from_file(self, filepath: str) -> List[HistoricalEvent]:
        """
        Load events from a JSON file
        
        File format: List of event dictionaries
        """
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                events = [HistoricalEvent.from_dict(e) for e in data]
            else:
                events = [HistoricalEvent.from_dict(data)]
            
            logger.info(f"Loaded {len(events)} events from {filepath}")
            return events
            
        except Exception as e:
            logger.error(f"Error loading from file {filepath}: {e}")
            return []
    
    def save_to_file(self, events: List[HistoricalEvent], filepath: str):
        """Save events to a JSON file"""
        try:
            with open(filepath, 'w') as f:
                json.dump([e.to_dict() for e in events], f, indent=2)
            
            logger.info(f"Saved {len(events)} events to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving to file {filepath}: {e}")
    
    def create_sample_events(self) -> List[HistoricalEvent]:
        """
        Create sample historical events for testing
        
        These are real-ish events with known outcomes for backtesting
        """
        base_date = datetime(2024, 1, 1)
        
        events = [
            HistoricalEvent(
                title="CPI y/y",
                country="USD",
                date=base_date + timedelta(days=10, hours=8, minutes=30),
                impact=EventImpact.HIGH,
                forecast="3.0%",
                previous="3.1%",
                actual="3.1%",  # Slight miss
                event_id="test_cpi_001"
            ),
            HistoricalEvent(
                title="Non-Farm Payrolls",
                country="USD",
                date=base_date + timedelta(days=5, hours=8, minutes=30),
                impact=EventImpact.HIGH,
                forecast="185K",
                previous="216K",
                actual="353K",  # Big beat
                event_id="test_nfp_001"
            ),
            HistoricalEvent(
                title="FOMC Statement",
                country="USD",
                date=base_date + timedelta(days=30, hours=14),
                impact=EventImpact.HIGH,
                forecast="",
                previous="",
                actual="Hawkish tone",  # Text-based outcome
                event_id="test_fomc_001"
            ),
            HistoricalEvent(
                title="PPI m/m",
                country="USD",
                date=base_date + timedelta(days=12, hours=8, minutes=30),
                impact=EventImpact.MEDIUM,
                forecast="0.2%",
                previous="0.1%",
                actual="0.3%",  # Higher than expected
                event_id="test_ppi_001"
            ),
            HistoricalEvent(
                title="Retail Sales m/m",
                country="USD",
                date=base_date + timedelta(days=17, hours=8, minutes=30),
                impact=EventImpact.HIGH,
                forecast="0.4%",
                previous="0.3%",
                actual="-0.1%",  # Big miss
                event_id="test_retail_001"
            ),
        ]
        
        return events
    
    def filter_events(
        self,
        events: List[HistoricalEvent],
        countries: List[str] = None,
        impacts: List[EventImpact] = None,
        keywords: List[str] = None,
        has_actual: bool = True
    ) -> List[HistoricalEvent]:
        """
        Filter events by criteria
        
        Args:
            events: List of events to filter
            countries: Filter by country codes (e.g., ['USD', 'EUR'])
            impacts: Filter by impact levels
            keywords: Filter by keywords in title
            has_actual: Only include events with actual values
        """
        filtered = events
        
        if countries:
            filtered = [e for e in filtered if e.country in countries]
        
        if impacts:
            filtered = [e for e in filtered if e.impact in impacts]
        
        if keywords:
            filtered = [
                e for e in filtered 
                if any(kw.lower() in e.title.lower() for kw in keywords)
            ]
        
        if has_actual:
            filtered = [e for e in filtered if e.has_actual]
        
        return filtered
    
    def get_high_impact_usd_events(
        self,
        events: List[HistoricalEvent]
    ) -> List[HistoricalEvent]:
        """
        Get high-impact USD events (most relevant for gold)
        """
        return self.filter_events(
            events,
            countries=['USD', 'US'],
            impacts=[EventImpact.HIGH],
            has_actual=True
        )
    
    def get_events_by_category(
        self,
        events: List[HistoricalEvent],
        category: str
    ) -> List[HistoricalEvent]:
        """
        Get events by category keyword
        
        Categories: 'inflation', 'labor', 'fed', 'growth', 'all'
        """
        category_keywords = {
            'inflation': ['CPI', 'PPI', 'Inflation'],
            'labor': ['NFP', 'Payrolls', 'Unemployment', 'Jobless', 'Employment'],
            'fed': ['FOMC', 'Fed', 'Interest Rate', 'Powell'],
            'growth': ['GDP', 'Retail Sales', 'Industrial Production'],
            'all': []
        }
        
        keywords = category_keywords.get(category, [])
        if not keywords:
            return events
        
        return self.filter_events(events, keywords=keywords, has_actual=True)


# Convenience functions
_loader = None

def get_loader() -> HistoricalEventLoader:
    """Get singleton HistoricalEventLoader instance"""
    global _loader
    if _loader is None:
        _loader = HistoricalEventLoader()
    return _loader


def load_events(
    start: datetime,
    end: datetime,
    use_cache: bool = True
) -> List[HistoricalEvent]:
    """Load events for date range"""
    return get_loader().fetch_forexfactory(start, end, use_cache)


def load_sample_events() -> List[HistoricalEvent]:
    """Load sample events for testing"""
    return get_loader().create_sample_events()
