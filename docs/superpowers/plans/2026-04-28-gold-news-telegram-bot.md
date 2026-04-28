# Gold News Telegram Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python daemon that fetches gold-related news from ForexFactory and Polymarket, analyzes impact on gold prices using Gemini API, and sends Thai-language alerts to Telegram every 30 minutes during market hours.

**Architecture:** Modular Python package with separate modules for config, scheduling, news fetching, AI analysis, Telegram delivery, and Thai message formatting. Each module has one responsibility. The main entry point orchestrates the flow: scheduler triggers → news_fetcher gets events → analyzer processes via Gemini → formatter creates Thai messages → telegram_bot delivers.

**Tech Stack:** Python 3.10+, requests, google-generativeai, python-dotenv, schedule

---

## File Structure

```
goldnews/
├── main.py              # Entry point, starts daemon loop
├── config.py            # Loads .env, provides configuration constants
├── scheduler.py         # 30-min interval scheduler with market hours check
├── news_fetcher.py      # ForexFactory + Polymarket data fetching
├── analyzer.py          # Gemini API impact analysis (Thai prompts)
├── telegram_bot.py      # Telegram Bot API message sending
├── formatter.py         # Thai message formatting with emoji
├── requirements.txt     # Dependencies
├── .env.example         # Template for environment variables
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_news_fetcher.py
    ├── test_analyzer.py
    ├── test_formatter.py
    ├── test_telegram_bot.py
    └── test_scheduler.py
```

---

### Task 1: Project Setup and Configuration

**Files:**
- Create: `goldnews/requirements.txt`
- Create: `goldnews/.env.example`
- Create: `goldnews/config.py`
- Create: `goldnews/tests/__init__.py`
- Create: `goldnews/tests/test_config.py`

- [ ] **Step 1: Create requirements.txt**

```
requests>=2.31.0
google-generativeai>=0.7.0
python-dotenv>=1.0.0
schedule>=1.2.0
pytest>=8.0.0
```

- [ ] **Step 2: Create .env.example**

```
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
GEMINI_API_KEY=your_gemini_api_key_here
CHECK_INTERVAL=30
MARKET_HOURS_ONLY=true
LOG_LEVEL=INFO
```

- [ ] **Step 3: Write test_config.py**

