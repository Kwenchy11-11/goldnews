"""
Tests for Paper Trading Logger

Tests paper trade creation, MFE/MAE tracking, and performance reporting
with mock price data.
"""

import pytest
import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from src.core.paper_trading_logger import (
    PaperTradingLogger, PaperTrade, WeeklyPerformance,
    TradeResult, ExitReason, create_paper_trade
)
from src.core.trade_decision_engine import TradeDecision


class TestPaperTradeCreation:
    """Test paper trade creation."""
    
    def test_create_long_trade(self, tmp_path):
        """Create a LONG (buy gold) paper trade."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        event_time = datetime(2024, 1, 15, 8, 30)
        
        trade = logger.create_trade(
            event_id="event_001",
            event_name="CPI y/y",
            event_time=event_time,
            trade_decision=TradeDecision.BUY_GOLD,
            composite_score=-6.5,
            confidence=75.0,
            entry_price=2025.50,
        )
        
        assert trade.trade_id.startswith("paper_")
        assert trade.direction == "LONG"
        assert trade.entry_price == 2025.50
        assert trade.tp_price == 2026.50  # +100 points
        assert trade.sl_price == 2025.00  # -50 points
        assert trade.result == TradeResult.OPEN
    
    def test_create_short_trade(self, tmp_path):
        """Create a SHORT (sell gold) paper trade."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        event_time = datetime(2024, 1, 15, 8, 30)
        
        trade = logger.create_trade(
            event_id="event_002",
            event_name="NFP",
            event_time=event_time,
            trade_decision=TradeDecision.SELL_GOLD,
            composite_score=7.2,
            confidence=80.0,
            entry_price=2030.00,
        )
        
        assert trade.direction == "SHORT"
        assert trade.tp_price == 2029.00  # -100 points (for short)
        assert trade.sl_price == 2030.50  # +50 points (for short)
    
    def test_create_trade_with_custom_tp_sl(self, tmp_path):
        """Create trade with custom TP/SL levels."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        trade = logger.create_trade(
            event_id="event_003",
            event_name="FOMC",
            event_time=datetime.now(),
            trade_decision=TradeDecision.BUY_GOLD,
            composite_score=-5.0,
            confidence=70.0,
            entry_price=2020.00,
            tp_points=200.0,  # $2.00 TP
            sl_points=100.0,  # $1.00 SL
        )
        
        assert trade.tp_points == 200.0
        assert trade.sl_points == 100.0
        assert trade.tp_price == 2022.00
        assert trade.sl_price == 2019.00
    
    def test_non_actionable_decision_raises_error(self, tmp_path):
        """Creating trade with WAIT/NO_TRADE should raise error."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        with pytest.raises(ValueError, match="non-actionable"):
            logger.create_trade(
                event_id="event_004",
                event_name="GDP",
                event_time=datetime.now(),
                trade_decision=TradeDecision.WAIT,
                composite_score=2.0,
                confidence=40.0,
                entry_price=2025.00,
            )


class TestMfeMaeTracking:
    """Test MFE (Max Favorable Excursion) and MAE (Max Adverse Excursion) tracking."""
    
    def test_mfe_tracking_long(self):
        """Track max favorable excursion for LONG position."""
        trade = PaperTrade(
            trade_id="test_001",
            event_id="event_001",
            event_name="CPI",
            event_time=datetime.now(),
            trade_decision="buy",
            composite_score=-5.0,
            confidence=70.0,
            entry_time=datetime.now(),
            entry_price=2025.00,
            direction="LONG",
        )
        
        # Price moves in favor (up)
        trade.update_mfe(2026.00, datetime.now())  # +100 points
        assert trade.max_favorable_excursion == 100.0
        
        # Price moves more in favor
        trade.update_mfe(2027.00, datetime.now())  # +200 points
        assert trade.max_favorable_excursion == 200.0
        
        # Price pulls back - MFE should not change
        trade.update_mfe(2026.50, datetime.now())  # +150 points
        assert trade.max_favorable_excursion == 200.0  # Still 200
    
    def test_mae_tracking_long(self):
        """Track max adverse excursion for LONG position."""
        trade = PaperTrade(
            trade_id="test_002",
            event_id="event_002",
            event_name="NFP",
            event_time=datetime.now(),
            trade_decision="buy",
            composite_score=-5.0,
            confidence=70.0,
            entry_time=datetime.now(),
            entry_price=2025.00,
            direction="LONG",
        )
        
        # Price moves against (down)
        trade.update_mae(2024.50, datetime.now())  # -50 points
        assert trade.max_adverse_excursion == 50.0
        
        # Price moves more against
        trade.update_mae(2024.00, datetime.now())  # -100 points
        assert trade.max_adverse_excursion == 100.0
        
        # Price recovers - MAE should not change
        trade.update_mae(2024.75, datetime.now())  # -25 points
        assert trade.max_adverse_excursion == 100.0  # Still 100
    
    def test_mfe_tracking_short(self):
        """Track max favorable excursion for SHORT position."""
        trade = PaperTrade(
            trade_id="test_003",
            event_id="event_003",
            event_name="FOMC",
            event_time=datetime.now(),
            trade_decision="sell",
            composite_score=6.0,
            confidence=75.0,
            entry_time=datetime.now(),
            entry_price=2030.00,
            direction="SHORT",
        )
        
        # Price moves in favor (down for short)
        trade.update_mfe(2029.00, datetime.now())  # +100 points
        assert trade.max_favorable_excursion == 100.0
        
        # Price moves more in favor
        trade.update_mfe(2028.00, datetime.now())  # +200 points
        assert trade.max_favorable_excursion == 200.0
    
    def test_mae_tracking_short(self):
        """Track max adverse excursion for SHORT position."""
        trade = PaperTrade(
            trade_id="test_004",
            event_id="event_004",
            event_name="CPI",
            event_time=datetime.now(),
            trade_decision="sell",
            composite_score=6.0,
            confidence=75.0,
            entry_time=datetime.now(),
            entry_price=2030.00,
            direction="SHORT",
        )
        
        # Price moves against (up for short)
        trade.update_mae(2031.00, datetime.now())  # -100 points
        assert trade.max_adverse_excursion == 100.0


