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
        'label_th': 'Fed & Interest Rates',
        'emoji': '🏦',
        'explanation': (
            'คณะกรรมการนโยบายการเงินของสหรัฐฯ (Fed) จะตัดสินใจเรื่องดอกเบี้ย\n'
            '• ขึ้นดอกเบี้ย → ดอลลาร์แข็ง → ทองมักลง\n'
            '• ลดดอกเบี้ย → ดอลลาร์อ่อน → ทองมักขึ้น\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
    'gold': {
        'label_th': 'Gold Price Targets',
        'emoji': '🥇',
        'explanation': (
            'ตลาดคาดการณ์ราคาทองคำว่าจะไปถึงระดับไหน\n'
            '• % สูง = ตลาดมองว่ามีโอกาสสูงที่จะไปถึงราคานั่น\n'
            '• % ต่ำ = ตลาดมองว่าโอกาสน้อย\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
    'geopolitics': {
        'label_th': 'Geopolitics (War/Risk)',
        'emoji': '🌍',
        'explanation': (
            'ปัจจัยเสี่ยงทางภูมิรัฐศาสตร์ที่กระทบทองคำแรงมาก\n'
            '• สงครามตะวันออกกลาง → ทองขึ้น (safe haven)\n'
            '• การหยุดยิง → ทองอาจลง (risk-on)\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
    'inflation': {
        'label_th': 'Inflation & Macro',
        'emoji': '💰',
        'explanation': (
            'ข้อมูลเงินเฟ้อและเศรษฐกิจมหภาค\n'
            '• เงินเฟ้อสูง → ทองมักขึ้น (เพราะทองป้องกันเงินเฟ้อ)\n'
            '• NFP/ว่างงาน → ส่งผลต่อนโยบาย Fed\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
    'energy': {
        'label_th': 'Energy (Oil)',
        'emoji': '🛢️',
        'explanation': (
            'ราคาน้ำมันส่งผลต่อเงินเฟ้อและทองคำ\n'
            '• น้ำมันแพง → เงินเฟ้อ → ทองขึ้น\n'
            '• OPEC ตัดสินใจ → กระทบอุปทานน้ำมัน\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
    'crypto': {
        'label_th': 'Crypto Macro',
        'emoji': '₿',
        'explanation': (
            'Bitcoin ETF flows ส่งผลต่อ sentiment ตลาดการเงิน\n'
            '• BTC ETF ไหลเข้า = risk-on = ทองอาจลง\n'
            '• BTC ETF ไหลออก = risk-off = ทองอาจขึ้น\n'
            'ตัวเลข % คือความน่าจะเป็นที่ตลาดคาดการณ์'
        ),
    },
}


# ============================================================
# Keyword Dictionary for Gold Trading Analysis
# ============================================================
# Partial match, case-insensitive, scans both Title and Description
# Priority order: Fed > Gold > Geopolitics > Inflation > Energy > Crypto

CATEGORY_KEYWORDS = {
    'fed': [
        'fed ', 'federal reserve', 'interest rate', 'rate cut', 'rate hike',
        'fomc', 'basis points', 'bps', 'rate decision', 'fed fund',
        'monetary policy', 'powell', 'fed decision', 'federal open market',
    ],
    'gold': [
        'gold', 'xau', 'ounce of gold', 'xauusd', 'gold price',
    ],
    'geopolitics': [
        'iran', 'israel', 'middle east', 'ceasefire', 'strike', 'hormuz',
        'gaza', 'lebanon', 'hezbollah', 'war ', 'war in', 'war by',
        'nuclear', 'nuke', 'geopolitical',
    ],
    'inflation': [
        'cpi', 'pce', 'inflation', 'nfp', 'unemployment', 'recession',
        'nonfarm', 'non-farm', 'consumer price', 'producer price',
        'jobless', 'payroll', 'jobs report',
    ],
    'energy': [
        'wti', 'crude oil', 'brent', 'opec', 'oil price', 'oil supply',
        'crude ', 'energy ',
    ],
    'crypto': [
        'bitcoin etf', 'btc etf', 'btc etf flows', 'bitcoin etf flows',
    ],
}

# Category priority order (first match wins if market matches multiple)
CATEGORY_PRIORITY = ['fed', 'gold', 'geopolitics', 'inflation', 'energy', 'crypto']

# Volume thresholds by category
VOLUME_THRESHOLDS = {
    'fed': 50000,      # $50k for Fed (high liquidity)
    'gold': 5000,      # $5k for others (catch early trends)
    'geopolitics': 5000,
    'inflation': 5000,
    'energy': 5000,
    'crypto': 5000,
}

# Exclusion keywords - remove noise
EXCLUDE_KEYWORDS = [
    # Sports
    'nhl', 'nba', 'nfl', 'mlb', 'soccer', 'football', 'hockey',
    'basketball', 'baseball', 'stanley cup', 'super bowl',
    'olympics', 'world cup', 'championship', 'epl', 'premier league',
    # Crypto (except ETF flows)
    'bitcoin price', 'ethereum price', 'btc price', 'eth price',
    'crypto ', 'blockchain', 'defi', 'nft',
    # Tech companies
    'openai', 'chatgpt', 'ai company', 'tech company', 'tesla',
    # US Politics (personality politics, not policy)
    'biden', 'election', 'vote', 'polling', 'campaign',
    # UK/EU Politics
    'uk election', 'british', 'germany election', 'france election',
    # Generic Russia/Ukraine (keep only if nuclear-related)
    'putin', 'zelenskyy', 'president russia', 'president ukraine',
    'ukraine election', 'russia election', 'netanyahu',
    # Other noise
    'brentford',  # Football team, not Brent crude
    # Financial institutions (not gold price)
    'goldman', 'goldman sachs', 'jp morgan', 'morgan stanley',
]

# Dead market threshold - filter out one-sided markets where one outcome dominates
# If any outcome has >= 95% probability, the market is "dead" (no real competition)
DEAD_MARKET_THRESHOLD = 0.95  # 95% - markets with any outcome >= 95% are dead


def _categorize_market(question: str, description: str = '') -> str:
    """
    Categorize a market using keyword dictionary with priority order.
    
    Priority: Fed > Gold > Geopolitics > Inflation > Energy > Crypto
    First match wins (based on priority order).
    """
    combined = (question + ' ' + description).lower()
    
    for category in CATEGORY_PRIORITY:
        keywords = CATEGORY_KEYWORDS.get(category, [])
        if any(kw in combined for kw in keywords):
            return category
    
    return 'other'


def _translate_question(question: str, category: str) -> str:
    """
    Smart Thai translation that preserves numbers and price targets.
    
    Examples:
    - "Will Gold hit $4,600 in April?" → "ทองคำจะแตะ $4,600 ในเดือนเมษายนหรือไม่?"
    - "No Fed rate cuts in 2026?" → "เฟดจะไม่ลดดอกเบี้ยเลยในปี 2026?"
    - "GDP QoQ > 2.5%?" → "GDP ไตรมาสต่อไตรมาสโต > 2.5% หรือไม่?"
    """
    q_lower = question.lower()

    # Extract numbers and years for context
    import re
    year_match = re.search(r'\b(20\d{2})\b', question)
    year_str = f"ในปี {year_match.group(1)}" if year_match else ""

    # Extract dollar amounts
    dollar_match = re.search(r'\$([\d,]+(?:\.\d+)?)', question)
    dollar_str = f"${dollar_match.group(1)}" if dollar_match else None

    # Extract percentage
    pct_match = re.search(r'([\d.]+)%', question)
    pct_str = f"{pct_match.group(1)}%" if pct_match else None

    # Extract month names
    month_map = {
        'january': 'มกราคม', 'february': 'กุมภาพันธ์', 'march': 'มีนาคม',
        'april': 'เมษายน', 'may': 'พฤษภาคม', 'june': 'มิถุนายน',
        'july': 'กรกฎาคม', 'august': 'สิงหาคม', 'september': 'กันยายน',
        'october': 'ตุลาคม', 'november': 'พฤศจิกายน', 'december': 'ธันวาคม',
    }
    month_str = ''
    for eng, thai in month_map.items():
        if eng in q_lower:
            month_str = f'ในเดือน{thai}'
            break

    # Fed rate decisions
    if 'fed rate' in q_lower or 'federal reserve' in q_lower or 'the fed ' in q_lower or 'fomc' in q_lower:
        # Number of rate cuts - handle both patterns:
        # "3 or more fed rate cuts" and "cut rates 3 or more times"
        cuts_match = re.search(r'(\d+)\s*(?:or\s*more\s*)?\s*fed\s*rate\s*cuts?', q_lower)
        cuts_match2 = re.search(r'(?:fed\s+)?cut\s+rates?\s+(\d+)\s*(?:or\s*more)?\s*times?', q_lower)
        no_cuts_match = re.search(r'no\s+fed\s*rate\s*cuts?', q_lower)
        will_cut_match = re.search(r'will\s+the\s+fed\s+cut', q_lower)

        if no_cuts_match:
            return f'เฟดจะไม่ลดดอกเบี้ยเลย{year_str}?'
        if cuts_match:
            num = cuts_match.group(1)
            or_more = 'or more' in q_lower
            more_str = 'ครั้งขึ้นไป' if or_more else 'ครั้ง'
            return f'เฟดจะลดดอกเบี้ย {num} {more_str}{year_str}?'
        if cuts_match2:
            num = cuts_match2.group(1)
            or_more = 'or more' in q_lower
            more_str = 'ครั้งขึ้นไป' if or_more else 'ครั้ง'
            return f'เฟดจะลดดอกเบี้ย {num} {more_str}{year_str}?'
        if will_cut_match:
            return f'เฟดจะลดดอกเบี้ย{year_str}?'

        if 'raise' in q_lower or 'increase' in q_lower or 'hike' in q_lower:
            return f'เฟดจะขึ้นดอกเบี้ย{year_str}?'
        if 'cut' in q_lower or 'decrease' in q_lower or 'reduce' in q_lower:
            return f'เฟดจะลดดอกเบี้ย{year_str}?'
        if 'hold' in q_lower or 'keep' in q_lower or 'unchanged' in q_lower:
            return f'เฟดจะคงดอกเบี้ย{year_str}?'
        return f'การตัดสินใจดอกเบี้ยของเฟด{year_str}'

    # Gold price targets
    if 'gold' in q_lower:
        price = dollar_str or '?'
        if 'hit' in q_lower or 'reach' in q_lower or 'above' in q_lower:
            return f'ทองคำจะแตะ {price}{month_str}{year_str}หรือไม่?'
        if 'below' in q_lower or 'under' in q_lower:
            return f'ทองคำจะต่ำกว่า {price}{month_str}{year_str}หรือไม่?'
        if 'end' in q_lower or 'close' in q_lower or 'finish' in q_lower:
            return f'ทองคำจะปิดที่ {price}{month_str}{year_str}หรือไม่?'
        if 'at' in q_lower and dollar_str:
            return f'ทองคำจะอยู่ที่ {price}{month_str}{year_str}หรือไม่?'
        if 'to ' in q_lower and dollar_str:
            return f'ทองคำจะไปถึง {price}{year_str}หรือไม่?'
        # Fallback with price if found
        if dollar_str:
            return f'ทองคำที่ระดับ {price}{year_str}จะเป็นอย่างไร?'
        return 'คาดการณ์ราคาทองคำ'

    # Inflation / CPI
    if 'cpi' in q_lower:
        if 'above' in q_lower or '>' in question:
            return f'CPI จะเกิน {pct_str or "?"}{year_str}หรือไม่?'
        if 'below' in q_lower or '<' in question:
            return f'CPI จะต่ำกว่า {pct_str or "?"}{year_str}หรือไม่?'
        return f'คาดการณ์เงินเฟ้อ (CPI){year_str}'

    if 'inflation' in q_lower:
        if 'above' in q_lower or '>' in question:
            return f'เงินเฟ้อจะเกิน {pct_str or "?"}{year_str}หรือไม่?'
        return f'คาดการณ์เงินเฟ้อ{year_str}'

    # GDP
    if 'gdp' in q_lower:
        if '>' in question or 'above' in q_lower or 'greater' in q_lower:
            return f'GDP จะโตเกิน {pct_str or "?"}{year_str}หรือไม่?'
        if '<' in question or 'below' in q_lower or 'negative' in q_lower:
            return f'GDP จะติดลบหรือต่ำกว่า {pct_str or "?"}{year_str}หรือไม่?'
        return f'คาดการณ์ GDP{year_str}'

    # Recession
    if 'recession' in q_lower:
        return f'เศรษฐกิจสหรัฐฯ จะเข้าสู่ภาวะถดถอย{year_str}?'

    # Employment / Jobs
    if 'job' in q_lower or 'employment' in q_lower or 'unemployment' in q_lower:
        if 'rate' in q_lower and pct_str:
            return f'อัตราการว่างงานจะเกิน {pct_str}หรือไม่?'
        return f'คาดการณ์การจ้างงาน{year_str}'

    # Oil
    if 'oil' in q_lower or 'crude' in q_lower or 'wti' in q_lower:
        price = dollar_str or '?'
        if 'above' in q_lower or '>' in question:
            return f'ราคาน้ำมันจะเกิน {price}หรือไม่?'
        if 'below' in q_lower or '<' in question:
            return f'ราคาน้ำมันจะต่ำกว่า {price}หรือไม่?'
        return f'คาดการณ์ราคาน้ำมัน{year_str}'

    # Fallback - return original question
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
    """
    Fetch prediction markets from Polymarket Gamma API.
    
    Uses partial match, case-insensitive search across Title + Description.
    Filters by category-specific volume thresholds.
    """
    markets_data = []

    # Strategy 1: Fetch from economics tag (tag_id=107) - PRIMARY SOURCE
    try:
        response = requests.get(
            'https://gamma-api.polymarket.com/markets',
            params={
                'active': 'true',
                'closed': 'false',
                'limit': '500',
                'tag_id': '107',
            },
            timeout=15,
            headers={'Accept': 'application/json'}
        )
        response.raise_for_status()
        data = response.json()
        market_list = data if isinstance(data, list) else data.get('markets', data)
        markets_data.extend(market_list)
        logger.info(f"Fetched {len(market_list)} markets from economics tag (107)")
    except Exception as e:
        logger.warning(f"Failed to fetch economics tag markets: {e}")

    # Strategy 2: Additional tag IDs for broader discovery
    additional_tags = [
        ('1', 'World'),           # World events (geopolitics)
        ('108', 'Politics'),      # Politics (may have policy impacts)
    ]
    for tag_id, tag_name in additional_tags:
        try:
            response = requests.get(
                'https://gamma-api.polymarket.com/markets',
                params={
                    'active': 'true',
                    'closed': 'false',
                    'limit': '500',
                    'tag_id': tag_id,
                },
                timeout=15,
                headers={'Accept': 'application/json'}
            )
            response.raise_for_status()
            data = response.json()
            market_list = data if isinstance(data, list) else data.get('markets', data)
            markets_data.extend(market_list)
            logger.info(f"Fetched {len(market_list)} markets from {tag_name} tag ({tag_id})")
        except Exception as e:
            logger.warning(f"Failed to fetch {tag_name} tag markets: {e}")

    # Strategy 3: Events API with economics tag
    try:
        response = requests.get(
            'https://gamma-api.polymarket.com/events',
            params={
                'active': 'true',
                'closed': 'false',
                'limit': '100',
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

    # Strategy 4: Direct fetch without tag filter
    try:
        response = requests.get(
            'https://gamma-api.polymarket.com/markets',
            params={
                'active': 'true',
                'closed': 'false',
                'limit': '500',
            },
            timeout=15,
            headers={'Accept': 'application/json'}
        )
        response.raise_for_status()
        data = response.json()
        market_list = data if isinstance(data, list) else data.get('markets', data)
        markets_data.extend(market_list)
        logger.info(f"Fetched {len(market_list)} markets from direct fetch")
    except Exception as e:
        logger.warning(f"Failed to fetch direct markets: {e}")

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
            combined = (question + ' ' + description).lower()

            # Check exclusions first
            if any(kw in combined for kw in EXCLUDE_KEYWORDS):
                continue

            # Categorize using keyword dictionary (partial match, case-insensitive)
            category = _categorize_market(question, description)
            if category == 'other':
                continue  # Skip markets that don't match any category

            # Year filter - skip 2027+ unless nuclear-related
            import re
            year_match = re.search(r'\b(20\d{2})\b', question)
            if year_match:
                year = int(year_match.group(1))
                if year > 2026 and 'nuclear' not in combined and 'nuke' not in combined:
                    continue

            # Russia/Ukraine only if nuclear-related
            if any(kw in combined for kw in ['putin', 'zelenskyy', 'ukraine', 'russia']):
                if 'nuclear' not in combined and 'nuke' not in combined:
                    continue

            # Volume threshold by category
            volume = float(market.get('volume', market.get('volumeNum', 0)))
            min_volume = VOLUME_THRESHOLDS.get(category, 5000)
            if volume < min_volume:
                continue

            # Parse outcomes
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

            # Filter out dead markets - if any outcome >= 95%, market is one-sided (dead)
            max_prob = max(o['price'] for o in outcomes)
            if max_prob >= DEAD_MARKET_THRESHOLD:
                logger.debug(f"Skipping dead market (max prob {max_prob:.0%}): {question}")
                continue

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
    # Show all 6 categories in priority order
    display_categories = ['fed', 'gold', 'geopolitics', 'inflation', 'energy', 'crypto']

    for category in display_categories:
        cat_info = CATEGORY_INFO.get(category, {})
        cat_emoji = cat_info.get('emoji', '📌')
        cat_label = cat_info.get('label_th', category.capitalize())

        if category not in by_category:
            # Show category header with "no active markets" message
            message += f"{cat_emoji} <b>{cat_label}</b>\n"
            message += "<i>ไม่มีตลาด active ตอนนี้ (จะแสดงเมื่อมีตลาดใหม่)</i>\n\n"
            continue

        cat_markets = by_category[category][:3]
        message += f"{cat_emoji} <b>{cat_label}</b>\n"

        for market in cat_markets:
            outcomes_str = _format_outcomes_detailed(market)
            # Show smart Thai translation with numbers preserved
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
    Format outcomes with Thai labels for Yes/No, original names for others.
    
    For Yes/No markets: show ใช่/ไม่ใช่ (the Thai question provides context).
    For named outcomes (e.g., "$2500", "$2600"): show the outcome name directly.
    
    Example:
    • ทองคำจะแตะ $4,600 ในเดือนเมษายนหรือไม่?
      🟢 ใช่: 20%
      🔴 ไม่ใช่: 80%
    """
    lines = []
    
    for outcome in market.outcomes[:4]:  # Show up to 4 outcomes
        name = outcome.get('name', '')
        price = outcome.get('price', 0)
        pct = price * 100
        
        name_lower = name.lower()
        
        # Translate Yes/No to Thai
        if name_lower in ('yes', 'true', 'yes '):
            label = 'ใช่'
        elif name_lower in ('no', 'false', 'no '):
            label = 'ไม่ใช่'
        else:
            # For named outcomes (price levels, rate decisions, etc.), show original name
            label = name
        
        # Add indicator based on probability
        if pct >= 60:
            indicator = '🟢'
        elif pct >= 40:
            indicator = '🟡'
        else:
            indicator = '🔴'
        
        lines.append(f"  {indicator} {label}: {pct:.0f}%")
    
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
