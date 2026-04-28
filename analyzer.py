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
    Parse Gemini's batch response into individual analyses and market summary.
    Returns (list[AnalysisResult], MarketSummary).
    """
    lines = response.strip().split('\n')

    # Parse market summary section
    overall_bias = 'NEUTRAL'
    gold_outlook = ''
    key_times = ''
    usd_impact = ''
    summary_confidence = 50

    # Parse individual event sections
    event_analyses = {}
    current_event = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Summary section
        if 'OVERALL_BIAS:' in line:
            overall_bias = line.split('OVERALL_BIAS:')[1].strip().upper()
            if overall_bias not in ('BULLISH', 'BEARISH', 'NEUTRAL'):
                overall_bias = 'NEUTRAL'
        elif 'GOLD_OUTLOOK:' in line:
            gold_outlook = line.split('GOLD_OUTLOOK:')[1].strip()
        elif 'KEY_TIMES:' in line:
            key_times = line.split('KEY_TIMES:')[1].strip()
        elif 'USD_IMPACT:' in line:
            usd_impact = line.split('USD_IMPACT:')[1].strip()
        elif 'CONFIDENCE:' in line and not current_event:
            conf_str = line.split('CONFIDENCE:')[1].strip().replace('%', '')
            try:
                summary_confidence = int(conf_str) if conf_str.isdigit() else 50
            except ValueError:
                summary_confidence = 50

        # Individual event section
        elif 'EVENT:' in line:
            event_name = line.split('EVENT:')[1].strip()
            # Match to original event
            for orig in events:
                if orig.title.lower() in event_name.lower() or event_name.lower() in orig.title.lower():
                    current_event = orig.title
                    event_analyses[current_event] = {
                        'impact': orig.impact.upper(),
                        'bias': 'NEUTRAL',
                        'confidence': 50,
                        'reasoning': '',
                    }
                    break
        elif current_event and current_event in event_analyses:
            if 'IMPACT:' in line:
                impact = line.split('IMPACT:')[1].strip().upper()
                if impact in ('HIGH', 'MEDIUM', 'LOW'):
                    event_analyses[current_event]['impact'] = impact
            elif 'BIAS:' in line:
                bias = line.split('BIAS:')[1].strip().upper()
                if bias in ('BULLISH', 'BEARISH', 'NEUTRAL'):
                    event_analyses[current_event]['bias'] = bias
            elif 'CONFIDENCE:' in line:
                conf_str = line.split('CONFIDENCE:')[1].strip().replace('%', '')
                try:
                    event_analyses[current_event]['confidence'] = int(conf_str) if conf_str.isdigit() else 50
                except ValueError:
                    pass
            elif 'REASONING:' in line:
                event_analyses[current_event]['reasoning'] = line.split('REASONING:')[1].strip()

    # Build AnalysisResult list matching original events order
    analyses = []
    for event in events:
        if event.title in event_analyses:
            a = event_analyses[event.title]
            analyses.append(AnalysisResult(
                event_title=event.title,
                event_title_th=event.title_th,
                impact=a['impact'],
                bias=a['bias'],
                confidence=max(0, min(100, a['confidence'])),
                reasoning=a['reasoning'] or f'วิเคราะห์อัตโนมัติ: {event.title_th}',
                country=event.country,
                forecast=event.forecast,
                previous=event.previous,
                event_datetime=getattr(event, 'event_datetime', None),
            ))
        else:
            # Event not found in response, use fallback
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

    # Build MarketSummary
    summary = MarketSummary(
        overall_bias=overall_bias,
        gold_outlook=gold_outlook or 'ไม่สามารถวิเคราะห์ได้',
        key_times=key_times or 'ดูรายละเอียดในแต่ละข่าว',
        usd_impact=usd_impact or 'ข่าวเศรษฐกิจสหรัฐมีผลต่อทองคำ',
        confidence=max(0, min(100, summary_confidence)),
    )

    return analyses, summary
