# Gold Predictions v2 — Hybrid Discovery + Auto-Alert Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance Gold Predictions Bot with improved market discovery and automatic Telegram alerts when new Fed/Gold/Econ markets appear on Polymarket.

**Architecture:** Single bot (`predictions_bot.py`) with integrated alert monitor thread. Uses Gamma API only (no CLOB keys needed). Alerts fire based on time window (20:30-21:30 TH) and volume threshold.

**Tech Stack:** Python 3.10, requests, python-dotenv, threading, JSON persistence

---

## File Structure

```
goldnews/
├── predictions_bot.py        # Main bot (MODIFY)
├── alert_monitor.py          # New: auto-alert system (CREATE)
├── config.py                # New config vars (MODIFY)
├── .env.example             # New env vars (MODIFY)
├── data/                    # New: persistence directory (CREATE)
│   └── seen_markets.json    # Tracks already-seen markets (CREATE)
└── tests/
    └── test_alert_monitor.py # New tests (CREATE)
```

---

### Task 1: Add Config Vars

**Files:**
- Modify: `config.py`
- Modify: `.env.example`

- [ ] **Step 1: Add new config vars to config.py**

Add after line 24 (after `PREDICTIONS_BOT_TOKEN`):

```python
# Auto-alert settings
ENABLE_AUTO_ALERTS = os.getenv('ENABLE_AUTO_ALERTS', 'false').lower() == 'true'
ALERT_CHECK_INTERVAL = int(os.getenv('ALERT_CHECK_INTERVAL', '5'))  # minutes
ALERT_WINDOW_START = os.getenv('ALERT_WINDOW_START', '20:30')  # Thai time
ALERT_WINDOW_END = os.getenv('ALERT_WINDOW_END', '21:30')    # Thai time
ALERT_VOLUME_THRESHOLD = int(os.getenv('ALERT_VOLUME_THRESHOLD', '10000'))  # USD
```

- [ ] **Step 2: Add new vars to .env.example**

Add after `PREDICTIONS_BOT_TOKEN` line:

```
ENABLE_AUTO_ALERTS=true
ALERT_CHECK_INTERVAL=5
ALERT_WINDOW_START=20:30
ALERT_WINDOW_END=21:30
ALERT_VOLUME_THRESHOLD=10000
```

- [ ] **Step 3: Commit**

```bash
git add config.py .env.example
git commit -m "feat: add auto-alert config vars"
```

---

### Task 2: Create alert_monitor.py

**Files:**
- Create: `alert_monitor.py`
- Create: `data/seen_markets.json`
- Create: `tests/test_alert_monitor.py`

- [ ] **Step 1: Create data directory and seen_markets.json**

```bash
mkdir -p data
echo '{"seen_ids": []}' > data/seen_markets.json
```

- [ ] **Step 2: Write test file for alert_monitor.py**

```python
"""Tests for alert_monitor module."""
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest

# Create temp data dir for tests
@pytest.fixture
def temp_data_dir(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr('alert_monitor', 'DATA_DIR', str(data_dir))
    return data_dir


def test_should_check_now_during_window():
    """During 20:30-21:30 TH, should always check."""
    from alert_monitor import should_check_now
    # Mock time to be 20:45 TH (13:45 UTC)
    with patch('alert_monitor.datetime') as mock_dt:
        mock_dt.now.return_value.hour = 13
        mock_dt.now.return_value.minute = 45
        mock_dt.now.return_value.utcnow.return_value.hour = 13
        assert should_check_now() == True


def test_should_check_now_outside_window():
    """Outside window, check less frequently."""
    from alert_monitor import should_check_now
    # Mock time to be 10:00 TH (03:00 UTC)
    with patch('alert_monitor.datetime') as mock_dt:
        mock_dt.now.return_value.hour = 3
        mock_dt.now.return_value.minute = 0
        assert should_check_now() == False


def test_load_seen_markets_creates_file():
    """If seen_markets.json doesn't exist, creates empty."""
    import alert_monitor
    result = alert_monitor.load_seen_markets()
    assert 'seen_ids' in result
    assert isinstance(result['seen_ids'], list)
```

- [ ] **Step 3: Write alert_monitor.py**