class TestTradeClosing:
    """Test trade closing scenarios."""
    
    def test_close_trade_win(self):
        """Close a winning trade."""
        trade = PaperTrade(
            trade_id="test_005",
            event_id="event_005",
            event_name="CPI",
            event_time=datetime.now(),
            trade_decision="buy",
            composite_score=-6.0,
            confidence=75.0,
            entry_time=datetime.now(),
            entry_price=2025.00,
            direction="LONG",
            tp_points=100.0,
            sl_points=50.0,
        )
        trade.calculate_tp_sl_prices()
        
        exit_time = datetime.now() + timedelta(minutes=15)
        trade.close_trade(2026.20, exit_time, ExitReason.TAKE_PROFIT)
        
        assert trade.result == TradeResult.WIN
        assert trade.pnl_points == pytest.approx(120.0, abs=0.01)
        assert trade.exit_reason == ExitReason.TAKE_PROFIT
    
    def test_close_trade_loss(self):
        """Close a losing trade."""
        trade = PaperTrade(
            trade_id="test_006",
            event_id="event_006",
            event_name="NFP",
            event_time=datetime.now(),
            trade_decision="buy",
            composite_score=-5.0,
            confidence=70.0,
            entry_time=datetime.now(),
            entry_price=2025.00,
            direction="LONG",
        )
        
        exit_time = datetime.now() + timedelta(minutes=10)
        trade.close_trade(2024.30, exit_time, ExitReason.STOP_LOSS)
        
        assert trade.result == TradeResult.LOSS
        assert trade.pnl_points == pytest.approx(-70.0, abs=0.01)
        assert trade.exit_reason == ExitReason.STOP_LOSS
    
    def test_close_trade_breakeven(self):
        """Close a breakeven trade (small P&L)."""
        trade = PaperTrade(
            trade_id="test_007",
            event_id="event_007",
            event_name="GDP",
            event_time=datetime.now(),
            trade_decision="buy",
            composite_score=-4.0,
            confidence=60.0,
            entry_time=datetime.now(),
            entry_price=2025.00,
            direction="LONG",
        )
        
        exit_time = datetime.now() + timedelta(minutes=20)
        trade.close_trade(2025.03, exit_time, ExitReason.TIMEOUT)  # Only 3 points
        
        assert trade.result == TradeResult.BREAKEVEN
        assert abs(trade.pnl_points) < 5  # Within breakeven threshold
    
    def test_close_trade_timeout(self):
        """Close trade at holding period timeout."""
        trade = PaperTrade(
            trade_id="test_008",
            event_id="event_008",
            event_name="Retail Sales",
            event_time=datetime.now(),
            trade_decision="sell",
            composite_score=5.0,
            confidence=65.0,
            entry_time=datetime.now(),
            entry_price=2030.00,
            direction="SHORT",
            holding_period_minutes=30,
        )
        
        exit_time = datetime.now() + timedelta(minutes=30)
        trade.close_trade(2029.50, exit_time, ExitReason.TIMEOUT)
        
        assert trade.result == TradeResult.WIN
        assert trade.exit_reason == ExitReason.TIMEOUT
        assert trade.pnl_points == 50.0  # 50 points profit


