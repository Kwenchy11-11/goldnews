"""
AI Analyzer Module
==================
Uses Gemini API to analyze news events' impact on gold prices.
Provides Thai-language analysis with conditional scenarios:
- If Actual > Forecast → gold tends to X
- If Actual < Forecast → gold tends to Y

Never gives definitive direction before data is released.
"""

import logging
from typing import List, Optional, Dict
from dataclasses import dataclass

import requests

import config

logger = logging.getLogger('goldnews')


@dataclass
class AnalysisResult:
    """Result of AI analysis for a news event."""
    event_title: str
    event_title_th: str
    impact: str  # HIGH, MEDIUM, LOW
    bias: str    # BULLISH, BEARISH, NEUTRAL (expected tendency)
    confidence: int  # 0-100
    reasoning: str
    country: str
    forecast: str
    previous: str
    event_datetime: object = None  # Parsed datetime (ICT) for display
    trade_decision: dict = None  # Trade recommendation from No Trade Zone engine


@dataclass
class MarketSummary:
    """Overall market outlook summary from AI analysis."""
    overall_bias: str      # BULLISH, BEARISH, NEUTRAL
    gold_outlook: str      # Thai description of gold outlook
    key_times: str         # Thai description of key time periods
    usd_impact: str        # Thai description of USD impact on gold
    confidence: int        # 0-100


def build_analysis_prompt(event) -> str:
    """
    Build a Thai-language prompt for Gemini to analyze a news event's
    impact on gold prices using CONDITIONAL analysis.

    Key principle: Don't predict direction before data is released.
    Instead, explain what happens if Actual > Forecast vs Actual < Forecast.
    """
    forecast_info = ""
    if event.forecast:
        forecast_info = f"- ค่าคาดการณ์ (Forecast): {event.forecast}\n"
    if event.previous:
        forecast_info += f"- ค่าก่อนหน้า (Previous): {event.previous}\n"

    # Determine if event is in the past or future
    time_context = ""
    if hasattr(event, 'event_datetime') and event.event_datetime:
        from datetime import datetime, timedelta
        now = datetime.utcnow() + timedelta(hours=7)  # ICT
        if event.event_datetime <= now:
            time_context = "⚠️ ข่าวนี้ประกาศแล้ว — ให้วิเคราะห์จากข้อมูลที่มี"
        else:
            time_context = "⚠️ ข่าวนี้ยังไม่ได้ประกาศ — ให้วิเคราะห์แบบมีเงื่อนไข (ถ้า Actual > Forecast → ... ถ้า Actual < Forecast → ...)"

    return f"""คุณเป็น News Analyst มืออาชีพสำหรับตลาดทองคำ (XAU/USD)

📰 ข่าวที่ต้องวิเคราะห์:
- ชื่อข่าว: {event.title} ({event.title_th})
- ประเทศ: {event.country}
- ระดับผลกระทบ: {event.impact}
{forecast_info}
{time_context}

🎯 งานของคุณ:
1. ประเมินผลกระทบต่อราคาทองคำ: HIGH / MEDIUM / LOW
2. ตัดสินใจแนวโน้มที่คาดหวัง: BULLISH (ทองขึ้น) / BEARISH (ทองลง) / NEUTRAL (เป็นกลาง)
3. ให้คะแนนความมั่นใจ (0-100%) — ข่าวที่ยังไม่ประกาศควรให้ 30-60% เพราะยังไม่รู้ผล
4. อธิบายเหตุผลสั้นๆ เป็นภาษาไทย

📌 สำคัญ — กฎการวิเคราะห์:
- ถ้าข่าวนี้ยังไม่ได้ประกาศ: ให้วิเคราะห์แบบมีเงื่อนไข
  เช่น "CPI: หาก Actual สูงกว่า Forecast (เงินเฟ้อสูงกว่าคาด) → USD แข็ง → ทองลง | หาก Actual ต่ำกว่า Forecast → ทองขึ้น"
  เช่น "GDP: หากเศรษฐกิจดีกว่าคาด → USD แข็ง → ทองลง | หากแย่กว่าคาด → ทองขึ้น"
- ถ้าข่าวนี้ประกาศแล้ว: วิเคราะห์จากผลจริง
- อย่าฟันธงทิศทางก่อนตัวเลขออก

💡 ความสัมพันธ์หลัก:
- ทองคำมีความสัมพันธ์ผกผันกับดอลลาร์สหรัฐ (USD)
- ข่าวที่ทำให้ USD แข็งแกร่ง → ทองลง
- ข่าวที่ทำให้ USD อ่อนค่า → ทองขึ้น
- CPI สูงกว่าคาด → เฟดอาจขึ้นดอกเบี้ย → USD แข็ง → ทองลง
- GDP ต่ำกว่าคาด → เศรษฐกิจแย่ → ทองขึ้น (safe haven)
- การว่างงานสูงกว่าคาด → เศรษฐกิจแย่ → ทองขึ้น
- FOMC ขึ้นดอกเบี้ย → USD แข็ง → ทองลง

📤 ตอบในรูปแบบนี้เท่านั้น:
IMPACT: [HIGH/MEDIUM/LOW]
BIAS: [BULLISH/BEARISH/NEUTRAL]
CONFIDENCE: [0-100]%
REASONING: [เหตุผลเป็นภาษาไทย — ถ้ายังไม่ประกาศให้ใช้รูปแบบ 'หาก...→... หาก...→...']"""


