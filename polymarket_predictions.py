"""
Polymarket Predictions Module
=============================
Fetches prediction market data from Polymarket Gamma API for gold, Fed,
and economic events. Provides beginner-friendly Thai explanations.

Unlike the existing fetch_polymarket_gold() in news_fetcher.py which only
fetches gold-specific markets, this module fetches a broader set of
markets including Fed rate decisions, inflation, employment, etc.
that affect gold prices.
"""

import logging
import json
from typing import List, Dict, Optional
from dataclasses import dataclass

import requests

import config

logger = logging.getLogger('goldnews')


@dataclass
class PredictionMarket:
    """A single prediction market from Polymarket."""
    question: str           # e.g., "Will the Fed raise rates in May 2026?"
    question_th: str        # Thai translation/explanation
    outcomes: List[Dict]    # [{name: "Yes", price: 0.75}, {name: "No", price: 0.25}]
    volume: float           # Trading volume in USD
    url: str                # Link to the market
    category: str           # "fed", "inflation", "gold", "employment", "economy"
    explanation_th: str     # Beginner-friendly Thai explanation


# Category definitions with Thai explanations for beginners
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

    # Fed rate decisions
    if 'fed rate' in q_lower or 'federal reserve' in q_lower or 'the fed ' in q_lower:
        if 'raise' in q_lower or 'increase' in q_lower or 'hike' in q_lower:
            return 'เฟดจะขึ้นดอกเบี้ยหรือไม่?'
        if 'cut' in q_lower or 'decrease' in q_lower or 'reduce' in q_lower:
            return 'เฟดจะลดดอกเบี้ยหรือไม่?'
        if 'hold' in q_lower or 'keep' in q_lower or 'unchanged' in q_lower:
            return 'เฟดจะคงดอกเบี้ยหรือไม่?'
        return 'การตัดสินใจดอกเบี้ยของเฟด'

    # Gold price targets
    if 'gold' in q_lower:
        if 'above' in q_lower:
            # Extract price
            import re
            match = re.search(r'\$?([\d,]+)', question)
            price = match.group(1) if match else '?'
            return f'ราคาทองจะเกิน ${price} หรือไม่?'
        if 'below' in q_lower:
            import re
            match = re.search(r'\$?([\d,]+)', question)
            price = match.group(1) if match else '?'
            return f'ราคาทองจะต่ำกว่า ${price} หรือไม่?'
        if 'end' in q_lower or 'close' in q_lower or 'finish' in q_lower:
            import re
            match = re.search(r'\$?([\d,]+)', question)
            price = match.group(1) if match else '?'
            return f'ราคาทองจะปิดที่ ${price} หรือไม่?'
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

    return question  # Fallback to English


def _format_outcome_explanation(outcomes: List[Dict], category: str) -> str:
    """Format outcomes with beginner-friendly Thai labels."""
    lines = []
    for outcome in outcomes[:4]:  # Max 4 outcomes
        name = outcome.get('name', '')
        price = outcome.get('price', 0)
        pct = price * 100

        # Translate outcome names to Thai based on category
        name_th = _translate_outcome_name(name, category)

        # Color indicator
        if pct >= 60:
            indicator = '🟢'  # Likely
        elif pct >= 40:
            indicator = '🟡'  # Possible
        else:
            indicator = '🔴'  # Unlikely

        lines.append(f"  {indicator} {name_th}: {pct:.0f}%")

    return '\n'.join(lines)


