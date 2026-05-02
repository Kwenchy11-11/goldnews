"""Consensus Layer - Layer 3 of Event Impact Scoring Engine.

Provides market-derived consensus data from prediction markets like Polymarket
to cross-reference with traditional economic forecasts and surprise calculations.

Note: This is currently a simplified implementation that can be extended
with actual Polymarket API integration in the future.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ConsensusSource(Enum):
    """Sources for market consensus data."""

    POLYMARKET = "polymarket"
    KALSHI = "kalshi"
    MANIFOLD = "manifold"
    INTERNAL = "internal"  # Fallback/source-derived
    MOCK = "mock"  # For testing


@dataclass
class MarketOutcome:
    """Represents a possible outcome in a prediction market."""

    name: str
    probability: float  # 0.0 to 1.0
    volume_usd: Optional[float] = None


@dataclass
class MarketConsensus:
    """Consensus data from prediction markets for an economic event."""

    event_name: str
    source: ConsensusSource
    market_url: Optional[str] = None
    outcomes: List[MarketOutcome] = None
    total_volume_usd: Optional[float] = None
    last_updated: Optional[datetime] = None
    confidence_score: float = 0.0  # 0.0 to 1.0 based on volume, liquidity

    def __post_init__(self):
        if self.outcomes is None:
            self.outcomes = []


@dataclass
class ConsensusComparison:
    """Result of comparing market consensus with traditional forecast."""

    event_name: str
    market_consensus: Optional[MarketConsensus]
    traditional_forecast: Optional[float]
    consensus_aligned: bool
    divergence_score: float  # 0.0 = perfect alignment, 1.0 = complete divergence
    interpretation: str
    trading_signal: str  # "strong-long", "long", "neutral", "short", "strong-short"


class ConsensusEngine:
    """Fetches and analyzes prediction market consensus data."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the ConsensusEngine.

        Args:
            config: Optional configuration with:
                - polymarket_api_key: API key for Polymarket
                - enable_mock_data: Use mock data when APIs unavailable
                - min_confidence_threshold: Minimum confidence for using consensus
        """
        self.config = config or {}
        self.api_key = self.config.get("polymarket_api_key")
        self.enable_mock = self.config.get("enable_mock_data", True)
        self.min_confidence = self.config.get("min_confidence_threshold", 0.5)
        self.cache: Dict[str, MarketConsensus] = {}

    async def fetch_market_consensus(
        self,
        event_name: str,
        category: str = "default",
        source: ConsensusSource = ConsensusSource.POLYMARKET,
    ) -> Optional[MarketConsensus]:
        """Fetch consensus data from prediction markets.

        Args:
            event_name: Name of the economic event
            category: Event category for context
            source: Which prediction market to query

        Returns:
            MarketConsensus object or None if unavailable
        """
        # Check cache first
        cache_key = f"{source.value}:{event_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Try to fetch from actual API if available
        if source == ConsensusSource.POLYMARKET and self.api_key:
            consensus = await self._fetch_polymarket(event_name, category)
        elif source == ConsensusSource.KALSHI:
            consensus = await self._fetch_kalshi(event_name, category)
        else:
            consensus = None

        # Fallback to mock data if enabled and no real data
        if consensus is None and self.enable_mock:
            consensus = self._generate_mock_consensus(event_name, category)

        # Cache result
        if consensus:
            self.cache[cache_key] = consensus

        return consensus

    async def _fetch_polymarket(
        self, event_name: str, category: str
    ) -> Optional[MarketConsensus]:
        """Fetch data from Polymarket API.

        TODO: Implement actual Polymarket API integration.
        For now, returns None to trigger mock data fallback.
        """
        # Placeholder for actual API integration
        # Would query Polymarket's Gamma API for event markets
        return None

    async def _fetch_kalshi(
        self, event_name: str, category: str
    ) -> Optional[MarketConsensus]:
        """Fetch data from Kalshi API.

        TODO: Implement actual Kalshi API integration.
        """
        return None

    def _generate_mock_consensus(
        self, event_name: str, category: str
    ) -> MarketConsensus:
        """Generate realistic mock consensus data for testing.

        Args:
            event_name: Name of the event
            category: Event category

        Returns:
            MarketConsensus with mock data
        """
        # Generate contextually appropriate outcomes based on event type
        outcomes = []

        if "cpi" in event_name.lower() or "inflation" in category.lower():
            outcomes = [
                MarketOutcome("Above 3.0%", 0.45, 150000.0),
                MarketOutcome("2.5% - 3.0%", 0.40, 120000.0),
                MarketOutcome("Below 2.5%", 0.15, 80000.0),
            ]
        elif "nfp" in event_name.lower() or "employment" in category.lower():
            outcomes = [
                MarketOutcome("Above 200K", 0.35, 200000.0),
                MarketOutcome("150K - 200K", 0.45, 180000.0),
                MarketOutcome("Below 150K", 0.20, 100000.0),
            ]
        elif "rates" in event_name.lower() or "fed" in category.lower():
            outcomes = [
                MarketOutcome("Rate Hike", 0.10, 500000.0),
                MarketOutcome("No Change", 0.75, 800000.0),
                MarketOutcome("Rate Cut", 0.15, 300000.0),
            ]
        else:
            outcomes = [
                MarketOutcome("Bullish", 0.40, 50000.0),
                MarketOutcome("Neutral", 0.35, 40000.0),
                MarketOutcome("Bearish", 0.25, 30000.0),
            ]

        total_volume = sum(o.volume_usd or 0 for o in outcomes)
        confidence = min(1.0, total_volume / 1000000)  # Scale volume to confidence

        return MarketConsensus(
            event_name=event_name,
            source=ConsensusSource.MOCK,
            market_url=None,
            outcomes=outcomes,
            total_volume_usd=total_volume,
            last_updated=datetime.utcnow(),
            confidence_score=confidence,
        )

    def compare_with_forecast(
        self,
        market_consensus: Optional[MarketConsensus],
        forecast_value: Optional[float],
        event_category: str = "default",
    ) -> ConsensusComparison:
        """Compare market consensus with traditional forecast.

        Args:
            market_consensus: Market-derived consensus
            forecast_value: Traditional economist forecast
            event_category: Category for context

        Returns:
            ConsensusComparison showing alignment or divergence
        """
        if market_consensus is None:
            return ConsensusComparison(
                event_name="unknown",
                market_consensus=None,
                traditional_forecast=forecast_value,
                consensus_aligned=False,
                divergence_score=0.0,
                interpretation="No market consensus data available",
                trading_signal="neutral",
            )

        # Calculate implied forecast from market probabilities
        market_implied = self._calculate_market_implied_forecast(
            market_consensus, event_category
        )

        # Determine alignment
        if market_implied is None or forecast_value is None:
            divergence = 0.5  # Unknown divergence
            aligned = False
        else:
            # Calculate percentage divergence
            if forecast_value != 0:
                pct_diff = abs(market_implied - forecast_value) / abs(forecast_value)
            else:
                pct_diff = abs(market_implied - forecast_value)
            
            divergence = min(1.0, pct_diff / 0.5)  # 50% diff = max divergence
            aligned = divergence < 0.2  # Within 10% is "aligned"

        # Generate interpretation
        interpretation = self._generate_interpretation(
            market_consensus, market_implied, forecast_value, aligned
        )

        # Generate trading signal
        signal = self._generate_trading_signal(
            market_consensus, divergence, market_consensus.confidence_score
        )

        return ConsensusComparison(
            event_name=market_consensus.event_name,
            market_consensus=market_consensus,
            traditional_forecast=forecast_value,
            consensus_aligned=aligned,
            divergence_score=divergence,
            interpretation=interpretation,
            trading_signal=signal,
        )

    def _calculate_market_implied_forecast(
        self, consensus: MarketConsensus, category: str
    ) -> Optional[float]:
        """Calculate numerical forecast implied by market probabilities.

        Args:
            consensus: Market consensus with outcomes
            category: Event category

        Returns:
            Implied numerical forecast or None
        """
        if not consensus.outcomes:
            return None

        # For binary/categorical outcomes, return probability of bullish outcome
        if len(consensus.outcomes) == 2:
            return consensus.outcomes[0].probability

        # For multi-outcome events, calculate weighted average
        # This is simplified - real implementation would need outcome values
        weighted_prob = 0.0
        total_weight = 0.0

        for i, outcome in enumerate(consensus.outcomes):
            # Assign ordinal values to outcomes
            value = i / (len(consensus.outcomes) - 1) if len(consensus.outcomes) > 1 else 0.5
            weighted_prob += value * outcome.probability
            total_weight += outcome.probability

        if total_weight > 0:
            return weighted_prob / total_weight
        return None

    def _generate_interpretation(
        self,
        consensus: MarketConsensus,
        market_implied: Optional[float],
        forecast: Optional[float],
        aligned: bool,
    ) -> str:
        """Generate human-readable interpretation of consensus comparison."""
        if market_implied is None:
            return f"Market shows mixed signals from {len(consensus.outcomes)} outcomes"

        if forecast is None:
            return f"Market implies value of {market_implied:.1%}"

        if aligned:
            return f"Market consensus ({market_implied:.1%}) aligns with forecast"
        else:
            return f"Market ({market_implied:.1%}) diverges from forecast - potential surprise opportunity"

    def _generate_trading_signal(
        self, consensus: MarketConsensus, divergence: float, confidence: float
    ) -> str:
        """Generate trading signal based on consensus analysis.

        Args:
            consensus: Market consensus
            divergence: Divergence score (0-1)
            confidence: Confidence score (0-1)

        Returns:
            Trading signal string
        """
        if confidence < self.min_confidence:
            return "neutral"

        # Check most probable outcome
        if not consensus.outcomes:
            return "neutral"

        top_outcome = max(consensus.outcomes, key=lambda o: o.probability)
        prob = top_outcome.probability

        # Signal strength based on probability and divergence
        if prob > 0.7 and divergence > 0.3:
            return "strong-long" if "bullish" in top_outcome.name.lower() else "strong-short"
        elif prob > 0.6:
            return "long" if "bullish" in top_outcome.name.lower() else "short"
        elif divergence > 0.4:
            return "long"  # Divergence = opportunity
        else:
            return "neutral"

    def get_consensus_summary(
        self, comparisons: List[ConsensusComparison]
    ) -> Dict[str, Any]:
        """Generate summary statistics for multiple consensus comparisons.

        Args:
            comparisons: List of consensus comparisons

        Returns:
            Summary dictionary with statistics
        """
        if not comparisons:
            return {
                "total_events": 0,
                "aligned_count": 0,
                "divergent_count": 0,
                "avg_divergence": 0.0,
                "signals": {},
            }

        aligned = sum(1 for c in comparisons if c.consensus_aligned)
        divergent = len(comparisons) - aligned
        avg_div = sum(c.divergence_score for c in comparisons) / len(comparisons)

        # Count signals
        signals = {}
        for c in comparisons:
            signals[c.trading_signal] = signals.get(c.trading_signal, 0) + 1

        return {
            "total_events": len(comparisons),
            "aligned_count": aligned,
            "divergent_count": divergent,
            "avg_divergence": avg_div,
            "signals": signals,
        }

    def clear_cache(self):
        """Clear the consensus cache."""
        self.cache.clear()