def call_gemini(prompt: str, max_tokens: int = 300) -> Optional[str]:
    """
    Call Gemini API with the given prompt.

    Args:
        prompt: The prompt text to send
        max_tokens: Maximum output tokens (default: 300, use 2000 for batch)

    Returns the text response or None on failure.
    """
    if not config.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set, skipping AI analysis")
        return None

    try:
        response = requests.post(
            f"{config.GEMINI_API_URL}?key={config.GEMINI_API_KEY}",
            json={
                'contents': [{
                    'role': 'user',
                    'parts': [{'text': prompt}]
                }],
                'generationConfig': {
                    'temperature': 0.3,
                    'maxOutputTokens': max_tokens,
                }
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text')
        return text

    except requests.exceptions.RequestException as e:
        logger.error(f"Gemini API error: {e}")
        return None
    except (KeyError, IndexError, TypeError) as e:
        logger.error(f"Gemini response parsing error: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error calling Gemini: {e}")
        return None


def parse_gemini_response(response: str) -> Dict[str, str]:
    """
    Parse Gemini's text response into structured fields.

    Expected format:
    IMPACT: HIGH
    BIAS: BEARISH
    CONFIDENCE: 75%
    REASONING: ...
    """
    lines = response.strip().split('\n')

    def extract(key: str) -> str:
        for line in lines:
            if key in line:
                value = line.split(key)[1].strip()
                # Remove trailing % from confidence
                if key == 'CONFIDENCE:':
                    value = value.replace('%', '')
                return value
        return ''

    confidence_str = extract('CONFIDENCE:').replace('%', '') or '50'
    confidence = int(confidence_str) if confidence_str.isdigit() else 50

    return {
        'impact': extract('IMPACT:').upper() or 'LOW',
        'bias': extract('BIAS:').upper() or 'NEUTRAL',
        'confidence': confidence,
        'reasoning': extract('REASONING:') or 'ไม่มีข้อมูลเพิ่มเติม',
    }


def analyze_event(event) -> AnalysisResult:
    """
    Analyze a single news event using Gemini API.

    Returns AnalysisResult with impact, bias, confidence, and reasoning.
    Falls back to conditional analysis if Gemini is unavailable.
    """
    prompt = build_analysis_prompt(event)
    response = call_gemini(prompt)

    if response:
        parsed = parse_gemini_response(response)
        confidence = parsed['confidence'] if isinstance(parsed['confidence'], int) else 50
        confidence = max(0, min(100, confidence))

        return AnalysisResult(
            event_title=event.title,
            event_title_th=event.title_th,
            impact=parsed['impact'],
            bias=parsed['bias'],
            confidence=confidence,
            reasoning=parsed['reasoning'],
            country=event.country,
            forecast=event.forecast,
            previous=event.previous,
            event_datetime=getattr(event, 'event_datetime', None),
        )

    # Fallback: use conditional keyword-based analysis when Gemini is unavailable
    logger.warning(f"Gemini unavailable, using fallback analysis for: {event.title}")
    bias, reasoning = _fallback_bias_analysis(event)

    return AnalysisResult(
        event_title=event.title,
        event_title_th=event.title_th,
        impact=event.impact.upper(),
        bias=bias,
        confidence=40,
        reasoning=reasoning,
        country=event.country,
        forecast=event.forecast,
        previous=event.previous,
        event_datetime=getattr(event, 'event_datetime', None),
    )


def _fallback_bias_analysis(event) -> tuple:
    """
    Determine bias direction using conditional keyword heuristics.

    Key principle: Don't predict direction — explain conditional scenarios.
    Gold has an inverse relationship with USD.

    Returns:
        tuple of (bias, reasoning) strings
    """
    title = event.title.lower()
    title_th = event.title_th
    forecast = event.forecast
    previous = event.previous

    # Conditional analysis templates for common event types
    conditional_templates = {
        # Inflation events (CPI, PPI, PCE)
        'cpi': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (เงินเฟ้อสูงกว่าคาด) → เฟดอาจคงดอกเบี้ยสูง → USD แข็ง → 📉 ทองลง | หาก Actual ต่ำกว่า Forecast → ทองขึ้น 📈'
        ),
        'ppi': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (เงินเฟ้อผู้ผลิตสูง) → ส่งสัญญาณเงินเฟ้อผู้บริโภค → 📉 ทองลง | หากต่ำกว่าคาด → 📈 ทองขึ้น'
        ),
        'core pce': (
            'NEUTRAL',
            f'{title_th} (ตัววัดเงินเฟ้อที่เฟดชอบ): หาก Actual สูงกว่า Forecast → เฟดอาจขึ้นดอกเบี้ย → 📉 ทองลง | หากต่ำกว่าคาด → 📈 ทองขึ้น'
        ),
        'trimmed mean cpi': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast → เงินเฟ้อพื้นฐานสูง → 📉 ทองลง | หากต่ำกว่าคาด → 📈 ทองขึ้น'
        ),

        # Economic growth events (GDP)
        'gdp': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (เศรษฐกิจดีกว่าคาด) → USD แข็ง → 📉 ทองลง | หาก Actual ต่ำกว่า Forecast (เศรษฐกิจแย่) → ทองเป็น safe haven → 📈 ทองขึ้น'
        ),
        'gdp price index': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (เงินเฟ้อใน GDP สูง) → 📉 ทองลง | หากต่ำกว่าคาด → 📈 ทองขึ้น'
        ),

        # Employment events
        'unemployment': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (ว่างงานมากกว่าคาด) → เศรษฐกิจแย่ → 📈 ทองขึ้น (safe haven) | หากต่ำกว่าคาด → 📉 ทองลง'
        ),
        'unemployment claims': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (คนขอว่างงานมากขึ้น) → เศรษฐกิจแย่ → 📈 ทองขึ้น | หากต่ำกว่าคาด → 📉 ทองลง'
        ),
        'employment cost': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (ค่าจ้างสูง) → เงินเฟ้อเพิ่ม → เฟดอาจขึ้นดอกเบี้ย → 📉 ทองลง | หากต่ำกว่าคาด → 📈 ทองขึ้น'
        ),
        'non-farm': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (จ้างงานมากกว่าคาด) → เศรษฐกิจดี → USD แข็ง → 📉 ทองลง | หากต่ำกว่าคาด → 📈 ทองขึ้น'
        ),

        # Fed events
        'federal funds rate': (
            'NEUTRAL',
            f'{title_th}: หากขึ้นดอกเบี้ย → USD แข็ง → 📉 ทองลง | หากคงดอกเบี้ย → ทองอาจขึ้นหากสัญญาณ dovish 📈 | หากลดดอกเบี้ย → 📈 ทองขึ้นแรง'
        ),
        'fomc statement': (
            'NEUTRAL',
            f'{title_th}: หากสัญญาณ hawkish (ขึ้นดอกเบี้ย) → 📉 ทองลง | หาก dovish (คง/ลดดอกเบี้ย) → 📈 ทองขึ้น'
        ),
        'fomc press conference': (
            'NEUTRAL',
            f'{title_th}: หากประธานเฟดส่งสัญญาณขึ้นดอกเบี้ย → 📉 ทองลง | หากส่งสัญญาณคง/ลด → 📈 ทองขึ้น'
        ),

        # Consumer sentiment
        'consumer confidence': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (ผู้บริโภคมั่นใจ) → เศรษฐกิจดี → 📉 ทองลง | หากต่ำกว่าคาด → 📈 ทองขึ้น'
        ),
        'consumer sentiment': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast → เศรษฐกิจดี → 📉 ทองลง | หากต่ำกว่าคาด → 📈 ทองขึ้น'
        ),

        # Manufacturing/Services
        'ism manufacturing': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (ภาคการผลิตขยาย) → เศรษฐกิจดี → 📉 ทองลง | หากต่ำกว่าคาด → 📈 ทองขึ้น'
        ),
        'ism services': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (ภาคบริการขยาย) → เศรษฐกิจดี → 📉 ทองลง | หากต่ำกว่าคาด → 📈 ทองขึ้น'
        ),
        'pmi': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (ภาคการผลิต/บริการขยาย) → 📉 ทองลง | หากต่ำกว่าคาด → 📈 ทองขึ้น'
        ),
        'durable goods': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (สินค้าทนทานสั่งซื้อมาก) → เศรษฐกิจดี → 📉 ทองลง | หากต่ำกว่าคาด → 📈 ทองขึ้น'
        ),

        # Retail sales
        'retail sales': (
            'NEUTRAL',
            f'{title_th}: หาก Actual สูงกว่า Forecast (ขายปลีกสูง) → เศรษฐกิจดี → USD แข็ง → 📉 ทองลง | หากต่ำกว่าคาด → 📈 ทองขึ้น'
        ),
    }

    # Match event title to conditional template
    for keyword, (bias, reasoning) in conditional_templates.items():
        if keyword in title:
            return (bias, reasoning)

    # Default: neutral with generic conditional
    return (
        'NEUTRAL',
        f'{title_th}: หากข้อมูลออกมาดีกว่าคาด → USD แข็ง → 📉 ทองลง | หากแย่กว่าคาด → 📈 ทองขึ้น (safe haven)'
    )


