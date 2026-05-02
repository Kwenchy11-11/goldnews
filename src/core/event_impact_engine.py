"""Event Impact Engine - Main orchestrator for the Event Impact Scoring System.

Coordinates all layers:
- Layer 1: Event Classification
- Layer 2: Surprise Calculation
- Layer 3: Consensus Analysis
- Layer 5: Event Logging

Provides unified interface for processing economic events and generating
impact assessments for gold price movements.
"""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from event_classifier import classify_event, EventCategory, ImpactScore
from surprise_engine import (
    SurpriseEngine, EconomicDataPoint, SurpriseResult
)
from consensus_engine import (
    ConsensusEngine, ConsensusSource, ConsensusComparison
)
from event_logger import EventLogger, LoggedEvent


@dataclass
class EventImpactResult:
    """Complete impact assessment result for an economic event."""
    
    # Event identification
    event_id: str
    timestamp: datetime
    event_name: str
    category: EventCategory
    source: str
    
    # Classification (Layer 1)
    impact_score: ImpactScore
    
    # Surprise analysis (Layer 2)
    surprise_result: SurpriseResult
    data_point: EconomicDataPoint
    
    # Consensus (Layer 3)
    consensus_comparison: Optional[ConsensusComparison]
    
    # Combined assessment
    overall_gold_impact: str  # "strong-bullish", "bullish", "neutral", "bearish", "strong-bearish"
    confidence_score: float  # 0.0 to 1.0
    composite_score: float  # -10 to +10
    
    # Alert recommendations
    should_alert: bool
    alert_priority: str  # "immediate", "high", "normal", "low"
    alert_message: str
    
    # Metadata
    processed_at: datetime