class TestDatabaseOperations:
    """Test database storage and retrieval."""
    
    def test_save_and_retrieve_trade(self, tmp_path):
        """Save trade to DB and retrieve it."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        # Create trade
        trade = logger.create_trade(
            event_id="event_009",
            event_name="CPI",
            event_time=datetime(2024, 1, 15, 8, 30),
            trade_decision=TradeDecision.BUY_GOLD,
            composite_score=-6.0,
            confidence=75.0,
            entry_price=2025.00,
        )
        
        # Retrieve
        retrieved = logger.get_trade(trade.trade_id)
        
        assert retrieved is not None
        assert retrieved.trade_id == trade.trade_id
        assert retrieved.event_name == "CPI"
        assert retrieved.direction == "LONG"
    
    def test_get_open_trades(self, tmp_path):
        """Get list of open trades."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        # Create open trade
        logger.create_trade(
            event_id="event_010",
            event_name="NFP",
            event_time=datetime.now(),
            trade_decision=TradeDecision.SELL_GOLD,
            composite_score=7.0,
            confidence=80.0,
            entry_price=2030.00,
        )
        
        open_trades = logger.get_open_trades()
        
        assert len(open_trades) == 1
        assert open_trades[0].result == TradeResult.OPEN
    
    def test_get_trades_by_date_range(self, tmp_path):
        """Get trades within date range."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        # Create trades on different dates
        logger.create_trade(
            event_id="event_011",
            event_name="CPI",
            event_time=datetime(2024, 1, 10, 8, 30),
            trade_decision=TradeDecision.BUY_GOLD,
            composite_score=-5.0,
            confidence=70.0,
            entry_price=2025.00,
            entry_time=datetime(2024, 1, 10, 8, 30),
        )
        
        logger.create_trade(
            event_id="event_012",
            event_name="NFP",
            event_time=datetime(2024, 1, 20, 8, 30),
            trade_decision=TradeDecision.SELL_GOLD,
            composite_score=6.0,
            confidence=75.0,
            entry_price=2030.00,
            entry_time=datetime(2024, 1, 20, 8, 30),
        )
        
        # Query for first half of January
        trades = logger.get_trades_by_date_range(
            datetime(2024, 1, 1),
            datetime(2024, 1, 15)
        )
        
        assert len(trades) == 1
        assert trades[0].event_name == "CPI"
    
    def test_update_trade_with_price(self, tmp_path):
        """Update trade with price for MFE/MAE tracking."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        trade = logger.create_trade(
            event_id="event_013",
            event_name="FOMC",
            event_time=datetime.now(),
            trade_decision=TradeDecision.BUY_GOLD,
            composite_score=-5.0,
            confidence=70.0,
            entry_price=2025.00,
            tp_points=100.0,
            sl_points=50.0,
        )
        
        # Update with price that moves in favor (but not at TP)
        timestamp = datetime.now() + timedelta(minutes=5)
        logger.update_trade_with_price(trade.trade_id, 2025.80, timestamp)

        # Retrieve and check MFE
        updated = logger.get_trade(trade.trade_id)
        assert updated.max_favorable_excursion == pytest.approx(80.0, abs=0.01)
        assert updated.result == TradeResult.OPEN  # Not closed yet (below TP at 2026.0)
    
    def test_tp_hit_closes_trade(self, tmp_path):
        """TP hit should automatically close trade."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        trade = logger.create_trade(
            event_id="event_014",
            event_name="CPI",
            event_time=datetime.now(),
            trade_decision=TradeDecision.BUY_GOLD,
            composite_score=-6.0,
            confidence=75.0,
            entry_price=2025.00,
            tp_points=100.0,
            sl_points=50.0,
        )
        
        # Update with price at TP level
        timestamp = datetime.now() + timedelta(minutes=10)
        logger.update_trade_with_price(trade.trade_id, 2026.00, timestamp)
        
        # Retrieve
        updated = logger.get_trade(trade.trade_id)
        assert updated.result == TradeResult.WIN
        assert updated.exit_reason == ExitReason.TAKE_PROFIT
        assert updated.exit_price == 2026.00
    
    def test_sl_hit_closes_trade(self, tmp_path):
        """SL hit should automatically close trade."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        trade = logger.create_trade(
            event_id="event_015",
            event_name="NFP",
            event_time=datetime.now(),
            trade_decision=TradeDecision.SELL_GOLD,
            composite_score=6.0,
            confidence=75.0,
            entry_price=2030.00,
            tp_points=100.0,
            sl_points=50.0,
        )
        
        # Update with price at SL level (for short, SL is above entry)
        timestamp = datetime.now() + timedelta(minutes=5)
        logger.update_trade_with_price(trade.trade_id, 2030.50, timestamp)
        
        # Retrieve
        updated = logger.get_trade(trade.trade_id)
        assert updated.result == TradeResult.LOSS
        assert updated.exit_reason == ExitReason.STOP_LOSS