def analyze_events(events: list, delay: float = 2.0) -> List[AnalysisResult]:
    """
    Analyze multiple news events with rate limiting delay between API calls.

    Args:
        events: List of EconomicEvent objects to analyze
        delay: Seconds to wait between API calls (default: 2.0)

    Returns list of AnalysisResult objects.
    """
    import time

    results = []
    for i, event in enumerate(events):
        try:
            result = analyze_event(event)
            results.append(result)
            # Rate limit: wait between API calls, but not after the last one
            if i < len(events) - 1:
                time.sleep(delay)
        except Exception as e:
            logger.error(f"Error analyzing event {event.title}: {e}")
    return results


def build_batch_prompt(events: list) -> str:
    """
    Build a single prompt for Gemini to analyze ALL events at once
    and provide an overall market summary.

    Uses CONDITIONAL analysis — explains scenarios, not predictions.
    """
    event_list = ""
    for i, event in enumerate(events, 1):
        # Include event date/time so Gemini knows when each event occurs
        time_info = ""
        if hasattr(event, 'event_datetime') and event.event_datetime:
            from datetime import datetime, timedelta
            now = datetime.utcnow() + timedelta(hours=7)  # ICT
            day_diff = (event.event_datetime.date() - now.date()).days
            thai_months = {
                1: 'ม.ค.', 2: 'ก.พ.', 3: 'มี.ค.', 4: 'เม.ย.',
                5: 'พ.ค.', 6: 'มิ.ย.', 7: 'ก.ค.', 8: 'ส.ค.',
                9: 'ก.ย.', 10: 'ต.ค.', 11: 'พ.ย.', 12: 'ธ.ค.'
            }
            time_str = event.event_datetime.strftime('%H:%M')
            month_thai = thai_months.get(event.event_datetime.month, str(event.event_datetime.month))
            if day_diff == 0:
                time_info = f"วันนี้ {time_str} ICT"
            elif day_diff == 1:
                time_info = f"พรุ่งนี้ {time_str} ICT"
            elif day_diff == -1:
                time_info = f"เมื่อวาน {time_str} ICT"
            else:
                time_info = f"{event.event_datetime.day} {month_thai} {time_str} ICT"
        elif event.date:
            time_info = f"วันที่ {event.date}"

        forecast_line = ""
        if event.forecast:
            forecast_line = f"Forecast: {event.forecast} | "
        if event.previous:
            forecast_line += f"Previous: {event.previous}"

        event_list += (
            f"{i}. {event.title} ({event.title_th}) | "
            f"ประเทศ: {event.country} | "
            f"ผลกระทบ: {event.impact} | "
            f"เวลา: {time_info or 'ไม่ระบุ'} | "
            f"{forecast_line}\n"
        )

    return f"""คุณเป็น News Analyst มืออาชีพสำหรับตลาดทองคำ (XAU/USD)

📰 ข่าวเศรษฐกิจที่ต้องวิเคราะห์ ({len(events)} รายการ):
{event_list}
🎯 งานของคุณ — ตอบ 2 ส่วน:

━━━ ส่วนที่ 1: สรุปภาพรวมตลาด ━━━
OVERALL_BIAS: [BULLISH/BEARISH/NEUTRAL]
GOLD_OUTLOOK: [สรุปแนวโน้มทองคำเป็นภาษาไทย 2-3 ประโยค บอกปัจจัยหลักที่ต้องจับตา]
KEY_TIMES: [ช่วงเวลาสำคัญที่ต้องระวัง เช่น "08:30 ICT CPI อาจทำให้ทองผันผวน" เป็นภาษาไทย]
USD_IMPACT: [อธิบายผลกระทบของค่าเงินดอลลาร์ต่อทองคำในช่วงนี้ เป็นภาษาไทย]
CONFIDENCE: [0-100] — ให้ต่ำถ้าข่าวสำคัญยังไม่ออก ให้สูงถ้าออกแล้ว

━━━ ส่วนที่ 2: วิเคราะห์แต่ละข่าว ━━━
สำหรับแต่ละข่าว ตอบในรูปแบบ:
EVENT: [ชื่อข่าว]
IMPACT: [HIGH/MEDIUM/LOW]
BIAS: [BULLISH/BEARISH/NEUTRAL]
CONFIDENCE: [0-100] — ข่าวที่ยังไม่ประกาศให้ 30-60%
REASONING: [เหตุผลสั้นๆ เป็นภาษาไทย]

⚠️ สำคัญ — กฎการวิเคราะห์:
1. ข่าวที่ยังไม่ได้ประกาศ: ให้วิเคราะห์แบบมีเงื่อนไข
   เช่น "CPI: หาก Actual สูงกว่า Forecast → USD แข็ง → ทองลง | หาก Actual ต่ำกว่า Forecast → ทองขึ้น"
2. ข่าวที่ประกาศแล้ว: วิเคราะห์จากผลจริง
3. อย่าฟันธงทิศทางก่อนตัวเลขออก — ให้ confidence ต่ำ (30-60%) สำหรับข่าวที่ยังไม่ประกาศ
4. ให้ confidence ต่างกันตามความไม่แน่นอน — ไม่ให้เท่ากันทุกรายการ

💡 ความสัมพันธ์หลัก:
- ทองคำมีความสัมพันธ์ผกผันกับดอลลาร์สหรัฐ (USD)
- CPI สูงกว่าคาด → USD แข็ง → ทองลง
- GDP ต่ำกว่าคาด → เศรษฐกิจแย่ → ทองขึ้น (safe haven)
- FOMC ขึ้นดอกเบี้ย → USD แข็ง → ทองลง
- การว่างงานสูงกว่าคาด → เศรษฐกิจแย่ → ทองขึ้น

⚠️ ห้ามพูดถึง: Technical indicators, ความเสี่ยง, การบริหารเงิน, ราคาเป้าหมาย"""


