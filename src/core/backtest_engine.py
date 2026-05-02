"""
Backtest Engine

Core backtesting system that:
1. Runs historical events through the Impact Engine
2. Fetches gold prices before/after events
3. Records predictions vs actual outcomes
4. Calculates accuracy and P&L statistics
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

from config import DATA_DIR
from core.historical_event_loader import HistoricalEvent, HistoricalEventLoader
from core.gold_price_fetcher import GoldPriceFetcher, get_price_change
from core.event_impact_engine import (
    EventImpactEngine, 
    EventImpactResult,
    ImpactScore,
    SurpriseResult,
    analyze_event_impact
)
from core.surprise_engine import SurpriseEngine, EconomicDataPoint

logger = logging.getLogger(__name__)


class PredictionDirection(str, Enum):
    """Direction predicted by the impact engine"""
    BULLISH = "bullish"       # Gold up
    BEARISH = "bearish"       # Gold down
    NEUTRAL = "neutral"       # No significant move


class OutcomeResult(str, Enum):
    """Actual outcome of the prediction"""
    CORRECT = "correct"
    INCORRECT = "incorrect"
    NO_SIGNAL = "no_signal"   # Prediction was neutral
    NO_DATA = "no_data"       # Couldn't fetch price data


@dataclass
class BacktestTrade:
    """
    A single simulated trade based on a prediction
    
    Records entry/exit prices and P&L
    """
    entry_price: float
    exit_price: float
    direction: PredictionDirection  # Direction we traded
    position_size: float = 1.0  # In ounces (standard lot = 100 oz)
    
    @property
    def pnl(self) -> float:
        """Profit/Loss in USD"""
        if self.direction == PredictionDirection.BULLISH:
            return (self.exit_price - self.entry_price) * self.position_size
        elif self.direction == PredictionDirection.BEARISH:
            return (self.entry_price - self.exit_price) * self.position_size
        return 0.0
    
    @property
    def pnl_pct(self) -> float:
        """Profit/Loss as percentage"""
        if self.entry_price == 0:
            return 0.0
        return (self.pnl / (self.entry_price * self.position_size)) * 100


@dataclass
class BacktestResult:
    """
    Result of backtesting a single event
    
    Contains prediction, actual outcome, and trade details
    """
    # Event info
    event_id: str
    event_title: str
    event_date: datetime
    event_category: str
    
    # Impact Engine prediction
    impact_score: float  # -10 to +10 composite score
    predicted_direction: PredictionDirection
    confidence: float  # 0.0 to 1.0
    
    # Price data
    price_before: Optional[float] = None
    price_after_5m: Optional[float] = None
    price_after_15m: Optional[float] = None
    price_after_30m: Optional[float] = None
    price_after_60m: Optional[float] = None
    
    # Actual outcome
    actual_direction_5m: Optional[PredictionDirection] = None
    actual_direction_15m: Optional[PredictionDirection] = None
    actual_direction_30m: Optional[PredictionDirection] = None
    actual_direction_60m: Optional[PredictionDirection] = None
    
    # Outcome results
    outcome_5m: OutcomeResult = OutcomeResult.NO_DATA
    outcome_15m: OutcomeResult = OutcomeResult.NO_DATA
    outcome_30m: OutcomeResult = OutcomeResult.NO_DATA
    outcome_60m: OutcomeResult = OutcomeResult.NO_DATA
    
    # Trades at different timeframes
    trade_5m: Optional[BacktestTrade] = None
    trade_15m: Optional[BacktestTrade] = None
    trade_30m: Optional[BacktestTrade] = None
    trade_60m: Optional[BacktestTrade] = None
    
    # Event details
    forecast: Optional[str] = None
    actual: Optional[str] = None
    surprise_score: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result['event_date'] = self.event_date.isoformat()
        result['predicted_direction'] = self.predicted_direction.value
        result['outcome_5m'] = self.outcome_5m.value
        result['outcome_15m'] = self.outcome_15m.value
        result['outcome_30m'] = self.outcome_30m.value
        result['outcome_60m'] = self.outcome_60m.value
        
        # Convert enums in optional fields
        for timeframe in ['5m', '15m', '30m', '60m']:
            dir_key = f'actual_direction_{timeframe}'
            if result.get(dir_key):
                result[dir_key] = result[dir_key].value
        
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BacktestResult':
        """Create from dictionary"""
        data = data.copy()
        data['event_date'] = datetime.fromisoformat(data['event_date'])
        data['predicted_direction'] = PredictionDirection(data['predicted_direction'])
        data['outcome_5m'] = OutcomeResult(data['outcome_5m'])
        data['outcome_15m'] = OutcomeResult(data['outcome_15m'])
        data['outcome_30m'] = OutcomeResult(data['outcome_30m'])
        data['outcome_60m'] = OutcomeResult(data['outcome_60m'])
        
        # Convert optional direction enums
        for timeframe in ['5m', '15m', '30m', '60m']:
            dir_key = f'actual_direction_{timeframe}'
            if data.get(dir_key):
                data[dir_key] = PredictionDirection(data[dir_key])
        
        return cls(**data)
    
    def get_pnl(self, timeframe: str = '15m') -> Optional[float]:
        """Get P&L for specific timeframe"""
        trade = getattr(self, f'trade_{timeframe}', None)
        if trade:
            return trade.pnl
        return None
    
    def was_correct(self, timeframe: str = '15m') -> Optional[bool]:
        """Check if prediction was correct for timeframe"""
        outcome = getattr(self, f'outcome_{timeframe}', None)
        if outcome == OutcomeResult.CORRECT:
            return True
        elif outcome == OutcomeResult.INCORRECT:
            return False
        return None


class BacktestEngine:
    """
    Main backtest engine
    
    Runs historical events through the impact engine and measures
    prediction accuracy against actual gold price movements.
    """
    
    # Price movement thresholds (in USD)
    MOVE_THRESHOLD_SMALL = 1.0   # $1 - neutral
    MOVE_THRESHOLD_MEDIUM = 3.0  # $3 - small move
    MOVE_THRESHOLD_LARGE = 5.0   # $5 - significant move
    
    # Impact score thresholds for trading
    SCORE_THRESHOLD_TRADE = 3.0  # Only trade if |score| >= 3
    
    def __init__(
        self,
        impact_engine: Optional[EventImpactEngine] = None,
        price_fetcher: Optional[GoldPriceFetcher] = None
    ):
        self.impact_engine = impact_engine or EventImpactEngine()
        self.price_fetcher = price_fetcher or GoldPriceFetcher()
        self.results: List[BacktestResult] = []
    
    def run_backtest(
        self,
        events: List[HistoricalEvent],
        pre_event_minutes: int = 15,
        timeframes: List[int] = None
    ) -> List[BacktestResult]:
        """
        Run backtest on a list of historical events
        
        Args:
            events: Historical events to backtest
            pre_event_minutes: Minutes before event to fetch baseline price
            timeframes: List of minutes after event to analyze [5, 15, 30, 60]
        
        Returns:
            List of BacktestResult
        """
        if timeframes is None:
            timeframes = [5, 15, 30, 60]
        
        self.results = []
        
        logger.info(f"Running backtest on {len(events)} events...")
        
        for i, event in enumerate(events, 1):
            logger.info(f"Processing event {i}/{len(events)}: {event.title}")
            
            try:
                result = self._backtest_single_event(event, pre_event_minutes, timeframes)
                if result:
                    self.results.append(result)
            except Exception as e:
                logger.error(f"Error backtesting event {event.title}: {e}")
                continue
        
        logger.info(f"Backtest complete. Processed {len(self.results)} events.")
        
        return self.results
    
    def _backtest_single_event(
        self,
        event: HistoricalEvent,
        pre_event_minutes: int,
        timeframes: List[int]
    ) -> Optional[BacktestResult]:
        """
        Backtest a single event
        
        1. Run through impact engine
        2. Get prediction direction and confidence
        3. Fetch gold prices (before and after)
        4. Calculate actual price movements
        5. Determine if prediction was correct
        6. Calculate simulated trade P&L
        """
        # Step 1: Run through impact engine
        impact_result = self._analyze_event_impact(event)
        if not impact_result:
            logger.warning(f"Could not analyze impact for {event.title}")
            return None
        
        # Step 2: Determine prediction direction (access dict fields)
        composite_score = impact_result.get('composite_score', 0) if isinstance(impact_result, dict) else impact_result.composite_score
        predicted_direction = self._score_to_direction(composite_score)
        
        # Step 3: Fetch prices
        price_before = self._get_price_before_event(event.date, pre_event_minutes)
        if price_before is None:
            logger.warning(f"Could not fetch price before event: {event.title}")
            return None
        
        # Get surprise score from result
        surprise_score = impact_result.get('surprise_score') if isinstance(impact_result, dict) else getattr(impact_result, 'surprise_score', None)
        
        # Create result object
        result = BacktestResult(
            event_id=event.event_id or f"evt_{event.date.strftime('%Y%m%d_%H%M')}",
            event_title=event.title,
            event_date=event.date,
            event_category=event.country,  # TODO: Use proper category
            impact_score=composite_score,
            predicted_direction=predicted_direction,
            confidence=0.7,  # Default confidence since analyze_event_impact doesn't return it
            price_before=price_before,
            forecast=event.forecast,
            actual=event.actual,
            surprise_score=surprise_score
        )
        
        # Step 4: Analyze each timeframe
        for minutes in timeframes:
            self._analyze_timeframe(result, event.date, minutes, price_before)
        
        return result
    
    def _analyze_event_impact(self, event: HistoricalEvent) -> Optional[EventImpactResult]:
        """Run event through impact engine"""
        try:
            # Create data point from event
            data_point = None
            if event.actual and event.forecast:
                # Try to parse numeric values
                try:
                    actual_val = self._parse_numeric_value(event.actual)
                    forecast_val = self._parse_numeric_value(event.forecast)
                    
                    if actual_val is not None and forecast_val is not None:
                        data_point = EconomicDataPoint(
                            name=event.title,
                            actual=actual_val,
                            forecast=forecast_val,
                            previous=self._parse_numeric_value(event.previous) if event.previous else None,
                            unit="",
                            release_time=event.date
                        )
                except ValueError:
                    pass
            
            # Run impact analysis using standalone function
            impact_dict = analyze_event_impact(
                event_name=event.title,
                actual=data_point.actual if data_point else 0.0,
                forecast=data_point.forecast if data_point else 0.0,
                previous=data_point.previous if data_point else None,
                event_dict={"title": event.title, "country": event.country, "impact": event.impact.value}
            )
            
            return impact_dict
            
        except Exception as e:
            logger.error(f"Error analyzing event impact: {e}")
            return None
    
    def _get_price_before_event(
        self,
        event_time: datetime,
        minutes_before: int
    ) -> Optional[float]:
        """Get gold price before event"""
        target_time = event_time - timedelta(minutes=minutes_before)
        return self.price_fetcher.get_price_at(target_time)
    
    def _analyze_timeframe(
        self,
        result: BacktestResult,
        event_time: datetime,
        minutes_after: int,
        price_before: float
    ):
        """Analyze a specific timeframe after the event"""
        # Get price after event
        target_time = event_time + timedelta(minutes=minutes_after)
        price_after = self.price_fetcher.get_price_at(target_time)
        
        # Set price attribute
        price_attr = f'price_after_{minutes_after}m'
        setattr(result, price_attr, price_after)
        
        if price_after is None:
            logger.warning(f"Could not fetch price at +{minutes_after}m")
            outcome_attr = f'outcome_{minutes_after}m'
            setattr(result, outcome_attr, OutcomeResult.NO_DATA)
            return
        
        # Determine actual direction
        price_change = price_after - price_before
        actual_direction = self._price_change_to_direction(price_change)
        
        dir_attr = f'actual_direction_{minutes_after}m'
        setattr(result, dir_attr, actual_direction)
        
        # Determine if prediction was correct
        outcome = self._determine_outcome(result.predicted_direction, actual_direction)
        outcome_attr = f'outcome_{minutes_after}m'
        setattr(result, outcome_attr, outcome)
        
        # Create simulated trade (only if we had a directional signal)
        if result.predicted_direction != PredictionDirection.NEUTRAL:
            trade = BacktestTrade(
                entry_price=price_before,
                exit_price=price_after,
                direction=result.predicted_direction
            )
            trade_attr = f'trade_{minutes_after}m'
            setattr(result, trade_attr, trade)
    
    def _parse_numeric_value(self, value_str: str) -> Optional[float]:
        """Parse numeric value from string (handles %, K, M suffixes)"""
        if not value_str:
            return None
        
        value_str = value_str.strip().replace(',', '')
        
        # Remove common suffixes
        multipliers = {
            'K': 1000,
            'M': 1000000,
            'B': 1000000000,
            '%': 1
        }
        
        multiplier = 1
        for suffix, mult in multipliers.items():
            if value_str.endswith(suffix):
                value_str = value_str[:-1]
                multiplier = mult
                break
        
        try:
            return float(value_str) * multiplier
        except ValueError:
            return None
    
    def _score_to_direction(self, score: float) -> PredictionDirection:
        """Convert impact score to prediction direction"""
        if abs(score) < self.SCORE_THRESHOLD_TRADE:
            return PredictionDirection.NEUTRAL
        elif score > 0:
            return PredictionDirection.BULLISH  # Positive score = gold up
        else:
            return PredictionDirection.BEARISH  # Negative score = gold down
    
    def _price_change_to_direction(self, price_change: float) -> PredictionDirection:
        """Convert price change to direction"""
        if abs(price_change) < self.MOVE_THRESHOLD_SMALL:
            return PredictionDirection.NEUTRAL
        elif price_change > 0:
            return PredictionDirection.BULLISH
        else:
            return PredictionDirection.BEARISH
    
    def _determine_outcome(
        self,
        predicted: PredictionDirection,
        actual: PredictionDirection
    ) -> OutcomeResult:
        """Determine if prediction was correct"""
        if predicted == PredictionDirection.NEUTRAL:
            return OutcomeResult.NO_SIGNAL
        
        if actual == PredictionDirection.NEUTRAL:
            # Small move - consider it correct if prediction was neutral-ish
            return OutcomeResult.CORRECT if abs(predicted.value == PredictionDirection.NEUTRAL) else OutcomeResult.NO_SIGNAL
        
        if predicted == actual:
            return OutcomeResult.CORRECT
        else:
            return OutcomeResult.INCORRECT
    
    def get_statistics(self, timeframe: str = '15m') -> Dict[str, Any]:
        """
        Calculate backtest statistics for a timeframe
        
        Returns:
            Dict with accuracy, P&L stats, etc.
        """
        if not self.results:
            return {}
        
        # Filter results with valid outcomes
        valid_results = [
            r for r in self.results 
            if getattr(r, f'outcome_{timeframe}', None) in [OutcomeResult.CORRECT, OutcomeResult.INCORRECT]
        ]
        
        if not valid_results:
            return {
                'total_events': len(self.results),
                'valid_predictions': 0,
                'accuracy': 0.0
            }
        
        # Calculate accuracy
        correct = sum(1 for r in valid_results if r.was_correct(timeframe))
        accuracy = (correct / len(valid_results)) * 100
        
        # Calculate P&L stats
        pnls = [r.get_pnl(timeframe) for r in valid_results if r.get_pnl(timeframe) is not None]
        
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0
        winning_trades = [p for p in pnls if p > 0]
        losing_trades = [p for p in pnls if p < 0]
        
        avg_win = sum(winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(losing_trades) / len(losing_trades) if losing_trades else 0
        
        total_pnl = sum(pnls)
        
        return {
            'timeframe': timeframe,
            'total_events': len(self.results),
            'valid_predictions': len(valid_results),
            'correct_predictions': correct,
            'incorrect_predictions': len(valid_results) - correct,
            'accuracy': round(accuracy, 2),
            'total_pnl': round(total_pnl, 2),
            'avg_pnl': round(avg_pnl, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'win_rate': round(len(winning_trades) / len(pnls) * 100, 2) if pnls else 0,
            'profit_factor': abs(sum(winning_trades) / sum(losing_trades)) if losing_trades and sum(losing_trades) != 0 else float('inf'),
            'total_trades': len(pnls)
        }
    
    def get_stats_by_category(self, timeframe: str = '15m') -> Dict[str, Dict[str, Any]]:
        """Get statistics grouped by event category"""
        if not self.results:
            return {}
        
        categories = {}
        
        for result in self.results:
            cat = result.event_category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(result)
        
        stats_by_cat = {}
        for cat, results in categories.items():
            # Temporarily set results to this category
            original_results = self.results
            self.results = results
            stats_by_cat[cat] = self.get_statistics(timeframe)
            self.results = original_results
        
        return stats_by_cat
    
    def export_results(self, filepath: str):
        """Export results to JSON file"""
        data = {
            'backtest_date': datetime.now().isoformat(),
            'total_events': len(self.results),
            'results': [r.to_dict() for r in self.results]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported {len(self.results)} results to {filepath}")
    
    def import_results(self, filepath: str):
        """Import results from JSON file"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.results = [BacktestResult.from_dict(r) for r in data['results']]
        
        logger.info(f"Imported {len(self.results)} results from {filepath}")


# Convenience functions
_backtest_engine = None

def get_backtest_engine() -> BacktestEngine:
    """Get singleton BacktestEngine instance"""
    global _backtest_engine
    if _backtest_engine is None:
        _backtest_engine = BacktestEngine()
    return _backtest_engine
