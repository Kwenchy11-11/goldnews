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
import alert_monitor
import gold_sentiment
import price_monitor

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
        'label_th': '🏦 Fed & Interest Rates',
        'emoji': '🏦',
        'explanation': (
            'คณะกรรมการนโยบายการเงินของสหรัฐฯ (Fed) จะตัดสินใจเรื่องดอกเบี้ย\n'
            '• ขึ้นดอกเบี้ย → ดอลลาร์แข็ง → ทองมักลง\n'
            '• ลดดอกเบี้ย → ดอลลาร์อ่อน → ทองมักขึ้น\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
    'inflation': {
        'label_th': '💰 Inflation (CPI/PPI)',
        'emoji': '💰',
        'explanation': (
            'เงินเฟ้อคือภาวะที่สินค้าแพงขึ้นเรื่อยๆ\n'
            '• เงินเฟ้อสูง → ทองมักขึ้น (เพราะทองป้องกันเงินเฟ้อ)\n'
            '• เงินเฟ้อต่ำ → ทองอาจลง\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
    'gold': {
        'label_th': '🥇 Gold Price Targets',
        'emoji': '🥇',
        'explanation': (
            'ตลาดคาดการณ์ราคาทองคำว่าจะไปถึงระดับไหน\n'
            '• % สูง = ตลาดมองว่ามีโอกาสสูงที่จะไปถึงราคานั่น\n'
            '• % ต่ำ = ตลาดมองว่าโอกาสน้อย\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
    'risk_factors': {
        'label_th': '🔥 Risk Factors (War/Oil)',
        'emoji': '🔥',
        'explanation': (
            'ปัจจัยเสี่ยงที่กระทบทองคำแรงมาก\n'
            '• สงครามตะวันออกกลาง → ทองขึ้น (safe haven)\n'
            '• น้ำมันแพง → เงินเฟ้อ → ทองขึ้น\n'
            '• นิวเคลียร์ → ทองพุ่ง (risk-off extreme)\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
}


def _categorize_market(question: str, description: str = '') -> str:
    """Categorize a market into clear trading-relevant categories."""
    combined = (question + ' ' + description).lower()

    # Fed & Interest Rates (primary driver)
    if any(kw in combined for kw in ['fed rate', 'federal reserve', 'interest rate', 'fed fund',
                                       'fed raise', 'fed cut', 'fed hold', 'the fed ', 'fomc']):
        return 'fed'

    # Gold Price Targets (direct trading)
    if any(kw in combined for kw in ['gold price', 'gold above', 'gold below', 'gold at',
                                       'gold hit', 'gold reach', 'xauusd', 'gold end',
                                       'gold close', 'gold finish', 'gold $', 'xau']):
        return 'gold'

    # Inflation Data (CPI/PPI)
    if any(kw in combined for kw in ['inflation', 'cpi', 'consumer price', 'ppi']):
        return 'inflation'

    # Risk Factors: Oil, War, Middle East (geopolitical risk → gold safe haven)
    if any(kw in combined for kw in ['oil', 'brent', 'wti', 'น้ำมัน',
                                       'iran', 'israel', 'gaza', 'lebanon', 'hezbollah',
                                       'ceasefire', 'หยุดยิง', 'war', 'nuclear', 'nuke']):
        return 'risk_factors'

    return 'economy'


def _translate_question(question: str, category: str) -> str:
    """Provide a Thai translation/explanation for the market question."""
    q_lower = question.lower()

    # Extract numbers and years for context
    import re
    numbers = re.findall(r'\d+', question)
    year_match = re.search(r'\b(20\d{2})\b', question)
    year_str = f" ปี {year_match.group(1)}" if year_match else ""

    # Fed rate decisions
    if 'fed rate' in q_lower or 'federal reserve' in q_lower or 'the fed ' in q_lower or 'fomc' in q_lower:
        # Number of rate cuts
        cuts_match = re.search(r'(\d+\s*(?:or\s*more\s*)?)\s*fed\s*rate\s*cuts?', q_lower)
        no_cuts_match = re.search(r'no\s+fed\s*rate\s*cuts?', q_lower)

        if no_cuts_match:
            return f'เฟดจะไม่ลดดอกเบี้ยเลย{year_str}?'
        if cuts_match:
            num = cuts_match.group(1).strip()
            # Clean up "or more" to Thai
            num = num.replace('or more', 'ขึ้นไป').replace('  ', ' ')
            return f'เฟดจะลดดอกเบี้ย {num} ครั้ง{year_str}?'

        if 'raise' in q_lower or 'increase' in q_lower or 'hike' in q_lower:
            return f'เฟดจะขึ้นดอกเบี้ย{year_str}?'
        if 'cut' in q_lower or 'decrease' in q_lower or 'reduce' in q_lower:
            return f'เฟดจะลดดอกเบี้ย{year_str}?'
        if 'hold' in q_lower or 'keep' in q_lower or 'unchanged' in q_lower:
            return f'เฟดจะคงดอกเบี้ย{year_str}?'
        return f'การตัดสินใจดอกเบี้ยของเฟด{year_str}'

    # Gold price targets
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

    # Inflation
    if 'inflation' in q_lower or 'cpi' in q_lower:
        return 'คาดการณ์เงินเฟ้อ (CPI)'

    # Employment
    if 'job' in q_lower or 'employment' in q_lower or 'unemployment' in q_lower:
        return 'คาดการณ์การจ้างงาน'

    # GDP
    if 'gdp' in q_lower:
        return 'คาดการณ์ GDP (ผลิตภัณฑ์มวลรวม)'

    # Recession
    if 'recession' in q_lower:
        return f'เศรษฐกิจสหรัฐฯ จะเข้าสู่ภาวะถดถอย{year_str}?'

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
    # STRICT keywords — only Gold/Fed/CPI/Oil/Middle East that impact gold prices
    # Note: Using word boundaries to avoid false positives (e.g., 'gold' in 'Goldman')
    relevant_keywords = [
        # Gold (primary focus) - avoid matching 'Goldman'
        'gold price', 'gold above', 'gold below', 'gold $', 'gold at', 'gold hit',
        'gold reach', 'xau', 'xauusd', 'ทองคำ', 'ทอง',
        # Fed / Interest rates (direct impact on gold)
        'fed', 'fomc', 'federal reserve', 'interest rate', 'rate decision',
        'rate cut', 'rate hike', 'rate hold',
        # Inflation (CPI/PPI impact on gold)
        'cpi', 'inflation', 'consumer price', 'ppi',
        # Oil (inflation/war hedge, impacts gold)
        'oil', 'brent', 'wti', 'crude', 'น้ำมัน',
        # Middle East conflicts (geopolitical risk → gold)
        'iran', 'israel', 'middle east', 'gaza', 'lebanon', 'hezbollah',
        'ceasefire', 'หยุดยิง', 'สงคราม',
        # War-related (but avoid 'war' in names like 'Warren')
        ' war ', 'war in', 'war by', 'war on', 'war?', 'war.', 'war,',
        # Nuclear threats (immediate gold impact)
        'nuclear', 'nuke', 'นิวเคลียร์',
    ]

    # STRICT exclusion — remove political noise that doesn't impact gold
    exclude_keywords = [
        # Sports
        'nhl', 'nba', 'nfl', 'mlb', 'soccer', 'football', 'hockey',
        'basketball', 'baseball', 'stanley cup', 'super bowl',
        'olympics', 'world cup', 'championship',
        # Crypto
        'crypto', 'bitcoin', 'ethereum', 'btc', 'eth',
        # Tech companies
        'openai', 'chatgpt', 'ai company', 'tech company', 'tesla',
        # US Politics (unless economic policy)
        'trump', 'biden', 'election', 'vote', 'polling',
        # UK/EU Politics
        'uk election', 'british', 'germany election', 'france election',
        # Generic Russia/Ukraine (keep only if nuclear-related - checked separately)
        'putin', 'zelenskyy', 'president russia', 'president ukraine',
        'ukraine election', 'russia election', 'netanyahu',
    ]

    markets_data = []

    # Strategy 1: Fetch from economics tag (tag_id=107)
    try:
        response = requests.get(
            'https://gamma-api.polymarket.com/markets',
            params={
                'active': 'true',
                'closed': 'false',
                'limit': '500',
                'tag_id': '107',  # Business/Economics tag
            },
            timeout=15,
            headers={'Accept': 'application/json'}
        )
        response.raise_for_status()
        data = response.json()
        market_list = data if isinstance(data, list) else data.get('markets', data)
        markets_data.extend(market_list)
        logger.info(f"Fetched {len(market_list)} markets from economics tag")
    except Exception as e:
        logger.warning(f"Failed to fetch economics tag markets: {e}")

    # Strategy 2: Search with specific queries
    search_queries = ['fed', 'interest rate', 'cpi', 'inflation', 'gold price', 'recession']
    for query in search_queries:
        try:
            response = requests.get(
                'https://gamma-api.polymarket.com/markets',
                params={
                    'active': 'true',
                    'closed': 'false',
                    'limit': '50',
                    'q': query,
                },
                timeout=15,
                headers={'Accept': 'application/json'}
            )
            response.raise_for_status()
            data = response.json()
            market_list = data if isinstance(data, list) else data.get('markets', data)
            markets_data.extend(market_list)
            logger.info(f"Search '{query}': {len(market_list)} results")
        except Exception as e:
            logger.warning(f"Failed to search '{query}': {e}")

    # Strategy 3: Events API with economics tag
    try:
        response = requests.get(
            'https://gamma-api.polymarket.com/events',
            params={
                'active': 'true',
                'closed': 'false',
                'limit': '50',
                'tag_id': '107',
            },
            timeout=15,
            headers={'Accept': 'application/json'}
        )
        response.raise_for_status()
        events_data = response.json()
        if isinstance(events_data, list):
            for event in events_data:
                for market in event.get('markets', []):
                    markets_data.append(market)
            logger.info(f"Fetched markets from {len(events_data)} events")
    except Exception as e:
        logger.warning(f"Failed to fetch events: {e}")

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

            # STRICT: Filter by year - only 2024-2025 markets (not 2026)
            import re
            year_match = re.search(r'\b(20\d{2})\b', question)
            if year_match:
                year = int(year_match.group(1))
                if year > 2025:
                    # Skip markets ending in 2026+ unless nuclear-related
                    if 'nuclear' not in combined and 'nuke' not in combined:
                        continue

            # STRICT: Russia/Ukraine only if nuclear-related
            if any(kw in combined for kw in ['putin', 'zelenskyy', 'ukraine', 'russia']):
                if 'nuclear' not in combined and 'nuke' not in combined:
                    continue  # Skip non-nuclear Russia/Ukraine news

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

def get_reply_keyboard():
    """Get the reply keyboard markup for quick commands."""
    return {
        'keyboard': [
            [{'text': '🎯 Predictions'}, {'text': '🔔 Alerts'}],
            [{'text': '❓ Help'}],
        ],
        'resize_keyboard': True,
        'one_time_keyboard': False,
    }


def send_message(text: str, chat_id: Optional[int] = None, reply_markup: Optional[dict] = None) -> bool:
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

    if reply_markup:
        payload['reply_markup'] = reply_markup

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


def format_predictions_message(predictions: List[PredictionMarket], include_prices: bool = True) -> str:
    """Format predictions into a Thai message with optional price data."""
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

    # Get current prices
    price_line = ""
    if include_prices:
        prices = price_monitor.get_current_prices()
        price_line = price_monitor.format_price_line(prices)

    # Calculate Gold Sentiment Score
    market_dicts = [
        {
            'question': p.question,
            'outcomes': p.outcomes,
            'category': p.category,
        }
        for p in predictions
    ]
    sentiment = gold_sentiment.calculate_gold_sentiment(market_dicts)
    sentiment_msg = gold_sentiment.format_sentiment_message(sentiment)

    message = "🎯 <b>ตลาดคาดการณ์อะไรอยู่? (Polymarket)</b>\n"

    if price_line:
        message += f"{price_line}\n"

    # Add Gold Sentiment Score
    message += f"\n{sentiment_msg}\n"

    message += (
        f"\n{'─' * 30}\n"
        "<i>ตัวเลข % = ความน่าจะเป็นที่ตลาดคาดการณ์</i>\n"
        "<i>🟢 = มีโอกาสสูง | 🟡 = เป็นไปได้ | 🔴 = โอกาสน้อย</i>\n\n"
    )

    by_category = get_predictions_by_category(predictions)
    # Show only categories that impact gold trading
    # Ordered by importance for traders
    display_categories = ['fed', 'gold', 'inflation', 'risk_factors']

    for category in display_categories:
        if category not in by_category:
            continue

        cat_markets = by_category[category][:3]
        cat_info = CATEGORY_INFO.get(category, {})
        cat_emoji = cat_info.get('emoji', '📌')
        cat_label = cat_info.get('label_th', category.capitalize())

        message += f"{cat_emoji} <b>{cat_label}</b>\n"

        for market in cat_markets:
            outcomes_str = _format_outcomes_detailed(market)
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


def _format_outcomes_detailed(market: PredictionMarket) -> str:
    """
    Format outcomes with FULL context showing what the question is asking.
    
    Instead of just showing "Yes: 49%", show:
    "Will NOT cut rates: 🟡 49% | Will cut: 🟡 51%"
    
    This fixes the "Data ขยะ" issue where users couldn't understand
    what "คาดการณ์ GDP ใช่ 6%" actually meant.
    """
    lines = []
    question = market.question.lower()
    category = market.category
    
    # Extract the condition from the question for context
    condition = _extract_condition_from_question(question)
    
    for outcome in market.outcomes[:2]:  # Show top 2 outcomes
        name = outcome.get('name', '')
        price = outcome.get('price', 0)
        pct = price * 100
        
        name_lower = name.lower()
        
        # Determine what this outcome means in context
        if name_lower in ('yes', 'true', 'yes '):
            # For "Yes", extract what condition means yes
            label = condition if condition else 'ใช่'
        elif name_lower in ('no', 'false', 'no '):
            # For "No", show the opposite
            label = _get_opposite_condition(condition) if condition else 'ไม่ใช่'
        else:
            # For named outcomes (Raise/Cut/Above/Below), translate directly
            label = _translate_outcome_name(name, category)
        
        # Add indicator based on probability
        if pct >= 60:
            indicator = '🟢'
        elif pct >= 40:
            indicator = '🟡'
        else:
            indicator = '🔴'
        
        lines.append(f"  {indicator} {label}: {pct:.0f}%")
    
    return '\n'.join(lines)


def _extract_condition_from_question(question: str) -> str:
    """
    Extract what the question is asking from the market question.
    
    Examples:
    - "GDP QoQ > 2.5%?" → "> 2.5%"
    - "No Fed rate cuts in 2026?" → "ไม่ลดดอกเบี้ย"
    - "Will gold hit $3200?" → "ทะลุ $3200"
    """
    import re
    q_lower = question.lower()
    
    # GDP conditions
    gdp_match = re.search(r'gdp.*?(above|>|greater than)\s*([\d.]+)%?', q_lower)
    if gdp_match:
        threshold = gdp_match.group(2)
        return f"โต > {threshold}%"
    
    gdp_negative = re.search(r'gdp.*?(negative|negative growth|recession)', q_lower)
    if gdp_negative:
        return "ติดลบ"
    
    # Fed rate decisions
    no_cuts = re.search(r'no\s+fed\s*rate\s*cuts?', q_lower)
    if no_cuts:
        return "ไม่ลดดอกเบี้ย"
    
    cuts_match = re.search(r'(\d+)\s+fed\s*rate\s*cuts?', q_lower)
    if cuts_match:
        num = cuts_match.group(1)
        return f"ลด {num} ครั้ง"
    
    rate_decision = re.search(r'fed\s*(raise|hike|increase).*?rate', q_lower)
    if rate_decision:
        return "ขึ้นดอกเบี้ย"
    
    rate_cut = re.search(r'fed\s*(cut|decrease|reduce).*?rate', q_lower)
    if rate_cut:
        return "ลดดอกเบี้ย"
    
    # Gold price targets
    gold_above = re.search(r'gold.*?((?:above|above \$|hit \$|reach \$)\s*[\d,]+)', q_lower)
    if gold_above:
        price = gold_above.group(1).replace('above', '').replace('$', '').strip()
        return f"ทะลุ ${price}"
    
    gold_below = re.search(r'gold.*?((?:below|below \$|under \$)\s*[\d,]+)', q_lower)
    if gold_below:
        price = gold_below.group(1).replace('below', '').replace('$', '').strip()
        return f"ต่ำกว่า ${price}"
    
    # Recession
    recession = re.search(r'(recession|ถดถอย)', q_lower)
    if recession:
        return "ถดถอย"
    
    # Default - return empty if can't extract
    return ""


def _get_opposite_condition(condition: str) -> str:
    """Get the opposite condition for 'No' outcomes."""
    if not condition:
        return "ไม่ใช่"
    
    opposites = {
        'โต > ': 'โต ≤ ',
        'ติดลบ': 'ไม่ติดลบ',
        'ไม่ลดดอกเบี้ย': 'ลดดอกเบี้ย',
        'ขึ้นดอกเบี้ย': 'ไม่ขึ้นดอกเบี้ย',
        'ลดดอกเบี้ย': 'ไม่ลดดอกเบี้ย',
        'ทะลุ ': 'ไม่ทะลุ ',
        'ต่ำกว่า ': 'สูงกว่า ',
        'ถดถอย': 'ไม่ถดถอย',
    }
    
    for key, opposite in opposites.items():
        if key in condition:
            return condition.replace(key, opposite)
    
    return f"ไม่{condition}"


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
        "🔔 <b>/alerts</b> — ดูสถานะ auto alert\n"
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
        "กดปุ่มด้านล่างเพื่อใช้งานได้เลยครับ"
    )
    return send_message(message, chat_id=chat_id, reply_markup=get_reply_keyboard())


def handle_alerts_command(chat_id: int) -> bool:
    """Handle /alerts command - show alert status."""
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


def process_update(update: dict) -> bool:
    """Process a single Telegram update."""
    global _last_update_id

    update_id = update.get('update_id')
    message = update.get('message', {})
    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '').strip()

    # Skip if we've already processed this update
    if _last_update_id is not None and update_id <= _last_update_id:
        return False

    _last_update_id = update_id

    # Route commands (both /commands and button text)
    text_lower = text.lower()

    if text_lower in ('/predictions', '/prediction', '🎯 predictions', 'predictions'):
        return handle_predictions_command(chat_id)
    elif text_lower in ('/alerts', '🔔 alerts', 'alerts'):
        return handle_alerts_command(chat_id)
    elif text_lower in ('/help', '❓ help', 'help'):
        return handle_help_command(chat_id)
    elif text_lower in ('/start', 'start'):
        return handle_start_command(chat_id)

    return False


def auto_push_predictions():
    """Auto-push predictions every hour and check for significant changes."""
    import threading

    def _run():
        while True:
            try:
                # Wait 1 hour (3600 seconds)
                time.sleep(3600)

                logger.info("Auto-push: Fetching predictions...")
                predictions = fetch_polymarket_predictions()

                if not predictions:
                    logger.info("Auto-push: No predictions to send")
                    continue

                # Check for significant changes (>5%)
                changes = price_monitor.check_significant_changes(predictions, threshold=5.0)

                if changes:
                    # Send emergency alert
                    prices = price_monitor.get_current_prices()
                    alert_msg = price_monitor.format_emergency_alert(changes, prices)
                    send_message(alert_msg)
                    logger.info(f"Emergency alert sent: {len(changes)} significant changes")

                # Send regular predictions update
                message = format_predictions_message(predictions)
                send_message(message)
                logger.info("Auto-push: Predictions sent")

            except Exception as e:
                logger.error(f"Auto-push error: {e}", exc_info=True)

    thread = threading.Thread(target=_run, daemon=True, name="AutoPush")
    thread.start()
    logger.info("Auto-push scheduler started (every 1 hour)")


def start_bot():
    """Start the predictions bot."""
    global _last_update_id

    if not PREDICTIONS_BOT_TOKEN:
        logger.error("PREDICTIONS_BOT_TOKEN not set. Please set it in .env file.")
        return

    logger.info("=" * 50)
    logger.info(" Gold Predictions Bot")
    logger.info("=" * 50)
    logger.info("Commands: /predictions, /alerts, /help, /start")
    logger.info("Features: Auto-push every 1 hour, Emergency alerts on 5%+ changes")

    # Get initial offset (skip old messages)
    updates = get_updates(timeout=1)
    if updates:
        _last_update_id = updates[-1].get('update_id')
        logger.info(f"Skipping {_last_update_id} old updates")

    # Start alert monitor if enabled
    alert_monitor.start_monitor()

    # Start auto-push scheduler
    auto_push_predictions()

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
            alert_monitor.stop_monitor()
            break
        except Exception as e:
            logger.error(f"Error in bot loop: {e}", exc_info=True)
            time.sleep(10)


if __name__ == "__main__":
    start_bot()