def analyze_events_batch(events: list) -> tuple:
    """
    Analyze ALL events in a single Gemini API call.
    Returns (list[AnalysisResult], MarketSummary) tuple.
    Falls back to per-event conditional analysis if batch fails.
    """
    if not events:
        empty_summary = MarketSummary(
            overall_bias='NEUTRAL',
            gold_outlook='ไม่มีข่าวสำคัญ',
            key_times='-',
            usd_impact='-',
            confidence=0,
        )
        return [], empty_summary

    prompt = build_batch_prompt(events)
    response = call_gemini(prompt, max_tokens=2000)

    if response:
        try:
            analyses, summary = parse_batch_response(response, events)
            if analyses:
                logger.info(f"Batch analysis: {len(analyses)} events, overall bias: {summary.overall_bias}")
                return analyses, summary
        except Exception as e:
            logger.error(f"Error parsing batch response: {e}")

    # Fallback: per-event conditional analysis
    logger.warning("Batch analysis failed, using per-event fallback")
    analyses = []
    for event in events:
        bias, reasoning = _fallback_bias_analysis(event)
        analyses.append(AnalysisResult(
            event_title=event.title,
            event_title_th=event.title_th,
            impact=event.impact.upper(),
            bias=bias,
            confidence=40,
            reasoning=reasoning,
            country=event.country,
            forecast=event.forecast,
            previous=event.previous,
            event_datetime=getattr(event, 'event_datetime', None),
        ))

    # Generate simple fallback summary
    bullish_count = sum(1 for a in analyses if a.bias == 'BULLISH')
    bearish_count = sum(1 for a in analyses if a.bias == 'BEARISH')

    if bullish_count > bearish_count:
        overall = 'BULLISH'
        outlook = f'สัปดาห์นี้มีข่าวเชิงบวกต่อทองคำมากกว่า ({bullish_count} vs {bearish_count}) — หากข้อมูลเศรษฐกิจออกมาแย่กว่าคาด ทองคำมีแนวโน้มขึ้น'
    elif bearish_count > bullish_count:
        overall = 'BEARISH'
        outlook = f'สัปดาห์นี้มีข่าวเชิงลบต่อทองคำมากกว่า ({bearish_count} vs {bullish_count}) — หากข้อมูลเศรษฐกิจออกมาดีกว่าคาด ทองคำมีแนวโน้มลง'
    else:
        overall = 'NEUTRAL'
        outlook = 'ข่าวมีทั้งเชิงบวกและเชิงลบ — ทิศทางทองคำขึ้นอยู่กับว่าข้อมูลจริงจะออกสูงกว่าหรือต่ำกว่าคาดการณ์'

    summary = MarketSummary(
        overall_bias=overall,
        gold_outlook=outlook,
        key_times='ดูรายละเอียดในแต่ละข่าวด้านล่าง',
        usd_impact='ข่าวเศรษฐกิจสหรัฐมีผลโดยตรงต่อราคาทองคำ — ข้อมูลที่ดีกว่าคาดทำให้ทองลง ข้อมูลที่แย่กว่าคาดทำให้ทองขึ้น',
        confidence=40,
    )

    return analyses, summary