```python
"""
Alert Monitor Module
===================
Background thread that monitors Polymarket for new Fed/Gold/Econ markets
and sends Telegram alerts when new ones appear.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, time as dtime
from typing import Set, List, Optional
from dataclasses import dataclass

import requests

import config

logger = logging.getLogger('goldnews')

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
SEEN_MARKETS_FILE = os.path.join(DATA_DIR, 'seen_markets.json')


@dataclass
class MarketAlert:
    """A new market alert."""
    market_id: str
    question: str
    question_th: str
    outcomes: List[dict]
    volume: float
    url: str
    category: str


def get_thai_time() -> datetime:
    """Get current time in Thailand timezone (UTC+7)."""
    from datetime import timezone, timedelta
    utc_now = datetime.now(timezone.utc)
    thai_tz = timezone(timedelta(hours=7))
    return utc_now.astimezone(thai_tz)


def is_in_alert_window() -> bool:
    """Check if current Thai time is in the alert window."""
    now = get_thai_time()
    current_time = now.time()

    start_str = config.ALERT_WINDOW_START  # "20:30"
    end_str = config.ALERT_WINDOW_END      # "21:30"

    start_hour, start_min = map(int, start_str.split(':'))
    end_hour, end_min = map(int, end_str.split(':'))

    start = dtime(start_hour, start_min)
    end = dtime(end_hour, end_min)

    if start <= end:
        return start <= current_time <= end
    else:
        return current_time >= start or current_time <= end


def should_check_now(verbose: bool = False) -> bool:
    """
    Decide if we should check for new markets now.
    During alert window (20:30-21:30 TH): always check
    Outside window: check every 30 min
    """
    if not config.ENABLE_AUTO_ALERTS:
        return False

    if is_in_alert_window():
        return True

    # Outside window, check every 30 min based on last check
    seen_file = SEEN_MARKETS_FILE
    if os.path.exists(seen_file):
        try:
            with open(seen_file, 'r') as f:
                data = json.load(f)
            last_check = data.get('last_check', '')
            if last_check:
                from datetime import datetime as dt
                last = dt.fromisoformat(last_check)
                elapsed = (datetime.now() - last).total_seconds() / 60
                if elapsed < 30:
                    return False
        except Exception:
            pass

    return True


def load_seen_markets() -> dict:
    """Load seen markets from JSON file, create if not exists."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(SEEN_MARKETS_FILE):
        data = {'seen_ids': [], 'last_check': ''}
        with open(SEEN_MARKETS_FILE, 'w') as f:
            json.dump(data, f)
        return data

    try:
        with open(SEEN_MARKETS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {'seen_ids': [], 'last_check': ''}


def save_seen_markets(data: dict):
    """Save seen markets to JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    data['last_check'] = datetime.now().isoformat()
    with open(SEEN_MARKETS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def add_to_seen(market_id: str):
    """Add a market ID to seen set."""
    data = load_seen_markets()
    if market_id not in data['seen_ids']:
        data['seen_ids'].append(market_id)
    save_seen_markets(data)


def is_market_seen(market_id: str) -> bool:
    """Check if a market ID has been seen."""
    data = load_seen_markets()
    return market_id in data['seen_ids']


def _translate_question_th(question: str, category: str) -> str:
    """Thai translation for alert messages (simplified version)."""
    import re
    q_lower = question.lower()

    year_match = re.search(r'\b(20\d{2})\b', question)
    year_str = f" ปี {year_match.group(1)}" if year_match else ""

    if 'fed rate' in q_lower or 'federal reserve' in q_lower:
        cuts_match = re.search(r'(\d+\s*(?:or\s*more\s*)?)\s*fed\s*rate\s*cuts?', q_lower)
        if cuts_match:
            num = cuts_match.group(1).strip().replace('or more', 'ขึ้นไป')
            return f'เฟดจะลดดอกเบี้ย {num} ครั้ง{year_str}?'
        return f'การตัดสินใจดอกเบี้ยเฟด{year_str}'

    if 'recession' in q_lower:
        return f'เศรษฐกิจสหรัฐฯ จะถดถอย{year_str}?'

    if 'inflation' in q_lower or 'cpi' in q_lower:
        return 'คาดการณ์เงินเฟ้อ (CPI)'

    if 'gold' in q_lower:
        return 'คาดการณ์ราคาทองคำ'

    return question[:100]


def _categorize_market(question: str, description: str = '') -> str:
    """Categorize market for alert."""
    combined = (question + ' ' + description).lower()

    if any(kw in combined for kw in ['fed rate', 'federal reserve', 'interest rate', 'fomc',
                                       'fed cut', 'fed raise', 'fed hold', 'rate decision']):
        return 'fed'
    if any(kw in combined for kw in ['inflation', 'cpi', 'ppi']):
        return 'inflation'
    if any(kw in combined for kw in ['gold price', 'gold above', 'gold below', 'xauusd']):
        return 'gold'
    if any(kw in combined for kw in ['job', 'employment', 'unemployment', 'payroll']):
        return 'employment'
    if any(kw in combined for kw in ['gdp', 'recession', 'economic']):
        return 'economy'
    return 'other'


def fetch_fresh_markets() -> List[dict]:
    """Fetch recently active markets from Polymarket."""
    import polymarket_predictions
    markets = polymarket_predictions.fetch_polymarket_predictions()
    return [
        {
            'id': f"{m.question[:50]}_{m.volume}",  # Simple ID from question+volume
            'question': m.question,
            'question_th': m.question_th,
            'outcomes': m.outcomes,
            'volume': m.volume,
            'url': m.url,
            'category': m.category,
        }
        for m in markets
        if m.volume > 0
    ]


def find_new_markets() -> List[MarketAlert]:
    """Find markets we haven't seen before."""
    all_markets = fetch_fresh_markets()
    new_alerts = []

    for market in all_markets:
        market_id = market['id']

        if is_market_seen(market_id):
            continue

        # Apply volume filter
        if config.ALERT_VOLUME_THRESHOLD > 0 and market['volume'] < config.ALERT_VOLUME_THRESHOLD:
            continue

        # Categorize
        category = _categorize_market(market['question'], '')

        # Only alert for relevant categories
        if category in ('fed', 'inflation', 'gold', 'employment', 'economy'):
            new_alerts.append(MarketAlert(
                market_id=market_id,
                question=market['question'],
                question_th=market['question_th'],
                outcomes=market['outcomes'],
                volume=market['volume'],
                url=market['url'],
                category=category,
            ))

    return new_alerts


def format_alert_message(alert: MarketAlert) -> str:
    """Format a new market alert as Telegram message."""
    outcomes_str = ""
    for o in alert.outcomes[:2]:
        pct = o['price'] * 100
        name_th = o['name']
        if pct >= 60:
            indicator = '🟢'
        elif pct >= 40:
            indicator = '🟡'
        else:
            indicator = ''
        outcomes_str += f"  {indicator} {name_th}: {pct:.0f}%\n"

    message = (
        f"🎯 <b>ตลาดใหม่!</b>\n\n"
        f"• คำถาม: {alert.question_th}\n"
        f"• ผลลัพธ์:\n{outcomes_str}"
        f"• Volume: ${alert.volume:,.0f}\n\n"
        f"🔗 <a href='{alert.url}'>ดูตลาด</a>"
    )
    return message


def send_alert(alert: MarketAlert) -> bool:
    """Send a new market alert to Telegram."""
    message = format_alert_message(alert)
    import telegram_bot
    return telegram_bot.send_message(message)


def check_and_alert():
    """Check for new markets and send alerts if found."""
    if not should_check_now():
        return

    logger.info("Checking for new markets...")
    new_markets = find_new_markets()

    for market in new_markets:
        logger.info(f"New market found: {market.question_th}")
        success = send_alert(market)
        if success:
            add_to_seen(market.market_id)
            logger.info(f"Alert sent and marked as seen: {market.market_id}")
        else:
            logger.warning(f"Failed to send alert for: {market.market_id}")


class AlertMonitor:
    """Background monitor for new Polymarket markets."""

    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the alert monitor thread."""
        if self._running:
            logger.warning("AlertMonitor already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="AlertMonitor")
        self._thread.start()
        logger.info("AlertMonitor started")

    def stop(self):
        """Stop the alert monitor thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("AlertMonitor stopped")

    def _run(self):
        """Main loop."""
        while self._running:
            try:
                check_and_alert()
            except Exception as e:
                logger.error(f"Error in AlertMonitor: {e}", exc_info=True)

            # Sleep based on config
            interval = config.ALERT_CHECK_INTERVAL * 60
            for _ in range(int(interval)):
                if not self._running:
                    break
                time.sleep(1)


# Global instance
_monitor: Optional[AlertMonitor] = None


def start_monitor():
    """Start the global alert monitor."""
    global _monitor
    if not config.ENABLE_AUTO_ALERTS:
        logger.info("Auto alerts disabled, not starting monitor")
        return

    if _monitor is None:
        _monitor = AlertMonitor()
    _monitor.start()


def stop_monitor():
    """Stop the global alert monitor."""
    global _monitor
    if _monitor:
        _monitor.stop()
        _monitor = None
```