def _translate_outcome_name(name: str, category: str) -> str:
    """Translate outcome names to Thai."""
    name_lower = name.lower()

    # Yes/No
    if name_lower in ('yes', 'yeah', 'true'):
        return 'ใช่'
    if name_lower in ('no', 'nope', 'false'):
        return 'ไม่ใช่'

    # Fed outcomes
    if 'raise' in name_lower or 'increase' in name_lower or 'hike' in name_lower:
        return 'ขึ้นดอกเบี้ย'
    if 'cut' in name_lower or 'decrease' in name_lower or 'reduce' in name_lower:
        return 'ลดดอกเบี้ย'
    if 'hold' in name_lower or 'keep' in name_lower or 'unchanged' in name_lower:
        return 'คงดอกเบี้ย'

    # Direction
    if 'above' in name_lower or 'higher' in name_lower or 'up' in name_lower:
        return 'สูงกว่า'
    if 'below' in name_lower or 'lower' in name_lower or 'down' in name_lower:
        return 'ต่ำกว่า'

    return name


def fetch_polymarket_predictions() -> List[PredictionMarket]:
    """
    Fetch prediction markets from Polymarket Gamma API.

    Fetches gold, Fed, inflation, employment, and economy markets
    that affect gold prices. Returns a list of PredictionMarket objects
    with Thai translations and beginner-friendly explanations.
    """
    # Keywords for markets that affect gold prices
    relevant_keywords = [
        # Gold
        'gold price', 'gold above', 'gold below', 'gold at', 'gold hit',
        'gold reach', 'gold end', 'gold close', 'gold finish', 'xauusd',
        # Fed
        'fed rate', 'federal reserve', 'interest rate', 'fed fund',
        'the fed ', 'fed raise', 'fed cut', 'fed hold',
        # Inflation
        'inflation', 'cpi', 'consumer price',
        # Employment
        'nonfarm', 'unemployment', 'jobless', 'payroll',
        # Economy
        'gdp', 'recession', 'economic growth',
    ]

    # Exclude irrelevant markets
    exclude_keywords = [
        'nhl', 'nba', 'nfl', 'mlb', 'soccer', 'football', 'hockey',
        'basketball', 'baseball', 'stanley cup', 'super bowl',
        'olympics', 'world cup', 'championship', 'election',
        'president', 'senate', 'congress', 'governor', 'trump',
        'biden', 'crypto', 'bitcoin', 'ethereum',
    ]

    try:
        response = requests.get(
            config.POLYMARKET_URL,
            params={'active': 'true', 'closed': 'false', 'limit': '100'},
            timeout=15,
            headers={'Accept': 'application/json'}
        )
        response.raise_for_status()
        data = response.json()

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch Polymarket predictions: {e}")
        return []
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse Polymarket data: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching Polymarket predictions: {e}")
        return []

    markets = []
    market_list = data.get('markets', data) if isinstance(data, dict) else data

    for market in market_list:
        try:
            question = market.get('question', '')
            description = market.get('description', '') or ''
            question_lower = question.lower()
            desc_lower = description.lower()
            combined = question_lower + ' ' + desc_lower

            # Skip excluded topics
            if any(kw in combined for kw in exclude_keywords):
                continue

            # Check if relevant
            if not any(kw in combined for kw in relevant_keywords):
                continue

            # Categorize
            category = _categorize_market(question, description)

            # Get outcomes
            outcomes_data = market.get('outcomes', [])
            outcome_prices = market.get('outcome_prices', [])

            outcomes = []
            for i, outcome_name in enumerate(outcomes_data):
                price = float(outcome_prices[i]) if i < len(outcome_prices) else 0
                outcomes.append({
                    'name': outcome_name,
                    'price': price,
                })

            # If no outcomes data, try alternative format
            if not outcomes:
                # Some markets have outcomes in a different format
                for outcome in market.get('outcomes_data', []):
                    outcomes.append({
                        'name': outcome.get('name', ''),
                        'price': float(outcome.get('price', 0)),
                    })

            # Skip if no valid outcomes
            if not outcomes:
                continue

            # Get volume
            volume = float(market.get('volume', 0))

            # Get URL
            slug = market.get('slug', '')
            url = f"https://polymarket.com/event/{slug}" if slug else ''

            # Thai translation
            question_th = _translate_question(question, category)

            # Get category explanation
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

    # Sort by volume (most popular first)
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
