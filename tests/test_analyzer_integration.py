"""
Tests for Event Impact Engine integration with analyzer.

This module tests the integration between the deterministic Event Impact Engine
and the AI analyzer, ensuring that:
1. Event classification works correctly
2. Impact scores are calculated properly
3. Thai reasoning is generated
4. The integration falls back gracefully on errors
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pytest


@dataclass
class MockEconomicEvent:
    """Mock event for testing."""
    title: str
    title_th: str
    country: str = 'US'
    impact: str = 'high'
    forecast: Optional[str] = None
    previous: Optional[str] = None
    date: Optional[str] = None
    event_datetime: Optional[datetime] = None


class TestAnalyzerIntegration:
    """Test suite for analyzer Event Impact Engine integration."""

    def test_parse_numeric_value_basic(self):
        """Test parsing numeric values from strings."""
        from analyzer import _parse_numeric_value

        assert _parse_numeric_value("3.2%") == 3.2
        assert _parse_numeric_value("250K") == 250.0
        assert _parse_numeric_value("1.5") == 1.5
        assert _parse_numeric_value(None) is None
        assert _parse_numeric_value("") is None

    def test_parse_numeric_value_range(self):
        """Test parsing range values."""
        from analyzer import _parse_numeric_value

        # Should take the middle of the range
        assert _parse_numeric_value("1.5-2.0") == 1.75

    def test_detect_unit(self):
        """Test unit detection from value strings."""
        from analyzer import _detect_unit

        assert _detect_unit("3.2%") == "%"
        assert _detect_unit("250K") == "K"
        assert _detect_unit("1.5M") == "M"
        assert _detect_unit("100") == "index"
        assert _detect_unit(None) == "%"

    def test_score_to_bias(self):
        """Test converting scores to bias directions."""
        from analyzer import _score_to_bias

        assert _score_to_bias(5) == "BULLISH"
        assert _score_to_bias(2) == "BULLISH"
        assert _score_to_bias(1.9) == "NEUTRAL"
        assert _score_to_bias(0) == "NEUTRAL"
        assert _score_to_bias(-1.9) == "NEUTRAL"
        assert _score_to_bias(-2) == "BEARISH"
        assert _score_to_bias(-5) == "BEARISH"

    def test_score_to_impact_level(self):
        """Test converting scores to impact levels."""
        from analyzer import _score_to_impact_level

        assert _score_to_impact_level(7) == "HIGH"
        assert _score_to_impact_level(5) == "HIGH"
        assert _score_to_impact_level(4.9) == "MEDIUM"
        assert _score_to_impact_level(2) == "MEDIUM"
        assert _score_to_impact_level(1.9) == "LOW"
        assert _score_to_impact_level(0) == "LOW"

    def test_calculate_confidence_with_data(self):
        """Test confidence calculation with complete data."""
        from analyzer import _calculate_confidence

        event = MockEconomicEvent(
            title="CPI",
            title_th="ดัชนีราคาผู้บริโภค",
            forecast="3.2%",
            previous="3.0%"
        )

        # Create a mock impact result with confidence_score attribute
        class MockImpactResult:
            def __init__(self, confidence_score):
                self.confidence_score = confidence_score

        impact_result = MockImpactResult(confidence_score=75)

        confidence = _calculate_confidence(event, impact_result)
        assert 50 <= confidence <= 100
        assert confidence > 50  # Should be higher with forecast and previous

    def test_calculate_confidence_without_data(self):
        """Test confidence calculation with minimal data."""
        from analyzer import _calculate_confidence

        event = MockEconomicEvent(
            title="CPI",
            title_th="ดัชนีราคาผู้บริโภค"
        )

        # Create a mock impact result with confidence_score attribute
        class MockImpactResult:
            def __init__(self, confidence_score):
                self.confidence_score = confidence_score

        impact_result = MockImpactResult(confidence_score=50)

        confidence = _calculate_confidence(event, impact_result)
        assert confidence >= 50
        assert confidence <= 70  # Should be capped for pre-event

    def test_fallback_thai_reasoning_inflation(self):
        """Test fallback reasoning generation for inflation events."""
        from analyzer import _fallback_thai_reasoning
        from event_classifier import classify_event

        event = MockEconomicEvent(
            title="CPI y/y",
            title_th="ดัชนีราคาผู้บริโภค"
        )

        classification = classify_event({"title": "CPI y/y"})
        reasoning = _fallback_thai_reasoning(event, classification, "NEUTRAL")

        assert "ดัชนีราคาผู้บริโภค" in reasoning
        assert "Actual" in reasoning or "📉" in reasoning or "📈" in reasoning

    def test_fallback_thai_reasoning_labor(self):
        """Test fallback reasoning generation for labor events."""
        from analyzer import _fallback_thai_reasoning
        from event_classifier import classify_event

        event = MockEconomicEvent(
            title="Non-Farm Payrolls",
            title_th="การจ้างงานนอกภาคเกษตร"
        )

        classification = classify_event({"title": "Non-Farm Payrolls"})
        reasoning = _fallback_thai_reasoning(event, classification, "NEUTRAL")

        assert "การจ้างงาน" in reasoning or "จ้างงาน" in reasoning

    def test_analyze_event_with_impact_engine_cpi(self):
        """Test full integration with CPI event."""
        from analyzer import analyze_event_with_impact_engine

        event = MockEconomicEvent(
            title="CPI y/y",
            title_th="ดัชนีราคาผู้บริโภครายปี",
            country="US",
            impact="high",
            forecast="3.2%",
            previous="3.0%"
        )

        result = analyze_event_with_impact_engine(event)

        assert result.event_title == "CPI y/y"
        assert result.event_title_th == "ดัชนีราคาผู้บริโภครายปี"
        assert result.country == "US"
        assert result.impact in ["HIGH", "MEDIUM", "LOW"]
        assert result.bias in ["BULLISH", "BEARISH", "NEUTRAL"]
        assert 0 <= result.confidence <= 100
        assert len(result.reasoning) > 0
        assert result.forecast == "3.2%"
        assert result.previous == "3.0%"

    def test_analyze_event_with_impact_engine_nfp(self):
        """Test full integration with NFP event."""
        from analyzer import analyze_event_with_impact_engine

        event = MockEconomicEvent(
            title="Non-Farm Payrolls",
            title_th="การจ้างงานนอกภาคเกษตร",
            country="US",
            impact="high",
            forecast="180K",
            previous="175K"
        )

        result = analyze_event_with_impact_engine(event)

        assert result.event_title == "Non-Farm Payrolls"
        assert result.bias in ["BULLISH", "BEARISH", "NEUTRAL"]
        assert result.impact in ["HIGH", "MEDIUM", "LOW"]

    def test_analyze_event_with_impact_engine_fomc(self):
        """Test full integration with FOMC event."""
        from analyzer import analyze_event_with_impact_engine

        event = MockEconomicEvent(
            title="FOMC Statement",
            title_th="แถลงการณ์ FOMC",
            country="US",
            impact="high"
        )

        result = analyze_event_with_impact_engine(event)

        assert result.event_title == "FOMC Statement"
        assert result.bias in ["BULLISH", "BEARISH", "NEUTRAL"]

    def test_analyze_event_fallback_on_error(self):
        """Test that integration falls back to standard analysis on error."""
        from analyzer import analyze_event_with_impact_engine

        # Create an event with problematic data
        event = MockEconomicEvent(
            title="",  # Empty title - should cause classification issues
            title_th="",
            country="US"
        )

        # Should not raise an exception, should fall back
        result = analyze_event_with_impact_engine(event)

        # Should still return a valid AnalysisResult
        assert hasattr(result, 'event_title')
        assert hasattr(result, 'bias')
        assert result.bias in ["BULLISH", "BEARISH", "NEUTRAL"]

    def test_analyze_events_with_impact_engine_batch(self):
        """Test batch analysis with impact engine."""
        from analyzer import analyze_events_with_impact_engine

        events = [
            MockEconomicEvent(
                title="CPI y/y",
                title_th="ดัชนีราคาผู้บริโภค",
                forecast="3.2%",
                previous="3.0%"
            ),
            MockEconomicEvent(
                title="Non-Farm Payrolls",
                title_th="การจ้างงาน",
                forecast="180K",
                previous="175K"
            ),
            MockEconomicEvent(
                title="FOMC Statement",
                title_th="FOMC"
            )
        ]

        results = analyze_events_with_impact_engine(events, delay=0.1)

        assert len(results) == 3
        for result in results:
            assert result.bias in ["BULLISH", "BEARISH", "NEUTRAL"]
            assert result.impact in ["HIGH", "MEDIUM", "LOW"]
            assert 0 <= result.confidence <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])