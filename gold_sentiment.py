"""
Gold Sentiment Score Calculator
==============================
Calculate gold sentiment based on market relationships:
- Ceasefire % down + Oil % up = Bullish 🟢 (risk-off, war continues)
- Ceasefire % up + Oil % down = Bearish 🔴 (risk-on, peace)
- Fed rate cut probability up = Bullish 🟢 (weaker USD)
- Fed rate hike probability up = Bearish 🔴 (stronger USD)
"""

from typing import List, Dict, Optional, Any
from dataclasses import dataclass


def _get_attr(obj, attr, default=None):
    """Safely get attribute from dict or object."""
    if isinstance(obj, dict):
        return obj.get(attr, default)
    return getattr(obj, attr, default)


@dataclass
class SentimentResult:
    """Gold sentiment analysis result."""
    score: float  # -100 to +100
    label: str    # 'Bullish 🟢', 'Bearish 🔴', 'Neutral ⚪'
    reasoning: str


def calculate_gold_sentiment(markets: List[Any]) -> SentimentResult:
    """
    Calculate gold sentiment score based on market relationships.
    
    Scoring:
    - Ceasefire probability DOWN (war continues) = +20 points (bullish)
    - Oil price UP = +15 points (inflation/war hedge)
    - Fed rate cut probability UP = +25 points (weaker USD)
    - Fed rate hike probability UP = -25 points (stronger USD)
    - Gold price target UP = +30 points (direct bullish)
    
    Total range: -100 to +100
    """
    score = 0
    reasons = []
    
    # Find relevant markets
    ceasefire_market = None
    oil_market = None
    fed_cut_market = None
    gold_target_market = None
    
    for market in markets:
        # Handle both dict and object access
        if isinstance(market, dict):
            q_lower = market.get('question', '').lower()
        else:
            q_lower = market.question.lower()
        
        # Ceasefire detection
        if any(kw in q_lower for kw in ['ceasefire', 'cease-fire', 'หยุดยิง']):
            ceasefire_market = market
            
        # Oil detection
        if any(kw in q_lower for kw in ['oil', 'brent', 'wti', 'น้ำมัน']):
            oil_market = market
            
        # Fed rate cut detection
        if 'fed' in q_lower and any(kw in q_lower for kw in ['cut', 'ลดดอกเบี้ย']):
            fed_cut_market = market
            
        # Gold price target detection
        if 'gold' in q_lower and any(kw in q_lower for kw in ['above', 'below', '$', 'target']):
            gold_target_market = market
    
    # Analyze Ceasefire (Geopolitics)
    if ceasefire_market:
        outcomes = _get_attr(ceasefire_market, 'outcomes', [])
        # Find "Yes" (ceasefire happens) probability
        yes_prob = None
        for outcome in outcomes:
            name = outcome.get('name', '').lower() if isinstance(outcome, dict) else outcome.name.lower()
            price = outcome.get('price', 0) if isinstance(outcome, dict) else outcome.price
            if 'yes' in name or 'ใช่' in name or 'เกิด' in name:
                yes_prob = price * 100
                break
        
        if yes_prob is not None:
            if yes_prob < 40:
                # Ceasefire unlikely = war continues = bullish for gold
                score += 20
                reasons.append(f"🟢 โอกาสหยุดยิงต่ำ ({yes_prob:.0f}%) = สงครามยังดำเนิน")
            elif yes_prob > 60:
                # Ceasefire likely = peace = bearish for gold
                score -= 20
                reasons.append(f"🔴 โอกาสหยุดยิงสูง ({yes_prob:.0f}%) = สันติภาพใกล้")
    
    # Analyze Oil
    if oil_market:
        outcomes = _get_attr(oil_market, 'outcomes', [])
        for outcome in outcomes:
            name = outcome.get('name', '').lower() if isinstance(outcome, dict) else outcome.name.lower()
            price = outcome.get('price', 0) if isinstance(outcome, dict) else outcome.price
            price_pct = price * 100
            # If oil price going UP
            if any(kw in name for kw in ['up', 'above', 'higher', 'ขึ้น']) and price_pct > 50:
                score += 15
                reasons.append(f"🟢 น้ำมันแนวโน้มขึ้น ({price_pct:.0f}%) = เงินเฟ้อ/สงคราม")
                break
            # If oil price going DOWN
            if any(kw in name for kw in ['down', 'below', 'lower', 'ลง']) and price_pct > 50:
                score -= 15
                reasons.append(f"🔴 น้ำมันแนวโน้มลง ({price_pct:.0f}%) = สงบ")
                break
    
    # Analyze Fed Rate Cut
    if fed_cut_market:
        outcomes = _get_attr(fed_cut_market, 'outcomes', [])
        for outcome in outcomes:
            name = outcome.get('name', '').lower() if isinstance(outcome, dict) else outcome.name.lower()
            price = outcome.get('price', 0) if isinstance(outcome, dict) else outcome.price
            price_pct = price * 100
            # If rate cut is likely
            if any(kw in name for kw in ['cut', 'ลด', '0.25', '25bps']) and price_pct > 50:
                score += 25
                reasons.append(f"🟢 เฟดลดดอกเบี้ยสูง ({price_pct:.0f}%) = USD อ่อน")
                break
            # If rate hike is likely
            if any(kw in name for kw in ['hike', 'raise', 'ขึ้น', 'increase']) and price_pct > 50:
                score -= 25
                reasons.append(f"🔴 เฟดขึ้นดอกเบี้ยสูง ({price_pct:.0f}%) = USD แข็ง")
                break
    
    # Analyze Gold Target
    if gold_target_market:
        outcomes = _get_attr(gold_target_market, 'outcomes', [])
        for outcome in outcomes:
            name = outcome.get('name', '').lower() if isinstance(outcome, dict) else outcome.name.lower()
            price = outcome.get('price', 0) if isinstance(outcome, dict) else outcome.price
            price_pct = price * 100
            # If gold expected to go ABOVE target
            if any(kw in name for kw in ['above', 'higher', 'break', 'ขึ้น', 'เกิน']) and price_pct > 50:
                score += 30
                reasons.append(f"🟢 ทองคำทะลุเป้า ({price_pct:.0f}%) = Bullish")
                break
            # If gold expected to stay BELOW
            if any(kw in name for kw in ['below', 'lower', 'under', 'ต่ำกว่า']) and price_pct > 50:
                score -= 30
                reasons.append(f"🔴 ทองคำไม่ทะลุเปา ({price_pct:.0f}%) = Bearish")
                break
    
    # Determine label
    if score >= 30:
        label = "Bullish 🟢"
    elif score <= -30:
        label = "Bearish 🔴"
    else:
        label = "Neutral ⚪"
    
    # Format reasoning
    if reasons:
        reasoning = "\n".join(reasons)
    else:
        reasoning = "📊 ไม่พบข้อมูลเพียงพอสำหรับประเมิน"
    
    return SentimentResult(
        score=max(-100, min(100, score)),  # Clamp between -100 and 100
        label=label,
        reasoning=reasoning
    )


def format_sentiment_message(result: SentimentResult) -> str:
    """Format sentiment result for Telegram."""
    return (
        f"📊 <b>Gold Sentiment Score</b>\n"
        f"<code>{'█' * int(abs(result.score) / 5)}{'░' * (20 - int(abs(result.score) / 5))}</code>\n"
        f"คะแนน: {result.score:+.0f}/100\n"
        f"แนวโน้ม: <b>{result.label}</b>\n\n"
        f"{result.reasoning}"
    )
