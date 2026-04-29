"""
Volatility Tracker Module
========================
Track prediction market probability changes and alert on significant moves (>5%).
"""

import json
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger('goldnews')

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
PRICE_HISTORY_FILE = os.path.join(DATA_DIR, 'price_history.json')

# Threshold for volatility alert (5% change in 1 hour)
VOLATILITY_THRESHOLD = 5.0  # percentage points


@dataclass
class MarketPrice:
    """Store a market's price at a point in time."""
    market_id: str
    question: str
    question_th: str
    outcome_name: str
    price: float  # 0.0 to 1.0
    timestamp: str  # ISO format
    volume: float


@dataclass
class VolatilityAlert:
    """A significant price movement alert."""
    market_id: str
    question_th: str
    outcome_name: str
    old_price: float
    new_price: float
    change_pct: float  # percentage point change
    direction: str  # 'UP' or 'DOWN'
    time_delta: str  # e.g., "30 นาที"


def _get_market_id(market) -> str:
    """Generate unique ID for a market."""
    return f"{market.question[:50]}_{market.category}"


def load_price_history() -> Dict:
    """Load price history from JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(PRICE_HISTORY_FILE):
        return {'prices': {}, 'last_updated': ''}
    
    try:
        with open(PRICE_HISTORY_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load price history: {e}")
        return {'prices': {}, 'last_updated': ''}


def save_price_history(history: Dict):
    """Save price history to JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    history['last_updated'] = datetime.now().isoformat()
    with open(PRICE_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2, default=str)


def record_current_prices(markets: List):
    """Record current prices for all markets."""
    history = load_price_history()
    now = datetime.now().isoformat()
    
    for market in markets:
        market_id = _get_market_id(market)
        
        # Record each outcome's price
        for outcome in market.outcomes:
            price_key = f"{market_id}_{outcome['name']}"
            history['prices'][price_key] = {
                'market_id': market_id,
                'question': market.question,
                'question_th': market.question_th,
                'outcome_name': outcome['name'],
                'price': outcome['price'],
                'timestamp': now,
                'volume': market.volume,
            }
    
    save_price_history(history)
    logger.info(f"Recorded prices for {len(markets)} markets")


def check_volatility_alerts(markets: List) -> List[VolatilityAlert]:
    """
    Check for significant price movements (>5% change).
    
    Returns list of alerts for markets that moved significantly
    since the last check (within last 2 hours).
    """
    history = load_price_history()
    alerts = []
    now = datetime.now()
    
    for market in markets:
        market_id = _get_market_id(market)
        
        for outcome in market.outcomes:
            price_key = f"{market_id}_{outcome['name']}"
            
            # Skip if no history
            if price_key not in history['prices']:
                continue
            
            old_data = history['prices'][price_key]
            old_price = old_data['price']
            new_price = outcome['price']
            old_time = datetime.fromisoformat(old_data['timestamp'])
            
            # Only check recent history (within 2 hours)
            time_diff = now - old_time
            if time_diff > timedelta(hours=2):
                continue
            
            # Calculate change in percentage points
            change_pct = (new_price - old_price) * 100
            
            # Check if change exceeds threshold (absolute value)
            if abs(change_pct) >= VOLATILITY_THRESHOLD:
                # Determine direction
                direction = 'UP ⬆️' if change_pct > 0 else 'DOWN ⬇️'
                
                # Format time delta
                minutes = int(time_diff.total_seconds() / 60)
                if minutes < 60:
                    time_str = f"{minutes} นาที"
                else:
                    hours = minutes // 60
                    time_str = f"{hours} ชม."
                
                alerts.append(VolatilityAlert(
                    market_id=market_id,
                    question_th=market.question_th,
                    outcome_name=outcome['name'],
                    old_price=old_price,
                    new_price=new_price,
                    change_pct=change_pct,
                    direction=direction,
                    time_delta=time_str,
                ))
    
    return alerts


def format_volatility_alert(alert: VolatilityAlert) -> str:
    """Format a volatility alert for Telegram."""
    emoji = '🚨' if abs(alert.change_pct) >= 10 else '⚡'
    
    message = (
        f"{emoji} <b>ตลาดขยับแรง!</b>\n\n"
        f"📊 {alert.question_th}\n"
        f"🎯 {alert.outcome_name}: {alert.direction}\n"
        f"📈 {alert.old_price*100:.0f}% → {alert.new_price*100:.0f}%\n"
        f"📊 เปลี่ยนแปลง: {alert.change_pct:+.1f}% ใน {alert.time_delta}\n\n"
        f"<i>การขยับตัวแรงแบบนี้อาจบ่งบอกว่ามีข่าวใหม่หรือคนกำลังเข้าซื้อ/ขายจำนวนมาก</i>"
    )
    return message


def get_volatility_summary(markets: List) -> str:
    """Get a summary of current volatility status."""
    alerts = check_volatility_alerts(markets)
    
    if not alerts:
        return "📊 ไม่มีตลาดขยับแรง (>5%) ใน 2 ชม.ที่ผ่านมา"
    
    message = f"📊 <b>สรุปความผันผวน</b>\n\n"
    message += f"พบ {len(alerts)} ตลาดที่ขยับแรง:\n\n"
    
    for alert in alerts[:5]:  # Show top 5
        direction_emoji = '🟢' if 'UP' in alert.direction else '🔴'
        message += f"{direction_emoji} {alert.question_th[:40]}...\n"
        message += f"   {alert.change_pct:+.1f}% ({alert.time_delta})\n"
    
    return message
