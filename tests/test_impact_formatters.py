"""
Tests for Event Impact Engine formatters.

This module tests the Telegram message formatting functions for displaying
Event Impact Engine results.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from dataclasses import dataclass
from typing import Optional

import pytest


# Mock classes for testing
@dataclass
class MockCategory:
    value: str


@dataclass
class MockImpactScore:
    category: MockCategory
    base_impact_score: int
    gold_correlation: float
    typical_volatility: float
    key_drivers: list


@dataclass
class MockSurpriseResult:
    surprise_score: float
    deviation_pct: float
    direction: str
    significance: str
    gold_impact_estimate: dict


@dataclass
class MockConsensusComparison:
    market_direction: str
    sentiment: str
    trading_signal: str
    divergence_score: float
    agreement_level: str


@dataclass
class MockEventImpactResult:
    event_id: str
    event_name: str
    category: MockCategory
    timestamp: datetime
    impact_score: MockImpactScore
    surprise_result: MockSurpriseResult
    consensus_comparison: Optional[MockConsensusComparison]
    overall_gold_impact: str
    confidence_score: float
    composite_score: float
    should_alert: bool
    alert_priority: str
    alert_message: str
    processed_at: datetime


class TestImpactFormatters:
    """Test suite for Event Impact Engine formatters."""

    def test_get_impact_strength_emoji(self):
        """Test emoji selection based on impact score."""
        from formatter import get_impact_strength_emoji

        assert get_impact_strength_emoji(8) == "🔴📈"
        assert get_impact_strength_emoji(5) == "🟠📈"
        assert get_impact_strength_emoji(3) == "🟡📈"
        assert get_impact_strength_emoji(0) == "⚪"
        assert get_impact_strength_emoji(-3) == "🟡📉"
        assert get_impact_strength_emoji(-5) == "🟠📉"
        assert get_impact_strength_emoji(-8) == "🔴📉"

    def test_get_alert_priority_emoji(self):
        """Test emoji selection for alert priorities."""
        from formatter import get_alert_priority_emoji

        assert get_alert_priority_emoji('immediate') == '🚨'
        assert get_alert_priority_emoji('high') == '⚠️'
        assert get_alert_priority_emoji('normal') == 'ℹ️'
        assert get_alert_priority_emoji('low') == '💡'
        assert get_alert_priority_emoji('unknown') == 'ℹ️'  # Default

    def test_format_impact_score_bar(self):
        """Test visual score bar formatting."""
        from formatter import format_impact_score_bar

        bar_positive = format_impact_score_bar(5.0)
        assert "[" in bar_positive
        assert "5.0" in bar_positive
        assert "+" in bar_positive

        bar_negative = format_impact_score_bar(-3.0)
        assert "[" in bar_negative
        assert "-3.0" in bar_negative

        bar_neutral = format_impact_score_bar(0)
        assert "0.0" in bar_neutral

    def test_format_event_impact_result_basic(self):
        """Test basic impact result formatting."""
        from formatter import format_event_impact_result

        now = datetime.now()
        category = MockCategory('inflation')
        impact_score = MockImpactScore(
            category=category,
            base_impact_score=8,
            gold_correlation=-0.7,
            typical_volatility=1.5,
            key_drivers=['CPI', 'Inflation']
        )
        surprise = MockSurpriseResult(
            surprise_score=3.5,
            deviation_pct=5.2,
            direction='higher',
            significance='high',
            gold_impact_estimate={'direction': 'bearish', 'strength': 'strong'}
        )

        result = MockEventImpactResult(
            event_id="test-123",
            event_name="CPI y/y",
            category=category,
            timestamp=now,
            impact_score=impact_score,
            surprise_result=surprise,
            consensus_comparison=None,
            overall_gold_impact='bearish',
            confidence_score=0.75,
            composite_score=-4.5,
            should_alert=True,
            alert_priority='high',
            alert_message="Test alert message",
            processed_at=now
        )

        message = format_event_impact_result(result)

        assert "CPI y/y" in message
        assert "เงินเฟ้อ" in message or "inflation" in message.lower()
        assert "-4.5" in message
        assert "75%" in message
        assert "Test alert" in message or "แนะนำให้แจ้งเตือน" in message

    def test_format_pre_event_alert(self):
        """Test pre-event alert formatting."""
        from formatter import format_pre_event_alert

        event_time = datetime.now()
        message = format_pre_event_alert(
            event_name="CPI y/y",
            forecast="3.2%",
            previous="3.0%",
            category="inflation",
            event_time=event_time
        )

        assert "CPI y/y" in message
        assert "ข่าวสำคัญกำลังจะประกาศ" in message
        assert "3.2%" in message
        assert "3.0%" in message
        assert "เงินเฟ้อ" in message or "inflation" in message.lower()

    def test_format_pre_event_alert_minimal(self):
        """Test pre-event alert with minimal data."""
        from formatter import format_pre_event_alert

        message = format_pre_event_alert(
            event_name="FOMC Statement",
            forecast=None,
            previous=None,
            category="fed_policy"
        )

        assert "FOMC Statement" in message
        assert "ข่าวสำคัญกำลังจะประกาฉ" in message or "ข่าวสำคัญ" in message

    def test_format_post_event_alert(self):
        """Test post-event alert formatting."""
        from formatter import format_post_event_alert

        message = format_post_event_alert(
            event_name="CPI y/y",
            actual="3.5%",
            forecast="3.2%",
            previous="3.0%",
            composite_score=5.5,
            alert_message="Gold expected to rise"
        )

        assert "CPI y/y" in message
        assert "ข่าวสำคัญประกาศแล้ว" in message
        assert "3.5%" in message
        assert "3.2%" in message
        assert "5.5" in message or "+5.5" in message
        assert "Gold expected" in message

    def test_format_post_event_alert_bearish(self):
        """Test post-event alert with negative impact."""
        from formatter import format_post_event_alert

        message = format_post_event_alert(
            event_name="Non-Farm Payrolls",
            actual="200K",
            forecast="180K",
            previous="175K",
            composite_score=-4.5
        )

        assert "Non-Farm Payrolls" in message
        assert "200K" in message
        assert "-4.5" in message or "4.5" in message

    def test_format_daily_impact_summary(self):
        """Test daily summary formatting."""
        from formatter import format_daily_impact_summary

        now = datetime.now()
        category = MockCategory('inflation')
        impact_score = MockImpactScore(
            category=category,
            base_impact_score=8,
            gold_correlation=-0.7,
            typical_volatility=1.5,
            key_drivers=[]
        )
        surprise = MockSurpriseResult(
            surprise_score=3.5,
            deviation_pct=5.2,
            direction='higher',
            significance='high',
            gold_impact_estimate={}
        )

        results = [
            MockEventImpactResult(
                event_id="1",
                event_name="CPI y/y",
                category=category,
                timestamp=now,
                impact_score=impact_score,
                surprise_result=surprise,
                consensus_comparison=None,
                overall_gold_impact='bearish',
                confidence_score=0.8,
                composite_score=-5.0,
                should_alert=True,
                alert_priority='high',
                alert_message="",
                processed_at=now
            ),
            MockEventImpactResult(
                event_id="2",
                event_name="Non-Farm Payrolls",
                category=MockCategory('labor'),
                timestamp=now,
                impact_score=impact_score,
                surprise_result=surprise,
                consensus_comparison=None,
                overall_gold_impact='bullish',
                confidence_score=0.7,
                composite_score=3.5,
                should_alert=False,
                alert_priority='normal',
                alert_message="",
                processed_at=now
            ),
        ]

        message = format_daily_impact_summary(results)

        assert "สรุปผลกระทบข่าวเศรษฐกิจ" in message or "summary" in message.lower()
        assert "CPI y/y" in message
        assert "Non-Farm Payrolls" in message
        assert "-5.0" in message or "5.0" in message
        assert "3.5" in message

    def test_format_daily_impact_summary_empty(self):
        """Test daily summary with no results."""
        from formatter import format_daily_impact_summary

        message = format_daily_impact_summary([])

        assert "ไม่มีข่าว" in message or "ไม่มี" in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])