def parse_batch_response(response: str, events: list) -> tuple:
    """
    Parse Gemini's batch response into list of AnalysisResult and MarketSummary.

    Returns (analyses, summary) tuple.
    """
    analyses = []
    summary = MarketSummary(
        overall_bias='NEUTRAL',
        gold_outlook='ไม่มีข้อมูล',
        key_times='-',
        usd_impact='-',
        confidence=0,
    )

    lines = response.strip().split('\n')
    current_analysis = {}
    parsing_summary = True  # Start with summary section

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check for section transition
        if 'ส่วนที่ 2' in line or 'วิเคราะห์แต่ละข่าว' in line or line.startswith('━━'):
            parsing_summary = False
            continue

        # Parse summary section
        if parsing_summary:
            if line.startswith('OVERALL_BIAS:'):
                summary.overall_bias = line.split(':', 1)[1].strip().upper()
            elif line.startswith('GOLD_OUTLOOK:'):
                summary.gold_outlook = line.split(':', 1)[1].strip()
            elif line.startswith('KEY_TIMES:'):
                summary.key_times = line.split(':', 1)[1].strip()
            elif line.startswith('USD_IMPACT:'):
                summary.usd_impact = line.split(':', 1)[1].strip()
            elif line.startswith('CONFIDENCE:'):
                conf_str = line.split(':', 1)[1].strip().replace('%', '')
                summary.confidence = int(conf_str) if conf_str.isdigit() else 50

        # Parse individual event analyses
        else:
            if line.startswith('EVENT:'):
                # Save previous analysis if complete
                if current_analysis and all(k in current_analysis for k in ['event_title', 'impact', 'bias', 'confidence', 'reasoning']):
                    analyses.append(AnalysisResult(**current_analysis))
                # Start new analysis
                event_title = line.split(':', 1)[1].strip()
                # Match to original event
                matched_event = None
                for evt in events:
                    if evt.title in event_title or event_title in evt.title:
                        matched_event = evt
                        break
                if not matched_event:
                    matched_event = events[0] if events else None

                current_analysis = {
                    'event_title': matched_event.title if matched_event else event_title,
                    'event_title_th': matched_event.title_th if matched_event else event_title,
                    'country': matched_event.country if matched_event else 'US',
                    'forecast': matched_event.forecast if matched_event else '',
                    'previous': matched_event.previous if matched_event else '',
                    'event_datetime': getattr(matched_event, 'event_datetime', None),
                }
            elif line.startswith('IMPACT:'):
                current_analysis['impact'] = line.split(':', 1)[1].strip().upper()
            elif line.startswith('BIAS:'):
                current_analysis['bias'] = line.split(':', 1)[1].strip().upper()
            elif line.startswith('CONFIDENCE:'):
                conf_str = line.split(':', 1)[1].strip().replace('%', '')
                current_analysis['confidence'] = int(conf_str) if conf_str.isdigit() else 50
            elif line.startswith('REASONING:'):
                current_analysis['reasoning'] = line.split(':', 1)[1].strip()

    # Don't forget the last analysis
    if current_analysis and all(k in current_analysis for k in ['event_title', 'impact', 'bias', 'confidence', 'reasoning']):
        analyses.append(AnalysisResult(**current_analysis))

    return analyses, summary


