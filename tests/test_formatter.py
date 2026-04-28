"""Tests for formatter module."""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from dataclasses import dataclass


def test_format_polymarket_summary_creates_sentiment_section():
    """format_polymarket_summary should create Polymarket sentiment section."""
    from formatter import format_polymarket_summary
    from news_fetcher import PolymarketData

    markets = [
        PolymarketData(
            title='Will gold close above $3000 this week?',
            probability=0.68,
            volume=150000,
            url='https://polymarket.com/event/gold-above-3000',
        ),
    ]

    message = format_polymarket_summary(markets)

    assert 'Polymarket' in message or 'polymarket' in message.lower()
    assert '68' in message  # 68% probability


def test_format_daily_summary_combines_events():
    """format_daily_summary should combine multiple analyses into one message."""
    from formatter import format_daily_summary
    from analyzer import AnalysisResult

    analyses = [
        AnalysisResult(
            event_title='CPI m/m',
            event_title_th='ดัชนีราคาผู้บริโภค',
            impact='HIGH',
            bias='BEARISH',
            confidence=75,
            reasoning='เงินเฟ้อสูง',
            country='USD',
            forecast='0.3%',
            previous='0.4%',
            event_datetime=datetime.utcnow() + timedelta(hours=1),
        ),
        AnalysisResult(
            event_title='FOMC',
            event_title_th='การประชุม FOMC',
            impact='HIGH',
            bias='BULLISH',
            confidence=80,
            reasoning='เฟดลดดอกเบี้ย',
            country='USD',
            forecast='',
            previous='',
            event_datetime=datetime.utcnow() + timedelta(hours=2),
        ),
    ]

    message = format_daily_summary(analyses)

    assert 'CPI' in message
    assert 'FOMC' in message
    assert 'ทองคำ' in message or 'ทอง' in message


def test_format_empty_analysis():
    """format_daily_summary should handle empty analysis list."""
    from formatter import format_daily_summary

    message = format_daily_summary([])

    assert 'ไม่มี' in message or 'ข่าว' in message


def test_get_impact_emoji():
    """get_impact_emoji should return correct emoji for impact levels."""
    from formatter import get_impact_emoji

    assert get_impact_emoji('HIGH') == '🔴'
    assert get_impact_emoji('MEDIUM') == '🟡'
    assert get_impact_emoji('LOW') == '🟢'


def test_get_bias_emoji():
    """get_bias_emoji should return correct emoji for bias directions."""
    from formatter import get_bias_emoji

    assert get_bias_emoji('BULLISH') == '📈'
    assert get_bias_emoji('BEARISH') == '📉'
    assert get_bias_emoji('NEUTRAL') == '⚪'


def test_format_event_time_shows_ict():
    """format_event_time should show full Thai date/time format."""
    from formatter import format_event_time
    from datetime import datetime, timedelta

    now = datetime.utcnow() + timedelta(hours=7)  # ICT

    # Today's event (use noon ICT to avoid midnight rollover)
    event = MagicMock()
    event.event_datetime = now.replace(hour=12, minute=0, second=0, microsecond=0)
    result = format_event_time(event)
    assert 'วันนี้' in result
    assert 'เวลา' in result
    assert '12:00' in result
    assert 'น.' in result


def test_format_daily_summary_shows_released_vs_upcoming():
    """format_daily_summary should separate released and upcoming events."""
    from formatter import format_daily_summary
    from analyzer import AnalysisResult
    from datetime import datetime, timedelta

    now = datetime.utcnow() + timedelta(hours=7)  # ICT

    analyses = [
        AnalysisResult(
            event_title='Past Event',
            event_title_th='เหตุการณ์ที่ผ่านมา',
            impact='HIGH',
            bias='NEUTRAL',
            confidence=50,
            reasoning='ประกาศแล้ว',
            country='USD',
            forecast='',
            previous='',
            event_datetime=now - timedelta(hours=1),  # Past
        ),
        AnalysisResult(
            event_title='Future Event',
            event_title_th='เหตุการณ์ที่กำลังจะมา',
            impact='HIGH',
            bias='NEUTRAL',
            confidence=50,
            reasoning='ยังไม่ประกาศ',
            country='USD',
            forecast='',
            previous='',
            event_datetime=now + timedelta(hours=2),  # Future
        ),
    ]

    message = format_daily_summary(analyses)

    assert 'ประกาศแล้ว' in message
    assert 'กำลังจะมา' in message