- [ ] **Step 4: Run tests**

Run: `cd /Users/kwanchanokroumsuk/goldnews && python3 -m pytest tests/test_alert_monitor.py -v`
Expected: Tests pass

- [ ] **Step 5: Commit**

```bash
git add alert_monitor.py data/seen_markets.json tests/test_alert_monitor.py
git commit -m "feat: add alert_monitor for new market detection"
```

---

### Task 3: Integrate Alert Monitor into predictions_bot.py

**Files:**
- Modify: `predictions_bot.py`

- [ ] **Step 1: Import alert_monitor at top**

Add after existing imports:

```python
import alert_monitor
```

- [ ] **Step 2: Start monitor in start_bot()**

Find the `start_bot()` function. After the initial offset skip (around line 450), add:

```python
    # Start alert monitor if enabled
    alert_monitor.start_monitor()

    logger.info("Bot started. Waiting for commands...")
```

- [ ] **Step 3: Stop monitor on shutdown (add signal handler)**

At the end of `start_bot()`, in the `except KeyboardInterrupt` block, add:

```python
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            alert_monitor.stop_monitor()
            break
```

- [ ] **Step 4: Add /alerts command to show status**

In `process_update()`, add after the `/start` handler:

```python
    elif text == '/alerts':
        return handle_alerts_command(chat_id)
```

