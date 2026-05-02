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
    
    Dynamic Scoring:
    - Score is normalized to -100..+100 based ONLY on categories that have data
    - Missing categories are NEVER included in the average (no score dilution)
    - If only Fed data exists, score = Fed score scaled to -100..+100
    
    Category max contributions (raw):
    - Fed: ±25   → scaled to ±100 relative to all active categories
    - Ceasefire: ±20
    - Oil: ±15
    - Gold Target: ±30
    
    Final = (sum(raw_scores) / sum(max_possible)) * 100
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
    
    # ---- Track active categories for dynamic normalization ----
    has_fed = len(fed_markets) > 0
    has_ceasefire = ceasefire_market is not None
    has_oil = oil_market is not None
    has_gold_target = gold_target_market is not None
    
    # Analyze Fed Markets (most important - always available)
    if has_fed:
        data_sources += 1
        fed_score = _analyze_fed_sentiment(fed_markets)
        score += fed_score['score']
        reasons.extend(fed_score['reasons'])
    
    # Analyze Ceasefire (Geopolitics)
    if has_ceasefire:
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
                reasons.append(f"🟢 หยุดยิงต่ำ ({yes_prob:.0f}%) → สงครามต่อ → Safe Haven → ทองขึ้น 📈")
            elif yes_prob > 60:
                score -= 20
                reasons.append(f"🔴 หยุดยิงสูง ({yes_prob:.0f}%) → สงบ → Risk-On → ทองลง 📉")
    
    # Analyze Oil
    if has_oil:
        data_sources += 1
        outcomes = _get_attr(oil_market, 'outcomes', [])
        for outcome in outcomes:
            name = outcome.get('name', '').lower() if isinstance(outcome, dict) else outcome.name.lower()
            price = outcome.get('price', 0) if isinstance(outcome, dict) else outcome.price
            price_pct = price * 100
            if any(kw in name for kw in ['up', 'above', 'higher', 'ขึ้น']) and price_pct > 50:
                score += 15
                reasons.append(f"🟢 น้ำมันขึ้น ({price_pct:.0f}%) → เงินเฟ้อสูง → ทองขึ้น 📈")
                break
            if any(kw in name for kw in ['down', 'below', 'lower', 'ลง']) and price_pct > 50:
                score -= 15
                reasons.append(f"🔴 น้ำมันลง ({price_pct:.0f}%) → เงินเฟ้อลด → ทองลง 📉")
                break
    
    # Analyze Gold Target
    if has_gold_target:
        data_sources += 1
        outcomes = _get_attr(gold_target_market, 'outcomes', [])
        for outcome in outcomes:
            name = outcome.get('name', '').lower() if isinstance(outcome, dict) else outcome.name.lower()
            price = outcome.get('price', 0) if isinstance(outcome, dict) else outcome.price
            price_pct = price * 100
            if any(kw in name for kw in ['above', 'higher', 'break', 'ขึ้น', 'เกิน']) and price_pct > 50:
                score += 30
                reasons.append(f"🟢 ทองถึงเป้า ({price_pct:.0f}%) → เชื่อมั่นสูง → ทองขึ้นต่อ 📈")
                break
            if any(kw in name for kw in ['below', 'lower', 'under', 'ต่ำกว่า']) and price_pct > 50:
                score -= 30
                reasons.append(f"🔴 ทองไม่ถึงเป้า ({price_pct:.0f}%) → เชื่อมั่นต่ำ → ทองลง 📉")
                break
    
    # ============================================================
    # DYNAMIC NORMALIZATION: Normalize score based on active categories
    # ------------------------------------------------------------
    # Each category has a max absolute contribution:
    #   Fed:       25   (from _analyze_fed_sentiment)
    #   Ceasefire: 20
    #   Oil:       15
    #   Gold Tgt:  30
    # Total max possible across ALL 4 categories = 90
    #
    # We normalize: final_score = (raw_score / max_possible) * 100
    # This ensures score is always -100 to +100 regardless of
    # which categories have data available.
    # ============================================================
    max_possible = 0
    if has_fed:
        max_possible += 25
    if has_ceasefire:
        max_possible += 20
    if has_oil:
        max_possible += 15
    if has_gold_target:
        max_possible += 30
    
    if max_possible > 0:
        normalized_score = (score / max_possible) * 100
    else:
        normalized_score = 0
    
    # Clamp to -100..+100
    normalized_score = max(-100, min(100, normalized_score))
    
    # Strict thresholds for FOMC-day clarity
    if normalized_score >= 10:
        label = "Bullish 🟢"
    elif normalized_score <= -10:
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
            reasoning += f"\n\n<i>คำนวณจาก {data_sources} หมวดหมู่ (ปรับขนาดตามสัดส่วน)</i>"
    else:
        if missing_data_warnings:
            reasoning = "<b>⚠️ ไม่พบข้อมูลเพียงพอสำหรับประเมิน</b>\n\n" + "\n".join(missing_data_warnings)
            reasoning += "\n\n<i>กรุณาตรวจสอบตลาดใน Polymarket โดยตรง</i>"
        else:
            reasoning = "📊 ไม่พบข้อมูลเพียงพอสำหรับประเมิน"
    
    return SentimentResult(
        score=int(round(normalized_score)),
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
                reasons.append(f"🔴 ไม่ลดดอกเบี้ยสูง ({yes_prob:.0f}%) → USD แข็ง → ทองลง 📉")
            elif yes_prob < 40:
                score += 25
                reasons.append(f"🟢 ไม่ลดดอกเบี้ยต่ำ ({yes_prob:.0f}%) → มีโอกาสลด → USD อ่อน → ทองขึ้น 📈")
            else:
                score -= 3
                reasons.append(f"🟡 ไม่ลดดอกเบี้ยก้ำกึ่ง ({yes_prob:.0f}%) → โน้ม Bearish เล็กน้อย")
        
        elif is_cuts_question:
            # "Will Fed cut rates 6 times?" → Yes=1% means almost no chance of 6 cuts
            # Extract number of cuts (English question may not have a number)
            cuts_match = re.search(r'(\d+)\s*(?:times|ครั้ง|cuts)', question)
            num_cuts = int(cuts_match.group(1)) if cuts_match else 0
            
            if num_cuts >= 4:
                # Many cuts expected → if Yes is low, that's bearish
                if yes_prob < 20:
                    score -= 20
                    reasons.append(f"🔴 โอกาสลด {num_cuts} ครั้งต่ำมาก ({yes_prob:.0f}%) → USD ไม่อ่อน → ทองลง 📉")
                elif yes_prob > 60:
                    score += 20
                    reasons.append(f"🟢 โอกาสลด {num_cuts} ครั้งสูง ({yes_prob:.0f}%) → USD อ่อนมาก → ทองขึ้น 📈")
            else:
                # Few cuts or unknown count → if Yes is high, slightly bullish
                if yes_prob > 60:
                    score += 15
                    label = f"ลด {num_cuts} ครั้ง" if num_cuts else "ลดดอกเบี้ย"
                    reasons.append(f"🟢 โอกาส{label}สูง ({yes_prob:.0f}%) → USD อ่อน → ทองขึ้น 📈")
                elif yes_prob <= 20:
                    score -= 15
                    label = f"ลด {num_cuts} ครั้ง" if num_cuts else "ลดดอกเบี้ย"
                    reasons.append(f"🔴 โอกาส{label}ต่ำ ({yes_prob:.0f}%) → USD แข็ง → ทองลง 📉")
        
        elif is_hike_question:
            # "Will Fed hike rates?" → Yes=high is bearish for gold
            if yes_prob > 60:
                score -= 25
                reasons.append(f"🔴 ขึ้นดอกเบี้ยสูง ({yes_prob:.0f}%) → USD แข็งแรง → ทองลงแรง 📉")
            elif yes_prob < 20:
                score += 15
                reasons.append(f"🟢 โอกาสขึ้นดอกเบี้ยต่ำ ({yes_prob:.0f}%) → ไม่กดดันทอง → ทองขึ้น 📈")
    
    # Average the score across all Fed markets (prevent double-counting)
    if len(fed_markets) > 1:
        score = score / len(fed_markets)
    
    return {'score': int(score), 'reasons': reasons}


def format_sentiment_message(result: SentimentResult) -> str:
    """Format sentiment result for Telegram."""
    return (
        f"📊 <b>Gold Sentiment Score</b>\n"
        f"คะแนน: {result.score:+.0f}/100 | แนวโน้ม: <b>{result.label}</b>\n\n"
        f"{result.reasoning}"
    )