# ============================================================================
# EVENT IMPACT ENGINE INTEGRATION
# ============================================================================
# Integrates deterministic Event Impact Scoring Engine (Layers 1-4) with
# Gemini AI for Thai-language formatting. Uses rule-based scoring for
# accuracy, AI only for presentation.

def analyze_event_with_impact_engine(event) -> AnalysisResult:
    """
    Analyze a news event using the Event Impact Engine (deterministic)
    combined with Gemini for Thai formatting.

    This is the PREFERRED analysis method as it uses:
    - Layer 1: Event Classification (rule-based)
    - Layer 2: Surprise Calculation (mathematical)
    - Layer 3: Consensus Analysis (market data)
    - Layer 4: Event Logging (persistence)
    - AI (Gemini): Thai language formatting only

    Args:
        event: EconomicEvent object with title, forecast, previous, etc.

    Returns:
        AnalysisResult with impact, bias, confidence, and Thai reasoning
    """
    try:
        # Import here to avoid circular imports at module level
        import sys
        sys.path.insert(0, '/Users/kwanchanokroumsuk/goldnews')

        from src.core.event_impact_engine import EventImpactEngine, analyze_event_impact
        from src.core.event_classifier import classify_event
        from src.core.surprise_engine import EconomicDataPoint, calculate_surprise
        from src.core.consensus_engine import MarketConsensus
        from src.core.trade_decision_engine import evaluate_trade_signal

        # Initialize the impact engine
        engine = EventImpactEngine()

        # Step 1: Classify the event (Layer 1)
        classification = classify_event(event.title)

        # Step 2: Prepare data point for surprise calculation (Layer 2)
        # Parse forecast and actual values if available
        forecast_value = _parse_numeric_value(event.forecast)
        previous_value = _parse_numeric_value(event.previous)

        # Create data point
        data_point = EconomicDataPoint(
            event_name=event.title,
            category=classification.category.value,
            forecast=forecast_value,
            actual=None,  # Not released yet for pre-event analysis
            previous=previous_value,
            unit=_detect_unit(event.forecast) if event.forecast else '%'
        )

        # Step 3: Use the engine to get comprehensive impact assessment
        impact_result = analyze_event_impact(
            event_name=event.title,
            category=classification.category.value,
            forecast=forecast_value,
            actual=None,
            previous=previous_value,
            unit=data_point.unit
        )

        # Step 4: Convert composite score to bias and impact
        composite_score = impact_result.composite_score
        bias = _score_to_bias(composite_score)
        impact_level = _score_to_impact_level(abs(composite_score))

        # Step 5: Generate Thai reasoning using Gemini (AI for formatting only)
        thai_reasoning = _generate_thai_reasoning(
            event=event,
            classification=classification,
            composite_score=composite_score,
            bias=bias,
            impact_result=impact_result
        )

        # Calculate confidence based on available data
        confidence = _calculate_confidence(event, impact_result)

        # Step 6: Evaluate trade decision using No Trade Zone engine
        try:
            trade_rec = evaluate_trade_signal(
                composite_score=composite_score,
                surprise_result=impact_result.surprise_result,
                consensus_comparison=impact_result.consensus_comparison,
                category=classification.category,
            )
            trade_decision = trade_rec.to_dict()
        except Exception as e:
            logger.warning(f"Trade decision evaluation failed: {e}")
            trade_decision = None

        return AnalysisResult(
            event_title=event.title,
            event_title_th=event.title_th,
            impact=impact_level,
            bias=bias,
            confidence=confidence,
            reasoning=thai_reasoning,
            country=event.country,
            forecast=event.forecast,
            previous=event.previous,
            event_datetime=getattr(event, 'event_datetime', None),
            trade_decision=trade_decision,
        )

    except Exception as e:
        logger.error(f"Event Impact Engine analysis failed for {event.title}: {e}")
        # Fall back to original analyze_event function
        return analyze_event(event)


