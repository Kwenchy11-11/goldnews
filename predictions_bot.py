#!/usr/bin/env python3
"""
Gold Predictions Bot
====================
Standalone Telegram bot for Polymarket predictions only.
User types /predictions to get market data with Thai explanations.

This bot is separate from the Gold News auto-alert bot.
It uses its own bot token (PREDICTIONS_BOT_TOKEN).

Usage:
    python predictions_bot.py
"""

import logging
import time
import json
import re
from typing import List, Dict, Optional
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

import config

# Load env vars
load_dotenv()

# Predictions bot uses its own token
PREDICTIONS_BOT_TOKEN = config.PREDICTIONS_BOT_TOKEN
TELEGRAM_CHAT_ID = config.TELEGRAM_CHAT_ID

logger = logging.getLogger('goldnews')

# Track last update_id to avoid processing old messages
_last_update_id: Optional[int] = None


# ============================================================
# Polymarket Predictions (copied from polymarket_predictions.py)
# ============================================================

@dataclass
class PredictionMarket:
    """A single prediction market from Polymarket."""
    question: str
    question_th: str
    outcomes: List[Dict]
    volume: float
    url: str
    category: str
    explanation_th: str


CATEGORY_INFO = {
    'fed': {
        'label_th': 'ดอกเบี้ยเฟด',
        'emoji': '🏦',
        'explanation': (
            'คณะกรรมการนโยบายการเงินของสหรัฐฯ (Fed) จะตัดสินใจเรื่องดอกเบี้ย\n'
            '• ขึ้นดอกเบี้ย → ดอลลาร์แข็ง → ทองมักลง\n'
            '• ลดดอกเบี้ย → ดอลลาร์อ่อน → ทองมักขึ้น\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
    'inflation': {
        'label_th': 'เงินเฟ้อ',
        'emoji': '💰',
        'explanation': (
            'เงินเฟ้อคือภาวะที่สินค้าแพงขึ้นเรื่อยๆ\n'
            '• เงินเฟ้อสูง → ทองมักขึ้น (เพราะทองป้องกันเงินเฟ้อ)\n'
            '• เงินเฟ้อต่ำ → ทองอาจลง\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
    'gold': {
        'label_th': 'ราคาทอง',
        'emoji': '🥇',
        'explanation': (
            'ตลาดคาดการณ์ราคาทองคำว่าจะไปถึงระดับไหน\n'
            '• % สูง = ตลาดมองว่ามีโอกาสสูงที่จะไปถึงราคานั่น\n'
            '• % ต่ำ = ตลาดมองว่าโอกาสน้อย\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
    'employment': {
        'label_th': 'การจ้างงาน',
        'emoji': '👷',
        'explanation': (
            'ข้อมูลการจ้างงานในสหรัฐฯ เช่น ตัวเลขคนตกงาน\n'
            '• จ้างงานดี → เศรษฐกิจแข็ง → Fed อาจขึ้นดอกเบี้ย → ทองอาจลง\n'
            '• จ้างงานแย่ → เศรษฐกิจอ่อน → Fed อาจลดดอกเบี้ย → ทองอาจขึ้น\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
    'economy': {
        'label_th': 'เศรษฐกิจ',
        'emoji': '📊',
        'explanation': (
            'ข้อมูลเศรษฐกิจอื่นๆ เช่น GDP, การเติบโตของเศรษฐกิจ\n'
            '• เศรษฐกิจดี → ดอลลาร์แข็ง → ทองอาจลง\n'
            '• เศรษฐกิจแย่ → ดอลลาร์อ่อน → ทองมักขึ้น\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
}


def _categorize_market(question: str, description: str = '') -> str:
    """Categorize a market into fed/inflation/gold/employment/economy."""
    combined = (question + ' ' + description).lower()

    if any(kw in combined for kw in ['fed rate', 'federal reserve', 'interest rate', 'fed fund',
                                       'fed raise', 'fed cut', 'fed hold', 'the fed ']):
        return 'fed'
    if any(kw in combined for kw in ['inflation', 'cpi', 'consumer price']):
        return 'inflation'
    if any(kw in combined for kw in ['gold price', 'gold above', 'gold below', 'gold at',
                                       'gold hit', 'gold reach', 'xauusd', 'gold end',
                                       'gold close', 'gold finish']):
        return 'gold'
    if any(kw in combined for kw in ['job', 'employment', 'unemployment', 'nonfarm',
                                       'payroll', 'labor']):
        return 'employment'
    return 'economy'


def _translate_question(question: str, category: str) -> str:
    """Provide a Thai translation/explanation for the market question."""
    q_lower = question.lower()

    if 'fed rate' in q_lower or 'federal reserve' in q_lower or 'the fed ' in q_lower:
        if 'raise' in q_lower or 'increase' in q_lower or 'hike' in q_lower:
            return 'เฟดจะขึ้นดอกเบี้ยหรือไม่?'
        if 'cut' in q_lower or 'decrease' in q_lower or 'reduce' in q_lower:
            return 'เฟดจะลดดอกเบี้ยหรือไม่?'
        if 'hold' in q_lower or 'keep' in q_lower or 'unchanged' in q_lower:
            return 'เฟดจะคงดอกเบี้ยหรือไม่?'
        return 'การตัดสินใจดอกเบี้ยของเฟด'

    if 'gold' in q_lower:
        if 'above' in q_lower:
            match = re.search(r'\$?([\d,]+)', question)
            price = match.group(1) if match else '?'
            return f'ราคาทองจะเกิน ${price} หรือไม่?'
        if 'below' in q_lower:
            match = re.search(r'\$?([\d,]+)', question)
            price = match.group(1) if match else '?'
            return f'ราคาทองจะต่ำกว่า ${price} หรือไม่?'
        return 'คาดการณ์ราคาทองคำ'

    if 'inflation' in q_lower or 'cpi' in q_lower:
        return 'คาดการณ์เงินเฟ้อ (CPI)'

    if 'job' in q_lower or 'employment' in q_lower or 'unemployment' in q_lower:
        return 'คาดการณ์การจ้างงาน'

    if 'gdp' in q_lower:
        return 'คาดการณ์ GDP (ผลิตภัณฑ์มวลรวม)'

    return question


def _translate_outcome_name(name: str, category: str) -> str:
    """Translate outcome names to Thai."""
    name_lower = name.lower()

    if name_lower in ('yes', 'yeah', 'true'):
        return 'ใช่'
    if name_lower in ('no', 'nope', 'false'):
        return 'ไม่ใช่'

    if 'raise' in name_lower or 'increase' in name_lower or 'hike' in name_lower:
        return 'ขึ้นดอกเบี้ย'
    if 'cut' in name_lower or 'decrease' in name_lower or 'reduce' in name_lower:
        return 'ลดดอกเบี้ย'
    if 'hold' in name_lower or 'keep' in name_lower or 'unchanged' in name_lower:
        return 'คงดอกเบี้ย'

    if 'above' in name_lower or 'higher' in name_lower or 'up' in name_lower:
        return 'สูงกว่า'
    if 'below' in name_lower or 'lower' in name_lower or 'down' in name_lower:
        return 'ต่ำกว่า'

    return name


def fetch_polymarket_predictions() -> List[PredictionMarket]:
    """Fetch prediction markets from Polymarket Gamma API."""
    relevant_keywords = [
        'gold price', 'gold above', 'gold below', 'gold at', 'gold hit',
        'gold reach', 'gold end', 'gold close', 'gold finish', 'xauusd',
        'fed rate', 'federal reserve', 'interest rate', 'fed fund',
        'the fed ', 'fed raise', 'fed cut', 'fed hold',
        'inflation', 'cpi', 'consumer price',
        'nonfarm', 'unemployment', 'jobless', 'payroll',
        'gdp', 'recession', 'economic growth',
    ]

    exclude_keywords = [
        'nhl', 'nba', 'nfl', 'mlb', 'soccer', 'football', 'hockey',
        'basketball', 'baseball', 'stanley cup', 'super bowl',
        'olympics', 'world cup', 'championship', 'election',
        'president', 'senate', 'congress', 'governor', 'trump',
        'biden', 'crypto', 'bitcoin', 'ethereum',
    ]

    markets_data = []

    # Try markets API
    try:
        response = requests.get(
            'https://gamma-api.polymarket.com/markets',
            params={'active': 'true', 'closed': 'false', 'limit': '200'},
            timeout=15,
            headers={'Accept': 'application/json'}
        )
        response.raise_for_status()
        data = response.json()
        market_list = data.get('markets', data) if isinstance(data, dict) else data
        markets_data.extend(market_list)
    except Exception as e:
        logger.warning(f"Failed to fetch Polymarket markets: {e}")

    # Try events API with economics tag
    try:
        response = requests.get(
            'https://gamma-api.polymarket.com/events',
            params={'active': 'true', 'closed': 'false', 'limit': '50', 'tag': 'economics'},
            timeout=15,
            headers={'Accept': 'application/json'}
        )
        response.raise_for_status()
        events_data = response.json()
        if isinstance(events_data, list):
            for event in events_data:
                for market in event.get('markets', []):
                    markets_data.append(market)
    except Exception as e:
        logger.warning(f"Failed to fetch Polymarket events: {e}")

    if not markets_data:
        logger.info("No Polymarket data available from any source")
        return []

    markets = []
    seen_questions = set()

    for market in markets_data:
        try:
            question = market.get('question', '')
            if not question or question in seen_questions:
                continue
            seen_questions.add(question)

            description = market.get('description', '') or ''
            question_lower = question.lower()
            desc_lower = description.lower()
            combined = question_lower + ' ' + desc_lower

            if any(kw in combined for kw in exclude_keywords):
                continue

            if not any(kw in combined for kw in relevant_keywords):
                continue

            category = _categorize_market(question, description)

            outcomes = []
            try:
                outcomes_names = market.get('outcomes', [])
                if isinstance(outcomes_names, str):
                    outcomes_names = json.loads(outcomes_names)

                outcome_prices_raw = market.get('outcomePrices', market.get('outcome_prices', []))
                if isinstance(outcome_prices_raw, str):
                    outcome_prices_raw = json.loads(outcome_prices_raw)

                for i, name in enumerate(outcomes_names):
                    price = float(outcome_prices_raw[i]) if i < len(outcome_prices_raw) else 0
                    outcomes.append({
                        'name': name,
                        'price': price,
                    })
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(f"Error parsing outcomes for '{question}': {e}")
                continue

            if not outcomes:
                continue

            volume = float(market.get('volume', market.get('volumeNum', 0)))
            slug = market.get('slug', '')
            url = f"https://polymarket.com/event/{slug}" if slug else ''
            question_th = _translate_question(question, category)
            cat_info = CATEGORY_INFO.get(category, {})
            explanation_th = cat_info.get('explanation', '')

            markets.append(PredictionMarket(
                question=question,
                question_th=question_th,
                outcomes=outcomes,
                volume=volume,
                url=url,
                category=category,
                explanation_th=explanation_th,
            ))

        except Exception as e:
            logger.warning(f"Error parsing Polymarket prediction: {e}")
            continue

    markets.sort(key=lambda m: m.volume, reverse=True)
    logger.info(f"Fetched {len(markets)} Polymarket prediction markets")
    return markets


def get_predictions_by_category(markets: List[PredictionMarket]) -> Dict[str, List[PredictionMarket]]:
    """Group prediction markets by category."""
    result = {}
    for market in markets:
        if market.category not in result:
            result[market.category] = []
        result[market.category].append(market)
    return result


# ============================================================
# Telegram Bot Functions
# ============================================================

def send_message(text: str, chat_id: Optional[int] = None) -> bool:
    """Send a message to Telegram."""
    if chat_id is None:
        chat_id = TELEGRAM_CHAT_ID

    url = f"https://api.telegram.org/bot{PREDICTIONS_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML',
        'disable_web_page_preview': True,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


def get_updates(offset: Optional[int] = None, timeout: int = 30) -> list:
    """Get updates from Telegram Bot API."""
    url = f"https://api.telegram.org/bot{PREDICTIONS_BOT_TOKEN}/getUpdates"
    params = {
        'timeout': timeout,
        'allowed_updates': ['message'],
    }
    if offset is not None:
        params['offset'] = offset

    try:
        response = requests.get(url, params=params, timeout=timeout + 5)
        response.raise_for_status()
        data = response.json()
        return data.get('result', [])
    except Exception as e:
        logger.error(f"Failed to get Telegram updates: {e}")
        return []


def format_predictions_message(predictions: List[PredictionMarket]) -> str:
    """Format predictions into a Thai message."""
    if not predictions:
        return (
            "🎯 <b>ตลาดคาดการณ์ (Polymarket)</b>\n\n"
            "ขณะนี้ยังไม่มีตลาดคาดการณ์ที่เกี่ยวข้องกับทองคำ/Fed/เศรษฐกิจ ที่ active อยู่\n\n"
            "ตลาด Polymarket จะเปิด-ปิดตามเหตุการณ์จริง บอทจะแสดงข้อมูลอัตโนมัติเมื่อมีตลาดใหม่ครับ\n\n"
            "💡 <b>Polymarket คืออะไร?</b>\n"
            "เป็นตลาดที่คนทั่วโลกมา \"เดิมพัน\" ว่าเหตุการณ์ต่างๆ จะเกิดขึ้นหรือไม่\n"
            "• % สูง = ตลาดมองว่ามีโอกาสเกิดสูง\n"
            "• ใช้เป็นข้อมูลประกอบการตัดสินใจเทรดทองคำได้"
        )

    message = (
        "🎯 <b>ตลาดคาดการณ์อะไรอยู่? (Polymarket)</b>\n"
        f"{'─' * 30}\n"
        "<i>ตัวเลข % = ความน่าจะเป็นที่ตลาดคาดการณ์</i>\n"
        "<i>🟢 = มีโอกาสสูง | 🟡 = เป็นไปได้ | 🔴 = โอกาสน้อย</i>\n\n"
    )

    by_category = get_predictions_by_category(predictions)
    category_order = ['fed', 'gold', 'inflation', 'employment', 'economy']

    for category in category_order:
        if category not in by_category:
            continue

        cat_markets = by_category[category][:3]
        cat_info = CATEGORY_INFO.get(category, {})
        cat_emoji = cat_info.get('emoji', '📌')
        cat_label = cat_info.get('label_th', category.capitalize())

        message += f"{cat_emoji} <b>{cat_label}</b>\n"

        for market in cat_markets:
            outcomes_str = _format_outcomes(market.outcomes, market.category)
            message += f"• {market.question_th}\n"
            message += f"{outcomes_str}\n"

        message += "\n"

    message += (
        f"💡 <b>อ่านยังไง?</b>\n"
        f"Polymarket คือตลาดที่คนทั่วโลกมา \"เดิมพัน\" ว่าเหตุการณ์ต่างๆ จะเกิดขึ้นหรือไม่\n"
        f"• ถ้า % สูง = ตลาดมองว่ามีโอกาสเกิดสูง\n"
        f"• ทองคำมัก <b>ขึ้น</b> เมื่อ Fed ลดดอกเบี้ย หรือเศรษฐกิจแย่\n"
        f"• ทองคำมัก <b>ลง</b> เมื่อ Fed ขึ้นดอกเบี้ย หรือเศรษฐกิจดี\n\n"
        f"<i>ข้อมูลนี้เป็นการคาดการณ์ล่วงหน้า ไม่ใช่ข่าวที่เกิดขึ้นแล้ว</i>"
    )

    return message


def _format_outcomes(outcomes: list, category: str) -> str:
    """Format outcomes with Thai labels."""
    lines = []
    for outcome in outcomes[:3]:
        name = outcome.get('name', '')
        price = outcome.get('price', 0)
        pct = price * 100

        name_th = _translate_outcome_name(name, category)

        if pct >= 60:
            indicator = '🟢'
        elif pct >= 40:
            indicator = '🟡'
        else:
            indicator = ''

        lines.append(f"  {indicator} {name_th}: {pct:.0f}%")

    return '\n'.join(lines)


def handle_predictions_command(chat_id: int) -> bool:
    """Handle /predictions command."""
    logger.info(f"Handling /predictions command for chat {chat_id}")

    predictions = fetch_polymarket_predictions()
    message = format_predictions_message(predictions)

    return send_message(message, chat_id=chat_id)


def handle_help_command(chat_id: int) -> bool:
    """Handle /help command."""
    message = (
        "🤖 <b>Gold Predictions Bot - คำสั่งที่ใช้ได้</b>\n\n"
        "🎯 <b>/predictions</b> — ดูตลาดคาดการณ์ Polymarket\n"
        "❓ <b>/help</b> — แสดงคำสั่งทั้งหมด\n\n"
        "<i>บอทนี้แสดงเฉพาะข้อมูลคาดการณ์จาก Polymarket เท่านั้น</i>\n"
        "<i>สำหรับข่าวทองคำอัตโนมัติ ใช้ @GoldNews_mifibot</i>"
    )
    return send_message(message, chat_id=chat_id)


def handle_start_command(chat_id: int) -> bool:
    """Handle /start command."""
    message = (
        "👋 <b>ยินดีต้อนรับสู่ Gold Predictions Bot!</b>\n\n"
        "บอทนี้แสดงข้อมูลคาดการณ์จาก Polymarket ที่เกี่ยวข้องกับ:\n"
        "🏦 ดอกเบี้ยเฟด\n"
        "🥇 ราคาทองคำ\n"
        "💰 เงินเฟ้อ\n"
        "👷 การจ้างงาน\n"
        "📊 เศรษฐกิจ\n\n"
        "พิมพ์ <b>/predictions</b> เพื่อดูตลาดล่าสุด\n"
        "พิมพ์ <b>/help</b> เพื่อดูคำสั่งทั้งหมด"
    )
    return send_message(message, chat_id=chat_id)


def process_update(update: dict) -> bool:
    """Process a single Telegram update."""
    global _last_update_id

    update_id = update.get('update_id')
    message = update.get('message', {})
    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '').strip().lower()

    # Skip if we've already processed this update
    if _last_update_id is not None and update_id <= _last_update_id:
        return False

    _last_update_id = update_id

    if not text.startswith('/'):
        return False

    # Route commands
    if text == '/predictions' or text == '/prediction':
        return handle_predictions_command(chat_id)
    elif text == '/help':
        return handle_help_command(chat_id)
    elif text == '/start':
        return handle_start_command(chat_id)

    return False


def start_bot():
    """Start the predictions bot."""
    global _last_update_id

    if not PREDICTIONS_BOT_TOKEN:
        logger.error("PREDICTIONS_BOT_TOKEN not set. Please set it in .env file.")
        return

    logger.info("=" * 50)
    logger.info(" Gold Predictions Bot")
    logger.info("=" * 50)
    logger.info("Commands: /predictions, /help, /start")

    # Get initial offset (skip old messages)
    updates = get_updates(timeout=1)
    if updates:
        _last_update_id = updates[-1].get('update_id')
        logger.info(f"Skipping {_last_update_id} old updates")

    logger.info("Bot started. Waiting for commands...")

    while True:
        try:
            updates = get_updates(offset=_last_update_id, timeout=30)

            for update in updates:
                try:
                    process_update(update)
                except Exception as e:
                    logger.error(f"Error processing update: {e}", exc_info=True)

        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in bot loop: {e}", exc_info=True)
            time.sleep(10)


if __name__ == "__main__":
    start_bot()
