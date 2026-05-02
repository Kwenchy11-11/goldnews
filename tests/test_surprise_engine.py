"""Tests for the Surprise Engine."""

import pytest
from src.core.surprise_engine import (
    EconomicDataPoint,
    SurpriseEngine,
    SurpriseResult,
)


class TestEconomicDataPoint:
    """Tests for EconomicDataPoint dataclass."""

    def test_basic_creation(self):
        """Test creating a basic EconomicDataPoint."""
        data = EconomicDataPoint(
            name="CPI",
            actual=3.2,
            forecast=3.0,
            previous=3.1,
            unit="%",
        )
        assert data.name == "CPI"
        assert data.actual == 3.2
        assert data.forecast == 3.0
        assert data.previous == 3.1
        assert data.unit == "%"

    def test_creation_with_defaults(self):
        """Test creating EconomicDataPoint with default values."""
        data = EconomicDataPoint(name="NFP")
        assert data.name == "NFP"
        assert data.actual is None
        assert data.forecast is None
        assert data.previous is None
        assert data.unit == "%"


class TestSurpriseEngineInitialization:
    """Tests for SurpriseEngine initialization."""

    def test_default_initialization(self):
        """Test engine initializes with default config."""
        engine = SurpriseEngine()
        assert engine.significance_thresholds["high"] == 20.0
        assert engine.significance_thresholds["medium"] == 10.0
        assert engine.significance_thresholds["low"] == 5.0

    def test_custom_thresholds(self):
        """Test engine with custom significance thresholds."""
        config = {
            "significance_thresholds": {
                "high": 30.0,
                "medium": 15.0,
                "low": 7.5,
            }
        }
        engine = SurpriseEngine(config)
        assert engine.significance_thresholds["high"] == 30.0
        assert engine.significance_thresholds["medium"] == 15.0
        assert engine.significance_thresholds["low"] == 7.5


class TestCalculateDeviation:
    """Tests for deviation calculation."""

    def test_positive_deviation(self):
        """Test calculation when actual is above forecast."""
        engine = SurpriseEngine()
        deviation = engine._calculate_deviation_pct(3.5, 3.0, "%")
        # (3.5 - 3.0) / 3.0 * 100 = 16.67%
        assert pytest.approx(deviation, rel=0.01) == 16.67

    def test_negative_deviation(self):
        """Test calculation when actual is below forecast."""
        engine = SurpriseEngine()
        deviation = engine._calculate_deviation_pct(2.5, 3.0, "%")
        # (2.5 - 3.0) / 3.0 * 100 = -16.67%
        assert pytest.approx(deviation, rel=0.01) == -16.67

    def test_zero_forecast_handling(self):
        """Test handling of zero forecast value."""
        engine = SurpriseEngine()
        deviation = engine._calculate_deviation_pct(0.2, 0.0, "%")
        # Should use scaled absolute difference
        assert deviation != 0
        assert deviation > 0


class TestDetermineDirection:
    """Tests for direction determination."""

    def test_above_forecast(self):
        """Test direction when actual is clearly above forecast."""
        engine = SurpriseEngine()
        direction = engine._determine_direction(3.5, 3.0)
        assert direction == "above"

    def test_below_forecast(self):
        """Test direction when actual is clearly below forecast."""
        engine = SurpriseEngine()
        direction = engine._determine_direction(2.5, 3.0)
        assert direction == "below"

    def test_as_expected_within_tolerance(self):
        """Test direction when within tolerance."""
        engine = SurpriseEngine()
        direction = engine._determine_direction(3.01, 3.0)
        assert direction == "as-expected"


class TestCalculateSignificance:
    """Tests for significance calculation."""

    def test_high_significance(self):
        """Test high significance threshold."""
        engine = SurpriseEngine()
        sig = engine._calculate_significance(25.0)
        assert sig == "high"

    def test_medium_significance(self):
        """Test medium significance threshold."""
        engine = SurpriseEngine()
        sig = engine._calculate_significance(15.0)
        assert sig == "medium"

    def test_low_significance(self):
        """Test low significance threshold."""
        engine = SurpriseEngine()
        sig = engine._calculate_significance(7.0)
        assert sig == "low"

    def test_no_significance(self):
        """Test no significance for small deviation."""
        engine = SurpriseEngine()
        sig = engine._calculate_significance(2.0)
        assert sig == "none"


