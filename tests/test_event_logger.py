"""Tests for the Event Logger."""

import json
import pytest
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src/core to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "core"))

from event_classifier import EventCategory, ImpactScore
from event_logger import EventLogger, LoggedEvent
from surprise_engine import EconomicDataPoint, SurpriseResult


class TestLoggedEvent:
    """Tests for LoggedEvent dataclass."""

    def test_basic_creation(self):
        """Test creating a LoggedEvent."""
        event = LoggedEvent(
            event_id="test-001",
            timestamp=datetime(2024, 1, 15, 8, 30),
            event_name="CPI Release",
            category="inflation",
            source="BLS",
            raw_text="CPI increased 3.2% year-over-year",
            actual_value=3.2,
            forecast_value=3.0,
            previous_value=3.1,
            unit="%",
            classification_category="inflation",
            base_impact_score=8,
            gold_correlation="negative",
            typical_volatility="high",
            key_drivers='["inflation expectations"]',
            surprise_score=5.0,
            deviation_pct=6.67,
            direction="above",
            significance="medium",
            gold_impact="bullish",
            market_consensus_available=True,
            consensus_aligned=True,
            divergence_score=0.1,
            trading_signal="long",
            gold_price_before=2050.0,
            gold_price_after=2065.0,
            price_change_pct=0.73,
            prediction_accuracy="correct",
            processed_at=datetime.utcnow(),
        )
        assert event.event_id == "test-001"
        assert event.event_name == "CPI Release"
        assert event.gold_impact == "bullish"


class TestEventLoggerInitialization:
    """Tests for EventLogger initialization."""

    def test_default_initialization(self, tmp_path):
        """Test logger initializes with default path."""
        db_path = tmp_path / "test.db"
        logger = EventLogger(db_path)
        assert logger.db_path == db_path
        assert db_path.parent.exists()

    def test_creates_parent_directory(self, tmp_path):
        """Test logger creates parent directories."""
        db_path = tmp_path / "subdir" / "nested" / "events.db"
        logger = EventLogger(db_path)
        assert db_path.parent.exists()

    def test_creates_table_on_init(self, tmp_path):
        """Test database table is created on initialization."""
        db_path = tmp_path / "test.db"
        logger = EventLogger(db_path)
        
        # Verify table exists
        with sqlite3.connect(db_path) as conn:
            result = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='events'"
            ).fetchone()
            assert result is not None


class TestLogEvent:
    """Tests for logging events."""

    @pytest.fixture
    def logger(self, tmp_path):
        """Create a test logger."""
        return EventLogger(tmp_path / "test.db")

    @pytest.fixture
    def sample_impact_score(self):
        """Create sample impact score."""
        return ImpactScore(
            category=EventCategory.INFLATION,
            base_impact_score=8,
            gold_correlation="negative",
            typical_volatility="high",
            key_drivers=["inflation expectations", "purchasing power"],
        )

    @pytest.fixture
    def sample_surprise_result(self):
        """Create sample surprise result."""
        return SurpriseResult(
            surprise_score=5.0,
            deviation_pct=6.67,
            direction="above",
            significance="medium",
            gold_impact="bullish",
        )

    @pytest.fixture
    def sample_data_point(self):
        """Create sample data point."""
        return EconomicDataPoint(
            name="CPI",
            actual=3.2,
            forecast=3.0,
            previous=3.1,
            unit="%",
        )

    def test_log_event(self, logger, sample_impact_score, sample_surprise_result, sample_data_point):
        """Test logging a complete event."""
        logged = logger.log_event(
            event_id="cpi-2024-01",
            timestamp=datetime(2024, 1, 15, 8, 30),
            event_name="CPI Release",
            category=EventCategory.INFLATION,
            source="BLS",
            raw_text="CPI data",
            impact_score=sample_impact_score,
            surprise_result=sample_surprise_result,
            data_point=sample_data_point,
            consensus_aligned=True,
            divergence_score=0.1,
            trading_signal="long",
        )
        
        assert logged.event_id == "cpi-2024-01"
        assert logged.event_name == "CPI Release"
        assert logged.category == "inflation"
        assert logged.gold_impact == "bullish"
        assert logged.market_consensus_available is True

    def test_log_event_without_consensus(self, logger, sample_impact_score, sample_surprise_result, sample_data_point):
        """Test logging an event without consensus data."""
        logged = logger.log_event(
            event_id="nfp-2024-01",
            timestamp=datetime(2024, 1, 5, 8, 30),
            event_name="NFP",
            category=EventCategory.LABOR,
            source="BLS",
            raw_text="Employment data",
            impact_score=sample_impact_score,
            surprise_result=sample_surprise_result,
            data_point=sample_data_point,
        )
        
        assert logged.market_consensus_available is False
        assert logged.consensus_aligned is None

    def test_retrieve_event(self, logger, sample_impact_score, sample_surprise_result, sample_data_point):
        """Test retrieving a logged event."""
        logger.log_event(
            event_id="test-retrieve",
            timestamp=datetime(2024, 1, 15),
            event_name="Test Event",
            category=EventCategory.INFLATION,
            source="Test",
            raw_text="Test data",
            impact_score=sample_impact_score,
            surprise_result=sample_surprise_result,
            data_point=sample_data_point,
        )
        
        retrieved = logger.get_event("test-retrieve")
        assert retrieved is not None
        assert retrieved.event_id == "test-retrieve"
        assert retrieved.event_name == "Test Event"

    def test_retrieve_nonexistent_event(self, logger):
        """Test retrieving an event that doesn't exist."""
        result = logger.get_event("nonexistent")
        assert result is None


