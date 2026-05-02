"""
Tests for Backtest Engine
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pytest

# Import the modules we're testing
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.backtest_engine import (
    PredictionDirection,
    OutcomeResult,
    BacktestTrade,
    BacktestResult,
    BacktestEngine
)
from core.historical_event_loader import HistoricalEvent, EventImpact


class TestPredictionDirection:
    """Test PredictionDirection enum"""
    
    def test_enum_values(self):
        """Test enum values"""
        assert PredictionDirection.BULLISH.value == "bullish"
        assert PredictionDirection.BEARISH.value == "bearish"
        assert PredictionDirection.NEUTRAL.value == "neutral"


class TestOutcomeResult:
    """Test OutcomeResult enum"""
    
    def test_enum_values(self):
        """Test enum values"""
        assert OutcomeResult.CORRECT.value == "correct"
        assert OutcomeResult.INCORRECT.value == "incorrect"
        assert OutcomeResult.NO_SIGNAL.value == "no_signal"
        assert OutcomeResult.NO_DATA.value == "no_data"


class TestBacktestTrade:
    """Test BacktestTrade dataclass"""
    
    def test_bullish_trade(self):
        """Test bullish trade P&L"""
        trade = BacktestTrade(
            entry_price=2000.0,
            exit_price=2010.0,
            direction=PredictionDirection.BULLISH,
            position_size=1.0
        )
        
        assert trade.pnl == 10.0
        assert trade.pnl_pct == 0.5
    
    def test_bearish_trade(self):
        """Test bearish trade P&L"""
        trade = BacktestTrade(
            entry_price=2000.0,
            exit_price=1990.0,
            direction=PredictionDirection.BEARISH,
            position_size=1.0
        )
        
        assert trade.pnl == 10.0  # Profit when price drops
        assert trade.pnl_pct == 0.5
    
    def test_losing_bullish_trade(self):
        """Test losing bullish trade"""
        trade = BacktestTrade(
            entry_price=2000.0,
            exit_price=1990.0,
            direction=PredictionDirection.BULLISH,
            position_size=1.0
        )
        
        assert trade.pnl == -10.0
        assert trade.pnl_pct == -0.5
    
    def test_neutral_trade(self):
        """Test neutral trade has no P&L"""
        trade = BacktestTrade(
            entry_price=2000.0,
            exit_price=2010.0,
            direction=PredictionDirection.NEUTRAL,
            position_size=1.0
        )
        
        assert trade.pnl == 0.0
        assert trade.pnl_pct == 0.0
    
    def test_pnl_with_position_size(self):
        """Test P&L with different position size"""
        trade = BacktestTrade(
            entry_price=2000.0,
            exit_price=2010.0,
            direction=PredictionDirection.BULLISH,
            position_size=10.0  # 10 oz
        )
        
        assert trade.pnl == 100.0  # 10 * $10


class TestBacktestResult:
    """Test BacktestResult dataclass"""
    
    def test_creation(self):
        """Test creating a BacktestResult"""
        result = BacktestResult(
            event_id="evt_001",
            event_title="CPI y/y",
            event_date=datetime(2024, 1, 15, 8, 30),
            event_category="USD",
            impact_score=5.5,
            predicted_direction=PredictionDirection.BULLISH,
            confidence=0.85,
            price_before=2000.0,
            price_after_15m=2010.0
        )
        
        assert result.event_id == "evt_001"
        assert result.impact_score == 5.5
        assert result.predicted_direction == PredictionDirection.BULLISH
    
    def test_to_dict(self):
        """Test conversion to dict"""
        result = BacktestResult(
            event_id="evt_001",
            event_title="CPI",
            event_date=datetime(2024, 1, 15, 8, 30),
            event_category="USD",
            impact_score=5.5,
            predicted_direction=PredictionDirection.BULLISH,
            confidence=0.85
        )
        
        data = result.to_dict()
        
        assert data['event_id'] == "evt_001"
        assert data['predicted_direction'] == "bullish"
        assert data['impact_score'] == 5.5
    
    def test_from_dict(self):
        """Test creation from dict"""
        data = {
            'event_id': 'evt_001',
            'event_title': 'CPI',
            'event_date': '2024-01-15T08:30:00',
            'event_category': 'USD',
            'impact_score': 5.5,
            'predicted_direction': 'bullish',
            'confidence': 0.85,
            'outcome_5m': 'correct',
            'outcome_15m': 'incorrect',
            'outcome_30m': 'no_data',
            'outcome_60m': 'no_signal'
        }
        
        result = BacktestResult.from_dict(data)
        
        assert result.event_id == "evt_001"
        assert result.predicted_direction == PredictionDirection.BULLISH
        assert result.outcome_5m == OutcomeResult.CORRECT
        assert result.outcome_15m == OutcomeResult.INCORRECT
    
    def test_get_pnl(self):
        """Test getting P&L for timeframe"""
        trade = BacktestTrade(
            entry_price=2000.0,
            exit_price=2010.0,
            direction=PredictionDirection.BULLISH
        )
        
        result = BacktestResult(
            event_id="evt_001",
            event_title="CPI",
            event_date=datetime.now(),
            event_category="USD",
            impact_score=5.0,
            predicted_direction=PredictionDirection.BULLISH,
            confidence=0.8,
            trade_15m=trade
        )
        
        assert result.get_pnl('15m') == 10.0
        assert result.get_pnl('30m') is None
    
    def test_was_correct(self):
        """Test was_correct method"""
        result = BacktestResult(
            event_id="evt_001",
            event_title="CPI",
            event_date=datetime.now(),
            event_category="USD",
            impact_score=5.0,
            predicted_direction=PredictionDirection.BULLISH,
            confidence=0.8,
            outcome_15m=OutcomeResult.CORRECT,
            outcome_30m=OutcomeResult.INCORRECT,
            outcome_60m=OutcomeResult.NO_DATA
        )
        
        assert result.was_correct('15m') is True
        assert result.was_correct('30m') is False
        assert result.was_correct('60m') is None


class TestBacktestEngine:
    """Test BacktestEngine"""
    
    def test_initialization(self):
        """Test engine initialization"""
        engine = BacktestEngine()
        
        assert engine.impact_engine is not None
        assert engine.price_fetcher is not None
        assert engine.results == []
    
    def test_parse_numeric_value_plain(self):
        """Test parsing plain number"""
        engine = BacktestEngine()
        
        assert engine._parse_numeric_value("3.1") == 3.1
        assert engine._parse_numeric_value("200") == 200.0
    
    def test_parse_numeric_value_with_percent(self):
        """Test parsing percentage"""
        engine = BacktestEngine()
        
        assert engine._parse_numeric_value("3.1%") == 3.1
        assert engine._parse_numeric_value("0.2%") == 0.2
    
    def test_parse_numeric_value_with_k(self):
        """Test parsing thousands"""
        engine = BacktestEngine()
        
        assert engine._parse_numeric_value("185K") == 185000
        assert engine._parse_numeric_value("1.5K") == 1500
    
    def test_parse_numeric_value_with_comma(self):
        """Test parsing with comma separator"""
        engine = BacktestEngine()
        
        assert engine._parse_numeric_value("1,234") == 1234
        assert engine._parse_numeric_value("185,000") == 185000
    
    def test_parse_numeric_value_empty(self):
        """Test parsing empty value"""
        engine = BacktestEngine()
        
        assert engine._parse_numeric_value("") is None
        assert engine._parse_numeric_value(None) is None
    
    def test_score_to_direction_bullish(self):
        """Test score to bullish direction"""
        engine = BacktestEngine()
        
        assert engine._score_to_direction(5.0) == PredictionDirection.BULLISH
        assert engine._score_to_direction(3.0) == PredictionDirection.BULLISH
    
    def test_score_to_direction_bearish(self):
        """Test score to bearish direction"""
        engine = BacktestEngine()
        
        assert engine._score_to_direction(-5.0) == PredictionDirection.BEARISH
        assert engine._score_to_direction(-3.0) == PredictionDirection.BEARISH
    
    def test_score_to_direction_neutral(self):
        """Test score to neutral direction"""
        engine = BacktestEngine()
        
        assert engine._score_to_direction(0) == PredictionDirection.NEUTRAL
        assert engine._score_to_direction(2.0) == PredictionDirection.NEUTRAL
        assert engine._score_to_direction(-2.0) == PredictionDirection.NEUTRAL
    
    def test_price_change_to_direction_bullish(self):
        """Test price change to bullish"""
        engine = BacktestEngine()
        
        assert engine._price_change_to_direction(5.0) == PredictionDirection.BULLISH
        assert engine._price_change_to_direction(10.0) == PredictionDirection.BULLISH
    
    def test_price_change_to_direction_bearish(self):
        """Test price change to bearish"""
        engine = BacktestEngine()
        
        assert engine._price_change_to_direction(-5.0) == PredictionDirection.BEARISH
        assert engine._price_change_to_direction(-10.0) == PredictionDirection.BEARISH
    
    def test_price_change_to_direction_neutral(self):
        """Test price change to neutral"""
        engine = BacktestEngine()
        
        assert engine._price_change_to_direction(0.5) == PredictionDirection.NEUTRAL
        assert engine._price_change_to_direction(-0.5) == PredictionDirection.NEUTRAL
    
    def test_determine_outcome_correct(self):
        """Test correct outcome"""
        engine = BacktestEngine()
        
        outcome = engine._determine_outcome(
            PredictionDirection.BULLISH,
            PredictionDirection.BULLISH
        )
        
        assert outcome == OutcomeResult.CORRECT
    
    def test_determine_outcome_incorrect(self):
        """Test incorrect outcome"""
        engine = BacktestEngine()
        
        outcome = engine._determine_outcome(
            PredictionDirection.BULLISH,
            PredictionDirection.BEARISH
        )
        
        assert outcome == OutcomeResult.INCORRECT
    
    def test_determine_outcome_no_signal(self):
        """Test no signal outcome"""
        engine = BacktestEngine()
        
        outcome = engine._determine_outcome(
            PredictionDirection.NEUTRAL,
            PredictionDirection.BULLISH
        )
        
        assert outcome == OutcomeResult.NO_SIGNAL
    
    @patch.object(BacktestEngine, '_analyze_event_impact')
    @patch.object(BacktestEngine, '_get_price_before_event')
    def test_backtest_single_event_success(self, mock_get_price, mock_analyze):
        """Test successful single event backtest"""
        # Setup mocks
        mock_impact_result = Mock()
        mock_impact_result.composite_score = 5.0
        mock_impact_result.confidence_score = 0.85
        mock_impact_result.surprise_result = None
        mock_analyze.return_value = mock_impact_result
        
        mock_get_price.return_value = 2000.0
        
        # Mock price fetcher for after-event prices
        engine = BacktestEngine()
        engine.price_fetcher.get_price_at = Mock(return_value=2010.0)
        
        event = HistoricalEvent(
            title="CPI y/y",
            country="USD",
            date=datetime(2024, 1, 15, 8, 30),
            impact=EventImpact.HIGH,
            forecast="3.0%",
            actual="3.1%",
            event_id="test_001"
        )
        
        result = engine._backtest_single_event(event, 15, [15])
        
        assert result is not None
        assert result.event_id == "test_001"
        assert result.impact_score == 5.0
        assert result.predicted_direction == PredictionDirection.BULLISH
        assert result.price_before == 2000.0
        assert result.price_after_15m == 2010.0
        assert result.outcome_15m == OutcomeResult.CORRECT
    
    @patch.object(BacktestEngine, '_analyze_event_impact')
    def test_backtest_single_event_no_impact(self, mock_analyze):
        """Test backtest when impact analysis fails"""
        mock_analyze.return_value = None
        
        engine = BacktestEngine()
        
        event = HistoricalEvent(
            title="CPI",
            country="USD",
            date=datetime.now(),
            impact=EventImpact.HIGH,
            actual="3.1%"
        )
        
        result = engine._backtest_single_event(event, 15, [15])
        
        assert result is None
    
    @patch.object(BacktestEngine, '_analyze_event_impact')
    @patch.object(BacktestEngine, '_get_price_before_event')
    def test_backtest_single_event_no_price(self, mock_get_price, mock_analyze):
        """Test backtest when can't fetch price"""
        mock_impact_result = Mock()
        mock_impact_result.composite_score = 5.0
        mock_impact_result.confidence_score = 0.85
        mock_impact_result.surprise_result = None
        mock_analyze.return_value = mock_impact_result
        
        mock_get_price.return_value = None  # No price data
        
        engine = BacktestEngine()
        
        event = HistoricalEvent(
            title="CPI",
            country="USD",
            date=datetime.now(),
            impact=EventImpact.HIGH,
            actual="3.1%"
        )
        
        result = engine._backtest_single_event(event, 15, [15])
        
        assert result is None
    
    def test_get_statistics_empty(self):
        """Test statistics with no results"""
        engine = BacktestEngine()
        engine.results = []
        
        stats = engine.get_statistics('15m')
        
        assert stats == {}
    
    def test_get_statistics_basic(self):
        """Test basic statistics calculation"""
        engine = BacktestEngine()
        
        # Create test results
        engine.results = [
            BacktestResult(
                event_id="1",
                event_title="CPI",
                event_date=datetime.now(),
                event_category="USD",
                impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH,
                confidence=0.8,
                outcome_15m=OutcomeResult.CORRECT,
                trade_15m=BacktestTrade(2000, 2010, PredictionDirection.BULLISH)
            ),
            BacktestResult(
                event_id="2",
                event_title="NFP",
                event_date=datetime.now(),
                event_category="USD",
                impact_score=-5.0,
                predicted_direction=PredictionDirection.BEARISH,
                confidence=0.8,
                outcome_15m=OutcomeResult.CORRECT,
                trade_15m=BacktestTrade(2000, 1990, PredictionDirection.BEARISH)
            ),
            BacktestResult(
                event_id="3",
                event_title="GDP",
                event_date=datetime.now(),
                event_category="USD",
                impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH,
                confidence=0.8,
                outcome_15m=OutcomeResult.INCORRECT,
                trade_15m=BacktestTrade(2000, 1990, PredictionDirection.BULLISH)
            )
        ]
        
        stats = engine.get_statistics('15m')
        
        assert stats['total_events'] == 3
        assert stats['accuracy'] == 66.67  # 2 out of 3 correct
        assert stats['total_pnl'] == 10.0  # +10 +10 -10
        assert stats['avg_pnl'] == 3.33
    
    def test_export_import_results(self):
        """Test exporting and importing results"""
        engine = BacktestEngine()
        
        engine.results = [
            BacktestResult(
                event_id="1",
                event_title="CPI",
                event_date=datetime(2024, 1, 15, 8, 30),
                event_category="USD",
                impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH,
                confidence=0.8
            )
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "results.json")
            
            # Export
            engine.export_results(filepath)
            assert os.path.exists(filepath)
            
            # Clear and import
            engine.results = []
            engine.import_results(filepath)
            
            assert len(engine.results) == 1
            assert engine.results[0].event_id == "1"
            assert engine.results[0].event_title == "CPI"


