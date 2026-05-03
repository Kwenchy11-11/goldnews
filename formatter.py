
"""
Formatter Module
===============
Creates Thai-language Telegram messages with emoji indicators.
Formats analysis results, event details, and Polymarket sentiment
into readable Telegram messages.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
import html

import config
from analyzer import AnalysisResult, MarketSummary
from news_fetcher import PolymarketData
from realtime_news import RealTimeNewsItem
from polymarket_predictions import PredictionMarket, CATEGORY_INFO

logger = logging.getLogger('goldnews')

# ICT offset
ICT_OFFSET = timedelta(hours=7)


def get_now_ict() -> datetime:
    """Get current time in ICT."""
    return datetime.utcnow() + ICT_OFFSET


def format_actionable_alert(
    event_name: str,
    actual,
    forecast,
    previous,
    composite_score: float,
    confidence: float,
    trade_decision: str,
    reasoning: str = None,
    alert_priority: str = "normal"
) -> str:
    """
    Format an actionable trading alert with clear bias and instructions.
    
    This format focuses on helping users make trading decisions rather than
    just showing scores. Includes entry timing, invalidation levels, and
    risk management guidance.
    
    Args:
        event_name: Name of the economic event
        actual: Actual released value
        forecast: Forecast value
        previous: Previous value
        composite_score: Impact score (-10 to +10)
        confidence: Confidence level (0-100)
        trade_decision: SELL_GOLD, BUY_GOLD, WAIT, NO_TRADE
        reasoning: Thai reasoning text
        alert_priority: immediate, high, normal, low
        
    Returns:
        Formatted actionable alert message
    """
    import html
    
    # Determine bias and direction
    if composite_score >= 5.5:
        bias = "SELL GOLD"
        bias_thai = "🔴 ขายทองคำ"
        direction_emoji = "🔴"
        price_action = "ลง"
    elif composite_score >= 2:
        bias = "SELL GOLD"
        bias_thai = "🟠 ขายทองคำ (อ่อน)"
        direction_emoji = "🟠"
        price_action = "ลง"
    elif composite_score <= -5.5:
        bias = "BUY GOLD"
        bias_thai = "🟢 ซื้อทองคำ"
        direction_emoji = "🟢"
        price_action = "ขึ้น"
    elif composite_score <= -2:
        bias = "BUY GOLD"
        bias_thai = "🟡 ซื้อทองคำ (อ่อน)"
        direction_emoji = "🟡"
        price_action = "ขึ้น"
    else:
        bias = "NEUTRAL"
        bias_thai = "⚪ เฝ้าดู"
        direction_emoji = "⚪"
        price_action = "ไม่มีทิศทางชัดเจน"
    
    # Alert urgency
    urgency_emoji = "🚨" if alert_priority in ["immediate", "high"] else "📢"
    
    # Calculate surprise deviation
    surprise_text = ""
    if actual and forecast:
        try:
            actual_val = float(str(actual).replace('%', '').replace('K', ''))
            forecast_val = float(str(forecast).replace('%', '').replace('K', ''))
            deviation = ((actual_val - forecast_val) / abs(forecast_val)) * 100 if forecast_val != 0 else 0
            
            if abs(deviation) >= 20:
                surprise_text = "สูงมาก" if deviation > 0 else "ต่ำมาก"
            elif abs(deviation) >= 10:
                surprise_text = "สูงกว่าคาด" if deviation > 0 else "ต่ำกว่าคาด"
            elif abs(deviation) >= 5:
                surprise_text = "สูงเล็กน้อย" if deviation > 0 else "ต่ำเล็กน้อย"
            else:
                surprise_text = "ใกล้เคียงคาด"
        except:
            surprise_text = "ไม่สามารถคำนวณได้"
    
    # Build the actionable alert
    message = f"""
{urgency_emoji} <b>GOLD NEWS IMPACT ALERT</b> {urgency_emoji}
{'─' * 35}

<b>📰 ข่าว:</b> {event_name}
<b>📊 ผลจริง:</b> {actual or 'N/A'}
<b>📈 คาดการณ์:</b> {forecast or 'N/A'}
<b>⚡ Surprise:</b> {surprise_text}

{'─' * 35}
<b>🎯 ผลต่อทองคำ:</b>
{bias_thai}
<b>🎚️ Confidence:</b> {confidence:.0f}/100
<b>📊 Impact Level:</b> {get_impact_level_from_score(abs(composite_score))}

