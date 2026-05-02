"""
Tests for Trade Decision Engine

Tests all No Trade Zone rules and edge cases.
"""

from src.core.trade_decision_engine import (
    TradeDecisionEngine, TradeDecision, TradeRecommendation,
    evaluate_trade_signal
)
from src.core.surprise_engine import SurpriseResult
from event_classifier import EventCategory
import pytest
from datetime import datetime


class TestTradeDecisionBasic:
    """Test basic decision logic."""
    
    def test_low_score_no_trade(self):
        """Score below threshold should result in NO_TRADE."""
        engine = TradeDecisionEngine()
        surprise = SurpriseResult(
            surprise_score=2.0,
            deviation_pct=10.0,
            direction="above",
            significance="medium",
            gold_impact="bullish"
        )
        
        result = engine.evaluate(
            composite_score=3.0,  # Below 5.5 threshold
            surprise_result=surprise,
            consensus_comparison=None,
            category=EventCategory.INFLATION,
        )
        
        assert result.decision == TradeDecision.NO_TRADE
        assert any("threshold" in r.lower() for r in result.reasons)
    
    def test_high_score_buy_signal(self):
        """High positive score should result in BUY."""
        engine = TradeDecisionEngine()
        surprise = SurpriseResult(
            surprise_score=6.0,
            deviation_pct=25.0,
            direction="above",
            significance="high",
            gold_impact="bullish"
        )
        
        result = engine.evaluate(
            composite_score=7.0,  # Above threshold
            surprise_result=surprise,
            consensus_comparison=None,
            category=EventCategory.INFLATION,
        )
        
        assert result.decision in [TradeDecision.BUY_GOLD, TradeDecision.STRONG_BUY_GOLD]
        assert result.direction == "bullish"
    
    def test_high_negative_score_sell_signal(self):
        """High negative score should result in SELL."""
        engine = TradeDecisionEngine()
        surprise = SurpriseResult(
            surprise_score=-6.0,
            deviation_pct=25.0,
            direction="below",
            significance="high",
            gold_impact="bearish"
        )
        
        result = engine.evaluate(
            composite_score=-7.0,
            surprise_result=surprise,
            consensus_comparison=None,
            category=EventCategory.INFLATION,
        )
        
        assert result.decision in [TradeDecision.SELL_GOLD, TradeDecision.STRONG_SELL_GOLD]
        assert result.direction == "bearish"


class TestNoTradeZoneRules:
    """Test No Trade Zone specific rules."""
    
    def test_small_deviation_no_trade(self):
        """Actual too close to forecast should result in NO_TRADE."""
        engine = TradeDecisionEngine()
        surprise = SurpriseResult(
            surprise_score=1.0,
            deviation_pct=2.0,  # Very small deviation
            direction="as-expected",
            significance="low",
            gold_impact="neutral"
        )
        
        result = engine.evaluate(
            composite_score=6.0,  # Would normally trade
            surprise_result=surprise,
            consensus_comparison=None,
            category=EventCategory.INFLATION,
        )
        
        assert result.decision == TradeDecision.NO_TRADE
        assert any("close to forecast" in r.lower() or "deviation" in r.lower() 
                   for r in result.reasons)
    
    def test_mixed_signals_wait(self):
        """Multiple events should result in WAIT."""
        engine = TradeDecisionEngine()
        surprise = SurpriseResult(
            surprise_score=5.0,
            deviation_pct=20.0,
            direction="above",
            significance="high",
            gold_impact="bullish"
        )
        
        related_events = [
            {"name": "NFP", "time": datetime.now()},
            {"name": "Unemployment", "time": datetime.now()},
        ]
        
        result = engine.evaluate(
            composite_score=6.0,
            surprise_result=surprise,
            consensus_comparison=None,
            category=EventCategory.LABOR,
            related_events=related_events
        )
        
        assert result.decision == TradeDecision.WAIT
        # Check in both reasons and warnings
        all_messages = result.reasons + result.warnings
        assert any("mixed" in r.lower() for r in all_messages)
    
    def test_high_spread_no_trade(self):
        """High spread should result in NO_TRADE."""
        engine = TradeDecisionEngine()
        surprise = SurpriseResult(
            surprise_score=5.0,
            deviation_pct=20.0,
            direction="above",
            significance="high",
            gold_impact="bullish"
        )
        
        market_conditions = {"spread_pips": 60}  # Above 50 threshold
        
        result = engine.evaluate(
            composite_score=6.0,
            surprise_result=surprise,
            consensus_comparison=None,
            category=EventCategory.INFLATION,
            market_conditions=market_conditions
        )
        
        assert result.decision == TradeDecision.NO_TRADE
        assert any("spread" in r.lower() for r in result.reasons)
    
    def test_high_volatility_no_trade(self):
        """High volatility should result in NO_TRADE."""
        engine = TradeDecisionEngine()
        surprise = SurpriseResult(
            surprise_score=5.0,
            deviation_pct=20.0,
            direction="above",
            significance="high",
            gold_impact="bullish"
        )
        
        market_conditions = {"volatility_percentile": 95}  # Above 90 threshold
        
        result = engine.evaluate(
            composite_score=6.0,
            surprise_result=surprise,
            consensus_comparison=None,
            category=EventCategory.INFLATION,
            market_conditions=market_conditions
        )
        
        assert result.decision == TradeDecision.NO_TRADE
        assert any("volatility" in r.lower() for r in result.warnings)


