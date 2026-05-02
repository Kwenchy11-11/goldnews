"""Tests for the Consensus Engine."""

import pytest
from datetime import datetime
from src.core.consensus_engine import (
    ConsensusEngine,
    ConsensusComparison,
    ConsensusSource,
    MarketConsensus,
    MarketOutcome,
)


class TestMarketOutcome:
    """Tests for MarketOutcome dataclass."""

    def test_basic_creation(self):
        """Test creating a MarketOutcome."""
        outcome = MarketOutcome(name="Above 3%", probability=0.6, volume_usd=100000.0)
        assert outcome.name == "Above 3%"
        assert outcome.probability == 0.6
        assert outcome.volume_usd == 100000.0

    def test_creation_without_volume(self):
        """Test creating MarketOutcome without volume."""
        outcome = MarketOutcome(name="Below 2%", probability=0.4)
        assert outcome.volume_usd is None


class TestMarketConsensus:
    """Tests for MarketConsensus dataclass."""

    def test_basic_creation(self):
        """Test creating MarketConsensus."""
        outcomes = [
            MarketOutcome("Above 3%", 0.6),
            MarketOutcome("Below 3%", 0.4),
        ]
        consensus = MarketConsensus(
            event_name="CPI Release",
            source=ConsensusSource.POLYMARKET,
            outcomes=outcomes,
            confidence_score=0.8,
        )
        assert consensus.event_name == "CPI Release"
        assert consensus.source == ConsensusSource.POLYMARKET
        assert len(consensus.outcomes) == 2
        assert consensus.confidence_score == 0.8

    def test_default_outcomes(self):
        """Test that outcomes defaults to empty list."""
        consensus = MarketConsensus(
            event_name="GDP Release",
            source=ConsensusSource.INTERNAL,
        )
        assert consensus.outcomes == []


class TestConsensusEngineInitialization:
    """Tests for ConsensusEngine initialization."""

    def test_default_initialization(self):
        """Test engine initializes with default config."""
        engine = ConsensusEngine()
        assert engine.api_key is None
        assert engine.enable_mock is True
        assert engine.min_confidence == 0.5
        assert engine.cache == {}

    def test_custom_config(self):
        """Test engine with custom configuration."""
        config = {
            "polymarket_api_key": "test_key",
            "enable_mock_data": False,
            "min_confidence_threshold": 0.7,
        }
        engine = ConsensusEngine(config)
        assert engine.api_key == "test_key"
        assert engine.enable_mock is False
        assert engine.min_confidence == 0.7


class TestMockConsensusGeneration:
    """Tests for mock consensus data generation."""

    @pytest.mark.asyncio
    async def test_cpi_mock_consensus(self):
        """Test mock generation for CPI event."""
        engine = ConsensusEngine()
        consensus = await engine.fetch_market_consensus("CPI Release", "inflation")

        assert consensus is not None
        assert consensus.source == ConsensusSource.MOCK
        assert len(consensus.outcomes) == 3
        assert consensus.total_volume_usd is not None
        assert consensus.confidence_score > 0

    @pytest.mark.asyncio
    async def test_nfp_mock_consensus(self):
        """Test mock generation for NFP event."""
        engine = ConsensusEngine()
        consensus = await engine.fetch_market_consensus("NFP Release", "employment")

        assert consensus is not None
        assert consensus.event_name == "NFP Release"
        assert len(consensus.outcomes) == 3
        # Check for employment-specific outcomes
        outcome_names = [o.name for o in consensus.outcomes]
        assert any("K" in name for name in outcome_names)

    @pytest.mark.asyncio
    async def test_fed_rates_mock_consensus(self):
        """Test mock generation for Fed rates event."""
        engine = ConsensusEngine()
        consensus = await engine.fetch_market_consensus("Fed Decision", "fed")

        assert consensus is not None
        outcome_names = [o.name.lower() for o in consensus.outcomes]
        assert any("hike" in name or "cut" in name for name in outcome_names)

    @pytest.mark.asyncio
    async def test_generic_mock_consensus(self):
        """Test mock generation for unknown event type."""
        engine = ConsensusEngine()
        consensus = await engine.fetch_market_consensus("Random Event", "unknown")

        assert consensus is not None
        outcome_names = [o.name.lower() for o in consensus.outcomes]
        assert "bullish" in outcome_names or "bearish" in outcome_names

    @pytest.mark.asyncio
    async def test_caching(self):
        """Test that consensus data is cached."""
        engine = ConsensusEngine()
        
        # First fetch
        consensus1 = await engine.fetch_market_consensus("CPI Release", "inflation")
        # Second fetch should come from cache
        consensus2 = await engine.fetch_market_consensus("CPI Release", "inflation")
        
        assert consensus1 is consensus2  # Same object from cache
        assert len(engine.cache) == 1

    def test_clear_cache(self):
        """Test clearing the cache."""
        engine = ConsensusEngine()
        # Manually add to cache
        engine.cache["test"] = MarketConsensus("test", ConsensusSource.MOCK)
        
        engine.clear_cache()
        assert len(engine.cache) == 0


