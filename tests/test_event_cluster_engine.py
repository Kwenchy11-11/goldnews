"""
Tests for Event Cluster Engine

Tests multi-event conflict handling with focus on NFP scenarios.
"""

import pytest
from datetime import datetime, timedelta
from src.core.event_cluster_engine import (
    EventClusterEngine, EventCluster, ClusterEvent,
    ConflictLevel, ClusterDirection, analyze_event_cluster
)
from event_classifier import EventCategory


class TestEventGrouping:
    """Test event grouping into clusters."""
    
    def test_single_event_is_own_cluster(self):
        """A single event should form its own cluster."""
        engine = EventClusterEngine()
        events = [
            {"name": "CPI", "time": datetime(2024, 1, 1, 8, 30)}
        ]
        
        clusters = engine.group_events_into_clusters(events)
        
        assert len(clusters) == 1
        assert len(clusters[0]) == 1
        assert clusters[0][0]["name"] == "CPI"
    
    def test_events_within_60_seconds_grouped(self):
        """Events within 60 seconds should be grouped."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        events = [
            {"name": "NFP", "time": base_time},
            {"name": "Unemployment", "time": base_time + timedelta(seconds=30)},
            {"name": "Wages", "time": base_time + timedelta(seconds=45)},
        ]
        
        clusters = engine.group_events_into_clusters(events)
        
        assert len(clusters) == 1
        assert len(clusters[0]) == 3
    
    def test_events_beyond_60_seconds_separate(self):
        """Events beyond 60 seconds should be separate clusters."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        events = [
            {"name": "NFP", "time": base_time},
            {"name": "GDP", "time": base_time + timedelta(seconds=90)},
        ]
        
        clusters = engine.group_events_into_clusters(events)
        
        assert len(clusters) == 2
    
    def test_empty_events_returns_empty(self):
        """Empty event list should return empty clusters."""
        engine = EventClusterEngine()
        clusters = engine.group_events_into_clusters([])
        
        assert clusters == []


