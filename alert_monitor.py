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


def should_check_now() -> bool:
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
    if os.path.exists(SEEN_MARKETS_FILE):
        try:
            with open(SEEN_MARKETS_FILE, 'r') as f:
                data = json.load(f)
            last_check = data.get('last_check', '')
            if last_check:
                last = datetime.fromisoformat(last_check)
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
            'id': f"{m.question[:50]}_{m.volume}",
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


def _matches_smart_alert_keywords(question: str) -> bool:
    """Check if question matches smart alert keywords (Gold, Fed, Ceasefire, etc.)."""
    q_lower = question.lower()
    return any(kw.lower() in q_lower for kw in config.SMART_ALERT_KEYWORDS)


def find_new_markets() -> List[MarketAlert]:
    """Find markets we haven't seen before."""
    all_markets = fetch_fresh_markets()
    new_alerts = []

    for market in all_markets:
        market_id = market['id']

        if is_market_seen(market_id):
            continue

        # Apply volume filter (> $20,000 to filter noise)
        if config.ALERT_VOLUME_THRESHOLD > 0 and market['volume'] < config.ALERT_VOLUME_THRESHOLD:
            continue

        # Categorize
        category = _categorize_market(market['question'], '')

        # Priority 1: Smart Alert Keywords (Gold, Fed, Ceasefire, etc.) - ALWAYS alert
        if _matches_smart_alert_keywords(market['question']):
            new_alerts.append(MarketAlert(
                market_id=market_id,
                question=market['question'],
                question_th=market['question_th'],
                outcomes=market['outcomes'],
                volume=market['volume'],
                url=market['url'],
                category=category,
            ))
            continue

        # Priority 2: Only alert for priority categories (hide politics/economy noise)
        if category in config.PRIORITY_CATEGORIES:
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
    """Send a new market alert to Telegram using predictions bot token."""
    message = format_alert_message(alert)

    # Use PREDICTIONS_BOT_TOKEN for sending alerts
    if not config.PREDICTIONS_BOT_TOKEN:
        logger.error("PREDICTIONS_BOT_TOKEN not set")
        return False

    api_url = f'https://api.telegram.org/bot{config.PREDICTIONS_BOT_TOKEN}/sendMessage'
    data = {
        'chat_id': config.TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True,
    }

    try:
        response = requests.post(api_url, data=data, timeout=10)
        response.raise_for_status()
        logger.info(f"Alert sent successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")
        return False


def check_and_alert():
    """Check for significant probability changes (>5%) - EMERGENCY ALERTS ONLY."""
    if not should_check_now():
        return

    # Import here to avoid circular import
    import predictions_bot
    import volatility_tracker

    logger.info("Checking for volatility alerts (>5% changes)...")

    # Fetch current markets
    markets = predictions_bot.fetch_polymarket_predictions()

    # Check for volatility alerts (>5% change)
    volatility_alerts = volatility_tracker.check_volatility_alerts(markets)

    for alert in volatility_alerts:
        logger.info(f"VOLATILITY ALERT: {alert.question_th} changed {alert.change_pct:+.1f}%")
        message = volatility_tracker.format_volatility_alert(alert)
        success = send_message(message)
        if success:
            logger.info(f"Volatility alert sent: {alert.question_th}")
        else:
            logger.warning(f"Failed to send volatility alert: {alert.question_th}")

    # Record current prices for next comparison
    volatility_tracker.record_current_prices(markets)

    # Note: We NO LONGER send alerts for new markets (too spammy)
    # Only emergency alerts on >5% probability changes


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
