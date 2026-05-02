"""
Tests for Event Impact Engine scheduler integration.

This module tests the pre-event and post-event alert scheduling functionality.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
from unittest.mock import Mock, patch

import pytest


@dataclass
class MockEvent:
    """Mock economic event for testing."""
    title: str
    impact: str
    country: str = 'US'
    forecast: Optional[str] = None
    previous: Optional[str] = None
    actual: Optional[str] = None
    event_datetime: Optional[datetime] = None


class TestSchedulerImpactIntegration:
    """Test suite for scheduler Event Impact Engine integration."""

    def test_get_event_datetime_with_datetime(self):
        """Test extracting datetime from event with event_datetime."""
        from scheduler import _get_event_datetime

        event_dt = datetime.now()
        event = MockEvent(title="CPI", impact="HIGH", event_datetime=event_dt)

        result = _get_event_datetime(event)
        assert result == event_dt

    def test_get_event_datetime_without_datetime(self):
        """Test extracting datetime from event without event_datetime."""
        from scheduler import _get_event_datetime

        event = MockEvent(title="CPI", impact="HIGH")

        result = _get_event_datetime(event)
        assert result is None

    def test_parse_value_numeric(self):
        """Test parsing numeric values."""
        from scheduler import _parse_value

        assert _parse_value("3.2%") == 3.2
        assert _parse_value("250K") == 250.0
        assert _parse_value("1.5") == 1.5
        assert _parse_value(3.2) == 3.2

    def test_parse_value_none(self):
        """Test parsing None value."""
        from scheduler import _parse_value

        assert _parse_value(None) is None

    def test_parse_value_invalid(self):
        """Test parsing invalid value."""
        from scheduler import _parse_value

        assert _parse_value("N/A") is None
        assert _parse_value("") is None

    @patch('config.ENABLE_PRE_EVENT_ALERTS', True)
    @patch('config.ENABLE_IMPACT_ENGINE', True)
    @patch('config.PRE_EVENT_ALERT_MINUTES', 15)
    @patch('scheduler.classify_event')
    def test_check_pre_event_alerts_finds_upcoming(self, mock_classify):
        """Test that pre-event alerts finds upcoming high-impact events."""
        from scheduler import check_pre_event_alerts

        # Mock the classification
        mock_classify.return_value = Mock(category=Mock(value='inflation'))

        # Create events - one happening in 10 minutes (should alert)
        now = datetime.now()
        events = [
            MockEvent(
                title="CPI y/y",
                impact="HIGH",
                event_datetime=now + timedelta(minutes=10)
            ),
            MockEvent(
                title="FOMC",
                impact="LOW",  # Should not alert
                event_datetime=now + timedelta(minutes=10)
            ),
        ]

        # Should find the HIGH impact event
        with patch('telegram_bot.send_message_with_retry', return_value=True):
            alerts = check_pre_event_alerts(events)

        # Only HIGH impact events trigger alerts
        assert alerts == 1

    @patch('config.ENABLE_PRE_EVENT_ALERTS', True)
    @patch('config.ENABLE_IMPACT_ENGINE', True)
    def test_check_pre_event_alerts_skips_past_events(self):
        """Test that pre-event alerts skips events in the past."""
        from scheduler import check_pre_event_alerts

        now = datetime.now()
        events = [
            MockEvent(
                title="CPI y/y",
                impact="HIGH",
                event_datetime=now - timedelta(minutes=10)  # Past event
            ),
        ]

        # Should not alert on past events
        with patch('telegram_bot.send_message_with_retry', return_value=True):
            alerts = check_pre_event_alerts(events)

        assert alerts == 0

    @patch('config.ENABLE_PRE_EVENT_ALERTS', True)
    @patch('config.ENABLE_IMPACT_ENGINE', True)
    @patch('scheduler.classify_event')
    def test_check_pre_event_alerts_no_duplicates(self, mock_classify):
        """Test that pre-event alerts don't send duplicates."""
        from scheduler import check_pre_event_alerts, _pre_event_alerts_sent
        import config

        mock_classify.return_value = Mock(category=Mock(value='inflation'))

        now = datetime.now(config.THAI_TZ)
        event_dt = now + timedelta(minutes=10)
        event_id = f"CPI y/y_{event_dt.isoformat()}"

        # Mark as already sent with timezone-aware datetime
        _pre_event_alerts_sent[event_id] = now

        events = [
            MockEvent(
                title="CPI y/y",
                impact="HIGH",
                event_datetime=event_dt
            ),
        ]

        # Should not send duplicate
        with patch('telegram_bot.send_message_with_retry', return_value=True):
            alerts = check_pre_event_alerts(events)

        assert alerts == 0

        # Cleanup
        if event_id in _pre_event_alerts_sent:
            del _pre_event_alerts_sent[event_id]

    @patch('config.ENABLE_PRE_EVENT_ALERTS', False)
    @patch('config.ENABLE_IMPACT_ENGINE', True)
    def test_check_pre_event_alerts_disabled(self):
        """Test that pre-event alerts respect feature flag."""
        from scheduler import check_pre_event_alerts

        now = datetime.now()
        events = [
            MockEvent(
                title="CPI y/y",
                impact="HIGH",
                event_datetime=now + timedelta(minutes=10)
            ),
        ]

        alerts = check_pre_event_alerts(events)
        assert alerts == 0

    @patch('config.ENABLE_POST_EVENT_ALERTS', True)
    @patch('config.ENABLE_IMPACT_ENGINE', True)
    @patch('config.POST_EVENT_DELAY_MINUTES', 5)
    @patch('config.ALERT_THRESHOLD_NORMAL', 2.0)
    @patch('scheduler.classify_event')
    def test_check_post_event_alerts_finds_released(self, mock_classify):
        """Test that post-event alerts finds recently released events with data."""
        from scheduler import check_post_event_alerts

        mock_classify.return_value = Mock(category=Mock(value='inflation'))

        # Create event that just happened with actual data
        now = datetime.now()
        events = [
            MockEvent(
                title="CPI y/y",
                impact="HIGH",
                forecast="3.2%",
                previous="3.0%",
                actual="3.5%",  # Has actual data
                event_datetime=now - timedelta(minutes=3)  # 3 minutes ago
            ),
        ]

        # Mock the impact engine analysis
        mock_result = Mock()
        mock_result.composite_score = 5.0
        mock_result.alert_message = "Test alert"

        with patch('telegram_bot.send_message_with_retry', return_value=True):
            with patch('src.core.event_impact_engine.analyze_event_impact', return_value=mock_result):
                alerts = check_post_event_alerts(events)

        # Should alert on high-impact events with actual data
        assert alerts == 1

    @patch('config.ENABLE_POST_EVENT_ALERTS', True)
    @patch('config.ENABLE_IMPACT_ENGINE', True)
    def test_check_post_event_alerts_skips_without_actual(self):
        """Test that post-event alerts skips events without actual data."""
        from scheduler import check_post_event_alerts

        now = datetime.now()
        events = [
            MockEvent(
                title="CPI y/y",
                impact="HIGH",
                forecast="3.2%",
                previous="3.0%",
                actual=None,  # No actual data yet
                event_datetime=now - timedelta(minutes=3)
            ),
        ]

        alerts = check_post_event_alerts(events)
        assert alerts == 0

    @patch('config.ENABLE_POST_EVENT_ALERTS', True)
    @patch('config.ENABLE_IMPACT_ENGINE', True)
    @patch('config.ALERT_THRESHOLD_NORMAL', 3.0)
    def test_check_post_event_alerts_skips_low_impact(self):
        """Test that post-event alerts skips events below threshold."""
        from scheduler import check_post_event_alerts

        now = datetime.now()
        events = [
            MockEvent(
                title="CPI y/y",
                impact="HIGH",
                actual="3.2%",
                event_datetime=now - timedelta(minutes=3)
            ),
        ]

        # Mock low impact result
        mock_result = Mock()
        mock_result.composite_score = 1.0  # Below threshold
        mock_result.alert_message = ""

        with patch('src.core.event_impact_engine.analyze_event_impact', return_value=mock_result):
            alerts = check_post_event_alerts(events)

        assert alerts == 0

    @patch('config.ENABLE_POST_EVENT_ALERTS', False)
    @patch('config.ENABLE_IMPACT_ENGINE', True)
    def test_check_post_event_alerts_disabled(self):
        """Test that post-event alerts respect feature flag."""
        from scheduler import check_post_event_alerts

        now = datetime.now()
        events = [
            MockEvent(
                title="CPI y/y",
                impact="HIGH",
                actual="3.5%",
                event_datetime=now - timedelta(minutes=3)
            ),
        ]

        alerts = check_post_event_alerts(events)
        assert alerts == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])