class TestNFPScenarios:
    """Test NFP mixed signal scenarios."""
    
    def test_nfp_aligned_bullish(self):
        """NFP where all signals point to gold bearish (USD bullish)."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            {
                "name": "Nonfarm Payrolls",
                "time": base_time,
                "actual": 250.0,  # Much better than expected
                "forecast": 180.0,
                "previous": 200.0,
            },
            {
                "name": "Unemployment Rate",
                "time": base_time,
                "actual": 3.5,  # Better than expected
                "forecast": 3.8,
                "previous": 3.7,
            },
            {
                "name": "Average Hourly Earnings",
                "time": base_time,
                "actual": 0.4,  # Higher wages (inflationary)
                "forecast": 0.3,
                "previous": 0.3,
            },
        ]
        
        cluster = engine.analyze_cluster(events)
        
        # All positive labor data = bearish for gold
        assert cluster.cluster_score > 0
        assert cluster.conflict_level in [ConflictLevel.ALIGNED, ConflictLevel.MOSTLY_ALIGNED]
        assert cluster.cluster_direction in [ClusterDirection.BEARISH, ClusterDirection.STRONGLY_BEARISH]
    
    def test_nfp_mixed_payroll_good_unemployment_bad(self):
        """NFP with conflicting signals: payrolls good but unemployment bad."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            {
                "name": "Nonfarm Payrolls",
                "time": base_time,
                "actual": 220.0,  # Good for USD (bearish gold)
                "forecast": 180.0,
                "previous": 200.0,
            },
            {
                "name": "Unemployment Rate",
                "time": base_time,
                "actual": 4.1,  # Bad for USD (bullish gold)
                "forecast": 3.8,
                "previous": 3.9,
            },
        ]
        
        cluster = engine.analyze_cluster(events)
        
        # Should detect mixed signals
        assert cluster.conflict_level == ConflictLevel.MIXED
        assert cluster.bullish_score > 0  # From unemployment
        assert cluster.bearish_score > 0  # From payrolls
        # NFP payrolls has higher weight, so bearish should dominate
        assert cluster.cluster_score > 0
    
    def test_nfp_mixed_payroll_bad_wages_high(self):
        """NFP with conflicting signals: payrolls bad but wages high."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            {
                "name": "Nonfarm Payrolls",
                "time": base_time,
                "actual": 120.0,  # Bad for USD (bullish gold)
                "forecast": 180.0,
                "previous": 200.0,
            },
            {
                "name": "Average Hourly Earnings",
                "time": base_time,
                "actual": 0.5,  # High wages (bearish gold - inflationary)
                "forecast": 0.3,
                "previous": 0.3,
            },
            {
                "name": "Unemployment Rate",
                "time": base_time,
                "actual": 3.7,  # Neutral/slightly good
                "forecast": 3.8,
                "previous": 3.8,
            },
        ]
        
        cluster = engine.analyze_cluster(events)
        
        # Should detect mixed signals
        assert cluster.conflict_level == ConflictLevel.MIXED
        # Payroll has higher weight but the conflict should be noted
        assert len(cluster.conflict_explanation) > 0
    
    def test_nfp_all_bad_bullish_gold(self):
        """NFP where all indicators are bad for USD = bullish for gold."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            {
                "name": "Nonfarm Payrolls",
                "time": base_time,
                "actual": 50.0,  # Much worse than expected
                "forecast": 180.0,
                "previous": 200.0,
            },
            {
                "name": "Unemployment Rate",
                "time": base_time,
                "actual": 4.5,  # Worse than expected
                "forecast": 3.8,
                "previous": 3.9,
            },
            {
                "name": "Average Hourly Earnings",
                "time": base_time,
                "actual": 0.1,  # Low wage growth
                "forecast": 0.3,
                "previous": 0.3,
            },
        ]
        
        cluster = engine.analyze_cluster(events)
        
        # All bad labor data = bullish for gold
        assert cluster.cluster_score < 0
        assert cluster.conflict_level in [ConflictLevel.ALIGNED, ConflictLevel.MOSTLY_ALIGNED]
        assert cluster.cluster_direction in [ClusterDirection.BULLISH, ClusterDirection.STRONGLY_BULLISH]
    
    def test_nfp_neutral_cancelling_signals(self):
        """NFP where signals roughly cancel out."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            {
                "name": "Nonfarm Payrolls",
                "time": base_time,
                "actual": 180.0,  # As expected
                "forecast": 180.0,
                "previous": 180.0,
            },
            {
                "name": "Unemployment Rate",
                "time": base_time,
                "actual": 3.8,  # As expected
                "forecast": 3.8,
                "previous": 3.8,
            },
        ]
        
        cluster = engine.analyze_cluster(events)
        
        # Neutral/aligned with no surprise
        assert abs(cluster.cluster_score) < 3
        assert cluster.conflict_level in [ConflictLevel.UNCLEAR, ConflictLevel.ALIGNED]
        assert cluster.final_alert_level in ["low", "none"]


class TestConflictDetection:
    """Test conflict level detection."""
    
    def test_aligned_all_bullish(self):
        """All events bullish = aligned."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            {"name": "CPI", "time": base_time, "actual": 3.5, "forecast": 3.2, "previous": 3.3},
            {"name": "Core CPI", "time": base_time, "actual": 3.6, "forecast": 3.3, "previous": 3.4},
        ]
        
        cluster = engine.analyze_cluster(events)
        
        assert cluster.conflict_level == ConflictLevel.ALIGNED
    
    def test_mixed_opposing_signals(self):
        """Opposing signals = mixed."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            {"name": "GDP", "time": base_time, "actual": 3.0, "forecast": 2.0, "previous": 2.5},
            {"name": "Retail Sales", "time": base_time, "actual": -1.0, "forecast": 0.5, "previous": 0.3},
        ]
        
        cluster = engine.analyze_cluster(events)
        
        assert cluster.conflict_level == ConflictLevel.MIXED


class TestCategoryWeights:
    """Test category weighting system."""
    
    def test_inflation_higher_weight_than_retail(self):
        """Inflation data should have higher weight than retail."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        # CPI (high weight) bullish, Retail (lower weight) bearish
        events = [
            {"name": "CPI y/y", "time": base_time, "actual": 3.8, "forecast": 3.2, "previous": 3.3},
            {"name": "Retail Sales", "time": base_time, "actual": 1.0, "forecast": 0.5, "previous": 0.3},
        ]
        
        cluster = engine.analyze_cluster(events)
        
        # CPI has higher weight, should dominate
        # CPI bullish (bearish for gold)
        assert cluster.cluster_score > 0
    
    def test_nfp_payrolls_highest_weight(self):
        """NFP payrolls should have higher weight than other labor indicators."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        # Payroll bullish (bearish gold), Unemployment bullish (bullish gold)
        # Payroll has higher weight
        events = [
            {
                "name": "Nonfarm Payrolls",
                "time": base_time,
                "actual": 250.0,  # Strong bullish USD (bearish gold)
                "forecast": 180.0,
            },
            {
                "name": "Unemployment Rate",
                "time": base_time,
                "actual": 4.2,  # Weak USD (bullish gold)
                "forecast": 3.8,
            },
        ]
        
        cluster = engine.analyze_cluster(events)
        
        # NFP payrolls (weight 1.6) > Unemployment (weight 1.3)
        # So bearish should win despite being mixed
        assert cluster.cluster_score > 0


class TestAlertLevels:
    """Test final alert level determination."""
    
    def test_aligned_high_score_immediate_alert(self):
        """Aligned high score should trigger immediate alert."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            {"name": "CPI", "time": base_time, "actual": 5.0, "forecast": 3.0},
            {"name": "Core CPI", "time": base_time, "actual": 4.8, "forecast": 3.2},
        ]
        
        cluster = engine.analyze_cluster(events)
        
        assert cluster.conflict_level == ConflictLevel.ALIGNED
        assert abs(cluster.cluster_score) >= 6
        assert cluster.final_alert_level == "immediate"
    
    def test_mixed_signal_reduces_alert(self):
        """Mixed signals should reduce alert level."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            {"name": "NFP", "time": base_time, "actual": 250, "forecast": 180},
            {"name": "Unemployment", "time": base_time, "actual": 4.5, "forecast": 3.8},
        ]
        
        cluster = engine.analyze_cluster(events)
        
        # Mixed signals should have lower alert
        assert cluster.conflict_level == ConflictLevel.MIXED
        assert cluster.final_alert_level in ["normal", "low"]
    
    def test_low_score_no_alert(self):
        """Low score should result in no alert."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            {"name": "Retail Sales", "time": base_time, "actual": 0.5, "forecast": 0.5},
        ]
        
        cluster = engine.analyze_cluster(events)
        
        assert abs(cluster.cluster_score) < 2
        assert cluster.final_alert_level == "none"