class TestConsensusComparison:
    """Tests for consensus comparison functionality."""

    def test_comparison_no_consensus(self):
        """Test comparison when no market consensus available."""
        engine = ConsensusEngine()
        comparison = engine.compare_with_forecast(None, 3.0)

        assert comparison.market_consensus is None
        assert comparison.traditional_forecast == 3.0
        assert comparison.consensus_aligned is False
        assert comparison.trading_signal == "neutral"

    def test_comparison_aligned(self):
        """Test comparison when consensus aligns with forecast."""
        engine = ConsensusEngine()
        consensus = MarketConsensus(
            event_name="Test",
            source=ConsensusSource.MOCK,
            outcomes=[
                MarketOutcome("Above 3%", 0.6, 100000.0),
                MarketOutcome("Below 3%", 0.4, 80000.0),
            ],
            confidence_score=0.8,
        )
        
        comparison = engine.compare_with_forecast(consensus, 0.6)
        
        assert comparison.consensus_aligned is True
        assert comparison.divergence_score < 0.2

    def test_comparison_divergent(self):
        """Test comparison when consensus diverges from forecast."""
        engine = ConsensusEngine()
        consensus = MarketConsensus(
            event_name="Test",
            source=ConsensusSource.MOCK,
            outcomes=[
                MarketOutcome("Above 3%", 0.8, 500000.0),
                MarketOutcome("Below 3%", 0.2, 100000.0),
            ],
            confidence_score=0.9,
        )
        
        # Forecast predicts low probability, market predicts high
        comparison = engine.compare_with_forecast(consensus, 0.2)
        
        assert comparison.consensus_aligned is False
        assert comparison.divergence_score > 0.2

    def test_comparison_no_forecast(self):
        """Test comparison when no traditional forecast available."""
        engine = ConsensusEngine()
        consensus = MarketConsensus(
            event_name="Test",
            source=ConsensusSource.MOCK,
            outcomes=[MarketOutcome("Bullish", 0.7)],
            confidence_score=0.6,
        )
        
        comparison = engine.compare_with_forecast(consensus, None)
        
        assert comparison.traditional_forecast is None
        assert comparison.consensus_aligned is False


