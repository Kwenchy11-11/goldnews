"""Event Cluster Engine - Multi-Event Conflict Handling

Groups simultaneous economic events (released within same time window) and analyzes
them as a cluster to detect conflicts and provide unified trading signals.

Key features:
- Groups events within 1-minute windows
- Weighted scoring by category importance
- Conflict detection (aligned/mixed/unclear)
- Aggregated cluster direction and score
- Thai-language explanations

Example NFP cluster:
- Nonfarm Payrolls: +200k (bearish for gold)
- Unemployment Rate: 4.0% (bullish for gold)
- Average Hourly Earnings: +0.2% (neutral)
- Result: Mixed signal with weighted aggregation
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Dict, Optional, Any, Tuple
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from event_classifier import EventCategory, classify_event
from event_impact_engine import EventImpactEngine, analyze_event_impact
from surprise_engine import SurpriseResult, EconomicDataPoint
from trade_decision_engine import TradeDecisionEngine, TradeDecision


class ConflictLevel(Enum):
    """Level of conflict within an event cluster."""
    ALIGNED = "aligned"           # All signals point same direction
    MOSTLY_ALIGNED = "mostly"     # Most signals agree
    MIXED = "mixed"               # Conflicting signals
    UNCLEAR = "unclear"           # Too many neutral signals


class ClusterDirection(Enum):
    """Overall direction of the cluster."""
    STRONGLY_BULLISH = "strongly_bullish"
    BULLISH = "bullish"
    NEUTRAL = "neutral"
    BEARISH = "bearish"
    STRONGLY_BEARISH = "strongly_bearish"


@dataclass
class ClusterEvent:
    """An event within a cluster with its analysis."""
    event_name: str
    event_time: datetime
    category: EventCategory
    actual: Optional[float]
    forecast: Optional[float]
    previous: Optional[float]
    unit: str
    
    # Analysis results
    impact_score: float = 0.0
    composite_score: float = 0.0
    surprise_score: float = 0.0
    direction: str = "neutral"  # bullish/bearish/neutral for gold
    confidence: float = 0.0
    
    # Category weight
    category_weight: float = 1.0


@dataclass
class EventCluster:
    """A group of simultaneous economic events."""
    cluster_id: str
    cluster_time: datetime
    events: List[ClusterEvent]
    
    # Aggregate metrics
    cluster_score: float = 0.0
    cluster_direction: ClusterDirection = ClusterDirection.NEUTRAL
    conflict_level: ConflictLevel = ConflictLevel.UNCLEAR
    
    # Signal quality
    bullish_score: float = 0.0
    bearish_score: float = 0.0
    neutral_score: float = 0.0
    
    # Trading recommendation
    final_alert_level: str = "none"  # immediate/high/normal/low/none
    trade_decision: Optional[TradeDecision] = None
    
    # Explanations
    summary_thai: str = ""
    conflict_explanation: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert cluster to dictionary."""
        return {
            "cluster_id": self.cluster_id,
            "cluster_time": self.cluster_time.isoformat(),
            "event_count": len(self.events),
            "cluster_score": round(self.cluster_score, 2),
            "cluster_direction": self.cluster_direction.value,
            "conflict_level": self.conflict_level.value,
            "bullish_score": round(self.bullish_score, 2),
            "bearish_score": round(self.bearish_score, 2),
            "neutral_score": round(self.neutral_score, 2),
            "final_alert_level": self.final_alert_level,
            "trade_decision": self.trade_decision.value if self.trade_decision else None,
            "summary_thai": self.summary_thai,
            "events": [
                {
                    "name": e.event_name,
                    "category": e.category.value,
                    "actual": e.actual,
                    "forecast": e.forecast,
                    "composite_score": round(e.composite_score, 2),
                    "direction": e.direction,
                    "weight": e.category_weight,
                }
                for e in self.events
            ],
        }


