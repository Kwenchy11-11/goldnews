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

    # Add disclaimer at the bottom
    message += (
        f"<i>⚠️ ข้อมูลนี้เป็นการคาดการณ์ ไม่ใช่คำแนะนำในการลงทุน</i>\n"
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
        f"   💡 {html.escape(analysis.reasoning)}\n"
    )

    # Add trade decision if available
    if hasattr(analysis, 'trade_decision') and analysis.trade_decision:
        decision = analysis.trade_decision
        decision_label = decision.get('decision_label', '')
        confidence = decision.get('confidence', 0)
        position_size = decision.get('position_size', 'none')
        risk = decision.get('risk_level', 'unknown')

        # Translate position size and risk to Thai
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

        # Only show actionable decisions or explicitly state NO_TRADE
        actionable = decision.get('actionable', False)
        if actionable:
            message += f"   📊 สัญญาณ: {decision_label} (ความมั่นใจ {confidence:.0f}%)\n"
            message += f"      ขนาด: {size_thai} | ความเสี่ยง: {risk_thai}\n"
        else:
            message += f"   ⚪ สัญญาณ: {decision_label} (ไม่เข้าเทรด)\n"

        # Add warnings if any
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


# ============================================================================
# EVENT IMPACT ENGINE FORMATTERS
# ============================================================================
# Formatters for displaying Event Impact Engine results in Telegram messages.
# Shows deterministic impact scores, layer breakdowns, and alert recommendations.


def get_impact_strength_emoji(score: float) -> str:
    """Return emoji based on composite impact score (-10 to +10)."""
    if score >= 7:
        return "🔴📈"  # Strong bullish
    elif score >= 4:
        return "🟠📈"  # Moderate bullish
    elif score >= 2:
        return "🟡📈"  # Weak bullish
    elif score > -2:
        return "⚪"     # Neutral
    elif score > -4:
        return "🟡📉"  # Weak bearish
    elif score > -7:
        return "🟠📉"  # Moderate bearish
    else:
        return "🔴📉"  # Strong bearish


def get_alert_priority_emoji(priority: str) -> str:
    """Return emoji for alert priority level."""
    return {
        'immediate': '🚨',
        'high': '⚠️',
        'normal': 'ℹ️',
        'low': '💡',
    }.get(priority.lower(), 'ℹ️')


def format_impact_score_bar(score: float, width: int = 20) -> str:
    """
    Create a visual bar representation of impact score (-10 to +10).
    
    Args:
        score: Composite score from -10 to +10
        width: Width of the bar in characters
        
    Returns:
        String representing the score visually
    """
    # Normalize score to 0-width range
    normalized = (score + 10) / 20  # Now 0 to 1
    filled = int(normalized * width)
    
    bar = "[" + "█" * filled + "░" * (width - filled) + "]"
    return f"{bar} {score:+.1f}"


def format_event_impact_result(result) -> str:
    """
    Format an EventImpactResult for Telegram display.
    
    Shows composite score, alert recommendation, and layer breakdown.
    
    Args:
        result: EventImpactResult from the impact engine
        
    Returns:
        Formatted Thai message string
    """
    from src.core.event_impact_engine import EventImpactResult
    
    impact_emoji = get_impact_strength_emoji(result.composite_score)
    alert_emoji = get_alert_priority_emoji(result.alert_priority)
    
    # Convert category to Thai
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
    
    # Overall gold impact to Thai
    impact_thai = {
        'strong-bullish': 'ทองขึ้นแรงมาก',
        'bullish': 'ทองขึ้น',
        'neutral': 'เป็นกลาง',
        'bearish': 'ทองลง',
        'strong-bearish': 'ทองลงแรงมาก',
    }.get(result.overall_gold_impact, result.overall_gold_impact)
    
    # Build message
    message = (
        f"{impact_emoji} <b>{result.event_name}</b>\n"
        f"{'─' * 30}\n"
        f"📂 หมวดหมู่: {category_thai}\n"
        f"🎯 ผลกระทบ: {impact_thai}\n"
        f"📊 คะแนนรวม: {format_impact_score_bar(result.composite_score)}\n"
        f"🎲 ความมั่นใจ: {int(result.confidence_score * 100)}%\n"
    )
    
    # Add alert recommendation if significant
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
    """
    Format a detailed layer-by-layer breakdown of impact calculation.
    
    Args:
        result: EventImpactResult from the impact engine
        
    Returns:
        Formatted message showing each layer's contribution
    """
    message = (
        f"🔍 <b>รายละเอียดการคำนวณ</b>\n"
        f"{'─' * 30}\n"
    )
    
    # Layer 1: Classification
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
    
    # Layer 2: Surprise
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
    
    # Layer 3: Consensus
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
    
    # Composite calculation
    message += (
        f"🎯 <b>คะแนนรวม</b>\n"
        f"   {format_impact_score_bar(result.composite_score)}\n"
        f"   น้ำหนัก: Surprise 70% | Base 20% | Consensus 10%\n"
    )
    
    return message


def format_pre_event_alert(event_name: str, forecast, previous, category: str,
                           event_time: datetime = None) -> str:
    """
    Format a pre-event alert message (15 minutes before event).
    
    Args:
        event_name: Name of the economic event
        forecast: Forecast value
        previous: Previous value
        category: Event category
        event_time: When the event will be released
        
    Returns:
        Formatted pre-event alert message
    """
    time_str = ""
    if event_time:
        time_str = f"⏰ เวลา: {event_time.strftime('%H:%M')} น.\n"
    
    # Get category in Thai
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
    """
    Format a post-event alert message with actual results.
    
    Args:
        event_name: Name of the economic event
        actual: Actual released value
        forecast: Forecast value
        previous: Previous value
        composite_score: Calculated impact score
        alert_message: Optional custom alert message
        
    Returns:
        Formatted post-event alert message
    """
    impact_emoji = get_impact_strength_emoji(composite_score)
    
    # Determine impact description
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
    
    # Show actual vs forecast
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
    """
    Format a daily summary of all impact analyses.
    
    Args:
        results: List of EventImpactResult objects
        date: Date for the summary (defaults to today)
        
    Returns:
        Formatted daily summary message
    """
    if not results:
        return "📋 ไม่มีข่าวสำคัญวันนี้"
    
    now = date or get_now_ict()
    day_thai = config.DAY_THAI.get(now.weekday(), '')
    
    # Calculate summary stats
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
    
    # Show each event
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