class TestTradingSignals:
    """Tests for trading signal generation."""

    def test_strong_long_signal(self):
        """Test strong long signal generation."""
        engine = ConsensusEngine()
        consensus = MarketConsensus(
            event_name="Test",
            source=ConsensusSource.MOCK,
            outcomes=[
                MarketOutcome("Bullish", 0.75, 500000.0),
                MarketOutcome("Bearish", 0.25, 100000.0),
            ],
            confidence_score=0.8,
        )
        
        comparison = engine.compare_with_forecast(consensus, 0.3)
        
        assert comparison.trading_signal == "strong-long"

    def test_strong_short_signal(self):
        """Test strong short signal generation."""
        engine = ConsensusEngine()
        consensus = MarketConsensus(
            event_name="Test",
            source=ConsensusSource.MOCK,
            outcomes=[
                MarketOutcome("Bearish", 0.75, 500000.0),
                MarketOutcome("Bullish", 0.25, 100000.0),
            ],
            confidence_score=0.8,
        )
        
        # Low forecast (0.1) vs high bearish probability (0.75) = high divergence
        comparison = engine.compare_with_forecast(consensus, 0.1)
        
        assert comparison.trading_signal == "strong-short"

    def test_neutral_low_confidence(self):
        """Test neutral signal when confidence is low."""
        engine = ConsensusEngine(config={"min_confidence_threshold": 0.9})
        consensus = MarketConsensus(
            event_name="Test",
            source=ConsensusSource.MOCK,
            outcomes=[MarketOutcome("Bullish", 0.8)],
            confidence_score=0.3,  # Below threshold
        )
        
        comparison = engine.compare_with_forecast(consensus, 0.5)
        
        assert comparison.trading_signal == "neutral"


class TestConsensusSummary:
    """Tests for consensus summary generation."""

    def test_empty_summary(self):
        """Test summary with no comparisons."""
        engine = ConsensusEngine()
        summary = engine.get_consensus_summary([])

        assert summary["total_events"] == 0
        assert summary["aligned_count"] == 0
        assert summary["avg_divergence"] == 0.0

    def test_summary_statistics(self):
        """Test summary with multiple comparisons."""
        engine = ConsensusEngine()
        comparisons = [
            ConsensusComparison(
                event_name="Event1",
                market_consensus=None,
                traditional_forecast=3.0,
                consensus_aligned=True,
                divergence_score=0.1,
                interpretation="Aligned",
                trading_signal="neutral",
            ),
            ConsensusComparison(
                event_name="Event2",
                market_consensus=None,
                traditional_forecast=2.5,
                consensus_aligned=False,
                divergence_score=0.4,
                interpretation="Divergent",
                trading_signal="long",
            ),
            ConsensusComparison(
                event_name="Event3",
                market_consensus=None,
                traditional_forecast=4.0,
                consensus_aligned=True,
                divergence_score=0.05,
                interpretation="Aligned",
                trading_signal="neutral",
            ),
        ]

        summary = engine.get_consensus_summary(comparisons)

        assert summary["total_events"] == 3
        assert summary["aligned_count"] == 2
        assert summary["divergent_count"] == 1
        assert summary["avg_divergence"] == pytest.approx(0.183, abs=0.01)
        assert summary["signals"]["neutral"] == 2
        assert summary["signals"]["long"] == 1


class TestMarketImpliedForecast:
    """Tests for market-implied forecast calculation."""

    def test_binary_outcome_implied(self):
        """Test implied forecast with binary outcomes."""
        engine = ConsensusEngine()
        consensus = MarketConsensus(
            event_name="Test",
            source=ConsensusSource.MOCK,
            outcomes=[
                MarketOutcome("Yes", 0.7),
                MarketOutcome("No", 0.3),
            ],
        )

        implied = engine._calculate_market_implied_forecast(consensus, "default")
        
        # Binary: returns probability of first outcome
        assert implied == 0.7

    def test_multi_outcome_weighted(self):
        """Test weighted implied forecast with multiple outcomes."""
        engine = ConsensusEngine()
        consensus = MarketConsensus(
            event_name="Test",
            source=ConsensusSource.MOCK,
            outcomes=[
                MarketOutcome("Low", 0.2),
                MarketOutcome("Medium", 0.5),
                MarketOutcome("High", 0.3),
            ],
        )

        implied = engine._calculate_market_implied_forecast(consensus, "default")
        
        # Weighted average: (0*0.2 + 0.5*0.5 + 1*0.3) / 1.0 = 0.55
        assert implied == pytest.approx(0.55, abs=0.01)

    def test_no_outcomes_returns_none(self):
        """Test that empty outcomes returns None."""
        engine = ConsensusEngine()
        consensus = MarketConsensus(
            event_name="Test",
            source=ConsensusSource.MOCK,
            outcomes=[],
        )

        implied = engine._calculate_market_implied_forecast(consensus, "default")
        
        assert implied is None
