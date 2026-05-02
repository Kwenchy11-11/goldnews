"""
Tests for Event Impact Engine configuration.

This module tests the configuration settings for the Event Impact Engine,
ensuring all required settings are present and have valid values.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


class TestImpactEngineConfig:
    """Test suite for Event Impact Engine configuration."""

    def test_impact_weights_sum_to_one(self):
        """Test that impact weights sum to approximately 1.0."""
        from config import (
            IMPACT_WEIGHT_SURPRISE,
            IMPACT_WEIGHT_BASE,
            IMPACT_WEIGHT_CONSENSUS
        )

        total = IMPACT_WEIGHT_SURPRISE + IMPACT_WEIGHT_BASE + IMPACT_WEIGHT_CONSENSUS
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    def test_impact_weights_are_positive(self):
        """Test that all impact weights are positive."""
        from config import (
            IMPACT_WEIGHT_SURPRISE,
            IMPACT_WEIGHT_BASE,
            IMPACT_WEIGHT_CONSENSUS
        )

        assert IMPACT_WEIGHT_SURPRISE >= 0
        assert IMPACT_WEIGHT_BASE >= 0
        assert IMPACT_WEIGHT_CONSENSUS >= 0

    def test_alert_thresholds_are_ordered(self):
        """Test that alert thresholds are in descending order."""
        from config import (
            ALERT_THRESHOLD_IMMEDIATE,
            ALERT_THRESHOLD_HIGH,
            ALERT_THRESHOLD_NORMAL
        )

        assert ALERT_THRESHOLD_IMMEDIATE > ALERT_THRESHOLD_HIGH
        assert ALERT_THRESHOLD_HIGH > ALERT_THRESHOLD_NORMAL
        assert ALERT_THRESHOLD_NORMAL > 0

    def test_event_log_db_path_is_set(self):
        """Test that event log database path is configured."""
        from config import EVENT_LOG_DB_PATH

        assert EVENT_LOG_DB_PATH is not None
        assert len(EVENT_LOG_DB_PATH) > 0
        assert '.db' in EVENT_LOG_DB_PATH or '/' in EVENT_LOG_DB_PATH

    def test_pre_event_alert_timing_is_positive(self):
        """Test that pre-event alert timing is positive."""
        from config import PRE_EVENT_ALERT_MINUTES

        assert PRE_EVENT_ALERT_MINUTES > 0
        assert PRE_EVENT_ALERT_MINUTES <= 60  # Should be within 1 hour

    def test_post_event_delay_is_reasonable(self):
        """Test that post-event delay is reasonable."""
        from config import POST_EVENT_DELAY_MINUTES

        assert POST_EVENT_DELAY_MINUTES >= 0
        assert POST_EVENT_DELAY_MINUTES <= 30  # Should be within 30 minutes

    def test_feature_flags_exist(self):
        """Test that all feature flags are defined."""
        from config import (
            ENABLE_IMPACT_ENGINE,
            ENABLE_PRE_EVENT_ALERTS,
            ENABLE_POST_EVENT_ALERTS,
            ENABLE_EVENT_LOGGING
        )

        # Should be boolean values
        assert isinstance(ENABLE_IMPACT_ENGINE, bool)
        assert isinstance(ENABLE_PRE_EVENT_ALERTS, bool)
        assert isinstance(ENABLE_POST_EVENT_ALERTS, bool)
        assert isinstance(ENABLE_EVENT_LOGGING, bool)

    def test_category_multipliers_are_positive(self):
        """Test that all category multipliers are positive."""
        from config import CATEGORY_IMPACT_MULTIPLIERS

        for category, multiplier in CATEGORY_IMPACT_MULTIPLIERS.items():
            assert multiplier > 0, f"Multiplier for {category} must be positive"
            assert multiplier <= 2.0, f"Multiplier for {category} seems too high"

    def test_category_multipliers_cover_all_categories(self):
        """Test that all event categories have multipliers."""
        from config import CATEGORY_IMPACT_MULTIPLIERS

        expected_categories = [
            'inflation', 'labor', 'fed_policy', 'growth',
            'yields', 'geopolitics', 'consumer', 'manufacturing', 'unknown'
        ]

        for category in expected_categories:
            assert category in CATEGORY_IMPACT_MULTIPLIERS, f"Missing multiplier for {category}"

    def test_gold_impact_thai_translations_exist(self):
        """Test that all gold impact levels have Thai translations."""
        from config import GOLD_IMPACT_THAI

        expected_impacts = [
            'strong-bullish', 'bullish', 'neutral',
            'bearish', 'strong-bearish'
        ]

        for impact in expected_impacts:
            assert impact in GOLD_IMPACT_THAI, f"Missing Thai translation for {impact}"
            assert len(GOLD_IMPACT_THAI[impact]) > 0

    def test_alert_priority_thai_translations_exist(self):
        """Test that all alert priorities have Thai translations."""
        from config import ALERT_PRIORITY_THAI

        expected_priorities = ['immediate', 'high', 'normal', 'low']

        for priority in expected_priorities:
            assert priority in ALERT_PRIORITY_THAI, f"Missing Thai translation for {priority}"
            assert len(ALERT_PRIORITY_THAI[priority]) > 0

    def test_category_thai_translations_exist(self):
        """Test that all categories have Thai translations."""
        from config import CATEGORY_THAI

        expected_categories = [
            'inflation', 'labor', 'fed_policy', 'growth',
            'yields', 'geopolitics', 'consumer', 'manufacturing', 'unknown'
        ]

        for category in expected_categories:
            assert category in CATEGORY_THAI, f"Missing Thai translation for {category}"
            assert len(CATEGORY_THAI[category]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])