{'─' * 35}
<b>💡 เหตุผล:</b>
{reasoning or _generate_default_reasoning(event_name, composite_score, actual, forecast)}

{'─' * 35}
<b>📋 คำแนะนำระบบ:</b>
"""
    
    # Add actionable advice based on decision - v0.2 uses bias/scenario language
    # NOT "เข้า Buy/Sell ทันที" - this is pre-production
    if "SELL" in bias or trade_decision in ["sell", "strong_sell"]:
        message += f"""<b>📊 Gold Bias:</b> BEARISH (ทองมีแนวโน้มลง)
<b>📌 Scenario:</b> หาก USD แข็งค่าต่อเนื่อง → ทองมีแนวโน้มย่อตัว
<b>⏰ Timing:</b> WAIT 1-3 นาที หลัง spike เพื่อยืนยันทิศทาง
<b>🛑 Invalidation:</b> ถ้าราคากลับมายืนเหนือ pre-news high → bias ไม่valid
<b>⚠️ Note:</b> นี่คือ bias จากข้อมูล ไม่ใช่สัญญาณเทรด (v{config.VERSION})
"""
    elif "BUY" in bias or trade_decision in ["buy", "strong_buy"]:
        message += f"""<b>📊 Gold Bias:</b> BULLISH (ทองมีแนวโน้มขึ้น)
<b>📌 Scenario:</b> หาก USD อ่อนค่าต่อเนื่อง → ทองมีแนวโน้มปรับตัวขึ้น
<b>⏰ Timing:</b> WAIT 1-3 นาที หลัง spike เพื่อยืนยันทิศทาง
<b>🛑 Invalidation:</b> ถ้าราคาหลุดต่ำกว่า pre-news low → bias ไม่valid
<b>⚠️ Note:</b> นี่คือ bias จากข้อมูล ไม่ใช่สัญญาณเทรด (v{config.VERSION})
"""
    elif trade_decision == "wait":
        message += f"""<b>📊 Gold Bias:</b> UNCLEAR (ทิศทางไม่ชัดเจน)
<b>📌 Scenario:</b> รอดู confirmation ก่อนตัดสินใจ
<b>💡 Reason:</b> ข้อมูลยังไม่ชัดเจนพอหรือมีความขัดแย้ง
<b>📍 Action:</b> เฝ้าดูราคา ไม่เข้า position ในตอนนี้
<b>⚠️ Note:</b> v{config.VERSION} - ยังอยู่ในช่วงทดสอบ
"""
    else:
        message += f"""<b>📊 Gold Bias:</b> NEUTRAL (ไม่มี bias ชัดเจน)