class TestPerformanceReporting:
    """Test performance reporting and statistics."""
    
    def test_weekly_performance_calculation(self, tmp_path):
        """Calculate weekly performance stats."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        week_start = datetime(2024, 1, 8)  # Monday
        
        # Create winning trade
        trade1 = logger.create_trade(
            event_id="event_016",
            event_name="CPI",
            event_time=week_start + timedelta(days=1),
            trade_decision=TradeDecision.BUY_GOLD,
            composite_score=-6.0,
            confidence=75.0,
            entry_price=2025.00,
            entry_time=week_start + timedelta(days=1),
        )
        trade1.close_trade(2026.50, week_start + timedelta(days=1, minutes=15), ExitReason.TAKE_PROFIT)
        logger._save_trade(trade1)
        
        # Create losing trade
        trade2 = logger.create_trade(
            event_id="event_017",
            event_name="NFP",
            event_time=week_start + timedelta(days=2),
            trade_decision=TradeDecision.SELL_GOLD,
            composite_score=5.0,
            confidence=70.0,
            entry_price=2030.00,
            entry_time=week_start + timedelta(days=2),
        )
        trade2.close_trade(2030.75, week_start + timedelta(days=2, minutes=10), ExitReason.STOP_LOSS)
        logger._save_trade(trade2)
        
        # Get weekly performance
        perf = logger.get_weekly_performance(week_start)
        
        assert perf.total_trades == 2
        assert perf.wins == 1
        assert perf.losses == 1
        assert perf.win_rate == 50.0
        assert perf.total_pnl_points == pytest.approx(75.0, abs=0.01)  # 150 - 75
    
    def test_export_weekly_report(self, tmp_path):
        """Export weekly performance to JSON."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        week_start = datetime(2024, 1, 8)
        
        # Create a trade
        trade = logger.create_trade(
            event_id="event_018",
            event_name="CPI",
            event_time=week_start + timedelta(days=1),
            trade_decision=TradeDecision.BUY_GOLD,
            composite_score=-6.0,
            confidence=75.0,
            entry_price=2025.00,
            entry_time=week_start + timedelta(days=1),
        )
        trade.close_trade(2026.50, week_start + timedelta(days=1, minutes=15), ExitReason.TAKE_PROFIT)
        logger._save_trade(trade)
        
        # Export
        export_path = tmp_path / "weekly_report.json"
        filepath = logger.export_weekly_report(week_start, str(export_path))
        
        assert Path(filepath).exists()
        
        # Verify content
        with open(filepath) as f:
            data = json.load(f)
        
        assert data["total_trades"] == 1
        assert data["wins"] == 1
        assert data["win_rate"] == 100.0
    
    def test_get_statistics(self, tmp_path):
        """Get overall trading statistics."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        # Create trades
        for i in range(3):
            trade = logger.create_trade(
                event_id=f"event_{100+i}",
                event_name=f"Event{i}",
                event_time=datetime.now(),
                trade_decision=TradeDecision.BUY_GOLD if i % 2 == 0 else TradeDecision.SELL_GOLD,
                composite_score=-5.0 if i % 2 == 0 else 5.0,
                confidence=70.0,
                entry_price=2025.00 + i,
                entry_time=datetime.now(),
            )
            if i < 2:
                trade.close_trade(
                    trade.entry_price + (0.5 if i % 2 == 0 else -0.5),
                    datetime.now(),
                    ExitReason.TAKE_PROFIT
                )
                logger._save_trade(trade)
        
        stats = logger.get_statistics()
        
        assert stats["total_trades"] == 3
        assert stats["wins"] == 2
        assert stats["losses"] == 0
        assert stats["open_trades"] == 1


class TestMockPriceScenarios:
    """Test with mock price data simulating real market scenarios."""
    
    def test_scenario_cpi_volatile_then_tp(self, tmp_path):
        """CPI release: volatile first, then hit TP."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        base_time = datetime(2024, 1, 15, 8, 30)
        
        trade = logger.create_trade(
            event_id="cpi_001",
            event_name="CPI y/y",
            event_time=base_time,
            trade_decision=TradeDecision.BUY_GOLD,
            composite_score=-7.0,
            confidence=80.0,
            entry_price=2025.00,
            entry_time=base_time,
            tp_points=100.0,
            sl_points=50.0,
        )
        
        # Simulate price action: dip first (near SL but not hitting), then rally to TP
        prices = [
            (2024.60, base_time + timedelta(minutes=1)),   # -40 points (near SL at -50)
            (2024.55, base_time + timedelta(minutes=2)),   # -45 points (closer to SL but not hit)
            (2024.80, base_time + timedelta(minutes=3)),   # recovering
            (2025.50, base_time + timedelta(minutes=5)),   # +50 points
            (2026.00, base_time + timedelta(minutes=8)),   # +100 points (TP hit!)
        ]
        
        for price, timestamp in prices:
            logger.update_trade_with_price(trade.trade_id, price, timestamp)
        
        # Verify
        updated = logger.get_trade(trade.trade_id)
        assert updated.result == TradeResult.WIN
        assert updated.exit_reason == ExitReason.TAKE_PROFIT
        assert updated.max_adverse_excursion == pytest.approx(45.0, abs=0.01)
        assert updated.max_favorable_excursion >= 100.0

        # Add note about the volatility
        updated.notes = "High volatility after release, near SL zone briefly before TP"
        logger._save_trade(updated)
    
    def test_scenario_nfp_mixed_signals_stopout(self, tmp_path):
        """NFP with mixed signals: stopped out before reversal."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        base_time = datetime(2024, 1, 5, 8, 30)
        
        # Mixed signal scenario - went short but market confused
        trade = logger.create_trade(
            event_id="nfp_mixed_001",
            event_name="NFP + Unemployment",
            event_time=base_time,
            trade_decision=TradeDecision.SELL_GOLD,  # Short
            composite_score=4.5,
            confidence=65.0,
            entry_price=2030.00,
            entry_time=base_time,
            tp_points=100.0,
            sl_points=50.0,
        )
        
        # Price spikes up (against short) and hits SL
        prices = [
            (2030.20, base_time + timedelta(minutes=1)),
            (2030.50, base_time + timedelta(minutes=2)),  # SL hit
        ]
        
        for price, timestamp in prices:
            logger.update_trade_with_price(trade.trade_id, price, timestamp)
        
        updated = logger.get_trade(trade.trade_id)
        assert updated.result == TradeResult.LOSS
        assert updated.exit_reason == ExitReason.STOP_LOSS
        assert updated.max_adverse_excursion == 50.0
        
        # Note about mixed signals
        updated.notes = "Mixed NFP signals - payrolls bullish but unemployment bearish. Wrong direction."
        logger._save_trade(updated)
    
    def test_scenario_timeout_with_small_profit(self, tmp_path):
        """Trade reaches timeout with small profit."""
        db_path = tmp_path / "test_paper.db"
        logger = PaperTradingLogger(db_path=str(db_path))
        
        base_time = datetime(2024, 1, 10, 10, 0)
        
        trade = logger.create_trade(
            event_id="gdp_timeout_001",
            event_name="GDP q/q",
            event_time=base_time,
            trade_decision=TradeDecision.BUY_GOLD,
            composite_score=-5.0,
            confidence=70.0,
            entry_price=2025.00,
            entry_time=base_time,
            holding_period=30,
        )
        
        # Price moves around but doesn't hit TP or SL
        for i in range(6):
            price = 2025.00 + (0.2 if i % 2 == 0 else -0.1)
            timestamp = base_time + timedelta(minutes=i * 5)
            logger.update_trade_with_price(trade.trade_id, price, timestamp)
        
        # Close at timeout
        exit_time = base_time + timedelta(minutes=30)
        logger.close_trade_at_timeout(trade.trade_id, 2025.25, exit_time)
        
        updated = logger.get_trade(trade.trade_id)
        assert updated.result == TradeResult.WIN  # Small profit
        assert updated.exit_reason == ExitReason.TIMEOUT
        assert updated.pnl_points == 25.0  # 25 points profit


class TestConvenienceFunction:
    """Test convenience function."""
    
    def test_create_paper_trade_function(self, tmp_path):
        """Test the convenience function."""
        # Use temp directory for DB
        import os
        os.chdir(tmp_path)
        
        trade = create_paper_trade(
            event_id="conv_test_001",
            event_name="CPI",
            event_time=datetime.now(),
            trade_decision=TradeDecision.BUY_GOLD,
            composite_score=-6.0,
            confidence=75.0,
            entry_price=2025.00,
            tp_points=150.0,
        )
        
        assert isinstance(trade, PaperTrade)
        assert trade.tp_points == 150.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