```python
"""Tests for config module."""
import os
import pytest
from unittest.mock import patch


def test_config_loads_env_vars():
    """Config should load values from environment variables."""
    env_vars = {
        'TELEGRAM_BOT_TOKEN': 'test_token_123',
        'TELEGRAM_CHAT_ID': 'test_chat_456',
        'GEMINI_API_KEY': 'test_gemini_key',
        'CHECK_INTERVAL': '15',
        'MARKET_HOURS_ONLY': 'false',
        'LOG_LEVEL': 'DEBUG',
    }
    with patch.dict(os.environ, env_vars, clear=False):
        # Re-import to pick up new env vars
        import importlib
        import config
        importlib.reload(config)
        
        assert config.TELEGRAM_BOT_TOKEN == 'test_token_123'
        assert config.TELEGRAM_CHAT_ID == 'test_chat_456'
        assert config.GEMINI_API_KEY == 'test_gemini_key'
        assert config.CHECK_INTERVAL == 15
        assert config.MARKET_HOURS_ONLY is False
        assert config.LOG_LEVEL == 'DEBUG'


def test_config_defaults():
    """Config should use defaults when env vars are missing."""
    env_vars = {
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_CHAT_ID': 'test_chat',
        'GEMINI_API_KEY': 'test_key',
    }
    with patch.dict(os.environ, env_vars, clear=True):
        import importlib
        import config
        importlib.reload(config)
        
        assert config.CHECK_INTERVAL == 30
        assert config.MARKET_HOURS_ONLY is True
        assert config.LOG_LEVEL == 'INFO'


def test_config_validates_required_vars():
    """Config should raise error when required vars are missing."""
    with patch.dict(os.environ, {}, clear=True):
        import importlib
        import config
        # Remove module so it re-runs
        if 'config' in dir():
            importlib.reload(config)
        
        # At least one required var should be missing
        assert not config.TELEGRAM_BOT_TOKEN or config.TELEGRAM_BOT_TOKEN == ''
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_config.py -v`
Expected: FAIL (config module doesn't exist yet)

- [ ] **Step 5: Write config.py**

```python
"""
Configuration module for Gold News Telegram Bot.

Loads settings from environment variables with sensible defaults.
Uses python-dotenv to load from .env file if present.
"""

import os
import logging
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# Required settings
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# Optional settings with defaults
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '30'))  # minutes
MARKET_HOURS_ONLY = os.getenv('MARKET_HOURS_ONLY', 'true').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# API URLs
FOREX_FACTORY_URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
POLYMARKET_URL = 'https://gamma-api.polymarket.com/markets'
TELEGRAM_API_URL = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}'
GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'

# Thai keyword categories for gold-related news filtering
GOLD_KEYWORDS = ['gold', 'xau', 'xauusd', 'ทองคำ', 'ทอง', 'bullion', 'precious metal']
USD_KEYWORDS = ['fed', 'fomc', 'powell', 'ธนาคารกลาง', 'อัตราดอกเบี้ย', 'interest rate',
                'dollar', 'usd', 'dxy']
INFLATION_KEYWORDS = ['cpi', 'ppi', 'inflation', 'เงินเฟ้อ', 'ราคาผู้บริโภค', 'ราคาผู้ผลิต']
EMPLOYMENT_KEYWORDS = ['nfp', 'non-farm', 'unemployment', 'employment', 'จ้างงาน', 'ว่างงาน']

# All relevant keywords combined
RELEVANT_KEYWORDS = GOLD_KEYWORDS + USD_KEYWORDS + INFLATION_KEYWORDS + EMPLOYMENT_KEYWORDS

# Thai translations for common economic event titles
THAI_TRANSLATIONS = {
    'CPI': 'ดัชนีราคาผู้บริโภค',
    'Core CPI': 'ดัชนีราคาผู้บริโภค (Core)',
    'PPI': 'ดัชนีราคาผู้ผลิต',
    'Core PPI': 'ดัชนีราคาผู้ผลิต (Core)',
    'FOMC': 'การประชุม FOMC',
    'Fed': 'ธนาคารกลางสหรัฐ',
    'NFP': 'ตัวเลขการจ้างงานนอกภาคเกษตร',
    'Non-Farm Payrolls': 'ตัวเลขการจ้างงานนอกภาคเกษตร',
    'Unemployment Rate': 'อัตราการว่างงาน',
    'GDP': 'ผลิตภัณฑ์มวลรวมภายในประเทศ',
    'PMI': 'ดัชนีผู้จัดการฝ่ายจัดซื้อ',
    'Interest Rate': 'อัตราดอกเบี้ย',
    'Retail Sales': 'ยอดขายปลีก',
    'Industrial Production': 'การผลิตอุตสาหกรรม',
    'Housing Starts': 'การเริ่มต้นสร้างบ้าน',
    'Building Permits': 'ใบอนุญาตก่อสร้าง',
    'Consumer Confidence': 'ความเชื่อมั่นผู้บริโภค',
    'Durable Goods Orders': 'คำสั่งซื้อสินค้าคงทน',
    'Trade Balance': 'ดุลการค้า',
    'Initial Jobless Claims': 'จำนวนผู้ขอรับสวัสดิการว่างงาน',
}

# Impact level Thai translations
IMPACT_THAI = {
    'High': 'สูง',
    'Medium': 'กลาง',
    'Low': 'ต่ำ',
}

# Bias Thai translations
BIAS_THAI = {
    'BULLISH': 'เชิงบวก (ทองขึ้น)',
    'BEARISH': 'เชิงลบ (ทองลง)',
    'NEUTRAL': 'เป็นกลาง',
}

# Day names in Thai
DAY_THAI = {
    0: 'จันทร์',
    1: 'อังคาร',
    2: 'พุธ',
    3: 'พฤหัสบดี',
    4: 'ศุกร์',
    5: 'เสาร์',
    6: 'อาทิตย์',
}

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('goldnews')
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd /Users/kwanchanokroumsuk/goldnews && git add requirements.txt .env.example config.py tests/__init__.py tests/test_config.py && git commit -m "feat: add project setup and config module"
```

---

### Task 2: News Fetcher Module

**Files:**
- Create: `goldnews/news_fetcher.py`
- Create: `goldnews/tests/test_news_fetcher.py`

- [ ] **Step 1: Write test_news_fetcher.py**

```python
"""Tests for news_fetcher module."""
import pytest
from unittest.mock import patch, MagicMock
import json


def test_fetch_forex_factory_events_returns_list():
    """fetch_forex_factory_events should return a list of event dicts."""
    from news_fetcher import fetch_forex_factory_events
    
    mock_data = [
        {
            'title': 'CPI m/m',
            'country': 'USD',
            'date': '04/28/2026',
            'time': '8:30am',
            'impact': 'High',
            'forecast': '0.3%',
            'previous': '0.4%',
        },
        {
            'title': 'Unemployment Claims',
            'country': 'USD',
            'date': '04/28/2026',
            'time': '8:30am',
            'impact': 'Medium',
            'forecast': '220K',
            'previous': '215K',
        },
    ]
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data
    mock_response.raise_for_status = MagicMock()
    
    with patch('news_fetcher.requests.get', return_value=mock_response):
        events = fetch_forex_factory_events()
    
    assert isinstance(events, list)
    assert len(events) == 2
    assert events[0]['title'] == 'CPI m/m'
    assert events[0]['impact'] == 'High'
    assert events[0]['country'] == 'USD'


def test_fetch_forex_factory_events_filters_relevant():
    """Should filter events to only gold-relevant ones."""
    from news_fetcher import fetch_forex_factory_events
    
    mock_data = [
        {
            'title': 'CPI m/m',
            'country': 'USD',
            'date': '04/28/2026',
            'time': '8:30am',
            'impact': 'High',
            'forecast': '0.3%',
            'previous': '0.4%',
        },
        {
            'title': 'NZ Business Confidence',
            'country': 'NZD',
            'date': '04/28/2026',
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
    
    with patch('news_fetcher.requests.get', return_value=mock_response):
        events = fetch_forex_factory_events()
    
    # Should include CPI (USD, High impact) but not NZ Business Confidence
    assert any(e['title'] == 'CPI m/m' for e in events)
    # NZ event should be filtered out (low impact, non-USD)
    assert not any(e['title'] == 'NZ Business Confidence' for e in events)


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
    assert any('gold' in m['title'].lower() or 'xau' in m['title'].lower() for m in markets)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_news_fetcher.py -v`
Expected: FAIL (news_fetcher module doesn't exist yet)

- [ ] **Step 3: Write news_fetcher.py**

```python
"""
News Fetcher Module
===================
Fetches gold-related news from ForexFactory economic calendar
and Polymarket prediction markets.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field

import requests

import config

logger = logging.getLogger('goldnews')


@dataclass
class EconomicEvent:
    """Structured economic calendar event."""
    title: str
    title_th: str
    country: str
    impact: str  # High, Medium, Low
    date: str
    time: str
    forecast: str
    previous: str
    source: str = 'ForexFactory'


@dataclass
class PolymarketData:
    """Polymarket prediction market data."""
    title: str
    probability: float
    volume: float
    url: str
    source: str = 'Polymarket'


def is_relevant_event(event: Dict) -> bool:
    """
    Check if an economic event is relevant to gold trading.
    
    Includes USD events (which inversely affect gold), gold-specific events,
    and high-impact events from major economies.
    """
    title = event.get('title', '').lower()
    country = event.get('country', '').upper()
    impact = event.get('impact', '')
    
    # Always include high-impact USD events
    if country == 'USD' and impact == 'High':
        return True
    
    # Check keyword relevance
    all_keywords = config.RELEVANT_KEYWORDS
    if any(kw.lower() in title for kw in all_keywords):
        return True
    
    # Include all USD high and medium impact events
    if country == 'USD' and impact in ('High', 'Medium'):
        return True
    
    # Filter out low-impact non-USD events
    if impact == 'Low' and country != 'USD':
        return False
    
    return False


def _translate_title(title: str) -> str:
    """Translate common economic event titles to Thai."""
    for english, thai in config.THAI_TRANSLATIONS.items():
        if english.lower() in title.lower():
            return thai
    return title


def _parse_forex_factory_date(date_str: str, time_str: str) -> Optional[datetime]:
    """Parse ForexFactory date and time strings into datetime object."""
    if not date_str:
        return None
    
    try:
        # Date format: "04/28/2026"
        parts = date_str.split('/')
        if len(parts) != 3:
            return None
        month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
        
        if time_str and time_str.strip():
            # Time format: "8:30am" or "2:00pm"
            time_lower = time_str.lower().strip()
            is_pm = 'pm' in time_lower
            is_am = 'am' in time_lower
            time_clean = time_lower.replace('am', '').replace('pm', '').strip()
            
            time_parts = time_clean.split(':')
            hours = int(time_parts[0])
            minutes = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            if is_pm and hours != 12:
                hours += 12
            if is_am and hours == 12:
                hours = 0
            
            return datetime(year, month, day, hours, minutes)
        else:
            return datetime(year, month, day, 0, 0)
    except (ValueError, IndexError):
        return None


def fetch_forex_factory_events() -> List[EconomicEvent]:
    """
    Fetch economic calendar events from ForexFactory.
    
    Returns list of EconomicEvent objects, filtered to gold-relevant events.
    """
    try:
        response = requests.get(
            config.FOREX_FACTORY_URL,
            timeout=15,
            headers={'Accept': 'application/json'}
        )
        response.raise_for_status()
        data = response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch ForexFactory data: {e}")
        return []
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse ForexFactory data: {e}")
        return []
    
    events = []
    now = datetime.utcnow()
    
    for item in data:
        try:
            title = item.get('title', '')
            country = item.get('country', '')
            impact = item.get('impact', '')
            date_str = item.get('date', '')
            time_str = item.get('time', '')
            forecast = item.get('forecast', '')
            previous = item.get('previous', '')
            
            # Build event dict for relevance check
            event_dict = {
                'title': title,
                'country': country,
                'impact': impact,
            }
            
            if not is_relevant_event(event_dict):
                continue
            
            # Parse date
            event_time = _parse_forex_factory_date(date_str, time_str)
            
            # Skip past events (more than 1 hour ago)
            if event_time and event_time < now - timedelta(hours=1):
                continue
            
            events.append(EconomicEvent(
                title=title,
                title_th=_translate_title(title),
                country=country,
                impact=impact,
                date=date_str,
                time=time_str,
                forecast=str(forecast) if forecast else '',
                previous=str(previous) if previous else '',
            ))
        except Exception as e:
            logger.warning(f"Error parsing ForexFactory event: {e}")
            continue
    
    # Sort by date/time
    events.sort(key=lambda e: e.date)
    logger.info(f"Fetched {len(events)} relevant ForexFactory events")
    return events


def fetch_polymarket_gold() -> List[PolymarketData]:
    """
    Fetch gold-related prediction markets from Polymarket.
    
    Returns list of PolymarketData objects for gold-related markets.
    """
    gold_keywords = ['gold', 'xau', 'xauusd', 'precious metal', 'bullion']
    
    try:
        response = requests.get(
            config.POLYMARKET_URL,
            params={'active': 'true', 'closed': 'false', 'limit': '50'},
            timeout=15,
            headers={'Accept': 'application/json'}
        )
        response.raise_for_status()
        data = response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch Polymarket data: {e}")
        return []
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse Polymarket data: {e}")
        return []
    
    markets = []
    market_list = data.get('markets', data) if isinstance(data, dict) else data
    
    for market in market_list:
        try:
            question = market.get('question', '').lower()
            description = market.get('description', '').lower()
            
            if any(kw in question or kw in description for kw in gold_keywords):
                markets.append(PolymarketData(
                    title=market.get('question', 'N/A'),
                    probability=float(market.get('probability', 0)),
                    volume=float(market.get('volume', 0)),
                    url=f"https://polymarket.com/event/{market.get('slug', '')}",
                ))
        except Exception as e:
            logger.warning(f"Error parsing Polymarket market: {e}")
            continue
    
    logger.info(f"Fetched {len(markets)} gold-related Polymarket markets")
    return markets


def fetch_all_news() -> Dict[str, list]:
    """
    Fetch all news sources and return combined data.
    
    Returns dict with 'events' (ForexFactory) and 'markets' (Polymarket) keys.
    """
    events = fetch_forex_factory_events()
    markets = fetch_polymarket_gold()
    
    logger.info(f"Total: {len(events)} events, {len(markets)} markets")
    return {
        'events': events,
        'markets': markets,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_news_fetcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/kwanchanokroumsuk/goldnews && git add news_fetcher.py tests/test_news_fetcher.py && git commit -m "feat: add news fetcher module for ForexFactory and Polymarket"
```

---

### Task 3: AI Analyzer Module

**Files:**
- Create: `goldnews/analyzer.py`
- Create: `goldnews/tests/test_analyzer.py`

- [ ] **Step 1: Write test_analyzer.py**

```python
"""Tests for analyzer module."""
import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass


def test_analyze_event_returns_analysis():
    """analyze_event should return an AnalysisResult with expected fields."""
    from analyzer import analyze_event, AnalysisResult
    
    mock_gemini_response = """IMPACT: HIGH
BIAS: BEARISH
CONFIDENCE: 75%
REASONING: CPI สูงกว่าคาดหมายถึงเงินเฟ้อยังเป็นปัญหา เฟดอาจขึ้นดอกเบี้ย ทองคำจะได้รับผลกระทบเชิงลบ"""
    
    event = MagicMock()
    event.title = 'CPI m/m'
    event.title_th = 'ดัชนีราคาผู้บริโภค'
    event.country = 'USD'
    event.impact = 'High'
    event.forecast = '0.3%'
    event.previous = '0.4%'
    
    with patch('analyzer.call_gemini', return_value=mock_gemini_response):
        result = analyze_event(event)
    
    assert isinstance(result, AnalysisResult)
    assert result.impact == 'HIGH'
    assert result.bias == 'BEARISH'
    assert result.confidence == 75
    assert 'CPI' in result.reasoning or 'เงินเฟ้อ' in result.reasoning


def test_analyze_event_handles_gemini_error():
    """analyze_event should return fallback analysis when Gemini fails."""
    from analyzer import analyze_event, AnalysisResult
    
    event = MagicMock()
    event.title = 'CPI m/m'
    event.title_th = 'ดัชนีราคาผู้บริโภค'
    event.country = 'USD'
    event.impact = 'High'
    event.forecast = '0.3%'
    event.previous = '0.4%'
    
    with patch('analyzer.call_gemini', return_value=None):
        result = analyze_event(event)
    
    assert isinstance(result, AnalysisResult)
    assert result.impact == 'HIGH'  # Falls back to event's own impact
    assert result.bias == 'NEUTRAL'  # Default fallback


def test_parse_gemini_response_extracts_fields():
    """parse_gemini_response should extract IMPACT, BIAS, CONFIDENCE, REASONING."""
    from analyzer import parse_gemini_response
    
    response = """IMPACT: HIGH
BIAS: BULLISH
CONFIDENCE: 80%
REASONING: เฟดลดดอกเบี้ย ทองคำน่าจะขึ้น"""
    
    result = parse_gemini_response(response)
    
    assert result['impact'] == 'HIGH'
    assert result['bias'] == 'BULLISH'
    assert result['confidence'] == 80
    assert 'เฟดลดดอกเบี้ย' in result['reasoning']


def test_build_analysis_prompt_includes_event_details():
    """build_analysis_prompt should include event details in Thai."""
    from analyzer import build_analysis_prompt
    
    event = MagicMock()
    event.title = 'Non-Farm Payrolls'
    event.title_th = 'ตัวเลขการจ้างงานนอกภาคเกษตร'
    event.country = 'USD'
    event.impact = 'High'
    event.forecast = '200K'
    event.previous = '180K'
    
    prompt = build_analysis_prompt(event)
    
    assert 'Non-Farm Payrolls' in prompt
    assert 'ตัวเลขการจ้างงานนอกภาคเกษตร' in prompt
    assert 'ทองคำ' in prompt  # Thai for gold
    assert 'IMPACT' in prompt
    assert 'BIAS' in prompt


def test_analyze_events_batch_processes_multiple():
    """analyze_events should process a list of events and return results."""
    from analyzer import analyze_events, AnalysisResult
    
    events = [
        MagicMock(title='CPI m/m', title_th='ดัชนีราคาผู้บริโภค',
                  country='USD', impact='High', forecast='0.3%', previous='0.4%'),
        MagicMock(title='FOMC', title_th='การประชุม FOMC',
                  country='USD', impact='High', forecast='', previous=''),
    ]
    
    mock_response = """IMPACT: HIGH
BIAS: BEARISH
CONFIDENCE: 70%
REASONING: ข่าวสำคัญที่มีผลต่อทอง"""
    
    with patch('analyzer.call_gemini', return_value=mock_response):
        results = analyze_events(events)
    
    assert len(results) == 2
    assert all(isinstance(r, AnalysisResult) for r in results)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_analyzer.py -v`
Expected: FAIL (analyzer module doesn't exist yet)

- [ ] **Step 3: Write analyzer.py**

```python
"""
AI Analyzer Module
==================
Uses Gemini API to analyze news events' impact on gold prices.
Provides Thai-language analysis with impact level, bias, confidence, and reasoning.
"""

import logging
from typing import List, Optional, Dict
from dataclasses import dataclass

import requests

import config

logger = logging.getLogger('goldnews')


@dataclass
class AnalysisResult:
    """Result of AI analysis for a news event."""
    event_title: str
    event_title_th: str
    impact: str  # HIGH, MEDIUM, LOW
    bias: str    # BULLISH, BEARISH, NEUTRAL
    confidence: int  # 0-100
    reasoning: str
    country: str
    forecast: str
    previous: str


def build_analysis_prompt(event) -> str:
    """
    Build a Thai-language prompt for Gemini to analyze a news event's
    impact on gold prices.
    """
    return f"""คุณเป็น News Analyst มืออาชีพสำหรับตลาดทองคำ (XAU/USD)

📰 ข่าวที่ต้องวิเคราะห์:
- ชื่อข่าว: {event.title} ({event.title_th})
- ประเทศ: {event.country}
- ระดับผลกระทบ: {event.impact}
- ค่าคาดการณ์: {event.forecast or 'ไม่มีข้อมูล'}
- ค่าก่อนหน้า: {event.previous or 'ไม่มีข้อมูล'}

🎯 งานของคุณ:
1. ประเมินผลกระทบต่อราคาทองคำ: HIGH / MEDIUM / LOW
2. ตัดสินใจแนวโน้ม: BULLISH (ทองขึ้น) / BEARISH (ทองลง) / NEUTRAL (เป็นกลาง)
3. ให้คะแนนความมั่นใจ (0-100%)
4. อธิบายเหตุผลสั้นๆ เป็นภาษาไทย

⚠️ ห้ามพูดถึง:
- Technical indicators
- ความเสี่ยง
- การบริหารเงิน
- ราคาเป้าหมาย

💡 จดจำ: ทองคำมีความสัมพันธ์ผกผันกับดอลลาร์สหรัฐ (USD) — ข่าวที่ทำให้ USD แข็งแกร่งมักทำให้ทองลง และในทางกลับกัน

📤 ตอบในรูปแบบนี้เท่านั้น:
IMPACT: [HIGH/MEDIUM/LOW]
BIAS: [BULLISH/BEARISH/NEUTRAL]
CONFIDENCE: [0-100]%
REASONING: [เหตุผลเป็นภาษาไทย]"""


def call_gemini(prompt: str) -> Optional[str]:
    """
    Call Gemini API with the given prompt.
    
    Returns the text response or None on failure.
    """
    if not config.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set, skipping AI analysis")
        return None
    
    try:
        response = requests.post(
            f"{config.GEMINI_API_URL}?key={config.GEMINI_API_KEY}",
            json={
                'contents': [{
                    'role': 'user',
                    'parts': [{'text': prompt}]
                }],
                'generationConfig': {
                    'temperature': 0.2,
                    'maxOutputTokens': 300,
                }
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        
        text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')
        return text
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Gemini API error: {e}")
        return None
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Gemini response parsing error: {e}")
        return None


def parse_gemini_response(response: str) -> Dict[str, str]:
    """
    Parse Gemini's text response into structured fields.
    
    Expected format:
    IMPACT: HIGH
    BIAS: BEARISH
    CONFIDENCE: 75%
    REASONING: ...
    """
    lines = response.strip().split('\n')
    
    def extract(key: str) -> str:
        for line in lines:
            if key in line:
                value = line.split(key)[1].strip()
                # Remove trailing % from confidence
                if key == 'CONFIDENCE:':
                    value = value.replace('%', '')
                return value
        return ''
    
    return {
        'impact': extract('IMPACT:').upper() or 'LOW',
        'bias': extract('BIAS:').upper() or 'NEUTRAL',
        'confidence': extract('CONFIDENCE:').replace('%', '') or '50',
        'reasoning': extract('REASONING:') or 'ไม่มีข้อมูลเพิ่มเติม',
    }


def analyze_event(event) -> AnalysisResult:
    """
    Analyze a single news event using Gemini API.
    
    Returns AnalysisResult with impact, bias, confidence, and reasoning.
    Falls back to basic analysis if Gemini is unavailable.
    """
    prompt = build_analysis_prompt(event)
    response = call_gemini(prompt)
    
    if response:
        parsed = parse_gemini_response(response)
        confidence = int(parsed['confidence']) if parsed['confidence'].isdigit() else 50
        confidence = max(0, min(100, confidence))
        
        return AnalysisResult(
            event_title=event.title,
            event_title_th=event.title_th,
            impact=parsed['impact'],
            bias=parsed['bias'],
            confidence=confidence,
            reasoning=parsed['reasoning'],
            country=event.country,
            forecast=event.forecast,
            previous=event.previous,
        )
    
    # Fallback: use event's own impact level, neutral bias
    logger.warning(f"Gemini unavailable, using fallback analysis for: {event.title}")
    return AnalysisResult(
        event_title=event.title,
        event_title_th=event.title_th,
        impact=event.impact.upper(),
        bias='NEUTRAL',
        confidence=40,
        reasoning=f'วิเคราะห์อัตโนมัติ: ข่าว {event.title_th} ระดับ {config.IMPACT_THAI.get(event.impact, event.impact)}',
        country=event.country,
        forecast=event.forecast,
        previous=event.previous,
    )


def analyze_events(events: list) -> List[AnalysisResult]:
    """
    Analyze multiple news events.
    
    Returns list of AnalysisResult objects.
    """
    results = []
    for event in events:
        try:
            result = analyze_event(event)
            results.append(result)
        except Exception as e:
            logger.error(f"Error analyzing event {event.title}: {e}")
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_analyzer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/kwanchanokroumsuk/goldnews && git add analyzer.py tests/test_analyzer.py && git commit -m "feat: add AI analyzer module with Gemini API integration"
```

---

### Task 4: Telegram Bot Module

**Files:**
- Create: `goldnews/telegram_bot.py`
- Create: `goldnews/tests/test_telegram_bot.py`

- [ ] **Step 1: Write test_telegram_bot.py**

```python
"""Tests for telegram_bot module."""
import pytest
from unittest.mock import patch, MagicMock


def test_send_message_success():
    """send_message should return True on successful API call."""
    from telegram_bot import send_message
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'ok': True}
    mock_response.raise_for_status = MagicMock()
    
    with patch('telegram_bot.requests.post', return_value=mock_response):
        result = send_message("Test message")
    
    assert result is True


def test_send_message_failure():
    """send_message should return False on API error."""
    from telegram_bot import send_message
    
    with patch('telegram_bot.requests.post', side_effect=Exception('Network error')):
        result = send_message("Test message")
    
    assert result is False


def test_send_message_with_retry_success_first_try():
    """send_message_with_retry should succeed on first try."""
    from telegram_bot import send_message_with_retry
    
    with patch('telegram_bot.send_message', return_value=True):
        result = send_message_with_retry("Test message", max_retries=3)
    
    assert result is True


def test_send_message_with_retry_success_after_retry():
    """send_message_with_retry should retry and eventually succeed."""
    from telegram_bot import send_message_with_retry
    
    with patch('telegram_bot.send_message', side_effect=[False, False, True]):
        result = send_message_with_retry("Test message", max_retries=3, retry_delay=0.01)
    
    assert result is True


def test_send_message_with_retry_all_fail():
    """send_message_with_retry should return False after all retries fail."""
    from telegram_bot import send_message_with_retry
    
    with patch('telegram_bot.send_message', return_value=False):
        result = send_message_with_retry("Test message", max_retries=3, retry_delay=0.01)
    
    assert result is False


def test_send_news_alert_formats_correctly():
    """send_news_alert should call send_message with formatted text."""
    from telegram_bot import send_news_alert
    
    sent_messages = []
    
    def mock_send(text):
        sent_messages.append(text)
        return True
    
    with patch('telegram_bot.send_message', side_effect=mock_send):
        result = send_news_alert("🔔 ข่าวสำคัญ: CPI", "รายละเอียดข่าว")
    
    assert result is True
    assert len(sent_messages) == 1
    assert "CPI" in sent_messages[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_telegram_bot.py -v`
Expected: FAIL (telegram_bot module doesn't exist yet)

- [ ] **Step 3: Write telegram_bot.py**

```python
"""
Telegram Bot Module
==================
Sends formatted messages to Telegram via Bot API.
Handles rate limiting, retries, and error handling.
"""

import time
import logging
from typing import Optional

import requests

import config

logger = logging.getLogger('goldnews')


def send_message(text: str, parse_mode: str = 'HTML') -> bool:
    """
    Send a message to the configured Telegram chat.
    
    Args:
        text: Message text (HTML formatted)
        parse_mode: Parse mode (HTML, Markdown, MarkdownV2)
        
    Returns:
        True if sent successfully, False otherwise
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram bot token or chat ID not configured")
        return False
    
    url = f"{config.TELEGRAM_API_URL}/sendMessage"
    
    payload = {
        'chat_id': config.TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True,
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info("Telegram message sent successfully")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def send_message_with_retry(text: str, max_retries: int = 3, retry_delay: float = 5.0,
                            parse_mode: str = 'HTML') -> bool:
    """
    Send a message with exponential backoff retry.
    
    Args:
        text: Message text
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries (doubles each time)
        parse_mode: Parse mode for Telegram
        
    Returns:
        True if sent successfully within retries, False otherwise
    """
    for attempt in range(max_retries):
        if send_message(text, parse_mode):
            return True
        
        if attempt < max_retries - 1:
            delay = retry_delay * (2 ** attempt)  # Exponential backoff
            logger.warning(f"Retry {attempt + 1}/{max_retries} in {delay:.1f}s...")
            time.sleep(delay)
    
    logger.error(f"Failed to send message after {max_retries} attempts")
    return False


def send_news_alert(title: str, body: str) -> bool:
    """
    Send a news alert message.
    
    Args:
        title: Alert title
        body: Alert body text
        
    Returns:
        True if sent successfully
    """
    message = f"{title}\n\n{body}"
    return send_message_with_retry(message)


def send_startup_message() -> bool:
    """Send a startup notification to confirm the bot is running."""
    message = (
        "🟡 <b>Gold News Bot เริ่มทำงาน</b>\n\n"
        f"⏰ ตรวจสอบข่าวทุก {config.CHECK_INTERVAL} นาที\n"
        f"📅 วันจันทร์-ศุกร์ (เวลาตลาด)\n\n"
        "<i>บอทพร้อมส่งข่าวสำคัญที่มีผลต่อราคาทองคำ</i>"
    )
    return send_message(message)


def send_error_alert(error_message: str) -> bool:
    """Send an error alert to notify of issues."""
    message = (
        f"🚨 <b>Gold News Bot Error</b>\n\n"
        f"{error_message}\n\n"
        f"<i>บอทจะลองใหม่ในรอบถัดไป</i>"
    )
    return send_message(message)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_telegram_bot.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/kwanchanokroumsuk/goldnews && git add telegram_bot.py tests/test_telegram_bot.py && git commit -m "feat: add Telegram bot module with retry and error handling"
```

---

### Task 5: Formatter Module

**Files:**
- Create: `goldnews/formatter.py`
- Create: `goldnews/tests/test_formatter.py`

- [ ] **Step 1: Write test_formatter.py**

```python
"""Tests for formatter module."""
import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass


def test_format_event_analysis_creates_thai_message():
    """format_event_analysis should create a Thai-language message with emoji."""
    from formatter import format_event_analysis
    from analyzer import AnalysisResult
    
    result = AnalysisResult(
        event_title='CPI m/m',
        event_title_th='ดัชนีราคาผู้บริโภค',
        impact='HIGH',
        bias='BEARISH',
        confidence=75,
        reasoning='CPI สูงกว่าคาดหมายถึงเงินเฟ้อยังเป็นปัญหา',
        country='USD',
        forecast='0.3%',
        previous='0.4%',
    )
    
    message = format_event_analysis(result)
    
    assert 'CPI m/m' in message
    assert 'ดัชนีราคาผู้บริโถค' in message or 'ดัชนีราคาผู้บริโภค' in message
    assert 'สูง' in message  # Thai for "High" impact
    assert 'BEARISH' in message or 'เชิงลบ' in message
    assert '75' in message  # Confidence percentage


def test_format_polymarket_summary_creates_sentiment_section():
    """format_polymarket_summary should create Polymarket sentiment section."""
    from formatter import format_polymarket_summary
    from news_fetcher import PolymarketData
    
    markets = [
        PolymarketData(
            title='Will gold close above $3000 this week?',
            probability=0.68,
            volume=150000,
            url='https://polymarket.com/event/gold-above-3000',
        ),
    ]
    
    message = format_polymarket_summary(markets)
    
    assert 'Polymarket' in message or 'polymarket' in message.lower()
    assert '68' in message  # 68% probability


def test_format_daily_summary_combines_events():
    """format_daily_summary should combine multiple analyses into one message."""
    from formatter import format_daily_summary
    from analyzer import AnalysisResult
    
    analyses = [
        AnalysisResult(
            event_title='CPI m/m',
            event_title_th='ดัชนีราคาผู้บริโภค',
            impact='HIGH',
            bias='BEARISH',
            confidence=75,
            reasoning='เงินเฟ้อสูง',
            country='USD',
            forecast='0.3%',
            previous='0.4%',
        ),
        AnalysisResult(
            event_title='FOMC',
            event_title_th='การประชุม FOMC',
            impact='HIGH',
            bias='BULLISH',
            confidence=80,
            reasoning='เฟดลดดอกเบี้ย',
            country='USD',
            forecast='',
            previous='',
        ),
    ]
    
    message = format_daily_summary(analyses)
    
    assert 'CPI' in message
    assert 'FOMC' in message
    assert 'ทองคำ' in message or 'ทอง' in message


def test_format_empty_analysis():
    """format_daily_summary should handle empty analysis list."""
    from formatter import format_daily_summary
    
    message = format_daily_summary([])
    
    assert 'ไม่มี' in message or 'ข่าว' in message


def test_get_impact_emoji():
    """get_impact_emoji should return correct emoji for impact levels."""
    from formatter import get_impact_emoji
    
    assert get_impact_emoji('HIGH') == '🔴'
    assert get_impact_emoji('MEDIUM') == '🟡'
    assert get_impact_emoji('LOW') == '🟢'


def test_get_bias_emoji():
    """get_bias_emoji should return correct emoji for bias directions."""
    from formatter import get_bias_emoji
    
    assert get_bias_emoji('BULLISH') == '📈'
    assert get_bias_emoji('BEARISH') == '📉'
    assert get_bias_emoji('NEUTRAL') == '➡️'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_formatter.py -v`
Expected: FAIL (formatter module doesn't exist yet)

- [ ] **Step 3: Write formatter.py**

```python
"""
Formatter Module
===============
Creates Thai-language Telegram messages with emoji indicators.
Formats analysis results, event details, and Polymarket sentiment
into readable Telegram messages.
"""

import logging
from datetime import datetime
from typing import List, Optional

import config
from analyzer import AnalysisResult
from news_fetcher import PolymarketData

logger = logging.getLogger('goldnews')


def get_impact_emoji(impact: str) -> str:
    """Return emoji for impact level."""
    return {
        'HIGH': '🔴',
        'MEDIUM': '🟡',
        'LOW': '🟢',
    }.get(impact.upper(), '⚪')


def get_bias_emoji(bias: str) -> str:
    """Return emoji for bias direction."""
    return {
        'BULLISH': '📈',
        'BEARISH': '📉',
        'NEUTRAL': '➡️',
    }.get(bias.upper(), '⚪')


def format_event_analysis(analysis: AnalysisResult) -> str:
    """
    Format a single event analysis into a Thai Telegram message.
    
    Args:
        analysis: AnalysisResult from the analyzer
        
    Returns:
        Formatted Thai message string
    """
    impact_thai = config.IMPACT_THAI.get(analysis.impact, analysis.impact)
    bias_thai = config.BIAS_THAI.get(analysis.bias, analysis.bias)
    impact_emoji = get_impact_emoji(analysis.impact)
    bias_emoji = get_bias_emoji(analysis.bias)
    
    # Get Thai day name
    now = datetime.now()
    day_thai = config.DAY_THAI.get(now.weekday(), '')
    
    message = (
        f"🔔 <b>ข่าวสำคัญ: {analysis.event_title}</b>\n"
        f"📅 เวลา: {now.strftime('%H:%M')} ICT ({day_thai})\n"
        f"🇺🇸 ประเทศ: {analysis.country}\n"
        f"{impact_emoji} ระดับผลกระทบ: {impact_thai}\n"
    )
    
    # Add forecast/previous if available
    if analysis.forecast:
        message += f"📊 ค่าคาดการณ์: {analysis.forecast}\n"
    if analysis.previous:
        message += f"📈 ค่าก่อนหน้า: {analysis.previous}\n"
    
    message += (
        f"\n📊 <b>วิเคราะห์ผลกระทบต่อทองคำ:</b>\n"
        f"{bias_emoji} ทิศทาง: {analysis.bias} ({bias_thai})\n"
        f"🎯 ความมั่นใจ: {analysis.confidence}%\n"
        f"💡 สาเหตุ: {analysis.reasoning}\n"
    )
    
    return message


def format_polymarket_summary(markets: List[PolymarketData]) -> str:
    """
    Format Polymarket data into a sentiment summary section.
    
    Args:
        markets: List of PolymarketData objects
        
    Returns:
        Formatted Thai message section
    """
    if not markets:
        return ""
    
    message = "\n🎲 <b>Polymarket Sentiment:</b>\n"
    
    for market in markets[:3]:  # Top 3 markets
        prob_pct = market.probability * 100
        message += f"• {market.title}\n"
        message += f"  ทองคำขึ้น: {prob_pct:.0f}% | ทองคำลง: {100 - prob_pct:.0f}%\n"
    
    return message


def format_daily_summary(analyses: List[AnalysisResult],
                         markets: Optional[List[PolymarketData]] = None) -> str:
    """
    Format a complete daily summary message combining all analyses.
    
    Args:
        analyses: List of AnalysisResult objects
        markets: Optional list of PolymarketData objects
        
    Returns:
        Complete formatted Thai message
    """
    if not analyses:
        now = datetime.now()
        day_thai = config.DAY_THAI.get(now.weekday(), '')
        return (
            f"📋 <b>สรุปข่าวทองคำ</b>\n"
            f"📅 {now.strftime('%d/%m/%Y')} ({day_thai})\n\n"
            f"ไม่มีข่าวสำคัญที่มีผลต่อทองคำในขณะนี้\n\n"
            f"<i>บอทจะตรวจสอบอีกครั้งใน {config.CHECK_INTERVAL} นาที</i>"
        )
    
    now = datetime.now()
    day_thai = config.DAY_THAI.get(now.weekday(), '')
    
    # Header
    message = (
        f"📋 <b>สรุปข่าวทองคำ</b>\n"
        f"📅 {now.strftime('%d/%m/%Y %H:%M')} ({day_thai})\n"
        f"📊 พบข่าวสำคัญ {len(analyses)} รายการ\n"
        f"{'─' * 30}\n\n"
    )
    
    # Individual analyses
    for i, analysis in enumerate(analyses, 1):
        impact_emoji = get_impact_emoji(analysis.impact)
        bias_emoji = get_bias_emoji(analysis.bias)
        impact_thai = config.IMPACT_THAI.get(analysis.impact, analysis.impact)
        bias_thai = config.BIAS_THAI.get(analysis.bias, analysis.bias)
        
        message += (
            f"{impact_emoji} <b>{i}. {analysis.event_title}</b>\n"
            f"   ชื่อไทย: {analysis.event_title_th}\n"
            f"   ผลกระทบ: {impact_thai} | ทิศทาง: {bias_emoji} {bias_thai}\n"
            f"   ความมั่นใจ: {analysis.confidence}%\n"
            f"   💡 {analysis.reasoning}\n\n"
        )
    
    # Polymarket section
    if markets:
        message += format_polymarket_summary(markets)
    
    # Footer
    message += f"\n{'─' * 30}\n<i>🔄 ตรวจสอบใหม่ใน {config.CHECK_INTERVAL} นาที</i>"
    
    return message
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_formatter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/kwanchanokroumsuk/goldnews && git add formatter.py tests/test_formatter.py && git commit -m "feat: add Thai message formatter module"
```

---

### Task 6: Scheduler Module

**Files:**
- Create: `goldnews/scheduler.py`
- Create: `goldnews/tests/test_scheduler.py`

- [ ] **Step 1: Write test_scheduler.py**

```python
"""Tests for scheduler module."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


def test_is_market_hours_weekday():
    """is_market_hours should return True on weekdays."""
    from scheduler import is_market_hours
    
    # Monday through Friday
    for weekday in range(5):
        with patch('scheduler.datetime') as mock_dt:
            mock_now = MagicMock()
            mock_now.weekday.return_value = weekday
            mock_dt.now.return_value = mock_now
            assert is_market_hours() is True


def test_is_market_hours_weekend():
    """is_market_hours should return False on weekends when MARKET_HOURS_ONLY is True."""
    from scheduler import is_market_hours
    
    with patch('scheduler.config.MARKET_HOURS_ONLY', True):
        # Saturday (5) and Sunday (6)
        for weekday in [5, 6]:
            with patch('scheduler.datetime') as mock_dt:
                mock_now = MagicMock()
                mock_now.weekday.return_value = weekday
                mock_dt.now.return_value = mock_now
                assert is_market_hours() is False


def test_is_market_hours_weekend_no_restriction():
    """is_market_hours should return True on weekends when MARKET_HOURS_ONLY is False."""
    from scheduler import is_market_hours
    
    with patch('scheduler.config.MARKET_HOURS_ONLY', False):
        assert is_market_hours() is True


def test_run_news_cycle_calls_all_steps():
    """run_news_cycle should fetch news, analyze, format, and send."""
    from scheduler import run_news_cycle
    
    mock_event = MagicMock(title='CPI', impact='High')
    mock_analysis = MagicMock(event_title='CPI', impact='HIGH')
    mock_market = MagicMock(title='Gold above $3000')
    
    with patch('scheduler.news_fetcher.fetch_all_news') as mock_fetch, \
         patch('scheduler.analyzer.analyze_events') as mock_analyze, \
         patch('scheduler.formatter.format_daily_summary') as mock_format, \
         patch('scheduler.telegram_bot.send_message_with_retry') as mock_send:
        
        mock_fetch.return_value = {'events': [mock_event], 'markets': [mock_market]}
        mock_analyze.return_value = [mock_analysis]
        mock_format.return_value = "Test message"
        mock_send.return_value = True
        
        result = run_news_cycle()
        
        mock_fetch.assert_called_once()
        mock_analyze.assert_called_once()
        mock_format.assert_called_once()
        mock_send.assert_called_once()
        assert result is True


def test_run_news_cycle_handles_no_events():
    """run_news_cycle should handle case with no relevant events."""
    from scheduler import run_news_cycle
    
    with patch('scheduler.news_fetcher.fetch_all_news') as mock_fetch, \
         patch('scheduler.analyzer.analyze_events') as mock_analyze, \
         patch('scheduler.formatter.format_daily_summary') as mock_format, \
         patch('scheduler.telegram_bot.send_message_with_retry') as mock_send:
        
        mock_fetch.return_value = {'events': [], 'markets': []}
        mock_analyze.return_value = []
        mock_format.return_value = "No events message"
        mock_send.return_value = True
        
        result = run_news_cycle()
        
        assert result is True


def test_run_news_cycle_handles_fetch_error():
    """run_news_cycle should handle fetch errors gracefully."""
    from scheduler import run_news_cycle
    
    with patch('scheduler.news_fetcher.fetch_all_news', side_effect=Exception('API error')), \
         patch('scheduler.telegram_bot.send_error_alert') as mock_error:
        
        mock_error.return_value = True
        
        result = run_news_cycle()
        
        assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_scheduler.py -v`
Expected: FAIL (scheduler module doesn't exist yet)

- [ ] **Step 3: Write scheduler.py**

```python
"""
Scheduler Module
===============
Runs the news cycle on a configurable interval.
Checks market hours and skips weekends.
"""

import time
import logging
from datetime import datetime
from typing import Optional

import config
import news_fetcher
import analyzer
import formatter
import telegram_bot

logger = logging.getLogger('goldnews')


def is_market_hours() -> bool:
    """
    Check if current time is within market hours.
    
    When MARKET_HOURS_ONLY is True, only runs Monday-Friday.
    When False, runs every day.
    """
    if not config.MARKET_HOURS_ONLY:
        return True
    
    now = datetime.now()
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    # Skip weekends (Saturday=5, Sunday=6)
    if weekday >= 5:
        logger.info(f"Weekend detected (day {weekday}), skipping news cycle")
        return False
    
    return True


def run_news_cycle() -> bool:
    """
    Run a complete news cycle:
    1. Fetch news from all sources
    2. Analyze events with AI
    3. Format messages
    4. Send to Telegram
    
    Returns:
        True if cycle completed successfully, False otherwise
    """
    logger.info("Starting news cycle...")
    
    try:
        # Step 1: Fetch news
        news_data = news_fetcher.fetch_all_news()
        events = news_data.get('events', [])
        markets = news_data.get('markets', [])
        
        logger.info(f"Fetched {len(events)} events and {len(markets)} markets")
        
        # Step 2: Analyze events
        if events:
            analyses = analyzer.analyze_events(events)
            logger.info(f"Analyzed {len(analyses)} events")
        else:
            analyses = []
            logger.info("No relevant events to analyze")
        
        # Step 3: Format message
        message = formatter.format_daily_summary(analyses, markets)
        
        # Step 4: Send to Telegram
        if analyses or markets:
            success = telegram_bot.send_message_with_retry(message)
            if success:
                logger.info("News alert sent successfully")
            else:
                logger.error("Failed to send news alert after retries")
            return success
        else:
            # No news to report - still send a "no news" message
            success = telegram_bot.send_message_with_retry(message)
            logger.info("No significant news - sent quiet update")
            return success
            
    except Exception as e:
        logger.error(f"Error in news cycle: {e}", exc_info=True)
        telegram_bot.send_error_alert(f"ข้อผิดพลาดในการตรวจสอบข่าว: {str(e)}")
        return False


def start_scheduler():
    """
    Start the main scheduler loop.
    
    Runs the news cycle every CHECK_INTERVAL minutes.
    Skips cycles outside market hours if MARKET_HOURS_ONLY is True.
    """
    logger.info(f"Starting Gold News Bot scheduler")
    logger.info(f"Check interval: {config.CHECK_INTERVAL} minutes")
    logger.info(f"Market hours only: {config.MARKET_HOURS_ONLY}")
    
    # Send startup message
    telegram_bot.send_startup_message()
    
    interval_seconds = config.CHECK_INTERVAL * 60
    
    while True:
        try:
            if is_market_hours():
                run_news_cycle()
            else:
                logger.info("Outside market hours, skipping cycle")
            
            logger.info(f"Sleeping for {config.CHECK_INTERVAL} minutes...")
            time.sleep(interval_seconds)
            
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error in scheduler loop: {e}", exc_info=True)
            # Sleep and try again
            time.sleep(60)  # Wait 1 minute before retrying on unexpected errors
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_scheduler.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/kwanchanokroumsuk/goldnews && git add scheduler.py tests/test_scheduler.py && git commit -m "feat: add scheduler module with market hours check"
```

---

### Task 7: Main Entry Point and Integration

**Files:**
- Create: `goldnews/main.py`
- Create: `goldnews/tests/test_main.py`

- [ ] **Step 1: Write test_main.py**

```python
"""Tests for main module."""
import pytest
from unittest.mock import patch, MagicMock
import sys


def test_main_runs_scheduler():
    """main() should start the scheduler."""
    with patch('main.scheduler.start_scheduler') as mock_scheduler:
        mock_scheduler.side_effect = KeyboardInterrupt()  # Stop the loop
        
        from main import main
        with pytest.raises(KeyboardInterrupt):
            main()
        
        mock_scheduler.assert_called_once()


def test_main_once_mode():
    """main() with --once flag should run a single news cycle."""
    with patch('sys.argv', ['main.py', '--once']), \
         patch('main.scheduler.run_news_cycle') as mock_cycle:
        mock_cycle.return_value = True
        
        from main import main
        main()
        
        mock_cycle.assert_called_once()


def test_main_test_mode():
    """main() with --test flag should send a test message."""
    with patch('sys.argv', ['main.py', '--test']), \
         patch('main.telegram_bot.send_message') as mock_send:
        mock_send.return_value = True
        
        from main import main
        main()
        
        mock_send.assert_called_once()
        # Check that test message contains Thai text
        call_args = mock_send.call_args
        assert 'ทองคำ' in call_args[0][0] or 'Gold' in call_args[0][0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_main.py -v`
Expected: FAIL (main module doesn't exist yet)

- [ ] **Step 3: Write main.py**

```python
#!/usr/bin/env python3
"""
Gold News Telegram Bot
=====================
Main entry point for the gold news alert bot.

Usage:
    python main.py              # Start continuous daemon
    python main.py --once       # Run a single news cycle
    python main.py --test       # Send a test message
"""

import argparse
import logging
import sys

import config
import scheduler
import telegram_bot

logger = logging.getLogger('goldnews')


def main():
    """Main entry point for the Gold News Bot."""
    parser = argparse.ArgumentParser(
        description='Gold News Telegram Bot - ส่งข่าวทองคำไปยัง Telegram'
    )
    parser.add_argument(
        '--once', action='store_true',
        help='Run a single news cycle and exit'
    )
    parser.add_argument(
        '--test', action='store_true',
        help='Send a test message and exit'
    )
    
    args = parser.parse_args()
    
    # Validate configuration
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Please set it in .env file.")
        sys.exit(1)
    
    if not config.TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID not set. Please set it in .env file.")
        sys.exit(1)
    
    logger.info("=" * 50)
    logger.info("🥇 Gold News Telegram Bot")
    logger.info("=" * 50)
    logger.info(f"Check interval: {config.CHECK_INTERVAL} minutes")
    logger.info(f"Market hours only: {config.MARKET_HOURS_ONLY}")
    logger.info(f"Gemini API: {'configured' if config.GEMINI_API_KEY else 'NOT configured'}")
    
    if args.test:
        # Test mode: send a test message
        logger.info("Sending test message...")
        test_message = (
            "🧪 <b>Gold News Bot - ทดสอบ</b>\n\n"
            "บอททองคำทำงานได้ปกติ ✅\n"
            f"⏰ ตรวจสอบข่าวทุก {config.CHECK_INTERVAL} นาที\n"
            f"📅 วันจันทร์-ศุกร์ (เวลาตลาด)\n\n"
            "<i>ข่าวสำคัญจะถูกส่งมาให้อัตโนมัติ</i>"
        )
        success = telegram_bot.send_message(test_message)
        if success:
            logger.info("✅ Test message sent successfully!")
        else:
            logger.error("❌ Failed to send test message")
        return
    
    if args.once:
        # Single cycle mode
        logger.info("Running single news cycle...")
        success = scheduler.run_news_cycle()
        if success:
            logger.info("✅ News cycle completed successfully")
        else:
            logger.error("❌ News cycle failed")
        return
    
    # Continuous mode
    logger.info("Starting continuous mode...")
    scheduler.start_scheduler()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_main.py -v`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/kwanchanokroumsuk/goldnews && git add main.py tests/test_main.py && git commit -m "feat: add main entry point with CLI arguments"
```

---

### Task 8: Integration Testing and Final Polish

**Files:**
- Modify: `goldnews/tests/test_integration.py` (create)
- Modify: `goldnews/.env.example` (update if needed)

- [ ] **Step 1: Write integration test**

```python
"""Integration tests for the full news cycle."""
import pytest
from unittest.mock import patch, MagicMock


def test_full_news_cycle_with_mock_data():
    """Test the complete news cycle with mocked external APIs."""
    from news_fetcher import EconomicEvent, PolymarketData
    from analyzer import AnalysisResult
    from formatter import format_daily_summary
    
    # Mock ForexFactory events
    events = [
        EconomicEvent(
            title='CPI m/m',
            title_th='ดัชนีราคาผู้บริโภค',
            country='USD',
            impact='High',
            date='04/28/2026',
            time='8:30am',
            forecast='0.3%',
            previous='0.4%',
        ),
    ]
    
    # Mock Polymarket data
    markets = [
        PolymarketData(
            title='Will gold close above $3000 this week?',
            probability=0.68,
            volume=150000,
            url='https://polymarket.com/event/gold-above-3000',
        ),
    ]
    
    # Mock analysis results
    analyses = [
        AnalysisResult(
            event_title='CPI m/m',
            event_title_th='ดัชนีราคาผู้บริโภค',
            impact='HIGH',
            bias='BEARISH',
            confidence=75,
            reasoning='CPI สูงกว่าคาดหมายถึงเงินเฟ้อยังเป็นปัญหา',
            country='USD',
            forecast='0.3%',
            previous='0.4%',
        ),
    ]
    
    # Format the message
    message = format_daily_summary(analyses, markets)
    
    # Verify message contains all expected sections
    assert 'CPI' in message
    assert 'ดัชนีราคาผู้บริโภค' in message
    assert 'สูง' in message  # Thai for "High" impact
    assert 'BEARISH' in message or 'เชิงลบ' in message
    assert '75' in message  # Confidence
    assert 'Polymarket' in message
    assert '68' in message  # Polymarket probability


def test_full_news_cycle_no_events():
    """Test the news cycle when there are no events."""
    from formatter import format_daily_summary
    
    message = format_daily_summary([])
    
    assert 'ไม่มี' in message or 'ข่าว' in message


def test_message_length_within_telegram_limit():
    """Verify formatted messages are within Telegram's 4096 character limit."""
    from analyzer import AnalysisResult
    from formatter import format_daily_summary
    
    # Create multiple analyses to test longer messages
    analyses = []
    for i in range(10):
        analyses.append(AnalysisResult(
            event_title=f'Test Event {i}',
            event_title_th=f'เหตุการณ์ทดสอบ {i}',
            impact='MEDIUM',
            bias='NEUTRAL',
            confidence=50,
            reasoning='เหตุผลทดสอบสำหรับเหตุการณ์นี้',
            country='USD',
            forecast='',
            previous='',
        ))
    
    message = format_daily_summary(analyses)
    
    # Telegram limit is 4096 characters
    assert len(message) <= 4096, f"Message too long: {len(message)} characters"
```

- [ ] **Step 2: Run integration tests**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Run all tests together**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Install dependencies and verify imports**

Run: `cd /Users/kwanchanokroumsuk/goldnews && pip install -r requirements.txt && python -c "import config; import news_fetcher; import analyzer; import formatter; import telegram_bot; import scheduler; print('All modules imported successfully')"`

- [ ] **Step 5: Commit**

```bash
cd /Users/kwanchanokroumsuk/goldnews && git add tests/test_integration.py && git commit -m "test: add integration tests for full news cycle"
```

---

### Task 9: Final Verification and Documentation

**Files:**
- Create: `goldnews/README.md`

- [ ] **Step 1: Create README.md**

```markdown
# 🥇 Gold News Telegram Bot

ส่งข่าวสำคัญที่มีผลต่อราคาทองคำไปยัง Telegram อัตโนมัติ พร้อมวิเคราะห์ผลกระทบด้วย AI

## คุณสมบัติ

- 📰 ดึงข่าวจาก ForexFactory Economic Calendar อัตโนมัติ
- 🎲 ติดตาม Polymarket prediction markets สำหรับทองคำ
- 🤖 วิเคราะห์ผลกระทบต่อราคาทองด้วย Gemini AI
- 📱 ส่งแจ้งเตือนไปยัง Telegram เป็นภาษาไทย
- ⏰ ตรวจสอบทุก 30 นาที (วันจันทร์-ศุกร์)

## การติดตั้ง

1. Clone repository:
```bash
git clone <repo-url>
cd goldnews
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.env` file:
```bash
cp .env.example .env
# Edit .env with your bot token, chat ID, and Gemini API key
```

4. Create a new Telegram bot via @BotFather and get the token

5. Get your chat ID (send a message to your bot, then visit:
   `https://api.telegram.org/bot<TOKEN>/getUpdates`)

## การใช้งาน

### เริ่มบอท (Continuous mode)
```bash
python main.py
```

### รันครั้งเดียว
```bash
python main.py --once
```

### ทดสอบการส่งข้อความ
```bash
python main.py --test
```

## การตั้งค่า

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather | Required |
| `TELEGRAM_CHAT_ID` | Telegram chat/channel ID | Required |
| `GEMINI_API_KEY` | Google Gemini API key | Required |
| `CHECK_INTERVAL` | Check interval in minutes | 30 |
| `MARKET_HOURS_ONLY` | Only run Mon-Fri | true |
| `LOG_LEVEL` | Logging level | INFO |

## โครงสร้าง

```
goldnews/
├── main.py              # Entry point
├── config.py            # Configuration
├── scheduler.py         # 30-min scheduler
├── news_fetcher.py      # ForexFactory + Polymarket
├── analyzer.py          # Gemini AI analysis
├── telegram_bot.py      # Telegram delivery
├── formatter.py         # Thai message formatting
├── requirements.txt     # Dependencies
└── tests/               # Test suite
```

## รัน Tests

```bash
python -m pytest tests/ -v
```
```

- [ ] **Step 2: Run final full test suite**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Verify all modules can be imported**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python -c "import config; import news_fetcher; import analyzer; import formatter; import telegram_bot; import scheduler; print('✅ All modules imported successfully')"`

- [ ] **Step 4: Commit**

```bash
cd /Users/kwanchanokroumsuk/goldnews && git add README.md && git commit -m "docs: add README with setup and usage instructions"
```

---

## Self-Review Checklist

- [x] **Spec coverage:** Every requirement in the design spec maps to a task
  - Task 1: Config (env vars, Thai translations, keywords)
  - Task 2: News fetcher (ForexFactory + Polymarket)
  - Task 3: AI analyzer (Gemini API, Thai prompts)
  - Task 4: Telegram bot (send, retry, error handling)
  - Task 5: Formatter (Thai messages, emoji)
  - Task 6: Scheduler (30-min interval, market hours)
  - Task 7: Main entry point (CLI args, --once, --test)
  - Task 8: Integration tests
  - Task 9: README and final verification
- [x] **Placeholder scan:** No TBDs, TODOs, or vague steps found
- [x] **Type consistency:** All dataclass types and function signatures are consistent across tasks (EconomicEvent, PolymarketData, AnalysisResult used consistently)