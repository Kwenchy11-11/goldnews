"""Surprise Engine - Layer 2 of Event Impact Scoring Engine.

Calculates deviation between actual economic data and market forecasts
to determine "surprise magnitude" and its impact on gold prices.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class EconomicDataPoint:
    """Represents a single economic data point with actual, forecast, and previous values."""

    name: str
    actual: Optional[float] = None
    forecast: Optional[float] = None
    previous: Optional[float] = None
    unit: str = "%"
    release_time: Optional[datetime] = None


@dataclass
class SurpriseResult:
    """Result of surprise calculation for an economic data point."""

    surprise_score: float  # -10 to +10
    deviation_pct: float  # Percentage deviation from forecast
    direction: str  # "above", "below", "as-expected", "no-data"
    significance: str  # "high", "medium", "low", "none"
    gold_impact: str  # "bullish", "bearish", "neutral"


class SurpriseEngine:
    """Calculates surprise magnitude and gold impact for economic data releases."""

    # Default significance thresholds
    DEFAULT_SIGNIFICANCE_THRESHOLDS = {
        "high": 20.0,
        "medium": 10.0,
        "low": 5.0,
    }

    # Gold impact mapping: category -> (above_forecast_impact, below_forecast_impact)
    # For each category, what happens to gold when data is above vs below forecast
    GOLD_IMPACT_MAP: Dict[str, tuple] = {
        # Inflation data - higher inflation = bullish for gold (inflation hedge)
        "inflation": ("bullish", "bearish"),
        "cpi": ("bullish", "bearish"),
        "pce": ("bullish", "bearish"),
        "ppi": ("bullish", "bearish"),
        # Employment data - better jobs = stronger USD = bearish for gold
        "employment": ("bearish", "bullish"),
        "nfp": ("bearish", "bullish"),
        "unemployment": ("bullish", "bearish"),  # Lower unemployment = bearish gold
        "jobs": ("bearish", "bullish"),
        # Fed policy - hawkish = bearish for gold
        "fed": ("bearish", "bullish"),
        "rates": ("bearish", "bullish"),
        "fed_policy": ("bearish", "bullish"),
        # Safe haven - escalation = bullish for gold
        "geopolitical": ("bullish", "bearish"),
        "war": ("bullish", "bearish"),
        "conflict": ("bullish", "bearish"),
        # Economic growth - better growth = stronger USD = bearish gold
        "gdp": ("bearish", "bullish"),
        "growth": ("bearish", "bullish"),
        "retail_sales": ("bearish", "bullish"),
        # Dollar strength - stronger dollar = bearish for gold
        "dxy": ("bearish", "bullish"),
        "usd": ("bearish", "bullish"),
        # Safe haven during crisis
        "crisis": ("bullish", "bearish"),
        "recession": ("bullish", "bearish"),
        # Default for unknown categories
        "default": ("neutral", "neutral"),
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the SurpriseEngine with configuration.

        Args:
            config: Optional configuration dictionary with:
                - significance_thresholds: Dict with 'high', 'medium', 'low' thresholds
                - gold_impact_map: Custom gold impact mappings
        """
        self.config = config or {}
        self.significance_thresholds = self.config.get(
            "significance_thresholds", self.DEFAULT_SIGNIFICANCE_THRESHOLDS
        )
        self.gold_impact_map = self.config.get("gold_impact_map", self.GOLD_IMPACT_MAP)

    def calculate_surprise(
        self, data: EconomicDataPoint, category: str = "default"
    ) -> SurpriseResult:
        """Calculate surprise score and gold impact for an economic data point.

        Args:
            data: EconomicDataPoint with actual and forecast values
            category: Event category for gold impact determination

        Returns:
            SurpriseResult with surprise metrics and gold impact
        """
        # Check if we have necessary data
        if data.actual is None or data.forecast is None:
            return SurpriseResult(
                surprise_score=0.0,
                deviation_pct=0.0,
                direction="no-data",
                significance="none",
                gold_impact="neutral",
            )

        # Calculate deviation
        deviation_pct = self._calculate_deviation_pct(
            data.actual, data.forecast, data.unit
        )

        # Determine direction
        direction = self._determine_direction(data.actual, data.forecast)

        # Determine significance
        significance = self._calculate_significance(deviation_pct)

        # Calculate surprise score (-10 to +10)
        surprise_score = self._calculate_surprise_score(deviation_pct, direction)

        # Determine gold impact
        gold_impact = self._get_gold_impact(category, direction)

        return SurpriseResult(
            surprise_score=surprise_score,
            deviation_pct=deviation_pct,
            direction=direction,
            significance=significance,
            gold_impact=gold_impact,
        )

    def _calculate_deviation_pct(
        self, actual: float, forecast: float, unit: str
    ) -> float:
        """Calculate percentage deviation from forecast.

        Args:
            actual: Actual released value
            forecast: Market forecast/consensus
            unit: Unit of measurement (%, K, M, etc.)

        Returns:
            Percentage deviation (positive = above forecast, negative = below)
        """
        if forecast == 0:
            # Handle zero forecast - use absolute difference scaled
            diff = actual - forecast
            # Scale by typical magnitude for the unit type
            if unit == "%":
                return (diff / 0.1) * 100  # Assume 0.1% is significant
            else:
                return (diff / 1000) * 100  # Assume 1000 units is baseline

        return ((actual - forecast) / abs(forecast)) * 100

    def _determine_direction(self, actual: float, forecast: float) -> str:
        """Determine if actual was above, below, or as expected.

        Args:
            actual: Actual released value
            forecast: Market forecast/consensus

        Returns:
            Direction string: "above", "below", "as-expected"
        """
        # Define "as expected" tolerance (0.5% relative or absolute for small values)
        tolerance = max(abs(forecast) * 0.005, 0.001)

        diff = actual - forecast
        if abs(diff) <= tolerance:
            return "as-expected"
        elif diff > 0:
            return "above"
        else:
            return "below"

    def _calculate_significance(self, deviation_pct: float) -> str:
        """Determine significance level based on deviation magnitude.

        Args:
            deviation_pct: Percentage deviation from forecast

        Returns:
            Significance level: "high", "medium", "low", "none"
        """
        abs_deviation = abs(deviation_pct)

        if abs_deviation >= self.significance_thresholds["high"]:
            return "high"
        elif abs_deviation >= self.significance_thresholds["medium"]:
            return "medium"
        elif abs_deviation >= self.significance_thresholds["low"]:
            return "low"
        else:
            return "none"

    def _calculate_surprise_score(self, deviation_pct: float, direction: str) -> float:
        """Calculate normalized surprise score from -10 to +10.

        Args:
            deviation_pct: Percentage deviation from forecast
            direction: Direction string

        Returns:
            Surprise score from -10 (very bearish) to +10 (very bullish)
        """
        if direction == "as-expected" or direction == "no-data":
            return 0.0

        # Normalize score: 20% deviation = 10 points, 10% = 5 points, etc.
        score = (deviation_pct / 20.0) * 10.0

        # Clamp to -10 to +10 range
        return max(-10.0, min(10.0, score))

    def _get_gold_impact(self, category: str, direction: str) -> str:
        """Determine gold price impact based on category and data direction.

        Args:
            category: Event category (e.g., "inflation", "employment")
            direction: Data direction relative to forecast ("above", "below", "as-expected")

        Returns:
            Gold impact: "bullish", "bearish", or "neutral"
        """
        if direction == "as-expected" or direction == "no-data":
            return "neutral"

        # Normalize category to lowercase
        category_lower = category.lower()

        # Look up impact mapping
        impacts = self.gold_impact_map.get(category_lower, self.gold_impact_map["default"])

        # impacts[0] = impact when data is "better" for USD (above forecast for most indicators)
        # impacts[1] = impact when data is "worse" for USD (below forecast)
        if direction == "above":
            return impacts[0]
        else:  # direction == "below"
            return impacts[1]

    def add_custom_impact_mapping(self, category: str, above_impact: str, below_impact: str):
        """Add or update a custom gold impact mapping.

        Args:
            category: Category name
            above_impact: Impact when actual is above forecast ("bullish", "bearish", "neutral")
            below_impact: Impact when actual is below forecast ("bullish", "bearish", "neutral")
        """
        self.gold_impact_map[category.lower()] = (above_impact, below_impact)

    def batch_calculate(
        self, data_points: list[tuple[EconomicDataPoint, str]]
    ) -> list[SurpriseResult]:
        """Calculate surprise for multiple data points.

        Args:
            data_points: List of tuples (EconomicDataPoint, category)

        Returns:
            List of SurpriseResult objects
        """
        return [self.calculate_surprise(data, cat) for data, cat in data_points]