class EventClusterEngine:
    """
    Engine for grouping and analyzing simultaneous economic events.
    
    Handles complex scenarios like NFP releases where multiple indicators
    come out at the same time with potentially conflicting signals.
    """
    
    # Category weights - higher = more important for gold
    CATEGORY_WEIGHTS = {
        # Primary indicators (highest weight)
        EventCategory.INFLATION: 1.5,      # CPI, Core CPI
        EventCategory.LABOR: 1.4,          # NFP payrolls
        EventCategory.FED_POLICY: 1.5,     # Rate decisions
        
        # Secondary labor indicators (high weight)
        EventCategory.CONSUMER: 1.2,       # Consumer data
        EventCategory.GROWTH: 1.3,         # GDP
        
        # Supporting indicators (medium weight)
        EventCategory.MANUFACTURING: 1.0,  # ISM, PMI
        EventCategory.YIELDS: 1.1,         # Bond yields
        
        # Lower weight indicators
        EventCategory.GEOPOLITICS: 0.8,    # Hard to quantify
        EventCategory.UNKNOWN: 0.7,        # Unknown category
    }
    
    # Special event patterns and their weights
    EVENT_SPECIFIC_WEIGHTS = {
        # Labor market
        "nonfarm payrolls": 1.6,
        "unemployment rate": 1.3,
        "average hourly earnings": 1.2,
        "labor force participation": 0.9,
        
        # Inflation
        "cpi": 1.5,
        "core cpi": 1.5,
        "ppi": 1.3,
        "core ppi": 1.3,
        
        # Fed
        "fomc": 1.5,
        "interest rate decision": 1.5,
        "dot plot": 1.2,
        
        # Growth
        "gdp": 1.3,
        "retail sales": 1.1,
    }
    
    # Time window for clustering (seconds)
    CLUSTER_WINDOW_SECONDS = 60
    
    # Conflict detection thresholds
    CONFLICT_THRESHOLD = 0.3  # Ratio of opposing signals to trigger "mixed"
    ALIGNMENT_THRESHOLD = 0.7  # Ratio of agreeing signals for "aligned"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Event Cluster Engine.
        
        Args:
            config: Optional configuration overrides
        """
        self.config = config or {}
        self.impact_engine = EventImpactEngine()
        self.trade_engine = TradeDecisionEngine()
        
        # Override defaults with config
        self.cluster_window = self.config.get(
            "cluster_window_seconds", self.CLUSTER_WINDOW_SECONDS
        )
    
    def group_events_into_clusters(
        self,
        events: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Group events into clusters based on release time.
        
        Args:
            events: List of event dictionaries with 'time' field
            
        Returns:
            List of event clusters (each cluster is a list of events)
        """
        if not events:
            return []
        
        # Sort by time
        sorted_events = sorted(events, key=lambda e: e.get("time", datetime.min))
        
        clusters = []
        current_cluster = [sorted_events[0]]
        
        for event in sorted_events[1:]:
            last_time = current_cluster[-1].get("time", datetime.min)
            event_time = event.get("time", datetime.min)
            
            # Check if within window
            if (event_time - last_time).total_seconds() <= self.cluster_window:
                current_cluster.append(event)
            else:
                clusters.append(current_cluster)
                current_cluster = [event]
        
        # Don't forget the last cluster
        if current_cluster:
            clusters.append(current_cluster)
        
        return clusters
    
    def analyze_cluster(
        self,
        events: List[Dict[str, Any]],
        cluster_time: Optional[datetime] = None
    ) -> EventCluster:
        """
        Analyze a cluster of simultaneous events.
        
        Args:
            events: List of events in the cluster
            cluster_time: Time of the cluster (defaults to first event time)
            
        Returns:
            EventCluster with aggregated analysis
        """
        if not events:
            raise ValueError("Cannot analyze empty cluster")
        
        # Determine cluster time
        if cluster_time is None:
            cluster_time = events[0].get("time", datetime.now())
        
        # Generate cluster ID
        cluster_id = self._generate_cluster_id(cluster_time, events)
        
        # Analyze each event
        cluster_events = []
        for event_data in events:
            cluster_event = self._analyze_single_event(event_data)
            cluster_events.append(cluster_event)
        
        # Create cluster
        cluster = EventCluster(
            cluster_id=cluster_id,
            cluster_time=cluster_time,
            events=cluster_events
        )
        
        # Calculate aggregate metrics
        self._calculate_cluster_metrics(cluster)
        
        # Detect conflicts
        self._detect_conflicts(cluster)
        
        # Determine final signal
        self._determine_final_signal(cluster)
        
        # Generate Thai explanation
        cluster.summary_thai = self._generate_thai_summary(cluster)
        cluster.conflict_explanation = self._generate_conflict_explanation(cluster)
        
        return cluster
    
    def _analyze_single_event(self, event_data: Dict[str, Any]) -> ClusterEvent:
        """Analyze a single event within a cluster."""
        # Extract event details
        name = event_data.get("name", "Unknown")
        time = event_data.get("time", datetime.now())
        actual = event_data.get("actual")
        forecast = event_data.get("forecast")
        previous = event_data.get("previous")
        unit = event_data.get("unit", "%")
        
        # Classify event
        event_dict = {
            'title': name,
            'country': 'USD',
            'impact': 'HIGH'
        }
        classification = classify_event(event_dict)
        category = classification.category
        
        # Get category weight
        weight = self._get_event_weight(name, category)
        
        # Detect specific indicator type for surprise calculation
        # This is important for unemployment data which has inverse logic
        name_lower = name.lower()
        if 'unemployment' in name_lower or 'jobless' in name_lower:
            # Use specific unemployment category for correct gold impact
            indicator_category = "unemployment"
        elif 'nfp' in name_lower or 'nonfarm' in name_lower or 'payroll' in name_lower:
            indicator_category = "nfp"
        elif 'wage' in name_lower or 'earnings' in name_lower:
            indicator_category = "employment"  # Wages act like employment data
        else:
            indicator_category = category.value
        
        # Analyze using impact engine
        try:
            # Get base classification
            impact_score = classify_event(event_dict)
            
            # Calculate surprise with specific indicator category
            from surprise_engine import SurpriseEngine, EconomicDataPoint
            data_point = EconomicDataPoint(
                name=name,
                actual=actual if actual is not None else 0,
                forecast=forecast if forecast is not None else 0,
                previous=previous,
            )
            surprise_engine = SurpriseEngine()
            surprise = surprise_engine.calculate_surprise(data_point, indicator_category)
            
            # Calculate composite score similar to analyze_event_impact
            base_magnitude = impact_score.base_impact_score / 10.0
            if impact_score.gold_correlation == "positive":
                base_directional = base_magnitude * 10
            elif impact_score.gold_correlation == "negative":
                base_directional = -base_magnitude * 10
            else:
                base_directional = 0.0
            
            composite = base_directional * 0.20 + surprise.surprise_score * 0.80
            composite = max(-10, min(10, composite))
            
            impact_result = {
                "event_name": name,
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
            
            # analyze_event_impact returns a dict, not an object
            composite_score = impact_result.get('composite_score', 0)
            
            # Get surprise score if available
            surprise_score = impact_result.get('surprise_score', 0)
            
            # Determine direction based on gold_impact from surprise analysis
            # This is more accurate than composite score sign for inverse-logic events like unemployment
            gold_impact = impact_result.get('gold_impact', 'neutral')
            if gold_impact == 'bullish':
                direction = "bullish"
            elif gold_impact == 'bearish':
                direction = "bearish"
            else:
                direction = "neutral"
            
            # Calculate confidence
            confidence = min(100, abs(composite_score) * 10 + 20)
            
        except Exception as e:
            # Fallback to simple analysis
            composite_score = 0
            surprise_score = 0
            direction = "neutral"
            confidence = 0
        
        return ClusterEvent(
            event_name=name,
            event_time=time,
            category=category,
            actual=actual,
            forecast=forecast,
            previous=previous,
            unit=unit,
            impact_score=classification.base_impact_score if hasattr(classification, 'base_impact_score') else 5,
            composite_score=composite_score,
            surprise_score=surprise_score,
            direction=direction,
            confidence=confidence,
            category_weight=weight
        )
    
    def _get_event_weight(self, event_name: str, category: EventCategory) -> float:
        """Get the weight for an event based on name and category."""
        name_lower = event_name.lower()
        
        # Check specific event patterns first
        for pattern, weight in self.EVENT_SPECIFIC_WEIGHTS.items():
            if pattern in name_lower:
                return weight
        
        # Fall back to category weight
        return self.CATEGORY_WEIGHTS.get(category, 1.0)
    
    def _calculate_cluster_metrics(self, cluster: EventCluster):
        """Calculate aggregate scores for the cluster."""
        bullish_weighted = 0.0
        bearish_weighted = 0.0
        neutral_weighted = 0.0
        total_weight = 0.0
        
        for event in cluster.events:
            weight = event.category_weight
            score = abs(event.composite_score)
            
            if event.direction == "bullish":
                bullish_weighted += score * weight
            elif event.direction == "bearish":
                bearish_weighted += score * weight
            else:
                neutral_weighted += score * weight * 0.5  # Neutral has less impact
            
            total_weight += weight
        
        # Store raw scores
        cluster.bullish_score = bullish_weighted
        cluster.bearish_score = bearish_weighted
        cluster.neutral_score = neutral_weighted
        
        # Calculate net score (bearish is positive for score, negative for gold)
        # Flip: bullish is good for gold (negative for score), bearish is bad (positive)
        cluster.cluster_score = (bearish_weighted - bullish_weighted) / max(total_weight, 1.0)
    
    def _detect_conflicts(self, cluster: EventCluster):
        """Detect conflict level within the cluster."""
        bullish_count = sum(1 for e in cluster.events if e.direction == "bullish")
        bearish_count = sum(1 for e in cluster.events if e.direction == "bearish")
        neutral_count = sum(1 for e in cluster.events if e.direction == "neutral")
        total = len(cluster.events)
        
        if total == 0:
            cluster.conflict_level = ConflictLevel.UNCLEAR
            return
        
        # Calculate ratios
        bullish_ratio = bullish_count / total
        bearish_ratio = bearish_count / total
        
        # Check for alignment
        dominant_ratio = max(bullish_ratio, bearish_ratio)
        opposing_ratio = min(bullish_ratio, bearish_ratio)
        
        if dominant_ratio >= self.ALIGNMENT_THRESHOLD and opposing_ratio < self.CONFLICT_THRESHOLD:
            cluster.conflict_level = ConflictLevel.ALIGNED
        elif dominant_ratio >= 0.5 and opposing_ratio < self.CONFLICT_THRESHOLD:
            cluster.conflict_level = ConflictLevel.MOSTLY_ALIGNED
        elif opposing_ratio >= self.CONFLICT_THRESHOLD:
            cluster.conflict_level = ConflictLevel.MIXED
        else:
            cluster.conflict_level = ConflictLevel.UNCLEAR
        
        # Determine cluster direction
        score = cluster.cluster_score
        abs_score = abs(score)
        
        if abs_score < 1:
            cluster.cluster_direction = ClusterDirection.NEUTRAL
        elif score > 0:
            # Bearish for gold (USD positive)
            cluster.cluster_direction = (
                ClusterDirection.STRONGLY_BEARISH if abs_score >= 6 
                else ClusterDirection.BEARISH
            )
        else:
            # Bullish for gold
            cluster.cluster_direction = (
                ClusterDirection.STRONGLY_BULLISH if abs_score >= 6 
                else ClusterDirection.BULLISH
            )
    
    def _determine_final_signal(self, cluster: EventCluster):
        """Determine final alert level and trade decision."""
        score = abs(cluster.cluster_score)
        
        # Determine alert level based on score and conflict
        if cluster.conflict_level in [ConflictLevel.MIXED, ConflictLevel.UNCLEAR]:
            # Lower alert for conflicting signals
            if score >= 5:
                cluster.final_alert_level = "normal"
            else:
                cluster.final_alert_level = "low"
        else:
            # Clear signals can have higher alerts
            if score >= 8:
                cluster.final_alert_level = "immediate"
            elif score >= 6:
                cluster.final_alert_level = "high"
            elif score >= 4:
                cluster.final_alert_level = "normal"
            elif score >= 2:
                cluster.final_alert_level = "low"
            else:
                cluster.final_alert_level = "none"
        
        # Create mock surprise result for trade decision
        mock_surprise = SurpriseResult(
            surprise_score=cluster.cluster_score,
            deviation_pct=score * 2,
            direction="above" if cluster.cluster_score > 0 else "below",
            significance="high" if score >= 5 else "medium",
            gold_impact="bearish" if cluster.cluster_score > 0 else "bullish"
        )
        
        # Get trade decision
        trade_rec = self.trade_engine.evaluate(
            composite_score=cluster.cluster_score,
            surprise_result=mock_surprise,
            consensus_comparison=None,
            category=cluster.events[0].category if cluster.events else EventCategory.UNKNOWN,
        )
        
        cluster.trade_decision = trade_rec.decision
    
    def _generate_cluster_id(self, time: datetime, events: List[Dict]) -> str:
        """Generate unique ID for the cluster."""
        time_str = time.strftime("%Y%m%d_%H%M")
        event_names = "_".join(e.get("name", "unknown")[:10] for e in events[:3])
        return f"cluster_{time_str}_{event_names}"
    
    def _generate_thai_summary(self, cluster: EventCluster) -> str:
        """Generate Thai language summary of the cluster."""
        event_names = [e.event_name for e in cluster.events]
        event_list = ", ".join(event_names[:3])
        if len(event_names) > 3:
            event_list += f" และอีก {len(event_names) - 3} ตัว"
        
        # Direction in Thai
        direction_thai = {
            ClusterDirection.STRONGLY_BULLISH: "ทองคำมีแนวโน้มแข็งค่าอย่างมาก",
            ClusterDirection.BULLISH: "ทองคำมีแนวโน้มแข็งค่า",
            ClusterDirection.NEUTRAL: "ทองคำมีแนวโน้มเป็นกลาง",
            ClusterDirection.BEARISH: "ทองคำมีแนวโน้มอ่อนค่า",
            ClusterDirection.STRONGLY_BEARISH: "ทองคำมีแนวโน้มอ่อนค่าอย่างมาก",
        }.get(cluster.cluster_direction, "ไม่สามารถระบุทิศทางได้")
        
        # Conflict explanation
        conflict_thai = {
            ConflictLevel.ALIGNED: "สัญญาณชัดเจน",
            ConflictLevel.MOSTLY_ALIGNED: "สัญญาณส่วนใหญ่ตรงกัน",
            ConflictLevel.MIXED: "สัญญาณขัดแย้งกัน",
            ConflictLevel.UNCLEAR: "สัญญาณไม่ชัดเจน",
        }.get(cluster.conflict_level, "ไม่ทราบสถานะ")
        
        summary = f"กลุ่มข่าว: {event_list}. "
        summary += f"{direction_thai} (คะแนนรวม {cluster.cluster_score:+.1f}). "
        summary += f"สถานะ: {conflict_thai}."
        
        return summary
    
    def _generate_conflict_explanation(self, cluster: EventCluster) -> str:
        """Generate explanation of any conflicts detected."""
        if cluster.conflict_level == ConflictLevel.ALIGNED:
            return "ข้อมูลทั้งหมดชี้ไปในทิศทางเดียวกัน"
        
        if cluster.conflict_level == ConflictLevel.MOSTLY_ALIGNED:
            return "ข้อมูลส่วนใหญ่ชี้ไปในทิศทางเดียวกัน มีบางตัวเป็นกลาง"
        
        # For mixed/unclear, explain the conflict
        bullish_events = [e for e in cluster.events if e.direction == "bullish"]
        bearish_events = [e for e in cluster.events if e.direction == "bearish"]
        
        explanations = []
        
        if bullish_events:
            names = ", ".join(e.event_name for e in bullish_events[:2])
            if len(bullish_events) > 2:
                names += f" และอีก {len(bullish_events) - 2}"
            explanations.append(f"{names} บ่งชี้ทองขึ้น")
        
        if bearish_events:
            names = ", ".join(e.event_name for e in bearish_events[:2])
            if len(bearish_events) > 2:
                names += f" และอีก {len(bearish_events) - 2}"
            explanations.append(f"{names} บ่งชี้ทองลง")
        
        if cluster.conflict_level == ConflictLevel.MIXED:
            return f"สัญญาณขัดแย้ง: {' | '.join(explanations)}"
        else:
            return f"สัญญาณไม่ชัดเจน: {' | '.join(explanations) if explanations else 'ข้อมูลไม่เพียงพอ'}"
    
    def analyze_event_batch(
        self,
        events: List[Dict[str, Any]]
    ) -> List[EventCluster]:
        """
        Analyze a batch of events, grouping them into clusters first.
        
        Args:
            events: List of all events to analyze
            
        Returns:
            List of EventCluster results
        """
        # Group into clusters
        event_groups = self.group_events_into_clusters(events)
        
        # Analyze each cluster
        clusters = []
        for group in event_groups:
            cluster = self.analyze_cluster(group)
            clusters.append(cluster)
        
        return clusters


# Convenience function
def analyze_event_cluster(
    events: List[Dict[str, Any]],
    cluster_time: Optional[datetime] = None
) -> EventCluster:
    """
    Convenience function to analyze a single cluster of events.
    
    Args:
        events: List of events in the cluster
        cluster_time: Optional explicit cluster time
        
    Returns:
        EventCluster with full analysis
    """
    engine = EventClusterEngine()
    return engine.analyze_cluster(events, cluster_time)
