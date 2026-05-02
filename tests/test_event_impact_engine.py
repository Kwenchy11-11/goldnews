"""Tests for the Event Impact Engine."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
import sys
from pathlib import Path

# Add src/core to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "core"))

from event_impact_engine import (
    EventImpactEngine, EventImpactResult, analyze_event_impact
)
from event_classifier import EventCategory, ImpactScore
from surprise_engine import SurpriseResult, EconomicDataPoint


class TestEventImpactEngine:
    """Test suite for EventImpactEngine."""
    
    @pytest.fixture
    def engine(self, tmp_path):
        """Create a test engine with temp database."""
        db_path = tmp_path / "test_events.db"
        config = {
            "enable_consensus": False,  # Disable for unit tests
            "min_confidence": 0.3,
        }
        return EventImpactEngine(config=config, db_path=str(db_path))
    
    @pytest.fixture
    def sample_event_dict(self):
        """Sample event dictionary for classification."""
        return {
            "title": "US CPI MoM",
            "country": "USD",
            "impact": "HIGH",
        }
    
    @pytest.mark.asyncio
    async def test_process_event_basic(self, engine, sample_event_dict):
        """Test basic event processing."""
        result = await engine.process_event(
            event_name="CPI",
            timestamp=datetime(2024, 1, 15, 8, 30),
            source="ForexFactory",
            raw_text="CPI data release",
            actual=3.5,
            forecast=3.2,
            previous=3.1,
            unit="%",
            event_dict=sample_event_dict,
        )
        
        assert isinstance(result, EventImpactResult)
        assert result.event_name == "CPI"
        assert result.category == EventCategory.INFLATION
        assert result.impact_score.base_impact_score > 0
        assert result.composite_score != 0
    
    @pytest.mark.asyncio
    async def test_process_event_with_consensus(self, tmp_path, sample_event_dict):
        """Test event processing with consensus enabled."""
        db_path = tmp_path / "test_events.db"
        config = {
            "enable_consensus": True,
            "consensus_config": {"enable_mock_data": True},
        }
        engine = EventImpactEngine(config=config, db_path=str(db_path))
        
        # Mock the consensus engine
        mock_consensus = MagicMock()
        mock_consensus.confidence_score = 0.8
        mock_consensus.outcomes = [MagicMock(probability=0.6, name="Above 3%")]
        
        mock_comparison = MagicMock()
        mock_comparison.consensus_aligned = True
        mock_comparison.divergence_score = 0.1
        mock_comparison.trading_signal = "neutral"
        mock_comparison.market_consensus = mock_consensus
        
        engine.consensus_engine.fetch_market_consensus = AsyncMock(
            return_value=mock_consensus
        )
        engine.consensus_engine.compare_with_forecast = MagicMock(
            return_value=mock_comparison
        )
        
        result = await engine.process_event(
            event_name="CPI",
            timestamp=datetime.now(),
            source="Test",
            raw_text="Test event",
            actual=3.5,
            forecast=3.2,
            event_dict=sample_event_dict,
        )
        
        assert result.consensus_comparison is not None
    
    @pytest.mark.asyncio
    async def test_event_id_generation(self, engine, sample_event_dict):
        """Test unique event ID generation."""
        result1 = await engine.process_event(
            event_name="CPI",
            timestamp=datetime(2024, 1, 15, 8, 30),
            source="Test",
            raw_text="Test",
            actual=3.0,
            forecast=3.0,
            event_dict=sample_event_dict,
        )
        
        result2 = await engine.process_event(
            event_name="CPI",
            timestamp=datetime(2024, 1, 15, 8, 30),
            source="Test",
            raw_text="Test",
            actual=3.0,
            forecast=3.0,
            event_dict=sample_event_dict,
        )
        
        # Same inputs should generate same ID
        assert result1.event_id == result2.event_id
    
    @pytest.mark.asyncio
    async def test_composite_score_calculation(self, engine, sample_event_dict):
        """Test composite score calculation."""
        result = await engine.process_event(
            event_name="CPI",
            timestamp=datetime.now(),
            source="Test",
            raw_text="Test",
            actual=4.0,  # Above forecast
            forecast=3.0,
            event_dict=sample_event_dict,
        )
        
        # High CPI surprise should be bullish for gold
        assert result.composite_score > 0
        assert result.overall_gold_impact in ["bullish", "strong-bullish"]
    
    @pytest.mark.asyncio
    async def test_alert_determination(self, engine, sample_event_dict):
        """Test alert determination logic."""
        # High impact event with large surprise
        result = await engine.process_event(
            event_name="CPI",
            timestamp=datetime.now(),
            source="Test",
            raw_text="Test",
            actual=5.0,
            forecast=3.0,
            event_dict=sample_event_dict,
        )
        
        assert result.should_alert is True
        assert result.should_alert is True
        assert result.alert_priority in ["normal", "high", "immediate"]
    
    @pytest.mark.asyncio
    async def test_no_alert_for_neutral(self, engine):
        """Test no alert for neutral events."""
        event_dict = {
            "title": "Consumer Confidence",
            "country": "USD",
            "impact": "LOW",
        }
        
        result = await engine.process_event(
            event_name="Consumer Confidence",
            timestamp=datetime.now(),
            source="Test",
            raw_text="Test",
            actual=100.0,
            forecast=100.0,  # No surprise
            event_dict=event_dict,
        )
        
        # Should not alert for neutral, no-surprise events
        assert result.should_alert is False or result.alert_priority == "low"
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, engine):
        """Test batch processing of multiple events."""
        events = [
            {
                "event_name": "CPI",
                "timestamp": datetime.now(),
                "source": "Test",
                "raw_text": "Test 1",
                "actual": 3.5,
                "forecast": 3.2,
                "event_dict": {"title": "CPI", "country": "USD", "impact": "HIGH"},
            },
            {
                "event_name": "NFP",
                "timestamp": datetime.now(),
                "source": "Test",
                "raw_text": "Test 2",
                "actual": 250.0,
                "forecast": 200.0,
                "event_dict": {"title": "Non-Farm Payrolls", "country": "USD", "impact": "HIGH"},
            },
        ]
        
        results = await engine.batch_process(events)
        
        assert len(results) == 2
        assert all(isinstance(r, EventImpactResult) for r in results)
    
    def test_get_statistics(self, engine, sample_event_dict):
        """Test statistics retrieval."""
        import asyncio
        
        # Process an event first
        asyncio.run(engine.process_event(
            event_name="CPI",
            timestamp=datetime.now(),
            source="Test",
            raw_text="Test",
            actual=3.5,
            forecast=3.2,
            event_dict=sample_event_dict,
        ))
        
        stats = engine.get_statistics()
        
        assert "total_events" in stats
        assert stats["total_events"] >= 1


class TestAnalyzeEventImpact:
    """Test suite for the convenience function."""
    
    def test_analyze_cpi_event(self):
        """Test analyzing a CPI event."""
        result = analyze_event_impact(
            event_name="CPI",
            actual=3.5,
            forecast=3.0,
            previous=2.8,
        )
        
        assert result["event_name"] == "CPI"
        assert result["category"] == "inflation"
        assert "surprise_score" in result
        assert "gold_impact" in result
        assert "composite_score" in result
        assert result["gold_impact"] == "bullish"
    
    def test_analyze_nfp_event(self):
        """Test analyzing an NFP event."""
        result = analyze_event_impact(
            event_name="NFP",
            actual=250.0,
            forecast=200.0,
            event_dict={"title": "Non-Farm Payrolls", "country": "USD", "impact": "HIGH"},
        )
        
        assert result["category"] == "labor"
        # Strong NFP is typically bearish for gold (above forecast = bearish)
        # Note: gold_impact in surprise result reflects the immediate reaction
        assert result["gold_impact"] in ["bearish", "neutral"]
    
    def test_analyze_as_expected(self):
        """Test analyzing event that meets forecast."""
        result = analyze_event_impact(
            event_name="CPI",
            actual=3.0,
            forecast=3.0,
        )
        
        assert result["direction"] == "as-expected"
        assert result["significance"] == "none"
        assert result["gold_impact"] == "neutral"
    
    def test_analyze_with_custom_dict(self):
        """Test analyzing with custom event dict."""
        result = analyze_event_impact(
            event_name="GDP",
            actual=2.5,
            forecast=2.0,
            event_dict={"title": "GDP QoQ", "country": "USD", "impact": "MEDIUM"},
        )
        
        assert result["category"] == "growth"


class TestCompositeScoreCalculation:
    """Test composite score calculation logic."""
    
    @pytest.fixture
    def engine(self, tmp_path):
        db_path = tmp_path / "test.db"
        return EventImpactEngine(
            config={"enable_consensus": False},
            db_path=str(db_path)
        )
    
    def test_high_base_impact_with_surprise(self, engine):
        """Test composite score with high base impact and surprise."""
        impact_score = ImpactScore(
            category=EventCategory.INFLATION,
            base_impact_score=9,
            gold_correlation="negative",
            typical_volatility="high",
            key_drivers=["test"],
        )
        surprise = SurpriseResult(
            surprise_score=8.0,
            deviation_pct=25.0,
            direction="above",
            significance="high",
            gold_impact="bullish",
        )
        
        composite = engine._calculate_composite_score(impact_score, surprise, None)

        # Should be bullish (surprise is 70% weight, base is 20%)
        # 8 * 0.7 + (-9 * 0.2) = 5.6 - 1.8 = 3.8
        assert composite > 3
    
    def test_bearish_composite(self, engine):
        """Test composite score for bearish scenario."""
        impact_score = ImpactScore(
            category=EventCategory.LABOR,
            base_impact_score=9,
            gold_correlation="negative",
            typical_volatility="high",
            key_drivers=["test"],
        )
        surprise = SurpriseResult(
            surprise_score=-8.0,
            deviation_pct=-25.0,
            direction="below",
            significance="high",
            gold_impact="bullish",  # Better jobs = bearish gold
        )
        
        composite = engine._calculate_composite_score(impact_score, surprise, None)
        
        # Strong jobs is bearish for gold
        assert composite < -3
    
    def test_neutral_composite(self, engine):
        """Test composite score for neutral scenario."""
        impact_score = ImpactScore(
            category=EventCategory.CONSUMER,
            base_impact_score=5,
            gold_correlation="negative",
            typical_volatility="low",
            key_drivers=["test"],
        )
        surprise = SurpriseResult(
            surprise_score=0.0,
            deviation_pct=0.5,
            direction="as-expected",
            significance="none",
            gold_impact="neutral",
        )
        
        composite = engine._calculate_composite_score(impact_score, surprise, None)
        
        # Should be near neutral
        assert -2 < composite < 2


class TestAlertDetermination:
    """Test alert determination logic."""
    
    @pytest.fixture
    def engine(self, tmp_path):
        db_path = tmp_path / "test.db"
        return EventImpactEngine(
            config={"min_confidence": 0.3},
            db_path=str(db_path)
        )
    
    def test_immediate_alert(self, engine):
        """Test immediate priority alert."""
        should_alert, priority = engine._determine_alert(9.0, 0.8, 10)
        
        assert should_alert is True
        assert priority == "immediate"
    
    def test_high_priority_alert(self, engine):
        """Test high priority alert."""
        should_alert, priority = engine._determine_alert(7.0, 0.8, 9)
        
        assert should_alert is True
        assert priority == "high"
    
    def test_no_alert_low_confidence(self, engine):
        """Test no alert when confidence too low."""
        should_alert, priority = engine._determine_alert(9.0, 0.2, 10)
        
        assert should_alert is False
    
    def test_no_alert_low_score(self, engine):
        """Test no alert when composite score too low."""
        should_alert, priority = engine._determine_alert(1.0, 0.8, 5)
        
        assert should_alert is False


class TestOverallImpact:
    """Test overall impact determination."""
    
    @pytest.fixture
    def engine(self, tmp_path):
        db_path = tmp_path / "test.db"
        return EventImpactEngine(db_path=str(db_path))
    
    def test_strong_bullish(self, engine):
        assert engine._determine_overall_impact(8) == "strong-bullish"
        assert engine._determine_overall_impact(7) == "strong-bullish"
    
    def test_bullish(self, engine):
        assert engine._determine_overall_impact(5) == "bullish"
        assert engine._determine_overall_impact(3) == "bullish"
    
    def test_bearish(self, engine):
        assert engine._determine_overall_impact(-5) == "bearish"
        assert engine._determine_overall_impact(-3) == "bearish"
    
    def test_strong_bearish(self, engine):
        assert engine._determine_overall_impact(-8) == "strong-bearish"
        assert engine._determine_overall_impact(-7) == "strong-bearish"
    
    def test_neutral(self, engine):
        assert engine._determine_overall_impact(0) == "neutral"
        assert engine._determine_overall_impact(2) == "neutral"
        assert engine._determine_overall_impact(-2) == "neutral"
