"""Trade Decision Engine - No Trade Zone Layer

Filters trading signals to prevent bad trades by applying deterministic rules
for when NOT to trade, even when the impact score is high.

Key principles:
1. Quality over quantity - fewer, higher-confidence signals
2. Clear direction required - ambiguous signals = NO_TRADE
3. Conflict detection - mixed signals = WAIT
4. Risk management - unfavorable conditions = NO_TRADE

Output decisions:
- STRONG_BUY_GOLD / STRONG_SELL_GOLD: High confidence, aligned signals
- BUY_GOLD / SELL_GOLD: Moderate confidence, clear direction
- WAIT: Unclear or conflicting signals, monitor for clarity
- NO_TRADE: Conditions unfavorable for trading
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional, Tuple
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from event_classifier import EventCategory
from surprise_engine import SurpriseResult
from consensus_engine import ConsensusComparison


class TradeDecision(Enum):
    """Trading decisions ordered by strength/direction."""
    STRONG_BUY_GOLD = "strong_buy"
    BUY_GOLD = "buy"
    WAIT = "wait"
    SELL_GOLD = "sell"
    STRONG_SELL_GOLD = "strong_sell"
    NO_TRADE = "no_trade"
    
    def is_actionable(self) -> bool:
        """Returns True if this decision suggests taking a position."""
        return self in (TradeDecision.STRONG_BUY_GOLD, TradeDecision.BUY_GOLD,
                       TradeDecision.SELL_GOLD, TradeDecision.STRONG_SELL_GOLD)
    
    def is_bullish(self) -> bool:
        """Returns True if decision is bullish for gold."""
        return self in (TradeDecision.STRONG_BUY_GOLD, TradeDecision.BUY_GOLD)
    
    def is_bearish(self) -> bool:
        """Returns True if decision is bearish for gold."""
        return self in (TradeDecision.STRONG_SELL_GOLD, TradeDecision.SELL_GOLD)


@dataclass
class TradeRecommendation:
    """Complete trading recommendation with decision, confidence, and reasoning."""
    
    # Core decision
    decision: TradeDecision
    confidence: float  # 0-100
    
    # Direction and strength
    direction: str  # "bullish", "bearish", "neutral"
    strength: str  # "strong", "moderate", "weak"
    
    # Scores that fed into the decision
    composite_score: float
    surprise_score: float
    consensus_alignment: float  # -1 to 1
    
    # Decision reasoning
    reasons: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Risk assessment
    risk_level: str = "unknown"  # "low", "medium", "high"
    position_size_suggestion: str = "none"  # "full", "half", "quarter", "none"
    
    # Metadata
    generated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "decision": self.decision.value,
            "decision_label": self.get_decision_label(),
            "confidence": self.confidence,
            "direction": self.direction,
            "strength": self.strength,
            "composite_score": self.composite_score,
            "surprise_score": self.surprise_score,
            "consensus_alignment": self.consensus_alignment,
            "reasons": self.reasons,
            "warnings": self.warnings,
            "risk_level": self.risk_level,
            "position_size": self.position_size_suggestion,
            "actionable": self.decision.is_actionable(),
        }
    
    def get_decision_label(self) -> str:
        """Get human-readable decision label."""
        labels = {
            TradeDecision.STRONG_BUY_GOLD: "🟢 STRONG BUY GOLD",
            TradeDecision.BUY_GOLD: "🟢 BUY GOLD",
            TradeDecision.WAIT: "🟡 WAIT",
            TradeDecision.SELL_GOLD: "🔴 SELL GOLD",
            TradeDecision.STRONG_SELL_GOLD: "🔴 STRONG SELL GOLD",
            TradeDecision.NO_TRADE: "⚪ NO TRADE",
        }
        return labels.get(self.decision, "UNKNOWN")
    
    def get_decision_emoji(self) -> str:
        """Get emoji representing the decision."""
        emojis = {
            TradeDecision.STRONG_BUY_GOLD: "🟢",
            TradeDecision.BUY_GOLD: "🟢",
            TradeDecision.WAIT: "🟡",
            TradeDecision.SELL_GOLD: "🔴",
            TradeDecision.STRONG_SELL_GOLD: "🔴",
            TradeDecision.NO_TRADE: "⚪",
        }
        return emojis.get(self.decision, "❓")


class TradeDecisionEngine:
    """
    No Trade Zone decision engine for the Event Impact Scoring System.
    
    Applies deterministic rules to filter out low-quality signals and
    prevent trading during unfavorable conditions.
    """
    
    # Configuration thresholds
    DEFAULT_CONFIG = {
        # Score thresholds
        "min_composite_score_for_trade": 5.5,
        "min_surprise_score_for_strong": 4.0,
        "min_confidence_for_trade": 60.0,
        
        # Consensus thresholds
        "consensus_contradiction_threshold": -0.3,  # Strong disagreement
        "consensus_alignment_threshold": 0.5,  # Good agreement
        
        # Surprise thresholds
        "no_trade_if_deviation_below": 5.0,  # % deviation too small
        "mixed_signal_threshold": 15.0,  # Multiple events within X minutes
        
        # Volatility/condition thresholds
        "max_acceptable_spread_pips": 50,
        "max_volatility_percentile": 90,
        
        # Confidence multipliers
        "strong_signal_threshold": 75.0,
        "high_impact_threshold": 7.0,
    }
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Trade Decision Engine.
        
        Args:
            config: Configuration dictionary overriding defaults
        """
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.reasons: List[str] = []
        self.warnings: List[str] = []
    
    def evaluate(
        self,
        composite_score: float,
        surprise_result: SurpriseResult,
        consensus_comparison: Optional[ConsensusComparison],
        category: EventCategory,
        market_conditions: Optional[Dict[str, Any]] = None,
        related_events: Optional[List[Dict[str, Any]]] = None,
    ) -> TradeRecommendation:
        """
        Evaluate trading conditions and generate recommendation.
        
        Args:
            composite_score: Combined impact score (-10 to +10)
            surprise_result: Surprise analysis result
            consensus_comparison: Market consensus comparison (optional)
            category: Event category
            market_conditions: Current market conditions (optional)
            related_events: Other events around same time (optional)
        
        Returns:
            TradeRecommendation with decision, confidence, and reasoning
        """
        self.reasons = []
        self.warnings = []
        
        # Extract key values
        surprise_score = surprise_result.surprise_score if surprise_result else 0
        deviation_pct = abs(surprise_result.deviation_pct) if surprise_result else 0
        
        # Calculate consensus alignment
        consensus_alignment = self._calculate_consensus_alignment(
            consensus_comparison, composite_score
        )
        
        # Apply No Trade Zone rules in order
        decision, confidence = self._apply_no_trade_rules(
            composite_score=composite_score,
            surprise_score=surprise_score,
            deviation_pct=deviation_pct,
            consensus_alignment=consensus_alignment,
            category=category,
            market_conditions=market_conditions or {},
            related_events=related_events or [],
        )
        
        # Determine direction and strength
        direction = self._determine_direction(composite_score, surprise_result)
        strength = self._determine_strength(composite_score, confidence)
        
        # Calculate risk level
        risk_level = self._assess_risk(
            decision, composite_score, consensus_alignment, market_conditions
        )
        
        # Suggest position size
        position_size = self._suggest_position_size(decision, confidence, risk_level)
        
        # Build final recommendation
        return TradeRecommendation(
            decision=decision,
            confidence=confidence,
            direction=direction,
            strength=strength,
            composite_score=composite_score,
            surprise_score=surprise_score,
            consensus_alignment=consensus_alignment,
            reasons=self.reasons.copy(),
            warnings=self.warnings.copy(),
            risk_level=risk_level,
            position_size_suggestion=position_size,
        )
    
    def _apply_no_trade_rules(
        self,
        composite_score: float,
        surprise_score: float,
        deviation_pct: float,
        consensus_alignment: float,
        category: EventCategory,
        market_conditions: Dict[str, Any],
        related_events: List[Dict[str, Any]],
    ) -> Tuple[TradeDecision, float]:
        """
        Apply all No Trade Zone rules and determine decision.
        
        Returns:
            Tuple of (TradeDecision, confidence_score)
        """
        confidence = 50.0  # Start at neutral
        
        # RULE 1: Score too low for trading
        min_score = self.config["min_composite_score_for_trade"]
        if abs(composite_score) < min_score:
            self.reasons.append(
                f"❌ Composite score |{composite_score:.1f}| < {min_score} threshold"
            )
            return TradeDecision.NO_TRADE, confidence
        
        # RULE 2: Surprise too small (actual close to forecast)
        min_deviation = self.config["no_trade_if_deviation_below"]
        if deviation_pct < min_deviation and deviation_pct > 0:
            self.reasons.append(
                f"❌ Deviation {deviation_pct:.1f}% < {min_deviation}% - too close to forecast"
            )
            return TradeDecision.NO_TRADE, confidence
        
        # RULE 3: Consensus strongly contradicts surprise
        contradiction_threshold = self.config["consensus_contradiction_threshold"]
        if consensus_alignment < contradiction_threshold:
            self.reasons.append(
                f"🟡 Consensus ({consensus_alignment:+.2f}) contradicts surprise signal"
            )
            self.warnings.append("Market consensus disagrees with data surprise")
            return TradeDecision.WAIT, confidence
        
        # RULE 4: Multiple related events = mixed signals
        if related_events and len(related_events) >= 2:
            self.reasons.append(
                f"🟡 {len(related_events)} events within time window - mixed signals"
            )
            self.warnings.append("Multiple events detected - wait for clarity")
            return TradeDecision.WAIT, confidence
        
        # RULE 5: Check market conditions if available
        if market_conditions:
            # High spread
            spread = market_conditions.get("spread_pips", 0)
            max_spread = self.config["max_acceptable_spread_pips"]
            if spread > max_spread:
                self.reasons.append(
                    f"❌ Spread {spread} pips > {max_spread} max"
                )
                return TradeDecision.NO_TRADE, confidence
            
            # High volatility
            vol_percentile = market_conditions.get("volatility_percentile", 0)
            max_vol = self.config["max_volatility_percentile"]
            if vol_percentile > max_vol:
                self.reasons.append(
                    f"❌ Volatility at {vol_percentile}th percentile (high)"
                )
                self.warnings.append("Extreme volatility - avoid trading")
                return TradeDecision.NO_TRADE, confidence
        
        # At this point, basic conditions are met
        # Now determine if we have a tradeable signal
        
        # Calculate base confidence from score magnitude
        confidence = min(100, abs(composite_score) * 10)
        
        # Boost confidence if consensus aligns
        alignment_threshold = self.config["consensus_alignment_threshold"]
        if consensus_alignment >= alignment_threshold:
            confidence += 15
            self.reasons.append(
                f"✅ Consensus aligns ({consensus_alignment:+.2f})"
            )
        elif consensus_alignment > 0:
            confidence += 5
            self.reasons.append(
                f"✓ Consensus slightly favors direction ({consensus_alignment:+.2f})"
            )
        
        # Check for high impact signal
        high_impact_threshold = self.config["high_impact_threshold"]
        if abs(composite_score) >= high_impact_threshold:
            self.reasons.append(
                f"✅ High impact score ({abs(composite_score):.1f})"
            )
        
        # Determine final decision based on confidence and direction
        min_confidence = self.config["min_confidence_for_trade"]
        strong_threshold = self.config["strong_signal_threshold"]
        
        if confidence < min_confidence:
            self.reasons.append(
                f"🟡 Confidence {confidence:.0f}% < {min_confidence}% threshold"
            )
            return TradeDecision.WAIT, confidence
        
        # Decision is actionable - determine strength
        if composite_score > 0:
            # Bullish
            if confidence >= strong_threshold and abs(composite_score) >= 7:
                return TradeDecision.STRONG_BUY_GOLD, confidence
            else:
                return TradeDecision.BUY_GOLD, confidence
        else:
            # Bearish
            if confidence >= strong_threshold and abs(composite_score) >= 7:
                return TradeDecision.STRONG_SELL_GOLD, confidence
            else:
                return TradeDecision.SELL_GOLD, confidence
    
    def _calculate_consensus_alignment(
        self,
        consensus: Optional[ConsensusComparison],
        composite_score: float
    ) -> float:
        """
        Calculate how well consensus aligns with the surprise signal.
        
        Returns:
            Alignment score from -1 (contradicts) to +1 (fully aligns)
        """
        if not consensus:
            return 0.0
        
        # Get market probability direction
        market_bullish = consensus.market_bullish_probability
        market_bearish = consensus.market_bearish_probability
        
        if market_bullish > market_bearish:
            market_direction = 1  # Bullish
        elif market_bearish > market_bullish:
            market_direction = -1  # Bearish
        else:
            market_direction = 0  # Neutral
        
        # Get signal direction
        if composite_score > 1:
            signal_direction = 1
        elif composite_score < -1:
            signal_direction = -1
        else:
            signal_direction = 0
        
        # Calculate alignment
        if signal_direction == 0:
            return 0.0
        
        alignment = signal_direction * market_direction
        
        # Adjust by strength of consensus
        confidence = getattr(consensus, 'confidence', 0.5)
        return alignment * confidence
    
    def _determine_direction(self, composite_score: float, 
                             surprise_result: SurpriseResult) -> str:
        """Determine the directional bias."""
        if composite_score > 2:
            return "bullish"
        elif composite_score < -2:
            return "bearish"
        else:
            return "neutral"
    
    def _determine_strength(self, composite_score: float, confidence: float) -> str:
        """Determine signal strength."""
        score_magnitude = abs(composite_score)
        
        if score_magnitude >= 7 and confidence >= 75:
            return "strong"
        elif score_magnitude >= 4 and confidence >= 50:
            return "moderate"
        else:
            return "weak"
    
    def _assess_risk(
        self,
        decision: TradeDecision,
        composite_score: float,
        consensus_alignment: float,
        market_conditions: Optional[Dict[str, Any]]
    ) -> str:
        """Assess risk level for the trade."""
        risk_factors = 0
        
        # Non-actionable decisions are low risk (no position)
        if not decision.is_actionable():
            return "low"
        
        # Score magnitude
        if abs(composite_score) < 5:
            risk_factors += 1
        
        # Consensus disagreement
        if consensus_alignment < 0:
            risk_factors += 1
        
        # Market conditions
        if market_conditions:
            if market_conditions.get("spread_pips", 0) > 30:
                risk_factors += 1
            if market_conditions.get("volatility_percentile", 0) > 75:
                risk_factors += 1
        
        if risk_factors >= 3:
            return "high"
        elif risk_factors >= 1:
            return "medium"
        return "low"
    
    def _suggest_position_size(
        self,
        decision: TradeDecision,
        confidence: float,
        risk_level: str
    ) -> str:
        """Suggest position size based on decision quality."""
        if not decision.is_actionable():
            return "none"
        
        # Base on confidence and risk
        if confidence >= 80 and risk_level == "low":
            return "full"
        elif confidence >= 60 and risk_level in ["low", "medium"]:
            return "half"
        elif confidence >= 50:
            return "quarter"
        else:
            return "none"
    
    def quick_evaluate(
        self,
        composite_score: float,
        deviation_pct: float = 0,
        has_consensus: bool = False,
    ) -> Tuple[TradeDecision, str]:
        """
        Quick evaluation for simple cases.
        
        Returns:
            Tuple of (decision, reason)
        """
        min_score = self.config["min_composite_score_for_trade"]
        min_deviation = self.config["no_trade_if_deviation_below"]
        
        if abs(composite_score) < min_score:
            return TradeDecision.NO_TRADE, f"Score too low ({composite_score:.1f})"
        
        if deviation_pct > 0 and deviation_pct < min_deviation:
            return TradeDecision.NO_TRADE, f"Deviation too small ({deviation_pct:.1f}%)"
        
        if not has_consensus:
            return TradeDecision.WAIT, "Awaiting market consensus"
        
        # Direction based on score
        if composite_score > 0:
            return TradeDecision.BUY_GOLD, "Score signals bullish"
        else:
            return TradeDecision.SELL_GOLD, "Score signals bearish"


# Convenience function
def evaluate_trade_signal(
    composite_score: float,
    surprise_result: SurpriseResult,
    consensus_comparison: Optional[ConsensusComparison] = None,
    category: EventCategory = EventCategory.UNKNOWN,
    **kwargs
) -> TradeRecommendation:
    """
    Convenience function to evaluate a trade signal.
    
    Args:
        composite_score: Combined impact score (-10 to +10)
        surprise_result: Surprise analysis result
        consensus_comparison: Market consensus data
        category: Event category
        **kwargs: Additional parameters for market conditions, related events, etc.
    
    Returns:
        TradeRecommendation with full analysis
    """
    engine = TradeDecisionEngine()
    return engine.evaluate(
        composite_score=composite_score,
        surprise_result=surprise_result,
        consensus_comparison=consensus_comparison,
        category=category,
        market_conditions=kwargs.get('market_conditions'),
        related_events=kwargs.get('related_events'),
    )
