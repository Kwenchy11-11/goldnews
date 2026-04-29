"""
Formatter Module
===============
Creates Thai-language Telegram messages with emoji indicators.
Formats analysis results, event details, and Polymarket sentiment
into readable Telegram messages.

Key design: Shows conditional analysis (if Actual > Forecast → ...)
instead of definitive direction. Separates Released vs Upcoming events.
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

    # Collect all event dates
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

    year_be = start_date.year + 543  # Buddhist year

    if start_date == end_date:
        date_str = fmt_date(start_date)
    else:
        date_str = f"{fmt_date(start_date)} - {fmt_date(end_date)}"

    update_time = now.strftime('%H:%M')
    return f"📅 ข่าววันที่ {date_str} {year_be} (อัปเดต {update_time} น.)"


def _format_realtime_news_section(items: List[RealTimeNewsItem], max_items: int = 5) -> str:
    """
    Format real-time news items into a Thai message section.
    """
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
    """
    Format Polymarket data into a sentiment summary section.
    """
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

    Groups by category (Fed, Gold, Inflation, etc.) with:
    - Emoji indicators
    - Thai translations
    - Beginner explanations
    - Probability percentages

    Args:
        predictions: List of PredictionMarket objects
        max_per_category: Max markets to show per category

    Returns:
        Formatted HTML string for Telegram
    """
    if not predictions:
        return ""

    # Group by category
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

    # Show categories in priority order
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
            # Format outcomes
            outcomes_str = _format_outcomes_thai(market.outcomes, market.category)
            message += f"• {market.question_th}\n"
            message += f"{outcomes_str}\n"

        message += "\n"

    # Add beginner explanation at the bottom
    message += (
        f"💡 <b>อ่านยังไง?</b>\n"
        f"Polymarket คือตลาดที่คนทั่วโลกมา \"เดิมพัน\" ว่าเหตุการณ์ต่างๆ จะเกิดขึ้นหรือไม่\n"
        f"• ถ้าคนส่วนใหญ่เชื่อว่า Fed จะขึ้นดอกเบี้ย → % ของ \"ขึ้น\" จะสูง\n"
        f"• ถ้า % สูง = ตลาดมองว่ามีโอกาสเกิดสูง\n"
        f"• ทองคำมัก <b>ขึ้น</b> เมื่อ Fed ลดดอกเบี้ย หรือเศรษฐกิจแย่\n"
        f"• ทองคำมัก <b>ลง</b> เมื่อ Fed ขึ้นดอกเบี้ย หรือเศรษฐกิจดี\n"
    )

    return message


def _format_outcomes_thai(outcomes: List[dict], category: str) -> str:
    """Format market outcomes with Thai labels and probability bars."""
    lines = []
    for outcome in outcomes[:3]:  # Max 3 outcomes
        name = outcome.get('name', '')
        price = outcome.get('price', 0)
        pct = price * 100

        # Translate outcome name
        name_th = _translate_outcome_name(name, category)

        # Visual bar
        bar_filled = int(pct / 10)
        bar_empty = 10 - bar_filled
        bar = '█' * bar_filled + '░' * bar_empty

        # Color indicator
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


def format_market_summary(summary: MarketSummary) -> str:
    """
    Format the overall market summary section.
    """
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
    """
    Format a single event analysis item.

    For released events: shows what happened
    For upcoming events: shows conditional analysis (if Actual > Forecast → ...)
    """
    impact_emoji = get_impact_emoji(analysis.impact)
    bias_emoji = get_bias_emoji(analysis.bias)
    impact_thai = config.IMPACT_THAI.get(analysis.impact, analysis.impact)
    bias_thai = config.BIAS_THAI.get(analysis.bias, analysis.bias)
    status_emoji = get_status_emoji(is_released)

    # Show event time
    time_str = ""
    if hasattr(analysis, 'event_datetime') and analysis.event_datetime:
        time_str = format_event_time(analysis)

    # Status label
    status_label = "ประกาศแล้ว" if is_released else "กำลังจะมา"

    message = (
        f"{impact_emoji} <b>{index}. {analysis.event_title}</b> {status_emoji} [{status_label}]\n"
        f"   ชื่อไทย: {analysis.event_title_th}\n"
        f"   🏳️ ประเทศ: {analysis.country}\n"
    )
    if time_str:
        message += f"   ⏰ เวลา: {time_str}\n"

    # Add forecast/previous if available
    if analysis.forecast:
        message += f"   📊 ค่าคาดการณ์: {analysis.forecast}\n"
    if analysis.previous:
        message += f"   📈 ค่าก่อนหน้า: {analysis.previous}\n"

    message += (
        f"   ผลกระทบ: {impact_thai}\n"
        f"   💡 {html.escape(analysis.reasoning)}\n\n"
    )

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

    # Separate events into "released" (past) and "upcoming" (future)
    released_events = []
    upcoming_events = []

    for analysis in analyses:
        if hasattr(analysis, 'event_datetime') and analysis.event_datetime:
            if analysis.event_datetime <= now:
                released_events.append(analysis)
            else:
                upcoming_events.append(analysis)
        else:
            # If no datetime info, treat as upcoming
            upcoming_events.append(analysis)

    # Header with date range
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

    # Market summary section (if available) - only show once at top
    if summary:
        message += format_market_summary(summary)

    # Clashing events warning - detect multiple HIGH events at same time
    if upcoming_events:
        time_groups = {}
        for a in upcoming_events:
            if hasattr(a, 'event_datetime') and a.event_datetime:
                # Group by date + hour (30-min window)
                dt = a.event_datetime
                key = dt.strftime('%Y-%m-%d %H:') + ('00' if dt.minute < 30 else '30')
                if key not in time_groups:
                    time_groups[key] = []
                time_groups[key].append(a)

        # Find clashes (2+ HIGH events in same window)
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

    # Released events section
    if released_events:
        message += f"✅ <b>ประกาศแล้ว</b>\n{'─' * 30}\n\n"
        for i, analysis in enumerate(released_events, 1):
            message += format_event_item(analysis, i, is_released=True)

    # Upcoming events section
    if upcoming_events:
        message += f"⏳ <b>กำลังจะมา</b>\n{'─' * 30}\n\n"
        for i, analysis in enumerate(upcoming_events, 1):
            message += format_event_item(analysis, i, is_released=False)

    # Real-time news section
    if realtime_news:
        message += _format_realtime_news_section(realtime_news, max_items=5)

    # Polymarket section (legacy format)
    if markets:
        message += format_polymarket_summary(markets)

    # Polymarket Predictions section (new format with beginner explanations)
    if predictions:
        message += format_predictions_section(predictions)

    # Footer
    message += f"\n{'─' * 30}\n<i>🔄 ตรวจสอบใหม่ใน {config.CHECK_INTERVAL} นาที</i>"

    return message