class TestEventQueries:
    """Tests for querying events."""

    @pytest.fixture
    def logger_with_data(self, tmp_path):
        """Create logger with sample data."""
        logger = EventLogger(tmp_path / "test.db")
        
        impact = ImpactScore(
            category=EventCategory.INFLATION,
            base_impact_score=8,
            gold_correlation="negative",
            typical_volatility="high",
            key_drivers=["test"],
        )
        surprise = SurpriseResult(5.0, 6.0, "above", "high", "bullish")
        data = EconomicDataPoint("CPI", 3.0, 2.8, unit="%")
        
        # Add multiple events
        for i in range(5):
            logger.log_event(
                event_id=f"event-{i}",
                timestamp=datetime(2024, 1, 10 + i),
                event_name=f"Event {i}",
                category=EventCategory.INFLATION if i % 2 == 0 else EventCategory.LABOR,
                source="Test",
                raw_text="Test",
                impact_score=impact,
                surprise_result=surprise,
                data_point=data,
            )
        
        return logger

    def test_get_events_by_date_range(self, logger_with_data):
        """Test filtering events by date range."""
        events = logger_with_data.get_events(
            start_date=datetime(2024, 1, 11),
            end_date=datetime(2024, 1, 13),
        )
        assert len(events) == 3  # events on 11, 12, 13

    def test_get_events_by_category(self, logger_with_data):
        """Test filtering events by category."""
        events = logger_with_data.get_events(category="inflation")
        assert len(events) == 3  # events 0, 2, 4

    def test_get_events_by_gold_impact(self, logger_with_data):
        """Test filtering events by gold impact."""
        events = logger_with_data.get_events(gold_impact="bullish")
        assert len(events) == 5  # all are bullish

    def test_get_events_limit(self, logger_with_data):
        """Test limiting number of results."""
        events = logger_with_data.get_events(limit=3)
        assert len(events) == 3

    def test_get_events_ordering(self, logger_with_data):
        """Test that events are ordered by timestamp desc."""
        events = logger_with_data.get_events(limit=2)
        assert events[0].timestamp > events[1].timestamp


class TestUpdateOutcome:
    """Tests for updating event outcomes."""

    @pytest.fixture
    def logger_with_event(self, tmp_path):
        """Create logger with a single event."""
        logger = EventLogger(tmp_path / "test.db")
        
        impact = ImpactScore(
            category=EventCategory.INFLATION,
            base_impact_score=8,
            gold_correlation="negative",
            typical_volatility="high",
            key_drivers=["test"],
        )
        surprise = SurpriseResult(5.0, 6.0, "above", "high", "bullish")
        data = EconomicDataPoint("CPI", 3.0, 2.8, unit="%")
        
        logger.log_event(
            event_id="outcome-test",
            timestamp=datetime(2024, 1, 15),
            event_name="CPI",
            category=EventCategory.INFLATION,
            source="BLS",
            raw_text="CPI data",
            impact_score=impact,
            surprise_result=surprise,
            data_point=data,
        )
        
        return logger

    def test_update_gold_prices(self, logger_with_event):
        """Test updating gold price data."""
        logger_with_event.update_outcome(
            event_id="outcome-test",
            gold_price_before=2050.0,
            gold_price_after=2065.0,
            price_change_pct=0.73,
        )
        
        event = logger_with_event.get_event("outcome-test")
        assert event.gold_price_before == 2050.0
        assert event.gold_price_after == 2065.0
        assert event.price_change_pct == 0.73

    def test_update_prediction_accuracy(self, logger_with_event):
        """Test updating prediction accuracy."""
        logger_with_event.update_outcome(
            event_id="outcome-test",
            prediction_accuracy="correct",
        )
        
        event = logger_with_event.get_event("outcome-test")
        assert event.prediction_accuracy == "correct"

    def test_update_multiple_fields(self, logger_with_event):
        """Test updating multiple outcome fields."""
        logger_with_event.update_outcome(
            event_id="outcome-test",
            gold_price_before=2000.0,
            gold_price_after=2020.0,
            price_change_pct=1.0,
            prediction_accuracy="partial",
        )
        
        event = logger_with_event.get_event("outcome-test")
        assert event.gold_price_before == 2000.0
        assert event.price_change_pct == 1.0
        assert event.prediction_accuracy == "partial"


