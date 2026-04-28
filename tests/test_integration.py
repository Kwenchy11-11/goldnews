"""Integration tests for the full news cycle."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta


def test_full_news_cycle_with_mock_data():
    """Test the complete news cycle with mocked external APIs."""
    from news_fetcher import EconomicEvent, PolymarketData
    from analyzer import AnalysisResult
    from formatter import format_daily_summary

    now = datetime.utcnow() + timedelta(hours=7)  # ICT

    # Mock analysis results with event_datetime
    analyses = [
        AnalysisResult(
            event_title='CPI m/m',
            event_title_th='ดัชนีราคาผู้บริโภค',
            impact='HIGH',
            bias='NEUTRAL',
            confidence=50,
            reasoning='CPI: หาก Actual > Forecast → USD แข็ง → ทองลง | หาก Actual < Forecast → ทองขึ้น',
            country='USD',
            forecast='0.3%',
            previous='0.4%',
            event_datetime=now + timedelta(hours=1),  # Future event
        ),
    ]

    # Mock Polymarket data
    markets = [
        PolymarketData(
            title='Will gold close above $3000 this week?',
            probability=0.68,
            volume=150000,
            url='https://polymarket.com/event/gold-above-3000',
        ),
    ]

    # Format the message
    message = format_daily_summary(analyses, markets)

    # Verify message contains all expected sections
    assert 'CPI' in message
    assert 'ดัชนีราคาผู้บริโภค' in message
    assert 'HIGH' in message or 'สูง' in message  # Impact level
    assert 'กำลังจะมา' in message  # Upcoming event label
    assert 'Polymarket' in message
    assert '68' in message  # Polymarket probability
    assert 'Actual' in message or 'คาด' in message  # Conditional analysis


def test_full_news_cycle_no_events():
    """Test the news cycle when there are no events."""
    from formatter import format_daily_summary

    message = format_daily_summary([])

    assert 'ไม่มี' in message or 'ข่าว' in message


def test_message_length_within_telegram_limit():
    """Verify formatted messages are within Telegram's 4096 character limit."""
    from analyzer import AnalysisResult
    from formatter import format_daily_summary
    from datetime import datetime, timedelta

    now = datetime.utcnow() + timedelta(hours=7)

    # Create multiple analyses to test longer messages
    analyses = []
    for i in range(10):
        analyses.append(AnalysisResult(
            event_title=f'Test Event {i}',
            event_title_th=f'เหตุการณ์ทดสอบ {i}',
            impact='MEDIUM',
            bias='NEUTRAL',
            confidence=50,
            reasoning='เหตุผลทดสอบสำหรับเหตุการณ์นี้',
            country='USD',
            forecast='',
            previous='',
            event_datetime=now + timedelta(hours=i+1),
        ))

    message = format_daily_summary(analyses)

    # Telegram limit is 4096 characters
    assert len(message) <= 4096, f"Message too long: {len(message)} characters"