class EventImpactEngine:
    """Main engine for processing economic events and calculating gold impact."""
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        db_path: Optional[str] = None,
    ):
        """Initialize the Event Impact Engine.
        
        Args:
            config: Configuration dictionary with settings for all layers
            db_path: Path to SQLite database for event logging
        """
        self.config = config or {}
        
        # Initialize sub-engines
        self.surprise_engine = SurpriseEngine(
            self.config.get("surprise_config")
        )
        self.consensus_engine = ConsensusEngine(
            self.config.get("consensus_config")
        )
        self.event_logger = EventLogger(
            db_path or self.config.get("db_path", "data/events.db")
        )
        
        # Alert thresholds
        self.alert_thresholds = self.config.get("alert_thresholds", {
            "immediate": 8.0,
            "high": 6.0,
            "normal": 4.0,
            "low": 2.0,
        })
        
        # Minimum confidence for alerting
        self.min_confidence = self.config.get("min_confidence", 0.5)
    
    async def process_event(
        self,
        event_name: str,
        timestamp: datetime,
        source: str,
        raw_text: str,
        actual: Optional[float] = None,
        forecast: Optional[float] = None,
        previous: Optional[float] = None,
        unit: str = "%",
        event_dict: Optional[Dict[str, Any]] = None,
    ) -> EventImpactResult:
        """Process an economic event through all layers.
        
        Args:
            event_name: Name of the economic indicator (e.g., "CPI", "NFP")
            timestamp: When the event was released
            source: Source of the event (e.g., "ForexFactory", "RSS")
            raw_text: Raw text content of the event
            actual: Actual released value
            forecast: Market forecast/consensus
            previous: Previous period value
            unit: Unit of measurement (%, K, etc.)
            event_dict: Optional dictionary for classification (title, country, impact)
            
        Returns:
            EventImpactResult with complete assessment
        """
        # Generate unique event ID
        event_id = self._generate_event_id(event_name, timestamp, source)
        
        # Layer 1: Classification
        if event_dict is None:
            event_dict = {
                "title": event_name,
                "country": "USD",
                "impact": "HIGH",
            }
        impact_score = classify_event(event_dict)
        
        # Layer 2: Surprise Calculation
        data_point = EconomicDataPoint(
            name=event_name,
            actual=actual,
            forecast=forecast,
            previous=previous,
            unit=unit,
            release_time=timestamp,
        )
        surprise_result = self.surprise_engine.calculate_surprise(
            data_point, impact_score.category.value
        )
        
        # Layer 3: Consensus Analysis
        consensus_comparison = None
        if self.config.get("enable_consensus", True):
            market_consensus = await self.consensus_engine.fetch_market_consensus(
                event_name, impact_score.category.value
            )
            consensus_comparison = self.consensus_engine.compare_with_forecast(
                market_consensus, forecast, impact_score.category.value
            )
        
        # Calculate composite score and overall impact
        composite_score = self._calculate_composite_score(
            impact_score, surprise_result, consensus_comparison
        )
        overall_impact = self._determine_overall_impact(composite_score)
        confidence = self._calculate_confidence(
            impact_score, surprise_result, consensus_comparison
        )
        
        # Determine if we should alert
        should_alert, alert_priority = self._determine_alert(
            composite_score, confidence, impact_score.base_impact_score
        )
        
        # Generate alert message
        alert_message = self._generate_alert_message(
            event_name, impact_score, surprise_result, 
            consensus_comparison, overall_impact, composite_score
        )
        
        # Create result
        result = EventImpactResult(
            event_id=event_id,
            timestamp=timestamp,
            event_name=event_name,
            category=impact_score.category,
            source=source,
            impact_score=impact_score,
            surprise_result=surprise_result,
            data_point=data_point,
            consensus_comparison=consensus_comparison,
            overall_gold_impact=overall_impact,
            confidence_score=confidence,
            composite_score=composite_score,
            should_alert=should_alert,
            alert_priority=alert_priority,
            alert_message=alert_message,
            processed_at=datetime.utcnow(),
        )
        
        # Layer 5: Log the event
        self._log_event(result)
        
        return result
    
    def _generate_event_id(
        self, event_name: str, timestamp: datetime, source: str
    ) -> str:
        """Generate unique event ID."""
        unique_string = f"{event_name}_{timestamp.isoformat()}_{source}"
        return hashlib.md5(unique_string.encode()).hexdigest()[:16]
    
    def _calculate_composite_score(
        self,
        impact_score: ImpactScore,
        surprise_result: SurpriseResult,
        consensus_comparison: Optional[ConsensusComparison],
    ) -> float:
        """Calculate composite impact score from all layers.
        
        Weights:
        - Base impact: 20%
        - Surprise: 70%
        - Consensus: 10%
        """
        # Calculate base impact direction based on gold correlation
        # Base impact score (1-10) indicates magnitude, correlation indicates direction
        base_magnitude = impact_score.base_impact_score / 10.0  # 0.1 to 1.0
        
        # Apply direction based on gold correlation
        if impact_score.gold_correlation == "positive":
            base_directional = base_magnitude * 10  # 1 to 10
        elif impact_score.gold_correlation == "negative":
            base_directional = -base_magnitude * 10  # -1 to -10
        else:
            base_directional = 0.0
        
        # Surprise score is already normalized (-10 to +10) with correct gold impact direction
        surprise = surprise_result.surprise_score
        
        # Consensus contribution
        consensus_score = 0.0
        if consensus_comparison and consensus_comparison.market_consensus:
            # If consensus diverges from forecast, it amplifies the signal
            divergence_factor = 1.0 + (consensus_comparison.divergence_score * 0.5)
            
            # Use trading signal as directional input
            signal_multipliers = {
                "strong-long": 2.0,
                "long": 1.0,
                "neutral": 0.0,
                "short": -1.0,
                "strong-short": -2.0,
            }
            consensus_score = signal_multipliers.get(
                consensus_comparison.trading_signal, 0.0
            ) * divergence_factor
        
        # Weighted average: surprise is most important
        composite = (
            base_directional * 0.20 +
            surprise * 0.70 +
            consensus_score * 0.10
        )
        
        return max(-10.0, min(10.0, composite))
    
    def _determine_overall_impact(self, composite_score: float) -> str:
        """Determine overall gold impact category."""
        if composite_score >= 7:
            return "strong-bullish"
        elif composite_score >= 3:
            return "bullish"
        elif composite_score <= -7:
            return "strong-bearish"
        elif composite_score <= -3:
            return "bearish"
        else:
            return "neutral"
    
    def _calculate_confidence(
        self,
        impact_score: ImpactScore,
        surprise_result: SurpriseResult,
        consensus_comparison: Optional[ConsensusComparison],
    ) -> float:
        """Calculate overall confidence in the assessment."""
        confidence = 0.5  # Base confidence
        
        # Higher base impact = higher confidence (known event types)
        if impact_score.category != EventCategory.UNKNOWN:
            confidence += 0.2
        
        # Significance of surprise
        if surprise_result.significance in ["high", "medium"]:
            confidence += 0.15
        
        # Consensus alignment
        if consensus_comparison:
            if consensus_comparison.market_consensus:
                confidence += consensus_comparison.market_consensus.confidence_score * 0.15
        
        return min(1.0, confidence)
    
    def _determine_alert(
        self, 
        composite_score: float, 
        confidence: float,
        base_impact: int
    ) -> tuple[bool, str]:
        """Determine if an alert should be sent and its priority.
        
        Returns:
            Tuple of (should_alert, priority)
        """
        if confidence < self.min_confidence:
            return False, "low"
        
        abs_score = abs(composite_score)
        
        # High base impact events get priority
        if base_impact >= 9:
            if abs_score >= self.alert_thresholds["immediate"]:
                return True, "immediate"
            elif abs_score >= self.alert_thresholds["high"]:
                return True, "high"
        
        # Standard alerting
        if abs_score >= self.alert_thresholds["immediate"]:
            return True, "immediate"
        elif abs_score >= self.alert_thresholds["high"]:
            return True, "high"
        elif abs_score >= self.alert_thresholds["normal"]:
            return True, "normal"
        elif abs_score >= self.alert_thresholds["low"]:
            return True, "low"
        
        return False, "low"
    
    def _generate_alert_message(
        self,
        event_name: str,
        impact_score: ImpactScore,
        surprise_result: SurpriseResult,
        consensus_comparison: Optional[ConsensusComparison],
        overall_impact: str,
        composite_score: float,
    ) -> str:
        """Generate human-readable alert message."""
        direction_emoji = {
            "strong-bullish": "🚀",
            "bullish": "📈",
            "neutral": "➡️",
            "bearish": "📉",
            "strong-bearish": "🔻",
        }.get(overall_impact, "➡️")
        
        message = f"{direction_emoji} {event_name}: {overall_impact.upper()}"
        message += f"\n   Composite Score: {composite_score:+.1f}/10"
        message += f"\n   Base Impact: {impact_score.base_impact_score}/10"
        message += f"\n   Surprise: {surprise_result.direction} ({surprise_result.significance})"
        
        if consensus_comparison and consensus_comparison.market_consensus:
            message += f"\n   Consensus: {consensus_comparison.trading_signal}"
        
        return message
    
    def _log_event(self, result: EventImpactResult):
        """Log event to database."""
        consensus_aligned = None
        divergence_score = None
        trading_signal = None
        
        if result.consensus_comparison:
            consensus_aligned = result.consensus_comparison.consensus_aligned
            divergence_score = result.consensus_comparison.divergence_score
            trading_signal = result.consensus_comparison.trading_signal
        
        self.event_logger.log_event(
            event_id=result.event_id,
            timestamp=result.timestamp,
            event_name=result.event_name,
            category=result.category,
            source=result.source,
            raw_text=result.data_point.name,  # Simplified
            impact_score=result.impact_score,
            surprise_result=result.surprise_result,
            data_point=result.data_point,
            consensus_aligned=consensus_aligned,
            divergence_score=divergence_score,
            trading_signal=trading_signal,
        )
    
    async def batch_process(
        self, events: List[Dict[str, Any]]
    ) -> List[EventImpactResult]:
        """Process multiple events in batch.
        
        Args:
            events: List of event dictionaries with all required fields
            
        Returns:
            List of EventImpactResult objects
        """
        results = []
        for event in events:
            result = await self.process_event(**event)
            results.append(result)
        return results
    
    def get_recent_events(
        self,
        hours: int = 24,
        category: Optional[str] = None,
        gold_impact: Optional[str] = None,
    ) -> List[LoggedEvent]:
        """Get recent logged events.
        
        Args:
            hours: How many hours back to query
            category: Filter by category
            gold_impact: Filter by gold impact
            
        Returns:
            List of LoggedEvent objects
        """
        from datetime import timedelta
        start_date = datetime.utcnow() - timedelta(hours=hours)
        return self.event_logger.get_events(
            start_date=start_date,
            category=category,
            gold_impact=gold_impact,
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall statistics from event logger."""
        return self.event_logger.get_statistics()


# Convenience function for quick analysis
def analyze_event_impact(
    event_name: str,
    actual: float,
    forecast: float,
    previous: Optional[float] = None,
    event_dict: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Quick analysis of a single event without async/consensus.
    
    Args:
        event_name: Name of the event
        actual: Actual value
        forecast: Forecast value
        previous: Previous value
        event_dict: Optional event dict for classification
        
    Returns:
        Dictionary with impact analysis
    """
    if event_dict is None:
        event_dict = {"title": event_name, "country": "USD", "impact": "HIGH"}
    
    # Classification
    impact_score = classify_event(event_dict)
    
    # Surprise calculation
    data_point = EconomicDataPoint(
        name=event_name,
        actual=actual,
        forecast=forecast,
        previous=previous,
    )
    engine = SurpriseEngine()
    surprise = engine.calculate_surprise(data_point, impact_score.category.value)
    
    # Determine overall impact
    base_magnitude = impact_score.base_impact_score / 10.0
    if impact_score.gold_correlation == "positive":
        base_directional = base_magnitude * 10
    elif impact_score.gold_correlation == "negative":
        base_directional = -base_magnitude * 10
    else:
        base_directional = 0.0
    
    composite = base_directional * 0.20 + surprise.surprise_score * 0.80
    composite = max(-10, min(10, composite))
    
    return {
        "event_name": event_name,
        "category": impact_score.category.value,
        "base_impact": impact_score.base_impact_score,
        "gold_correlation": impact_score.gold_correlation,
        "surprise_score": surprise.surprise_score,
        "deviation_pct": surprise.deviation_pct,
        "direction": surprise.direction,
        "significance": surprise.significance,
        "gold_impact": surprise.gold_impact,
        "composite_score": composite,
        "overall_impact": (
            "bullish" if composite > 3 else
            "bearish" if composite < -3 else
            "neutral"
        ),
    }