class TestStatistics:
    """Tests for statistics generation."""

    @pytest.fixture
    def logger_with_stats(self, tmp_path):
        """Create logger with diverse data."""
        logger = EventLogger(tmp_path / "test.db")
        
        categories = [EventCategory.INFLATION, EventCategory.LABOR, EventCategory.FED_POLICY]
        impacts = ["bullish", "bearish", "neutral"]
        sigs = ["high", "medium", "low"]
        
        for i in range(9):
            impact = ImpactScore(
                category=categories[i % 3],
                base_impact_score=i + 1,
                gold_correlation="negative",
                typical_volatility="high",
                key_drivers=["test"],
            )
            surprise = SurpriseResult(
                surprise_score=float(i),
                deviation_pct=float(i * 2),
                direction="above",
                significance=sigs[i % 3],
                gold_impact=impacts[i % 3],
            )
            data = EconomicDataPoint("Test", float(i), float(i), unit="%")
            
            logged = logger.log_event(
                event_id=f"stat-{i}",
                timestamp=datetime(2024, 1, i + 1),
                event_name=f"Event {i}",
                category=categories[i % 3],
                source="Test",
                raw_text="Test",
                impact_score=impact,
                surprise_result=surprise,
                data_point=data,
            )
            
            # Add outcome to some events
            if i % 2 == 0:
                logger.update_outcome(
                    event_id=f"stat-{i}",
                    prediction_accuracy="correct" if i % 4 == 0 else "incorrect",
                )
        
        return logger

    def test_total_events_stat(self, logger_with_stats):
        """Test total events statistic."""
        stats = logger_with_stats.get_statistics()
        assert stats["total_events"] == 9

    def test_category_breakdown(self, logger_with_stats):
        """Test category breakdown."""
        stats = logger_with_stats.get_statistics()
        assert "inflation" in stats["by_category"]
        assert "labor" in stats["by_category"]
        assert stats["by_category"]["inflation"] == 3

    def test_gold_impact_breakdown(self, logger_with_stats):
        """Test gold impact breakdown."""
        stats = logger_with_stats.get_statistics()
        assert "bullish" in stats["by_gold_impact"]
        assert "bearish" in stats["by_gold_impact"]
        assert stats["by_gold_impact"]["bullish"] == 3

    def test_prediction_accuracy_breakdown(self, logger_with_stats):
        """Test prediction accuracy breakdown."""
        stats = logger_with_stats.get_statistics()
        # 5 events have outcomes (even indices: 0, 2, 4, 6, 8)
        # 0, 4, 8 are "correct" (i % 4 == 0)
        # 2, 6 are "incorrect"
        assert stats["prediction_accuracy"].get("correct", 0) == 3
        assert stats["prediction_accuracy"].get("incorrect", 0) == 2


class TestExport:
    """Tests for data export."""

    def test_export_to_json(self, tmp_path):
        """Test exporting events to JSON."""
        logger = EventLogger(tmp_path / "test.db")
        
        impact = ImpactScore(
            category=EventCategory.INFLATION,
            base_impact_score=8,
            gold_correlation="negative",
            typical_volatility="high",
            key_drivers=["test"],
        )
        surprise = SurpriseResult(5.0, 6.0, "above", "high", "bullish")
        data = EconomicDataPoint("CPI", 3.0, 2.8, unit="%")
        
        logger.log_event(
            event_id="export-test",
            timestamp=datetime(2024, 1, 15),
            event_name="CPI",
            category=EventCategory.INFLATION,
            source="BLS",
            raw_text="CPI data",
            impact_score=impact,
            surprise_result=surprise,
            data_point=data,
        )
        
        export_path = tmp_path / "export.json"
        logger.export_to_json(export_path)
        
        assert export_path.exists()
        
        with open(export_path) as f:
            data = json.load(f)
        
        assert len(data) == 1
        assert data[0]["event_id"] == "export-test"
        assert "timestamp" in data[0]


class TestDeleteOldEvents:
    """Tests for deleting old events."""

    def test_delete_old_events(self, tmp_path):
        """Test deleting events older than specified days."""
        logger = EventLogger(tmp_path / "test.db")
        
        impact = ImpactScore(
            category=EventCategory.INFLATION,
            base_impact_score=8,
            gold_correlation="negative",
            typical_volatility="high",
            key_drivers=["test"],
        )
        surprise = SurpriseResult(5.0, 6.0, "above", "high", "bullish")
        data = EconomicDataPoint("CPI", 3.0, 2.8, unit="%")
        
        # Add old event
        logger.log_event(
            event_id="old-event",
            timestamp=datetime.utcnow() - timedelta(days=400),
            event_name="Old",
            category=EventCategory.INFLATION,
            source="Test",
            raw_text="Old data",
            impact_score=impact,
            surprise_result=surprise,
            data_point=data,
        )
        
        # Add recent event
        logger.log_event(
            event_id="recent-event",
            timestamp=datetime.utcnow(),
            event_name="Recent",
            category=EventCategory.INFLATION,
            source="Test",
            raw_text="Recent data",
            impact_score=impact,
            surprise_result=surprise,
            data_point=data,
        )
        
        # Delete events older than 365 days
        logger.delete_old_events(days=365)
        
        # Old event should be gone
        assert logger.get_event("old-event") is None
        # Recent event should still exist
        assert logger.get_event("recent-event") is not None
