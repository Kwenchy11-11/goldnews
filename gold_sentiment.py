"""
Gold Sentiment Score Calculator
==============================
Calculate gold sentiment based on market relationships:
- Ceasefire % down + Oil % up = Bullish 🟢 (risk-off, war continues)
- Ceasefire % up + Oil % down = Bearish 🔴 (risk-on, peace)
- Fed rate cut probability up = Bullish 🟢 (weaker USD)
- Fed rate hike probability up = Bearish 🔴 (stronger USD)

IMPORTANT: If only Fed data is available, calculate sentiment from Fed alone.
Don't show 0/Neutral if we have Fed data.
"""

import re
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
    - Fed rate cut probability UP = +25 points (weaker USD → gold up)
    - Fed rate hike/no-cut probability UP = -25 points (stronger USD → gold down)
    - Ceasefire probability DOWN (war continues) = +20 points (bullish)
    - Oil price UP = +15 points (inflation/war hedge)
    - Gold price target UP = +30 points (direct bullish)
    
    Total range: -100 to +100
    
    If only Fed data is available, calculate from Fed alone.
    """
    score = 0
    reasons = []
    data_sources = 0
    
    # Find relevant markets
    ceasefire_market = None
    oil_market = None
    fed_markets = []  # Collect ALL Fed markets, not just cut-specific
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
            
        # Fed detection - collect ALL Fed markets
        if any(kw in q_lower for kw in ['fed', 'fomc', 'federal reserve', 'interest rate']):
            fed_markets.append(market)
            
        # Gold price target detection
        if 'gold' in q_lower and any(kw in q_lower for kw in ['above', 'below', '$', 'target']):
            gold_target_market = market
    
    # Analyze Fed Markets (most important - always available)
    if fed_markets:
        data_sources += 1
        fed_score = _analyze_fed_sentiment(fed_markets)
        score += fed_score['score']
        reasons.extend(fed_score['reasons'])
    
    # Analyze Ceasefire (Geopolitics)
    if ceasefire_market:
        data_sources += 1
        outcomes = _get_attr(ceasefire_market, 'outcomes', [])
        yes_prob = None
        for outcome in outcomes:
            name = outcome.get('name', '').lower() if isinstance(outcome, dict) else outcome.name.lower()
            price = outcome.get('price', 0) if isinstance(outcome, dict) else outcome.price
            if 'yes' in name or 'ใช่' in name or 'เกิด' in name:
                yes_prob = price * 100
                break
        
        if yes_prob is not None:
            if yes_prob < 40:
                score += 20
                reasons.append(f"🟢 โอกาสหยุดยิงต่ำ ({yes_prob:.0f}%) = สงครามยังดำเนิน")
            elif yes_prob > 60:
                score -= 20
                reasons.append(f"🔴 โอกาสหยุดยิงสูง ({yes_prob:.0f}%) = สันติภาพใกล้")
    
    # Analyze Oil
    if oil_market:
        data_sources += 1
        outcomes = _get_attr(oil_market, 'outcomes', [])
        for outcome in outcomes:
            name = outcome.get('name', '').lower() if isinstance(outcome, dict) else outcome.name.lower()
            price = outcome.get('price', 0) if isinstance(outcome, dict) else outcome.price
            price_pct = price * 100
            if any(kw in name for kw in ['up', 'above', 'higher', 'ขึ้น']) and price_pct > 50:
                score += 15
                reasons.append(f"🟢 น้ำมันแนวโน้มขึ้น ({price_pct:.0f}%) = เงินเฟ้อ/สงคราม")
                break
            if any(kw in name for kw in ['down', 'below', 'lower', 'ลง']) and price_pct > 50:
                score -= 15
                reasons.append(f"🔴 น้ำมันแนวโน้มลง ({price_pct:.0f}%) = สงบ")
                break
    
    # Analyze Gold Target
    if gold_target_market:
        data_sources += 1
        outcomes = _get_attr(gold_target_market, 'outcomes', [])
        for outcome in outcomes:
            name = outcome.get('name', '').lower() if isinstance(outcome, dict) else outcome.name.lower()
            price = outcome.get('price', 0) if isinstance(outcome, dict) else outcome.price
            price_pct = price * 100
            if any(kw in name for kw in ['above', 'higher', 'break', 'ขึ้น', 'เกิน']) and price_pct > 50:
                score += 30
                reasons.append(f"🟢 ทองคำทะลุเป้า ({price_pct:.0f}%) = Bullish")
                break
            if any(kw in name for kw in ['below', 'lower', 'under', 'ต่ำกว่า']) and price_pct > 50:
                score -= 30
                reasons.append(f"🔴 ทองคำไม่ทะลุเป้า ({price_pct:.0f}%) = Bearish")
                break
    
    # Determine label based on score
    if score >= 30:
        label = "Bullish 🟢"
    elif score <= -30:
        label = "Bearish 🔴"
    else:
        label = "Neutral ⚪"
    
    # Format reasoning
    missing_data_warnings = []
    if not fed_markets:
        missing_data_warnings.append("⚠️ ไม่พบตลาด Fed")
    if not gold_target_market:
        missing_data_warnings.append("⚠️ ไม่พบตลาด Gold Target")
    if not oil_market:
        missing_data_warnings.append("⚠️ ไม่พบตลาด Oil")
    if not ceasefire_market:
        missing_data_warnings.append("⚠️ ไม่พบตลาด Geopolitics")
    
    if reasons:
        reasoning = "\n".join(reasons)
        if missing_data_warnings:
            reasoning += "\n\n<b>ข้อมูลขาดหาย:</b>\n" + "\n".join(missing_data_warnings)
            reasoning += f"\n\n<i>คำนวณจาก {data_sources} แหล่งข้อมูล</i>"
    else:
        if missing_data_warnings:
            reasoning = "<b>⚠️ ไม่พบข้อมูลเพียงพอสำหรับประเมิน</b>\n\n" + "\n".join(missing_data_warnings)
            reasoning += "\n\n<i>กรุณาตรวจสอบตลาดใน Polymarket โดยตรง</i>"
        else:
            reasoning = "📊 ไม่พบข้อมูลเพียงพอสำหรับประเมิน"
    
    return SentimentResult(
        score=max(-100, min(100, score)),
        label=label,
        reasoning=reasoning
    )


def _analyze_fed_sentiment(fed_markets: List[Any]) -> Dict:
    """
    Analyze Fed markets to determine gold sentiment.
    
    Logic:
    - If markets show HIGH probability of NO rate cuts → Bearish for gold (stronger USD)
    - If markets show HIGH probability of rate cuts → Bullish for gold (weaker USD)
    - Weight by volume (higher volume = more reliable)
    
    Returns dict with 'score' and 'reasons' list.
    """
    score = 0
    reasons = []
    
    for market in fed_markets:
        question = market.question.lower() if not isinstance(market, dict) else market.get('question', '').lower()
        outcomes = _get_attr(market, 'outcomes', [])
        volume = _get_attr(market, 'volume', 0)
        
        # Skip very low volume markets
        if volume < 100000:
            continue
        
        # Determine what this market is asking
        is_no_cuts_question = 'no' in question and ('cut' in question or 'cuts' in question)
        is_cuts_question = 'cut' in question and not is_no_cuts_question
        is_hike_question = any(kw in question for kw in ['hike', 'raise', 'increase'])
        
        # Find the "Yes" probability
        yes_prob = None
        no_prob = None
        for outcome in outcomes:
            name = outcome.get('name', '').lower() if isinstance(outcome, dict) else outcome.name.lower()
            price = outcome.get('price', 0) if isinstance(outcome, dict) else outcome.price
            price_pct = price * 100
            
            if 'yes' in name or 'ใช่' in name:
                yes_prob = price_pct
            elif 'no' in name or 'ไม่ใช่' in name:
                no_prob = price_pct
        
        if yes_prob is None:
            continue
        
        # Analyze based on question type
        if is_no_cuts_question:
            # "No Fed rate cuts in 2026?" → Yes=50% means 50% chance of NO cuts
            # High "Yes" = no cuts = bearish for gold
            if yes_prob > 60:
                score -= 25
                reasons.append(f"🔴 ตลาดมั่นใจเฟดไม่ลดดอกเบี้ย ({yes_prob:.0f}%) = USD แข็ง")
            elif yes_prob < 40:
                score += 25
                reasons.append(f"🟢 ตลาดมองเฟดจะลดดอกเบี้ย ({100-yes_prob:.0f}%) = USD อ่อน")
            else:
                score -= 10
                reasons.append(f"🟡 ตลาดแบ่งครึ่งเรื่องไม่ลดดอกเบี้ย ({yes_prob:.0f}%) = ไม่ชัดเจน")
        
        elif is_cuts_question:
            # "Will Fed cut rates 6 times?" → Yes=1% means almost no chance of 6 cuts
            # Extract number of cuts
            cuts_match = re.search(r'(\d+)\s*(?:times|ครั้ง|cuts)', question)
            num_cuts = int(cuts_match.group(1)) if cuts_match else 0
            
            if num_cuts >= 4:
                # Many cuts expected → if Yes is low, that's bearish
                if yes_prob < 20:
                    score -= 20
                    reasons.append(f"🔴 โอกาสลดดอกเบี้ย {num_cuts} ครั้งต่ำมาก ({yes_prob:.0f}%) = USD แข็ง")
                elif yes_prob > 60:
                    score += 20
                    reasons.append(f"🟢 โอกาสลดดอกเบี้ย {num_cuts} ครั้งสูง ({yes_prob:.0f}%) = USD อ่อน")
            else:
                # Few cuts (1-2) → if Yes is high, that's slightly bullish
                if yes_prob > 60:
                    score += 15
                    reasons.append(f"🟢 โอกาสลดดอกเบี้ย {num_cuts} ครั้งสูง ({yes_prob:.0f}%) = USD อ่อน")
                elif yes_prob < 20:
                    score -= 15
                    reasons.append(f"🔴 โอกาสลดดอกเบี้ย {num_cuts} ครั้งต่ำ ({yes_prob:.0f}%) = USD แข็ง")
        
        elif is_hike_question:
            # "Will Fed hike rates?" → Yes=high is bearish for gold
            if yes_prob > 60:
                score -= 25
                reasons.append(f"🔴 ตลาดมั่นใจเฟดขึ้นดอกเบี้ย ({yes_prob:.0f}%) = USD แข็งแรง")
            elif yes_prob < 20:
                score += 15
                reasons.append(f"🟢 โอกาสเฟดขึ้นดอกเบี้ยต่ำ ({yes_prob:.0f}%) = ไม่กดดันทอง")
    
    # Average the score across all Fed markets (don't stack too much)
    if len(fed_markets) > 1:
        score = score / min(len(fed_markets), 3)  # Cap at 3 markets for averaging
    
    return {'score': int(score), 'reasons': reasons}


def format_sentiment_message(result: SentimentResult) -> str:
    """Format sentiment result for Telegram."""
    # Create visual bar
    abs_score = abs(result.score)
    filled = int(abs_score / 5)
    empty = 20 - filled
    
    if result.score >= 0:
        bar = '█' * filled + '░' * empty
    else:
        bar = '░' * empty + '█' * filled
    
    return (
        f"📊 <b>Gold Sentiment Score</b>\n"
        f"<code>{bar}</code>\n"
        f"คะแนน: {result.score:+.0f}/100\n"
        f"แนวโน้ม: <b>{result.label}</b>\n\n"
        f"{result.reasoning}"
    )