<b>💡 Reason:</b> คะแนนไม่ผ่านเกณฑ์ minimum threshold
<b>📍 Action:</b> ข้ามข่าวนี้ รอโอกาสถัดไป
<b>⚠️ Note:</b> v{config.VERSION} - ยังอยู่ในช่วงทดสอบ
"""
    
    message += f"\n{'─' * 35}"
    
    return message


def get_impact_level_from_score(score: float) -> str:
    """Get impact level description from score."""
    if score >= 7:
        return "สูงมาก (High)"
    elif score >= 5:
        return "สูง (High)"
    elif score >= 3:
        return "ปานกลาง (Medium)"
    else:
        return "ต่ำ (Low)"


def _generate_default_reasoning(event_name: str, composite_score: float, actual, forecast) -> str:
    """Generate default Thai reasoning based on event and score."""
    if composite_score >= 5:
        return f"• ข้อมูล {event_name} แข็งแกร่งกว่าคาด → กดดันทองคำ\n• USD อาจแข็งค่า → ทองลง\n• Surprise score สูงพอสำหรับ post-event alert"
    elif composite_score >= 2:
        return f"• ข้อมูล {event_name} ดีกว่าคาดเล็กน้อย\n• มีแรงกดดันต่อทองคำ แต่ไม่แรงมาก\n• ควรระวังความผันผวน"
    elif composite_score <= -5:
        return f"• ข้อมูล {event_name} อ่อนแอกว่าคาด → หนุนทองคำ\n• USD อาจอ่อนค่า → ทองขึ้น\n• Surprise score สูงพอสำหรับ post-event alert"
    elif composite_score <= -2:
        return f"• ข้อมูล {event_name} อ่อนกว่าคาดเล็กน้อย\n• มีแรงหนุนทองคำ แต่ไม่แรงมาก\n• ควรระวังความผันผวน"
    else:
        return f"• ข้อมูล {event_name} ใกล้เคียงคาด\n• ไม่มีผลกระทบรุนแรงต่อทองคำ\n• แนะนำให้งดเทรด"


def get_impact_emoji(impact: str) -> str:
    """Return emoji for impact level."""
    return {
        'HIGH': '🔴',
        'MEDIUM': '🟡',
        'LOW': '🟢',
    }.get(impact.upper(), '⚪')


def get_bias_emoji(bias: str) -> str:
    """Return emoji for bias direction."""
    return {
        'BULLISH': '📈',
        'BEARISH': '📉',
        'NEUTRAL': '⚪',
    }.get(bias.upper(), '⚪')


def get_status_emoji(is_released: bool) -> str:
    """Return emoji for event status."""
    return '✅' if is_released else '⏳'


def format_event_time(event) -> str:
    """
    Format event date/time for display (event_datetime is already in ICT).

    Always shows full Thai date to avoid confusion:
    - "พฤหัสบดีที่ 30 เมษายน 2569 เวลา 01:00 น."
    - "ศุกร์ที่ 1 พฤษภาคม 2569 เวลา 19:30 น."
    - "เวลาไม่ระบุ" if no time available
    """
    if not event.event_datetime:
        return "เวลาไม่ระบุ"

    event_dt = event.event_datetime

    thai_days = {
        0: 'จันทร์', 1: 'อังคาร', 2: 'พุธ',
        3: 'พฤหัสบดี', 4: 'ศุกร์', 5: 'เสาร์', 6: 'อาทิตย์'
    }
    thai_months = {
        1: 'มกราคม', 2: 'กุมภาพันธ์', 3: 'มีนาคม', 4: 'เมษายน',
        5: 'พฤษภาคม', 6: 'มิถุนายน', 7: 'กรกฎาคม', 8: 'สิงหาคม',
        9: 'กันยายน', 10: 'ตุลาคม', 11: 'พฤศจิกายน', 12: 'ธันวาคม'
    }

    time_str = event_dt.strftime('%H:%M')
    day_name = thai_days.get(event_dt.weekday(), '')
    month_thai = thai_months.get(event_dt.month, str(event_dt.month))
    year_be = event_dt.year + 543  # Buddhist year

    return f"{day_name}ที่ {event_dt.day} {month_thai} {year_be} เวลา {time_str} น."


def format_date_range(analyses: List[AnalysisResult], now: datetime) -> str:
    """
    Format a date range header showing the span of events.
    E.g., "ข่าววันที่ 29 เมษายน - 30 เมษายน 2569 (อัปเดต 23:05 น.)"
    """
    thai_months = {
        1: 'มกราคม', 2: 'กุมภาพันธ์', 3: 'มีนาคม', 4: 'เมษายน',
        5: 'พฤษภาคม', 6: 'มิถุนายน', 7: 'กรกฎาคม', 8: 'สิงหาคม',
        9: 'กันยายน', 10: 'ตุลาคม', 11: 'พฤศจิกายน', 12: 'ธันวาคม'
    }

    event_dates = set()
    for a in analyses:
        if hasattr(a, 'event_datetime') and a.event_datetime:
            event_dates.add(a.event_datetime.date())

    if not event_dates:
        return f"📅 {now.strftime('%d/%m/%Y')} ({now.strftime('%H:%M')} น.)"

    sorted_dates = sorted(event_dates)
    start_date = sorted_dates[0]
    end_date = sorted_dates[-1]

    def fmt_date(d):
        month_thai = thai_months.get(d.month, str(d.month))
        return f"{d.day} {month_thai}"

    year_be = start_date.year + 543

    if start_date == end_date:
        date_str = fmt_date(start_date)
    else:
        date_str = f"{fmt_date(start_date)} - {fmt_date(end_date)}"

    update_time = now.strftime('%H:%M')
    return f"📅 ข่าววันที่ {date_str} {year_be} (อัปเดต {update_time} น.)"


def _format_realtime_news_section(items: List[RealTimeNewsItem], max_items: int = 5) -> str:
    """Format real-time news items into a Thai message section."""
    if not items:
        return ""

    message = "\n📰 <b>ข่าวสดล่าสุด:</b>\n"

    for i, item in enumerate(items[:max_items], 1):
        time_label = ""
        if item.published:
            now = get_now_ict()
            diff = now - item.published
            if diff.total_seconds() < 3600:
                mins = int(diff.total_seconds() / 60)
                time_label = f" ({mins} นาทีที่แล้ว)"
            elif diff.total_seconds() < 86400:
                hours = int(diff.total_seconds() / 3600)
                time_label = f" ({hours} ชม.ที่แล้ว)"
            else:
                time_label = f" ({item.published.strftime('%d/%m %H:%M')})"

        message += f"• {html.escape(item.title)}{time_label}\n"
        if item.summary:
            summary_clean = html.escape(item.summary[:150])
            message += f"  {summary_clean}...\n"
        message += "\n"

    return message


def format_polymarket_summary(markets: List[PolymarketData]) -> str:
    """Format Polymarket data into a sentiment summary section."""
    if not markets:
        return ""

    message = "\n🎲 <b>Polymarket Sentiment:</b>\n"

    for market in markets[:3]:
        prob_pct = market.probability * 100
        message += f"• {market.title}\n"
        message += f"  ทองคำขึ้น: {prob_pct:.0f}% | ทองคำลง: {100 - prob_pct:.0f}%\n"

    return message


def format_predictions_section(predictions: List[PredictionMarket],
                                max_per_category: int = 2) -> str:
    """
    Format Polymarket prediction markets into a beginner-friendly Thai section.
    """
    if not predictions:
        return ""

    by_category = {}
    for p in predictions:
        if p.category not in by_category:
            by_category[p.category] = []
        by_category[p.category].append(p)

    message = (
        f"\n🎯 <b>ตลาดคาดการณ์อะไรอยู่? (Polymarket)</b>\n"
        f"{'─' * 30}\n"
        f"<i>ตัวเลข % = ความน่าจะเป็นที่ตลาดคาดการณ์</i>\n"
        f"<i>🟢 = มีโอกาสสูง | 🟡 = เป็นไปได้ | 🔴 = โอกาสน้อย</i>\n\n"
    )

    category_order = ['fed', 'gold', 'inflation', 'employment', 'economy']

    for category in category_order:
        if category not in by_category:
            continue

        cat_markets = by_category[category][:max_per_category]
        cat_info = CATEGORY_INFO.get(category, {})
        cat_emoji = cat_info.get('emoji', '📌')
        cat_label = cat_info.get('label_th', category.capitalize())

        message += f"{cat_emoji} <b>{cat_label}</b>\n"

        for market in cat_markets:
            outcomes_str = _format_outcomes_thai(market.outcomes, market.category)
            message += f"• {market.question_th}\n"
            message += f"{outcomes_str}\n"

        message += "\n"

    message += f"<i>⚠️ ข้อมูลนี้เป็นการคาดการณ์ ไม่ใช่คำแนะนำในการลงทุน</i>\n"

    return message


def _format_outcomes_thai(outcomes: List[dict], category: str) -> str:
    """Format market outcomes with Thai labels and probability bars."""
    lines = []
    for outcome in outcomes[:3]:
        name = outcome.get('name', '')
        price = outcome.get('price', 0)
        pct = price * 100

        name_th = _translate_outcome_name(name, category)

        bar_filled = int(pct / 10)
        bar_empty = 10 - bar_filled
        bar = '█' * bar_filled + '░' * bar_empty

        if pct >= 60:
            indicator = '🟢'
        elif pct >= 40:
            indicator = '🟡'
        else:
            indicator = '🔴'

        lines.append(f"  {indicator} {name_th} {bar} {pct:.0f}%")

    return '\n'.join(lines)


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


def format_market_summary(summary: MarketSummary) -> str:
    """Format the overall market summary section."""
    bias_emoji = get_bias_emoji(summary.overall_bias)
    bias_thai = config.BIAS_THAI.get(summary.overall_bias, summary.overall_bias)

    message = (
        f"📊 <b>สรุปภาพรวมตลาดทองคำ</b>\n"
        f"{'─' * 30}\n"
        f"{bias_emoji} แนวโน้มรวม: <b>{bias_thai}</b> (มั่นใจ {summary.confidence}%)\n"
        f"🥇 {summary.gold_outlook}\n\n"
        f"⏰ <b>ช่วงเวลาสำคัญ:</b>\n{summary.key_times}\n\n"
        f"💵 <b>ผลกระทบ USD:</b>\n{summary.usd_impact}\n"
        f"{'─' * 30}\n\n"
    )

    return message


def format_event_item(analysis: AnalysisResult, index: int, is_released: bool) -> str:
    """Format a single event analysis item."""
    impact_emoji = get_impact_emoji(analysis.impact)
    bias_emoji = get_bias_emoji(analysis.bias)
    impact_thai = config.IMPACT_THAI.get(analysis.impact, analysis.impact)
    bias_thai = config.BIAS_THAI.get(analysis.bias, analysis.bias)
    status_emoji = get_status_emoji(is_released)

    time_str = ""
    if hasattr(analysis, 'event_datetime') and analysis.event_datetime:
        time_str = format_event_time(analysis)

    status_label = "ประกาศแล้ว" if is_released else "กำลังจะมา"

    message = (
        f"{impact_emoji} <b>{index}. {analysis.event_title}</b> {status_emoji} [{status_label}]\n"
        f"   ชื่อไทย: {analysis.event_title_th}\n"
        f"   🏳️ ประเทศ: {analysis.country}\n"
    )
    if time_str:
        message += f"   ⏰ เวลา: {time_str}\n"

    if analysis.forecast:
        message += f"   📊 ค่าคาดการณ์: {analysis.forecast}\n"
    if analysis.previous:
        message += f"   📈 ค่าก่อนหน้า: {analysis.previous}\n"

    message += (
        f"   ผลกระทบ: {impact_thai}\n"
        f"   💡 {html.escape(analysis.reasoning)}\n"
    )

    if hasattr(analysis, 'trade_decision') and analysis.trade_decision:
        decision = analysis.trade_decision
        decision_label = decision.get('decision_label', '')
        confidence = decision.get('confidence', 0)
        position_size = decision.get('position_size', 'none')
        risk = decision.get('risk_level', 'unknown')

        size_thai = {
            'full': 'เต็มขนาด',
            'half': 'ครึ่งขนาด',
            'quarter': '1/4 ขนาด',
            'none': 'ไม่เข้า'
        }.get(position_size, position_size)

        risk_thai = {
            'low': 'ต่ำ',
            'medium': 'ปานกลาง',
            'high': 'สูง'
        }.get(risk, risk)

        actionable = decision.get('actionable', False)
        if actionable:
            message += f"   📊 สัญญาณ: {decision_label} (ความมั่นใจ {confidence:.0f}%)\n"
            message += f"      ขนาด: {size_thai} | ความเสี่ยง: {risk_thai}\n"
        else:
            message += f"   ⚪ สัญญาณ: {decision_label} (ไม่เข้าเทรด)\n"

        warnings = decision.get('warnings', [])
        if warnings:
            for warning in warnings:
                message += f"      ⚠️  {warning}\n"

    message += "\n"

    return message


def format_daily_summary(analyses: List[AnalysisResult],
                          markets: Optional[List[PolymarketData]] = None,
                          summary: Optional[MarketSummary] = None,
                          realtime_news: Optional[List[RealTimeNewsItem]] = None,
                          predictions: Optional[List[PredictionMarket]] = None) -> str:
    """
    Format a complete daily summary message combining all analyses.

    Separates events into "Released" (ประกาศแล้ว) and "Upcoming" (กำลังจะมา).
    Shows conditional analysis for upcoming events.
    Includes real-time news section if available.
    Includes Polymarket predictions section with beginner-friendly explanations.
    """
    now = get_now_ict()
    day_thai = config.DAY_THAI.get(now.weekday(), '')

    if not analyses:
        return (
            f"📋 <b>สรุปข่าวทองคำ</b>\n"
            f"📅 {now.strftime('%d/%m/%Y')} ({day_thai})\n\n"
            f"ไม่มีข่าวสำคัญที่มีผลต่อทองคำในขณะนี้\n\n"
            f"<i>บอทจะตรวจสอบอีกครั้งใน {config.CHECK_INTERVAL} นาที</i>"
        )

    released_events = []
    upcoming_events = []

    for analysis in analyses:
        if hasattr(analysis, 'event_datetime') and analysis.event_datetime:
            if analysis.event_datetime <= now:
                released_events.append(analysis)
            else:
                upcoming_events.append(analysis)
        else:
            upcoming_events.append(analysis)

    message = (
        f"📋 <b>สรุปข่าวทองคำ</b>\n"
        f"{format_date_range(analyses, now)}\n"
    )

    if released_events and upcoming_events:
        message += f"📊 ประกาศแล้ว {len(released_events)} | กำลังจะมา {len(upcoming_events)} รายการ\n"
    elif released_events:
        message += f"📊 ประกาศแล้ว {len(released_events)} รายการ\n"
    else:
        message += f"📊 กำลังจะมา {len(upcoming_events)} รายการ\n"

    message += f"{'─' * 30}\n\n"

    if summary:
        message += format_market_summary(summary)

    if upcoming_events:
        time_groups = {}
        for a in upcoming_events:
            if hasattr(a, 'event_datetime') and a.event_datetime:
                dt = a.event_datetime
                key = dt.strftime('%Y-%m-%d %H:') + ('00' if dt.minute < 30 else '30')
                if key not in time_groups:
                    time_groups[key] = []
                time_groups[key].append(a)

        clashes = []
        for key, events in sorted(time_groups.items()):
            high_events = [e for e in events if e.impact.upper() == 'HIGH']
            if len(high_events) >= 2:
                time_str = format_event_time(high_events[0])
                names = [e.event_title_th for e in high_events]
                clashes.append((time_str, names))

        if clashes:
            message += "⚠️ <b>คำเตือน: ข่าวชนกัน!</b>\n"
            for time_str, names in clashes:
                message += f"   {time_str}: {' + '.join(names)}\n"
            message += "   🚨 ระวังความผันผวนรุนแรง (V-Shape) — ตัวเลขอาจขัดแย้งกันเอง\n\n"

    if released_events:
        message += f"✅ <b>ประกาศแล้ว</b>\n{'─' * 30}\n\n"
        for i, analysis in enumerate(released_events, 1):
            message += format_event_item(analysis, i, is_released=True)

    if upcoming_events:
        message += f"⏳ <b>กำลังจะมา</b>\n{'─' * 30}\n\n"
        for i, analysis in enumerate(upcoming_events, 1):
            message += format_event_item(analysis, i, is_released=False)

    if realtime_news:
        message += _format_realtime_news_section(realtime_news, max_items=5)

    if markets:
        message += format_polymarket_summary(markets)

    if predictions:
        message += format_predictions_section(predictions)

    message += f"\n{'─' * 30}\n<i>🔄 ตรวจสอบใหม่ใน {config.CHECK_INTERVAL} นาที</i>"

    return message


def get_impact_strength_emoji(score: float) -> str:
    """Return emoji based on composite impact score (-10 to +10)."""
    if score >= 7:
        return "🔴📈"
    elif score >= 4:
        return "🟠📈"
    elif score >= 2:
        return "🟡📈"
    elif score > -2:
        return "⚪"
    elif score > -4:
        return "🟡📉"
    elif score > -7:
        return "🟠📉"
    else:
        return "🔴📉"


def get_alert_priority_emoji(priority: str) -> str:
    """Return emoji for alert priority level."""
    return {
        'immediate': '🚨',
        'high': '⚠️',
        'normal': 'ℹ️',
        'low': '💡',
    }.get(priority.lower(), 'ℹ️')


def format_impact_score_bar(score: float, width: int = 20) -> str:
    """Create a visual bar representation of impact score (-10 to +10)."""
    normalized = (score + 10) / 20
    filled = int(normalized * width)

    bar = "[" + "█" * filled + "░" * (width - filled) + "]"
    return f"{bar} {score:+.1f}"


def format_event_impact_result(result) -> str:
    """Format an EventImpactResult for Telegram display."""
    impact_emoji = get_impact_strength_emoji(result.composite_score)
    alert_emoji = get_alert_priority_emoji(result.alert_priority)

    category_thai = {
        'inflation': 'เงินเฟ้อ',
        'labor': 'ตลาดแรงงาน',
        'fed_policy': 'นโยบายเฟด',
        'growth': 'การเติบโต',
        'yields': 'ผลตอบแทนพันธบัตร',
        'geopolitics': 'ภูมิรัฐศาสตร์',
        'consumer': 'ผู้บริโภค',
        'manufacturing': 'การผลิต',
        'unknown': 'อื่นๆ',
    }.get(result.category.value if hasattr(result.category, 'value') else str(result.category), 'อื่นๆ')

    impact_thai = {
        'strong-bullish': 'ทองขึ้นแรงมาก',
        'bullish': 'ทองขึ้น',
        'neutral': 'เป็นกลาง',
        'bearish': 'ทองลง',
        'strong-bearish': 'ทองลงแรงมาก',
    }.get(result.overall_gold_impact, result.overall_gold_impact)

    message = (
        f"{impact_emoji} <b>{result.event_name}</b>\n"
        f"{'─' * 30}\n"
        f"📂 หมวดหมู่: {category_thai}\n"
        f"🎯 ผลกระทบ: {impact_thai}\n"
        f"📊 คะแนนรวม: {format_impact_score_bar(result.composite_score)}\n"
        f"🎲 ความมั่นใจ: {int(result.confidence_score * 100)}%\n"
    )

    if result.should_alert:
        priority_thai = {
            'immediate': 'ทันที',
            'high': 'สูง',
            'normal': 'ปกติ',
            'low': 'ต่ำ',
        }.get(result.alert_priority, result.alert_priority)

        message += f"\n{alert_emoji} <b>แนะนำให้แจ้งเตือน</b> (ระดับ: {priority_thai})\n"
        if result.alert_message:
            message += f"💬 {html.escape(result.alert_message)}\n"

    message += f"{'─' * 30}\n"
    return message


def format_impact_layer_breakdown(result) -> str:
    """Format a detailed layer-by-layer breakdown of impact calculation."""
    message = (
        f"🔍 <b>รายละเอียดการคำนวณ</b>\n"
        f"{'─' * 30}\n"
    )

    if hasattr(result, 'impact_score') and result.impact_score:
        impact = result.impact_score
        message += (
            f"📂 <b>Layer 1: จัดหมวดหมู่</b>\n"
            f"   หมวด: {impact.category.value if hasattr(impact.category, 'value') else impact.category}\n"
            f"   คะแนนพื้นฐาน: {impact.base_impact_score}/10\n"
            f"   สัมพันธ์ทองคำ: {'📈' if impact.gold_correlation > 0 else '📉' if impact.gold_correlation < 0 else '➡️'}\n"
        )
        if impact.key_drivers:
            drivers = ', '.join(impact.key_drivers[:3])
            message += f"   ปัจจัย: {drivers}\n"
        message += "\n"

    if hasattr(result, 'surprise_result') and result.surprise_result:
        surprise = result.surprise_result
        message += (
            f"🎲 <b>Layer 2: คำนวณ Surprise</b>\n"
            f"   คะแนน: {surprise.surprise_score:+.1f}/10\n"
            f"   ความเบี่ยงเบน: {surprise.deviation_pct:+.1f}%\n"
            f"   ทิศทาง: {'📈' if surprise.direction == 'higher' else '📉' if surprise.direction == 'lower' else '➡️'}\n"
            f"   ความสำคัญ: {surprise.significance}\n"
        )
        if surprise.gold_impact_estimate:
            est = surprise.gold_impact_estimate
            message += f"   ประมาณการทอง: {est.get('direction', 'neutral')} ({est.get('strength', 'unknown')})\n"
        message += "\n"

    if hasattr(result, 'consensus_comparison') and result.consensus_comparison:
        consensus = result.consensus_comparison
        message += (
            f"👥 <b>Layer 3: ความเห็นตลาด</b>\n"
            f"   สัญญาณ: {consensus.trading_signal}\n"
        )
        if hasattr(consensus, 'divergence_score'):
            message += f"   ความแตกต่าง: {consensus.divergence_score:.2f}\n"
        if hasattr(consensus, 'agreement_level'):
            message += f"   ระดับเห็นพ้อง: {consensus.agreement_level}\n"
        message += "\n"

    message += (
        f"🎯 <b>คะแนนรวม</b>\n"
        f"   {format_impact_score_bar(result.composite_score)}\n"
        f"   น้ำหนัก: Surprise 70% | Base 20% | Consensus 10%\n"
    )

    return message


def format_pre_event_alert(event_name: str, forecast, previous, category: str,
                           event_time: datetime = None) -> str:
    """Format a pre-event alert message (15 minutes before event)."""
    time_str = ""
    if event_time:
        time_str = f"⏰ เวลา: {event_time.strftime('%H:%M')} น.\n"

    category_thai = {
        'inflation': 'เงินเฟ้อ',
        'labor': 'ตลาดแรงงาน',
        'fed_policy': 'นโยบายเฟด',
        'growth': 'การเติบโต',
        'yields': 'ผลตอบแทนพันธบัตร',
        'geopolitics': 'ภูมิรัฐศาสตร์',
        'consumer': 'ผู้บริโภค',
        'manufacturing': 'การผลิต',
        'unknown': 'อื่นๆ',
    }.get(category, category)

    message = (
        f"⏳ <b>ข่าวสำคัญกำลังจะประกาศ</b> (อีก ~15 นาที)\n"
        f"{'─' * 30}\n"
        f"📰 {event_name}\n"
        f"📂 หมวดหมู่: {category_thai}\n"
        f"{time_str}"
    )

    if forecast:
        message += f"📊 คาดการณ์: {forecast}\n"
    if previous:
        message += f"📈 ก่อนหน้า: {previous}\n"

    message += (
        f"\n⚠️ <b>เตรียมรับมือผลกระทบต่อทองคำ</b>\n"
        f"{'─' * 30}"
    )

    return message


def format_post_event_alert(event_name: str, actual, forecast, previous,
                            composite_score: float, alert_message: str = None) -> str:
    """Format a post-event alert message with actual results."""
    impact_emoji = get_impact_strength_emoji(composite_score)

    if composite_score >= 4:
        impact_desc = "📈 มีผลบวกต่อทองคำ"
    elif composite_score >= 2:
        impact_desc = "📈 มีผลบวกเล็กน้อยต่อทองคำ"
    elif composite_score > -2:
        impact_desc = "➡️ ผลกระทบเป็นกลาง"
    elif composite_score > -4:
        impact_desc = "📉 มีผลลบเล็กน้อยต่อทองคำ"
    else:
        impact_desc = "📉 มีผลลบต่อทองคำ"

    message = (
        f"🚨 <b>ข่าวสำคัญประกาศแล้ว!</b>\n"
        f"{'─' * 30}\n"
        f"{impact_emoji} <b>{event_name}</b>\n"
        f"{'─' * 30}\n"
    )

    if actual and forecast:
        try:
            actual_val = float(str(actual).replace('%', '').replace('K', ''))
            forecast_val = float(str(forecast).replace('%', '').replace('K', ''))

            if actual_val > forecast_val:
                vs_str = f"📈 สูงกว่าคาด ({actual} vs {forecast})"
            elif actual_val < forecast_val:
                vs_str = f"📉 ต่ำกว่าคาด ({actual} vs {forecast})"
            else:
                vs_str = f"➡️ ตรงคาด ({actual})"

            message += f"{vs_str}\n"
        except (ValueError, TypeError):
            message += f"📊 Actual: {actual} | Forecast: {forecast}\n"
    else:
        if actual:
            message += f"📊 Actual: {actual}\n"
        if forecast:
            message += f"📊 Forecast: {forecast}\n"

    if previous:
        message += f"📈 Previous: {previous}\n"

    message += (
        f"\n{impact_desc}\n"
        f"📊 คะแนนผลกระทบ: {format_impact_score_bar(composite_score)}\n"
    )

    if alert_message:
        message += f"\n💬 {html.escape(alert_message)}\n"

    message += f"{'─' * 30}"

    return message


def format_daily_impact_summary(results: list, date: datetime = None) -> str:
    """Format a daily summary of all impact analyses."""
    if not results:
        return "📋 ไม่มีข่าวสำคัญวันนี้"

    now = date or get_now_ict()
    day_thai = config.DAY_THAI.get(now.weekday(), '')

    high_impact = [r for r in results if abs(r.composite_score) >= 5]
    bullish = [r for r in results if r.composite_score >= 2]
    bearish = [r for r in results if r.composite_score <= -2]

    message = (
        f"📊 <b>สรุปผลกระทบข่าวเศรษฐกิจ</b>\n"
        f"📅 {now.strftime('%d/%m/%Y')} ({day_thai})\n"
        f"{'─' * 30}\n"
        f"📈 กดดันขึ้น: {len(bullish)} รายการ\n"
        f"📉 กดดันลง: {len(bearish)} รายการ\n"
        f"🔴 ผลกระทบสูง: {len(high_impact)} รายการ\n"
        f"{'─' * 30}\n\n"
    )

    for i, result in enumerate(results, 1):
        impact_emoji = get_impact_strength_emoji(result.composite_score)
        alert_emoji = get_alert_priority_emoji(result.alert_priority) if result.should_alert else ""

        category_thai = {
            'inflation': 'เงินเฟ้อ',
            'labor': 'แรงงาน',
            'fed_policy': 'เฟด',
            'growth': 'เติบโต',
            'yields': 'พันธบัตร',
            'geopolitics': 'ภูมิรัฐศาสตร์',
            'consumer': 'ผู้บริโภค',
            'manufacturing': 'การผลิต',
            'unknown': 'อื่นๆ',
        }.get(
            result.category.value if hasattr(result.category, 'value') else str(result.category),
            'อื่นๆ'
        )

        message += (
            f"{i}. {impact_emoji} {result.event_name}"
            f"{alert_emoji}\n"
            f"   [{category_thai}] คะแนน: {result.composite_score:+.1f}\n"
        )

    message += f"\n{'─' * 30}"
    return message