Add the handler function:

```python
def handle_alerts_command(chat_id: int) -> bool:
    """Handle /alerts command - show alert status."""
    import alert_monitor as am
    from alert_monitor import load_seen_markets

    seen = load_seen_markets()
    status = "✅ เปิดอยู่" if config.ENABLE_AUTO_ALERTS else "❌ ปิดอยู่"
    seen_count = len(seen.get('seen_ids', []))

    message = (
        "🔔 <b>สถานะ Auto Alert</b>\n\n"
        f"สถานะ: {status}\n"
        f"ตรวจสอบทุก: {config.ALERT_CHECK_INTERVAL} นาที\n"
        f"ช่วงเวลาพิเศษ: {config.ALERT_WINDOW_START} - {config.ALERT_WINDOW_END} (เวลาไทย)\n"
        f"Volume ขั้นต่ำ: ${config.ALERT_VOLUME_THRESHOLD:,}\n"
        f"ตลาดที่เห็นแล้ว: {seen_count} ตลาด"
    )
    return send_message(message, chat_id=chat_id)
```

- [ ] **Step 5: Update /help to mention /alerts**

Find the `handle_help_command()` function and add a line for `/alerts`:

```python
        "🔔 <b>/alerts</b> — ดูสถานะ auto alert\n"
```

- [ ] **Step 6: Commit**

```bash
git add predictions_bot.py
git commit -m "feat: integrate alert monitor into predictions bot"
```

---

### Task 4: Improve Market Discovery

**Files:**
- Modify: `predictions_bot.py` (update `fetch_polymarket_predictions()`)
- Modify: `tests/test_polymarket_predictions.py`

- [ ] **Step 1: Add more search queries to fetch_polymarket_predictions()**

In the `fetch_polymarket_predictions()` function, update the search queries list:

```python
    search_queries = [
        'fed funds rate', 'federal reserve', 'interest rate decision',
        'core pce', 'core cpi', 'pce inflation',
        'jobless claims', 'unemployment rate',
        'treasury yield', 'dollar index',
        'fed', 'interest rate', 'cpi', 'inflation', 'gold price', 'recession',
        'gdp growth', 'economic growth',
    ]
```

- [ ] **Step 2: Track market by ID instead of question**

Find the `seen_questions` tracking in `fetch_polymarket_predictions()` and change it to track by market ID (slug):

```python
    markets = []
    seen_ids = set()

    for market in markets_data:
        try:
            question = market.get('question', '')
            if not question:
                continue

            # Use slug as unique ID
            slug = market.get('slug', '')
            market_id = slug or question[:100]

            if market_id in seen_ids:
                continue
            seen_ids.add(market_id)
```

- [ ] **Step 3: Update tests if needed**

Run tests: `python3 -m pytest tests/test_polymarket_predictions.py -v`

- [ ] **Step 4: Commit**

```bash
git add predictions_bot.py
git commit -m "feat: improve market discovery with more search queries and ID-based dedup"
```

---

### Task 5: End-to-End Test

**Files:**
- None (manual testing)

- [ ] **Step 1: Test /predictions command**

Run: `python3 predictions_bot.py &` then send `/predictions` to the bot.

- [ ] **Step 2: Verify alert monitor starts**

Check logs show "AlertMonitor started"

- [ ] **Step 3: Test /alerts command**

Send `/alerts` to verify status display.

- [ ] **Step 4: Commit any final changes**

---

## Spec Coverage Check

- [x] Improved market discovery (Task 4)
- [x] Auto-alert system (Tasks 2, 3)
- [x] Volume threshold filtering (Task 2)
- [x] Thai time window (Task 2)
- [x] `/alerts` command (Task 3)
- [x] Seen market persistence (Task 2)

## Execution Options

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