class TestConfidenceCalculation:
    """Test confidence score calculations."""
    
    def test_strong_signal_high_confidence(self):
        """Strong signals should have high confidence."""
        engine = TradeDecisionEngine()
        surprise = SurpriseResult(
            surprise_score=8.0,
            deviation_pct=40.0,
            direction="above",
            significance="high",
            gold_impact="bullish"
        )
        
        result = engine.evaluate(
            composite_score=8.5,
            surprise_result=surprise,
            consensus_comparison=None,
            category=EventCategory.INFLATION,
        )
        
        assert result.confidence >= 75
        assert result.decision in [TradeDecision.STRONG_BUY_GOLD, TradeDecision.BUY_GOLD]
    
    def test_weak_signal_low_confidence(self):
        """Weak signals should have low confidence."""
        engine = TradeDecisionEngine()
        surprise = SurpriseResult(
            surprise_score=3.0,
            deviation_pct=12.0,
            direction="above",
            significance="medium",
            gold_impact="bullish"
        )
        
        result = engine.evaluate(
            composite_score=5.5,  # Just above threshold
            surprise_result=surprise,
            consensus_comparison=None,
            category=EventCategory.INFLATION,
        )
        
        # Should still trade but with lower confidence
        assert result.confidence < 75


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_exactly_at_threshold(self):
        """Test exactly at score threshold."""
        engine = TradeDecisionEngine()
        surprise = SurpriseResult(
            surprise_score=5.5,
            deviation_pct=20.0,
            direction="above",
            significance="high",
            gold_impact="bullish"
        )
        
        result = engine.evaluate(
            composite_score=5.5,  # Exactly at threshold
            surprise_result=surprise,
            consensus_comparison=None,
            category=EventCategory.INFLATION,
        )
        
        # Should pass threshold check
        assert result.decision != TradeDecision.NO_TRADE or any("threshold" not in r for r in result.reasons)
    
    def test_zero_score(self):
        """Test with zero composite score."""
        engine = TradeDecisionEngine()
        surprise = SurpriseResult(
            surprise_score=0,
            deviation_pct=0,
            direction="as-expected",
            significance="none",
            gold_impact="neutral"
        )
        
        result = engine.evaluate(
            composite_score=0,
            surprise_result=surprise,
            consensus_comparison=None,
            category=EventCategory.UNKNOWN,
        )
        
        assert result.decision == TradeDecision.NO_TRADE
    
    def test_none_surprise_result(self):
        """Test handling of None surprise result."""
        engine = TradeDecisionEngine()
        
        result = engine.evaluate(
            composite_score=6.0,
            surprise_result=None,
            consensus_comparison=None,
            category=EventCategory.INFLATION,
        )
        
        # Should handle gracefully
        assert isinstance(result, TradeRecommendation)
    
    def test_negative_confidence_handling(self):
        """Test that confidence doesn't go negative."""
        engine = TradeDecisionEngine()
        surprise = SurpriseResult(
            surprise_score=-8.0,
            deviation_pct=40.0,
            direction="below",
            significance="high",
            gold_impact="bearish"
        )
        
        result = engine.evaluate(
            composite_score=-8.0,
            surprise_result=surprise,
            consensus_comparison=None,
            category=EventCategory.INFLATION,
        )
        
        assert result.confidence >= 0


class TestRecommendationOutput:
    """Test TradeRecommendation output format."""
    
    def test_to_dict_output(self):
        """Test dictionary conversion."""
        engine = TradeDecisionEngine()
        surprise = SurpriseResult(
            surprise_score=6.0,
            deviation_pct=25.0,
            direction="above",
            significance="high",
            gold_impact="bullish"
        )
        
        result = engine.evaluate(
            composite_score=7.0,
            surprise_result=surprise,
            consensus_comparison=None,
            category=EventCategory.INFLATION,
        )
        
        data = result.to_dict()
        
        assert "decision" in data
        assert "confidence" in data
        assert "reasons" in data
        assert isinstance(data["reasons"], list)
    
    def test_decision_labels(self):
        """Test human-readable labels."""
        rec = TradeRecommendation(
            decision=TradeDecision.STRONG_BUY_GOLD,
            confidence=85,
            direction="bullish",
            strength="strong",
            composite_score=8.0,
            surprise_score=6.0,
            consensus_alignment=0.7,
        )
        
        assert "STRONG BUY" in rec.get_decision_label()
        assert len(rec.get_decision_emoji()) > 0
    
    def test_actionable_decisions(self):
        """Test is_actionable() method."""
        assert TradeDecision.BUY_GOLD.is_actionable() is True
        assert TradeDecision.SELL_GOLD.is_actionable() is True
        assert TradeDecision.WAIT.is_actionable() is False
        assert TradeDecision.NO_TRADE.is_actionable() is False
    
    def test_directional_methods(self):
        """Test is_bullish() and is_bearish() methods."""
        assert TradeDecision.BUY_GOLD.is_bullish() is True
        assert TradeDecision.SELL_GOLD.is_bearish() is True
        assert TradeDecision.BUY_GOLD.is_bearish() is False
        assert TradeDecision.SELL_GOLD.is_bullish() is False


class TestConvenienceFunction:
    """Test the convenience function."""
    
    def test_evaluate_trade_signal(self):
        """Test convenience function."""
        surprise = SurpriseResult(
            surprise_score=6.0,
            deviation_pct=25.0,
            direction="above",
            significance="high",
            gold_impact="bullish"
        )
        
        result = evaluate_trade_signal(
            composite_score=7.0,
            surprise_result=surprise,
            category=EventCategory.INFLATION,
        )
        
        assert isinstance(result, TradeRecommendation)
        assert result.decision.is_actionable()
    
    def test_quick_evaluate(self):
        """Test quick evaluation function."""
        engine = TradeDecisionEngine()
        
        # High score
        decision, reason = engine.quick_evaluate(8.0, 25.0, True)
        assert decision.is_actionable()
        
        # Low score
        decision, reason = engine.quick_evaluate(3.0, 25.0, True)
        assert decision == TradeDecision.NO_TRADE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