def _parse_numeric_value(value_str: Optional[str]) -> Optional[float]:
    """Parse a numeric value from string, handling various formats."""
    if not value_str:
        return None

    # Remove common suffixes and prefixes
    cleaned = value_str.strip()
    for suffix in ['%', 'K', 'M', 'B', 'k', 'm', 'b']:
        cleaned = cleaned.replace(suffix, '')

    # Handle ranges (take the middle value)
    if '-' in cleaned and cleaned.replace('-', '').replace('.', '').isdigit():
        parts = cleaned.split('-')
        try:
            return (float(parts[0]) + float(parts[1])) / 2
        except (ValueError, IndexError):
            pass

    # Try direct conversion
    try:
        return float(cleaned)
    except ValueError:
        return None


def _detect_unit(value_str: Optional[str]) -> str:
    """Detect the unit from a value string."""
    if not value_str:
        return '%'

    value_str = value_str.strip().upper()
    if '%' in value_str:
        return '%'
    elif 'K' in value_str:
        return 'K'
    elif 'M' in value_str:
        return 'M'
    elif 'B' in value_str:
        return 'B'
    else:
        return 'index'


def _score_to_bias(score: float) -> str:
    """Convert composite score (-10 to +10) to bias direction."""
    if score >= 2:
        return 'BULLISH'
    elif score <= -2:
        return 'BEARISH'
    else:
        return 'NEUTRAL'


def _score_to_impact_level(abs_score: float) -> str:
    """Convert absolute score to impact level."""
    if abs_score >= 5:
        return 'HIGH'
    elif abs_score >= 2:
        return 'MEDIUM'
    else:
        return 'LOW'


def _calculate_confidence(event, impact_result) -> int:
    """Calculate confidence score (0-100) based on data availability."""
    confidence = 50  # Base confidence

    # Increase confidence if we have forecast data
    if event.forecast:
        confidence += 15

    # Increase confidence if we have previous data
    if event.previous:
        confidence += 10

    # Increase confidence based on impact result confidence
    if hasattr(impact_result, 'confidence_score'):
        confidence = int((confidence + impact_result.confidence_score) / 2)

    # Cap at 70 for pre-event analysis (no actual data yet)
    return min(confidence, 70)