class TestBacktestEngineIntegration:
    """Integration tests for BacktestEngine"""
    
    @patch('core.backtest_engine.GoldPriceFetcher')
    @patch('core.backtest_engine.EventImpactEngine')
    def test_run_backtest(self, mock_engine_class, mock_fetcher_class):
        """Test full backtest run"""
        # Setup mocks
        mock_impact_engine = Mock()
        mock_impact_result = Mock()
        mock_impact_result.composite_score = 5.0
        mock_impact_result.confidence_score = 0.85
        mock_impact_result.surprise_result = None
        mock_impact_engine.analyze_event_impact.return_value = mock_impact_result
        mock_engine_class.return_value = mock_impact_engine
        
        mock_price_fetcher = Mock()
        mock_price_fetcher.get_price_at.return_value = 2000.0
        mock_fetcher_class.return_value = mock_price_fetcher
        
        # Create engine with mocked dependencies
        engine = BacktestEngine(
            impact_engine=mock_impact_engine,
            price_fetcher=mock_price_fetcher
        )
        
        # Create test events
        events = [
            HistoricalEvent(
                title="CPI",
                country="USD",
                date=datetime(2024, 1, 15, 8, 30),
                impact=EventImpact.HIGH,
                actual="3.1%",
                event_id="1"
            ),
            HistoricalEvent(
                title="NFP",
                country="USD",
                date=datetime(2024, 1, 16, 8, 30),
                impact=EventImpact.HIGH,
                actual="200K",
                event_id="2"
            )
        ]
        
        # Run backtest
        results = engine.run_backtest(events, pre_event_minutes=15, timeframes=[15])
        
        assert len(results) == 2
        assert all(r.event_id in ["1", "2"] for r in results)