class TestThaiExplanations:
    """Test Thai language explanations."""
    
    def test_summary_contains_direction(self):
        """Thai summary should contain direction."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [{"name": "CPI", "time": base_time, "actual": 4.0, "forecast": 3.0}]
        cluster = engine.analyze_cluster(events)
        
        # Should contain Thai text
        assert len(cluster.summary_thai) > 0
        assert "ทอง" in cluster.summary_thai or "ไม่" in cluster.summary_thai
    
    def test_conflict_explanation_for_mixed(self):
        """Mixed signals should have conflict explanation."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            {"name": "NFP", "time": base_time, "actual": 250, "forecast": 180},
            {"name": "Unemployment", "time": base_time, "actual": 4.5, "forecast": 3.8},
        ]
        
        cluster = engine.analyze_cluster(events)
        
        assert cluster.conflict_level == ConflictLevel.MIXED
        assert "สัญญาณขัดแย้ง" in cluster.conflict_explanation or len(cluster.conflict_explanation) > 0


class TestConvenienceFunction:
    """Test convenience function."""
    
    def test_analyze_event_cluster_function(self):
        """Test the convenience function."""
        base_time = datetime(2024, 1, 1, 8, 30)
        events = [
            {"name": "CPI", "time": base_time, "actual": 4.0, "forecast": 3.0},
        ]
        
        cluster = analyze_event_cluster(events)
        
        assert isinstance(cluster, EventCluster)
        assert len(cluster.events) == 1
    
    def test_analyze_event_batch(self):
        """Test batch analysis of multiple clusters."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            # First cluster
            {"name": "CPI", "time": base_time, "actual": 4.0, "forecast": 3.0},
            {"name": "Core CPI", "time": base_time + timedelta(seconds=30), "actual": 3.8, "forecast": 3.2},
            # Second cluster (separate by time)
            {"name": "GDP", "time": base_time + timedelta(minutes=5), "actual": 2.0, "forecast": 2.5},
        ]
        
        clusters = engine.analyze_event_batch(events)
        
        assert len(clusters) == 2
        assert len(clusters[0].events) == 2  # CPI cluster
        assert len(clusters[1].events) == 1  # GDP cluster


class TestEdgeCases:
    """Test edge cases."""
    
    def test_empty_cluster_raises_error(self):
        """Empty cluster should raise error."""
        engine = EventClusterEngine()
        
        with pytest.raises(ValueError, match="empty cluster"):
            engine.analyze_cluster([])
    
    def test_single_event_cluster(self):
        """Single event should still work."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            {"name": "FOMC Statement", "time": base_time},
        ]
        
        cluster = engine.analyze_cluster(events)
        
        assert len(cluster.events) == 1
        assert cluster.conflict_level == ConflictLevel.ALIGNED  # Single event is aligned with itself
    
    def test_cluster_to_dict(self):
        """Test dictionary serialization."""
        engine = EventClusterEngine()
        base_time = datetime(2024, 1, 1, 8, 30)
        
        events = [
            {"name": "CPI", "time": base_time, "actual": 4.0, "forecast": 3.0},
        ]
        
        cluster = engine.analyze_cluster(events)
        data = cluster.to_dict()
        
        assert "cluster_id" in data
        assert "cluster_score" in data
        assert "events" in data
        assert len(data["events"]) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