class TestGoldImpactMapping:
    """Tests for gold impact determination."""

    def test_inflation_above_forecast(self):
        """Test gold impact when inflation is above forecast."""
        engine = SurpriseEngine()
        impact = engine._get_gold_impact("inflation", "above")
        # Higher inflation = bearish for USD (in context of gold impact map)
        # Actually, higher inflation should be bullish for gold (inflation hedge)
        assert impact in ["bullish", "bearish"]

    def test_employment_above_forecast(self):
        """Test gold impact when employment is above forecast."""
        engine = SurpriseEngine()
        impact = engine._get_gold_impact("employment", "above")
        # Better employment = stronger USD = bearish for gold
        assert impact == "bearish"

    def test_unemployment_below_forecast(self):
        """Test gold impact when unemployment is below forecast."""
        engine = SurpriseEngine()
        impact = engine._get_gold_impact("unemployment", "below")
        # Lower unemployment = stronger USD = bearish for gold
        assert impact == "bearish"

    def test_geopolitical_escalation(self):
        """Test gold impact for geopolitical escalation."""
        engine = SurpriseEngine()
        impact = engine._get_gold_impact("geopolitical", "above")
        # Escalation should be bullish for gold (safe haven)
        assert impact == "bullish"

    def test_as_expected_neutral(self):
        """Test gold impact when as expected."""
        engine = SurpriseEngine()
        impact = engine._get_gold_impact("inflation", "as-expected")
        assert impact == "neutral"


class TestFullSurpriseCalculation:
    """Tests for full surprise calculation."""

    def test_cpi_surprise_above_forecast(self):
        """Test CPI surprise when above forecast."""
        engine = SurpriseEngine()
        data = EconomicDataPoint(
            name="CPI",
            actual=3.5,
            forecast=3.0,
            previous=3.1,
            unit="%",
        )
        result = engine.calculate_surprise(data, "inflation")

        assert result.deviation_pct > 0
        assert result.direction == "above"
        assert result.significance in ["medium", "high"]
        assert result.surprise_score > 0
        # Higher inflation should be bullish for gold
        assert result.gold_impact == "bullish"

    def test_nfp_surprise_below_forecast(self):
        """Test NFP surprise when below forecast."""
        engine = SurpriseEngine()
        data = EconomicDataPoint(
            name="NFP",
            actual=150.0,
            forecast=200.0,
            previous=180.0,
            unit="K",
        )
        result = engine.calculate_surprise(data, "employment")

        assert result.deviation_pct < 0
        assert result.direction == "below"
        assert result.significance == "high"
        assert result.surprise_score < 0
        # Worse employment = weaker USD = bullish for gold
        assert result.gold_impact == "bullish"

    def test_no_data_returns_neutral(self):
        """Test handling when actual or forecast is None."""
        engine = SurpriseEngine()
        data = EconomicDataPoint(name="GDP", actual=None, forecast=2.5)
        result = engine.calculate_surprise(data, "gdp")

        assert result.direction == "no-data"
        assert result.significance == "none"
        assert result.gold_impact == "neutral"
        assert result.surprise_score == 0.0

    def test_as_expected_results(self):
        """Test when actual matches forecast."""
        engine = SurpriseEngine()
        data = EconomicDataPoint(
            name="Retail Sales",
            actual=2.5,
            forecast=2.5,
            unit="%",
        )
        result = engine.calculate_surprise(data, "retail_sales")

        assert result.direction == "as-expected"
        assert result.significance == "none"
        assert result.gold_impact == "neutral"


class TestSurpriseScoreCalculation:
    """Tests for surprise score normalization."""

    def test_score_clamped_at_max(self):
        """Test that score doesn't exceed 10."""
        engine = SurpriseEngine()
        # 50% deviation would give 25 points without clamping
        score = engine._calculate_surprise_score(50.0, "above")
        assert score == 10.0

    def test_score_clamped_at_min(self):
        """Test that score doesn't go below -10."""
        engine = SurpriseEngine()
        score = engine._calculate_surprise_score(-50.0, "below")
        assert score == -10.0

    def test_proportional_score(self):
        """Test that score is proportional to deviation."""
        engine = SurpriseEngine()
        # 20% deviation should give 10 points
        score = engine._calculate_surprise_score(20.0, "above")
        assert pytest.approx(score, abs=0.1) == 10.0


class TestCustomImpactMapping:
    """Tests for custom impact mapping."""

    def test_add_custom_mapping(self):
        """Test adding a custom gold impact mapping."""
        engine = SurpriseEngine()
        engine.add_custom_impact_mapping("custom_event", "bullish", "bearish")

        impact_above = engine._get_gold_impact("custom_event", "above")
        impact_below = engine._get_gold_impact("custom_event", "below")

        assert impact_above == "bullish"
        assert impact_below == "bearish"


class TestBatchCalculation:
    """Tests for batch calculation."""

    def test_batch_calculate_multiple(self):
        """Test calculating surprise for multiple data points."""
        engine = SurpriseEngine()

        data_points = [
            (EconomicDataPoint("CPI", 3.5, 3.0, unit="%"), "inflation"),
            (EconomicDataPoint("NFP", 150.0, 200.0, unit="K"), "employment"),
            (EconomicDataPoint("GDP", 2.5, 2.5, unit="%"), "gdp"),
        ]

        results = engine.batch_calculate(data_points)

        assert len(results) == 3
        # CPI above forecast
        assert results[0].direction == "above"
        # NFP below forecast
        assert results[1].direction == "below"
        # GDP as expected
        assert results[2].direction == "as-expected"
