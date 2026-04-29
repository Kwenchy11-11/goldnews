"""
Price Monitor Module
===================
Fetches real-time XAU/USD (gold) and DXY (dollar index) prices.
Tracks prediction market changes and triggers emergency alerts.
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

import requests

import config

logger = logging.getLogger('goldnews')

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
PREDICTIONS_HISTORY_FILE = os.path.join(DATA_DIR, 'predictions_history.json')


@dataclass
class PriceData:
    """Current price data for gold and dollar."""
    xau_usd: float        # Gold price in USD
    xau_change_pct: float  # Gold change percentage
    dxy: float             # Dollar index
    dxy_change_pct: float  # DXY change percentage
    timestamp: str         # ISO timestamp


def fetch_gold_price() -> Tuple[float, float]:
    """
    Fetch current XAU/USD price.
    Returns (price, change_percentage)
    """
    try:
        # Try Yahoo Finance API
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GC=F"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        result = data['chart']['result'][0]
        price = result['meta']['regularMarketPrice']
        prev_close = result['meta']['chartPreviousClose']
        change_pct = ((price - prev_close) / prev_close) * 100

        return round(price, 2), round(change_pct, 2)
    except Exception as e:
        logger.warning(f"Failed to fetch gold price from Yahoo: {e}")

    try:
        # Fallback: Try alternative API
        url = "https://api.gold-api.com/price/XAU"
        response = requests.get(url, timeout=10)
        data = response.json()
        price = data.get('price', 0)
        return round(price, 2), 0.0
    except Exception as e:
        logger.warning(f"Failed to fetch gold price: {e}")
        return 0.0, 0.0


def fetch_dxy_price() -> Tuple[float, float]:
    """
    Fetch current DXY (Dollar Index) price.
    Returns (price, change_percentage)
    """
    try:
        # Try Yahoo Finance API
        url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()

        result = data['chart']['result'][0]
        price = result['meta']['regularMarketPrice']
        prev_close = result['meta']['chartPreviousClose']
        change_pct = ((price - prev_close) / prev_close) * 100

        return round(price, 2), round(change_pct, 2)
    except Exception as e:
        logger.warning(f"Failed to fetch DXY from Yahoo: {e}")

    return 0.0, 0.0


def get_current_prices() -> PriceData:
    """Get current gold and dollar prices."""
    xau_price, xau_change = fetch_gold_price()
    dxy_price, dxy_change = fetch_dxy_price()

    return PriceData(
        xau_usd=xau_price,
        xau_change_pct=xau_change,
        dxy=dxy_price,
        dxy_change_pct=dxy_change,
        timestamp=datetime.now().isoformat(),
    )


def format_price_line(prices: PriceData) -> str:
    """Format price data as a single line for messages."""
    if prices.xau_usd == 0 and prices.dxy == 0:
        return ""

    parts = []

    if prices.xau_usd > 0:
        xau_arrow = "🟢" if prices.xau_change_pct >= 0 else "🔴"
        parts.append(f"🥇 XAU/USD: ${prices.xau_usd:,.2f} ({xau_arrow}{prices.xau_change_pct:+.2f}%)")

    if prices.dxy > 0:
        dxy_arrow = "🟢" if prices.dxy_change_pct >= 0 else "🔴"
        parts.append(f"💵 DXY: {prices.dxy:.2f} ({dxy_arrow}{prices.dxy_change_pct:+.2f}%)")

    return " | ".join(parts)


# ============================================================
# Prediction Change Tracking
# ============================================================

def load_predictions_history() -> Dict:
    """Load prediction history from JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(PREDICTIONS_HISTORY_FILE):
        return {}

    try:
        with open(PREDICTIONS_HISTORY_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {}


def save_predictions_history(history: Dict):
    """Save prediction history to JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PREDICTIONS_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)


def get_market_key(question: str) -> str:
    """Create a unique key for a market question."""
    return question[:80].strip().lower()


def check_significant_changes(predictions: list, threshold: float = 5.0) -> list:
    """
    Check if any prediction changed by more than threshold percentage.
    Returns list of significant changes.
    """
    history = load_predictions_history()
    significant_changes = []

    for pred in predictions:
        key = get_market_key(pred.question)

        if key not in history:
            # First time seeing this market, save it
            history[key] = {
                'question': pred.question,
                'question_th': pred.question_th,
                'outcomes': pred.outcomes,
                'last_updated': datetime.now().isoformat(),
            }
            continue

        # Compare outcomes
        old_data = history[key]
        old_outcomes = {o['name']: o['price'] for o in old_data.get('outcomes', [])}

        for outcome in pred.outcomes:
            name = outcome['name']
            new_price = outcome['price']
            old_price = old_outcomes.get(name, new_price)

            if old_price > 0:
                change_pct = ((new_price - old_price) / old_price) * 100
                if abs(change_pct) >= threshold:
                    significant_changes.append({
                        'question_th': pred.question_th,
                        'outcome': name,
                        'old_pct': old_price * 100,
                        'new_pct': new_price * 100,
                        'change_pct': change_pct,
                        'category': pred.category,
                    })

        # Update history
        history[key] = {
            'question': pred.question,
            'question_th': pred.question_th,
            'outcomes': pred.outcomes,
            'last_updated': datetime.now().isoformat(),
        }

    save_predictions_history(history)
    return significant_changes


def format_emergency_alert(changes: list, prices: PriceData) -> str:
    """Format emergency alert message for significant changes."""
    message = "🚨 <b>EMERGENCY ALERT!</b> 🚨\n"
    message += "═" * 30 + "\n\n"
    message += "<b>การเปลี่ยนแปลงสำคัญในตลาดคาดการณ์!</b>\n\n"

    for change in changes[:5]:  # Max 5 changes
        direction = "📈" if change['change_pct'] > 0 else "📉"
        message += f"{direction} <b>{change['question_th']}</b>\n"
        message += f"   {change['outcome']}: {change['old_pct']:.0f}% → {change['new_pct']:.0f}%"
        message += f" ({change['change_pct']:+.1f}%)\n\n"

    # Add current prices
    price_line = format_price_line(prices)
    if price_line:
        message += f"\n{price_line}\n"

    message += "\n⚠️ <i>ตลาดขยับแรง! ตรวจสอบตำแหน่งของคุณ</i>"
    return message