def _generate_thai_reasoning(event, classification, composite_score, bias, impact_result) -> str:
    """
    Generate Thai-language reasoning using Gemini.
    AI is used ONLY for language formatting, not for decision-making.
    """
    try:
        # Build a factual prompt with all deterministic data
        prompt = f"""คุณเป็น News Analyst มืออาชีพสำหรับตลาดทองคำ

📰 ข่าวที่ต้องวิเคราะห์:
- ชื่อข่าว: {event.title} ({event.title_th})
- ประเทศ: {event.country}
- หมวดหมู่: {classification.category.value}
- ค่าคาดการณ์ (Forecast): {event.forecast or 'ไม่มี'}
- ค่าก่อนหน้า (Previous): {event.previous or 'ไม่มี'}

📊 ผลการคำนวณแบบ Deterministic (ไม่ใช้ AI):
- คะแนนผลกระทบรวม: {composite_score:.1f}/10 ({bias})
- ความสัมพันธ์กับทองคำ: {'บวก' if classification.gold_correlation > 0 else 'ลบ' if classification.gold_correlation < 0 else 'เป็นกลาง'}
- ปัจจัยสำคัญ: {', '.join(classification.key_drivers[:3]) if classification.key_drivers else 'ไม่ระบุ'}

🎯 งานของคุณ:
เขียนคำอธิบายสั้นๆ 1-2 ประโยค เป็นภาษาไทย อธิบายว่า:
1. ข่าวนี้มีผลกระทบต่อทองคำอย่างไร (ใช้รูปแบบ "หาก Actual > Forecast → ... หาก Actual < Forecast → ...")
2. ทำไมถึงได้คะแนน {composite_score:.1f}/10

⚠️ กฎสำคัญ:
- อย่าฟันธงทิศทางก่อนตัวเลขออก
- ใช้รูปแบบ "หาก...→..." เสมอสำหรับข่าวที่ยังไม่ประกาศ
- อธิบายเหตุผลสั้นๆ กระชับ

💡 ตัวอย่าง:
"CPI: หาก Actual สูงกว่า Forecast → เงินเฟ้อสูง → เฟดขึ้นดอกเบี้ย → 📉 ทองลง | หาก Actual ต่ำกว่า Forecast → 📈 ทองขึ้น"

📤 ตอบเฉพาะคำอธิบาย 1-2 ประโยคเท่านั้น:"""

        # Call Gemini for Thai formatting only
        response = call_gemini(prompt, max_tokens=200)

        if response:
            # Clean up the response
            reasoning = response.strip()
            # Remove common prefixes
            for prefix in ['REASONING:', 'คำอธิบาย:', 'ผลการวิเคราะห์:']:
                if reasoning.startswith(prefix):
                    reasoning = reasoning[len(prefix):].strip()
            return reasoning

    except Exception as e:
        logger.error(f"Error generating Thai reasoning: {e}")

    # Fallback to deterministic template-based reasoning
    return _fallback_thai_reasoning(event, classification, bias)


def _fallback_thai_reasoning(event, classification, bias) -> str:
    """Generate Thai reasoning using templates when Gemini fails."""
    category_templates = {
        'inflation': f"{event.title_th}: หาก Actual สูงกว่า Forecast → เงินเฟ้อสูง → เฟดขึ้นดอกเบี้ย → 📉 ทองลง | หากต่ำกว่า → 📈 ทองขึ้น",
        'labor': f"{event.title_th}: หาก Actual สูงกว่า Forecast (จ้างงานดี) → USD แข็ง → 📉 ทองลง | หากต่ำกว่า → 📈 ทองขึ้น",
        'fed_policy': f"{event.title_th}: หากขึ้นดอกเบี้ย → USD แข็ง → 📉 ทองลง | หากคง/ลด → 📈 ทองขึ้น",
        'growth': f"{event.title_th}: หาก Actual สูงกว่า Forecast (เศรษฐกิจดี) → USD แข็ง → 📉 ทองลง | หากต่ำกว่า → 📈 ทองขึ้น",
        'consumer': f"{event.title_th}: หาก Actual สูงกว่า Forecast → ผู้บริโภคมั่นใจ → USD แข็ง → 📉 ทองลง | หากต่ำกว่า → 📈 ทองขึ้น",
        'manufacturing': f"{event.title_th}: หาก Actual สูงกว่า Forecast → ภาคการผลิตขยาย → 📉 ทองลง | หากต่ำกว่า → 📈 ทองขึ้น",
        'yields': f"{event.title_th}: หากผลตอบแทนพันธบัตรสูงขึ้น → USD แข็ง → 📉 ทองลง | หากลง → 📈 ทองขึ้น",
        'geopolitics': f"{event.title_th}: ความไม่แน่นอนทางการเมือง → ทองเป็น safe haven → 📈 ทองขึ้น",
    }

    category = classification.category.value
    return category_templates.get(
        category,
        f"{event.title_th}: หากข้อมูลดีกว่าคาด → USD แข็ง → 📉 ทองลง | หากแย่กว่าคาด → 📈 ทองขึ้น"
    )


def analyze_events_with_impact_engine(events: list, delay: float = 2.0) -> List[AnalysisResult]:
    """
    Analyze multiple events using the Event Impact Engine with rate limiting.

    Args:
        events: List of EconomicEvent objects
        delay: Seconds to wait between API calls for Thai formatting

    Returns list of AnalysisResult objects.
    """
    import time

    results = []
    for i, event in enumerate(events):
        try:
            result = analyze_event_with_impact_engine(event)
            results.append(result)
            # Rate limit: wait between API calls for Thai formatting, but not after the last one
            if i < len(events) - 1:
                time.sleep(delay)
        except Exception as e:
            logger.error(f"Error analyzing event {event.title} with impact engine: {e}")
            # Fall back to standard analysis
            try:
                result = analyze_event(event)
                results.append(result)
            except Exception as e2:
                logger.error(f"Fallback analysis also failed: {e2}")
    return results
