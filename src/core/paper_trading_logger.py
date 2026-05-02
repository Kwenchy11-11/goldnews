"""Paper Trading Logger - Simulated trading for event-based gold signals.

Records paper trades without real money to validate signal quality before live trading.
Tracks MFE (Max Favorable Excursion) and MAE (Max Adverse Excursion) to understand
trade quality and potential improvements.

Key metrics tracked:
- Entry/exit prices and times
- TP/SL levels and hit rates
- Holding period performance
- MFE/MAE for trade quality analysis
- Win/loss/breakeven statistics
- Weekly performance summaries
"""

import sqlite3
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
import sys

sys.path.insert(0, str(Path(__file__).parent))

from trade_decision_engine import TradeDecision

logger = logging.getLogger(__name__)


class TradeResult(Enum):
    """Result of a paper trade."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    OPEN = "open"  # Still active


class ExitReason(Enum):
    """Reason for trade exit."""
    TAKE_PROFIT = "tp"
    STOP_LOSS = "sl"
    TIMEOUT = "timeout"
    MANUAL = "manual"
    STILL_OPEN = "open"


@dataclass
class PaperTrade:
    """A single paper trade record."""
    # Trade identification
    trade_id: str
    event_id: str
    event_name: str
    event_time: datetime
    
    # Signal details
    trade_decision: str  # BUY_GOLD, SELL_GOLD, etc.
    composite_score: float
    confidence: float
    
    # Entry details
    entry_time: datetime
    entry_price: float
    direction: str  # LONG or SHORT (from gold perspective)
    
    # Exit details
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    exit_reason: ExitReason = ExitReason.STILL_OPEN
    
    # TP/SL configuration
    tp_points: float = 100.0  # Default 100 points ($1.00)
    sl_points: float = 50.0   # Default 50 points ($0.50)
    tp_price: Optional[float] = None
    sl_price: Optional[float] = None
    
    # Holding period
    holding_period_minutes: int = 30
    
    # Results
    result: TradeResult = TradeResult.OPEN
    pnl_points: float = 0.0
    pnl_percent: float = 0.0
    
    # MFE/MAE tracking
    max_favorable_excursion: float = 0.0  # Max profit reached during trade
    max_adverse_excursion: float = 0.0    # Max loss reached during trade
    mfe_time: Optional[datetime] = None
    mae_time: Optional[datetime] = None
    
    # Price tracking at intervals
    price_5m: Optional[float] = None
    price_15m: Optional[float] = None
    price_30m: Optional[float] = None
    price_60m: Optional[float] = None
    
    # Notes
    notes: str = ""
    
    # Metadata
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()
    
    def calculate_tp_sl_prices(self):
        """Calculate TP and SL prices based on entry and points."""
        if self.direction == "LONG":
            self.tp_price = self.entry_price + (self.tp_points / 100)
            self.sl_price = self.entry_price - (self.sl_points / 100)
        else:  # SHORT
            self.tp_price = self.entry_price - (self.tp_points / 100)
            self.sl_price = self.entry_price + (self.sl_points / 100)
    
    def update_mfe(self, price: float, time: datetime):
        """Update Max Favorable Excursion if price is more favorable."""
        if self.direction == "LONG":
            excursion = price - self.entry_price
        else:
            excursion = self.entry_price - price
        
        excursion_points = excursion * 100
        
        if excursion_points > self.max_favorable_excursion:
            self.max_favorable_excursion = excursion_points
            self.mfe_time = time
    
    def update_mae(self, price: float, time: datetime):
        """Update Max Adverse Excursion if price is less favorable."""
        if self.direction == "LONG":
            excursion = self.entry_price - price
        else:
            excursion = price - self.entry_price
        
        excursion_points = excursion * 100
        
        if excursion_points > self.max_adverse_excursion:
            self.max_adverse_excursion = excursion_points
            self.mae_time = time
    
    def close_trade(self, exit_price: float, exit_time: datetime, reason: ExitReason):
        """Close the trade and calculate P&L."""
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_reason = reason
        
        # Calculate P&L
        if self.direction == "LONG":
            price_diff = exit_price - self.entry_price
        else:
            price_diff = self.entry_price - exit_price
        
        self.pnl_points = price_diff * 100  # Convert to points
        self.pnl_percent = (price_diff / self.entry_price) * 100
        
        # Determine result
        if abs(self.pnl_points) < 5:  # Within 5 points = breakeven
            self.result = TradeResult.BREAKEVEN
        elif self.pnl_points > 0:
            self.result = TradeResult.WIN
        else:
            self.result = TradeResult.LOSS
        
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert trade to dictionary."""
        return {
            "trade_id": self.trade_id,
            "event_id": self.event_id,
            "event_name": self.event_name,
            "event_time": self.event_time.isoformat(),
            "trade_decision": self.trade_decision,
            "composite_score": self.composite_score,
            "confidence": self.confidence,
            "entry_time": self.entry_time.isoformat(),
            "entry_price": self.entry_price,
            "direction": self.direction,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason.value,
            "tp_points": self.tp_points,
            "sl_points": self.sl_points,
            "tp_price": self.tp_price,
            "sl_price": self.sl_price,
            "holding_period_minutes": self.holding_period_minutes,
            "result": self.result.value,
            "pnl_points": round(self.pnl_points, 2),
            "pnl_percent": round(self.pnl_percent, 4),
            "max_favorable_excursion": round(self.max_favorable_excursion, 2),
            "max_adverse_excursion": round(self.max_adverse_excursion, 2),
            "mfe_time": self.mfe_time.isoformat() if self.mfe_time else None,
            "mae_time": self.mae_time.isoformat() if self.mae_time else None,
            "price_5m": self.price_5m,
            "price_15m": self.price_15m,
            "price_30m": self.price_30m,
            "price_60m": self.price_60m,
            "notes": self.notes,
        }


@dataclass
class WeeklyPerformance:
    """Weekly paper trading performance summary."""
    week_start: datetime
    week_end: datetime
    total_trades: int
    wins: int
    losses: int
    breakevens: int
    win_rate: float
    total_pnl_points: float
    total_pnl_percent: float
    avg_pnl_points: float
    avg_mfe: float
    avg_mae: float
    tp_hit_rate: float
    sl_hit_rate: float
    timeout_rate: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "week_start": self.week_start.isoformat(),
            "week_end": self.week_end.isoformat(),
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "breakevens": self.breakevens,
            "win_rate": round(self.win_rate, 2),
            "total_pnl_points": round(self.total_pnl_points, 2),
            "total_pnl_percent": round(self.total_pnl_percent, 4),
            "avg_pnl_points": round(self.avg_pnl_points, 2),
            "avg_mfe": round(self.avg_mfe, 2),
            "avg_mae": round(self.avg_mae, 2),
            "tp_hit_rate": round(self.tp_hit_rate, 2),
            "sl_hit_rate": round(self.sl_hit_rate, 2),
            "timeout_rate": round(self.timeout_rate, 2),
        }


class PaperTradingLogger:
    """
    Logger for paper trading simulation.
    
    Records simulated trades without real money to validate
    signal quality before live trading.
    """
    
    DEFAULT_CONFIG = {
        "tp_points": 100,          # $1.00 take profit
        "sl_points": 50,           # $0.50 stop loss
        "holding_period": 30,      # 30 minutes default
        "breakeven_threshold": 5,  # 5 points = breakeven
    }
    
    def __init__(self, db_path: str = "data/paper_trades.db", config: Optional[Dict] = None):
        """
        Initialize the paper trading logger.
        
        Args:
            db_path: Path to SQLite database
            config: Optional configuration overrides
        """
        self.db_path = db_path
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        
        # Ensure directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_trades (
                    trade_id TEXT PRIMARY KEY,
                    event_id TEXT,
                    event_name TEXT,
                    event_time TIMESTAMP,
                    trade_decision TEXT,
                    composite_score REAL,
                    confidence REAL,
                    entry_time TIMESTAMP,
                    entry_price REAL,
                    direction TEXT,
                    exit_time TIMESTAMP,
                    exit_price REAL,
                    exit_reason TEXT,
                    tp_points REAL,
                    sl_points REAL,
                    tp_price REAL,
                    sl_price REAL,
                    holding_period_minutes INTEGER,
                    result TEXT,
                    pnl_points REAL,
                    pnl_percent REAL,
                    max_favorable_excursion REAL,
                    max_adverse_excursion REAL,
                    mfe_time TIMESTAMP,
                    mae_time TIMESTAMP,
                    price_5m REAL,
                    price_15m REAL,
                    price_30m REAL,
                    price_60m REAL,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_event_time ON paper_trades(event_time)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_result ON paper_trades(result)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_entry_time ON paper_trades(entry_time)")
            
            conn.commit()
    
    def create_trade(
        self,
        event_id: str,
        event_name: str,
        event_time: datetime,
        trade_decision: TradeDecision,
        composite_score: float,
        confidence: float,
        entry_price: float,
        entry_time: Optional[datetime] = None,
        tp_points: Optional[float] = None,
        sl_points: Optional[float] = None,
        holding_period: Optional[int] = None,
    ) -> PaperTrade:
        """
        Create a new paper trade.
        
        Args:
            event_id: Unique event identifier
            event_name: Name of the event
            event_time: Time of event release
            trade_decision: BUY_GOLD, SELL_GOLD, etc.
            composite_score: Impact engine composite score
            confidence: Confidence level (0-100)
            entry_price: Entry price for XAUUSD
            entry_time: Optional entry time (defaults to now)
            tp_points: Optional override for TP in points
            sl_points: Optional override for SL in points
            holding_period: Optional override for holding period in minutes
            
        Returns:
            PaperTrade object
        """
        # Generate trade ID
        trade_id = f"paper_{event_time.strftime('%Y%m%d_%H%M%S')}_{event_name[:10]}"
        
        # Determine direction - compare by value since we might get enum or string
        decision_value = trade_decision.value if hasattr(trade_decision, 'value') else trade_decision
        if decision_value in ['buy', 'strong_buy']:
            direction = "LONG"
        elif decision_value in ['sell', 'strong_sell']:
            direction = "SHORT"
        else:
            raise ValueError(f"Cannot create trade for non-actionable decision: {trade_decision}")
        
        # Use defaults if not specified
        tp = tp_points or self.config["tp_points"]
        sl = sl_points or self.config["sl_points"]
        hold = holding_period or self.config["holding_period"]
        entry = entry_time or datetime.now()
        
        # Create trade
        trade = PaperTrade(
            trade_id=trade_id,
            event_id=event_id,
            event_name=event_name,
            event_time=event_time,
            trade_decision=trade_decision.value,
            composite_score=composite_score,
            confidence=confidence,
            entry_time=entry,
            entry_price=entry_price,
            direction=direction,
            tp_points=tp,
            sl_points=sl,
            holding_period_minutes=hold,
        )
        
        # Calculate TP/SL prices
        trade.calculate_tp_sl_prices()
        
        # Save to database
        self._save_trade(trade)
        
        logger.info(f"Created paper trade {trade_id}: {direction} {event_name} @ {entry_price}")
        
        return trade
    
    def _save_trade(self, trade: PaperTrade):
        """Save trade to database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO paper_trades (
                    trade_id, event_id, event_name, event_time, trade_decision,
                    composite_score, confidence, entry_time, entry_price, direction,
                    exit_time, exit_price, exit_reason, tp_points, sl_points,
                    tp_price, sl_price, holding_period_minutes, result,
                    pnl_points, pnl_percent, max_favorable_excursion, max_adverse_excursion,
                    mfe_time, mae_time, price_5m, price_15m, price_30m, price_60m,
                    notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.trade_id, trade.event_id, trade.event_name, trade.event_time,
                trade.trade_decision, trade.composite_score, trade.confidence,
                trade.entry_time, trade.entry_price, trade.direction,
                trade.exit_time, trade.exit_price, trade.exit_reason.value,
                trade.tp_points, trade.sl_points, trade.tp_price, trade.sl_price,
                trade.holding_period_minutes, trade.result.value, trade.pnl_points,
                trade.pnl_percent, trade.max_favorable_excursion, trade.max_adverse_excursion,
                trade.mfe_time, trade.mae_time, trade.price_5m, trade.price_15m,
                trade.price_30m, trade.price_60m, trade.notes, trade.created_at, trade.updated_at
            ))
            conn.commit()
    
    def update_trade_with_price(self, trade_id: str, price: float, timestamp: datetime):
        """
        Update trade with current price for MFE/MAE tracking.
        
        Args:
            trade_id: Trade ID
            price: Current XAUUSD price
            timestamp: Price timestamp
        """
        trade = self.get_trade(trade_id)
        if not trade or trade.result != TradeResult.OPEN:
            return
        
        # Update MFE/MAE
        trade.update_mfe(price, timestamp)
        trade.update_mae(price, timestamp)
        trade.updated_at = datetime.now()
        
        # Check if TP or SL hit
        if trade.direction == "LONG":
            if price >= trade.tp_price:
                trade.close_trade(price, timestamp, ExitReason.TAKE_PROFIT)
            elif price <= trade.sl_price:
                trade.close_trade(price, timestamp, ExitReason.STOP_LOSS)
        else:  # SHORT
            if price <= trade.tp_price:
                trade.close_trade(price, timestamp, ExitReason.TAKE_PROFIT)
            elif price >= trade.sl_price:
                trade.close_trade(price, timestamp, ExitReason.STOP_LOSS)
        
        # Save updated trade
        self._save_trade(trade)
    
    def close_trade_at_timeout(self, trade_id: str, price: float, timestamp: datetime):
        """Close a trade at holding period timeout."""
        trade = self.get_trade(trade_id)
        if not trade or trade.result != TradeResult.OPEN:
            return
        
        trade.close_trade(price, timestamp, ExitReason.TIMEOUT)
        self._save_trade(trade)
        
        logger.info(f"Closed paper trade {trade_id} at timeout: {trade.pnl_points:+.1f} points")
    
    def get_trade(self, trade_id: str) -> Optional[PaperTrade]:
        """Retrieve a trade by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM paper_trades WHERE trade_id = ?",
                (trade_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._row_to_trade(row)
    
    def get_open_trades(self) -> List[PaperTrade]:
        """Get all open trades."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM paper_trades WHERE result = ? ORDER BY entry_time DESC",
                (TradeResult.OPEN.value,)
            )
            return [self._row_to_trade(row) for row in cursor.fetchall()]
    
    def get_trades_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        result_filter: Optional[TradeResult] = None
    ) -> List[PaperTrade]:
        """Get trades within date range."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            if result_filter:
                cursor = conn.execute(
                    """SELECT * FROM paper_trades 
                       WHERE entry_time >= ? AND entry_time <= ? AND result = ?
                       ORDER BY entry_time DESC""",
                    (start_date, end_date, result_filter.value)
                )
            else:
                cursor = conn.execute(
                    """SELECT * FROM paper_trades 
                       WHERE entry_time >= ? AND entry_time <= ?
                       ORDER BY entry_time DESC""",
                    (start_date, end_date)
                )
            
            return [self._row_to_trade(row) for row in cursor.fetchall()]
    
    def _row_to_trade(self, row: sqlite3.Row) -> PaperTrade:
        """Convert database row to PaperTrade object."""
        return PaperTrade(
            trade_id=row["trade_id"],
            event_id=row["event_id"],
            event_name=row["event_name"],
            event_time=datetime.fromisoformat(row["event_time"]),
            trade_decision=row["trade_decision"],
            composite_score=row["composite_score"],
            confidence=row["confidence"],
            entry_time=datetime.fromisoformat(row["entry_time"]),
            entry_price=row["entry_price"],
            direction=row["direction"],
            exit_time=datetime.fromisoformat(row["exit_time"]) if row["exit_time"] else None,
            exit_price=row["exit_price"],
            exit_reason=ExitReason(row["exit_reason"]),
            tp_points=row["tp_points"],
            sl_points=row["sl_points"],
            tp_price=row["tp_price"],
            sl_price=row["sl_price"],
            holding_period_minutes=row["holding_period_minutes"],
            result=TradeResult(row["result"]),
            pnl_points=row["pnl_points"],
            pnl_percent=row["pnl_percent"],
            max_favorable_excursion=row["max_favorable_excursion"],
            max_adverse_excursion=row["max_adverse_excursion"],
            mfe_time=datetime.fromisoformat(row["mfe_time"]) if row["mfe_time"] else None,
            mae_time=datetime.fromisoformat(row["mae_time"]) if row["mae_time"] else None,
            price_5m=row["price_5m"],
            price_15m=row["price_15m"],
            price_30m=row["price_30m"],
            price_60m=row["price_60m"],
            notes=row["notes"] or "",
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
    
    def get_weekly_performance(self, week_start: Optional[datetime] = None) -> WeeklyPerformance:
        """
        Calculate weekly performance statistics.
        
        Args:
            week_start: Start of week (defaults to current week)
            
        Returns:
            WeeklyPerformance summary
        """
        if week_start is None:
            # Get current week start (Monday)
            today = datetime.now()
            week_start = today - timedelta(days=today.weekday())
        
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=7)
        
        # Get all closed trades for the week
        trades = self.get_trades_by_date_range(week_start, week_end)
        closed_trades = [t for t in trades if t.result != TradeResult.OPEN]
        
        if not closed_trades:
            return WeeklyPerformance(
                week_start=week_start,
                week_end=week_end,
                total_trades=0,
                wins=0,
                losses=0,
                breakevens=0,
                win_rate=0.0,
                total_pnl_points=0.0,
                total_pnl_percent=0.0,
                avg_pnl_points=0.0,
                avg_mfe=0.0,
                avg_mae=0.0,
                tp_hit_rate=0.0,
                sl_hit_rate=0.0,
                timeout_rate=0.0,
            )
        
        # Calculate statistics
        wins = sum(1 for t in closed_trades if t.result == TradeResult.WIN)
        losses = sum(1 for t in closed_trades if t.result == TradeResult.LOSS)
        breakevens = sum(1 for t in closed_trades if t.result == TradeResult.BREAKEVEN)
        
        total_pnl = sum(t.pnl_points for t in closed_trades)
        total_pnl_pct = sum(t.pnl_percent for t in closed_trades)
        
        tp_hits = sum(1 for t in closed_trades if t.exit_reason == ExitReason.TAKE_PROFIT)
        sl_hits = sum(1 for t in closed_trades if t.exit_reason == ExitReason.STOP_LOSS)
        timeouts = sum(1 for t in closed_trades if t.exit_reason == ExitReason.TIMEOUT)
        
        total = len(closed_trades)
        
        return WeeklyPerformance(
            week_start=week_start,
            week_end=week_end,
            total_trades=total,
            wins=wins,
            losses=losses,
            breakevens=breakevens,
            win_rate=(wins / total * 100) if total > 0 else 0,
            total_pnl_points=total_pnl,
            total_pnl_percent=total_pnl_pct,
            avg_pnl_points=total_pnl / total if total > 0 else 0,
            avg_mfe=sum(t.max_favorable_excursion for t in closed_trades) / total if total > 0 else 0,
            avg_mae=sum(t.max_adverse_excursion for t in closed_trades) / total if total > 0 else 0,
            tp_hit_rate=(tp_hits / total * 100) if total > 0 else 0,
            sl_hit_rate=(sl_hits / total * 100) if total > 0 else 0,
            timeout_rate=(timeouts / total * 100) if total > 0 else 0,
        )
    
    def export_weekly_report(self, week_start: Optional[datetime] = None, filepath: Optional[str] = None) -> str:
        """
        Export weekly performance to JSON file.
        
        Args:
            week_start: Week to export (defaults to current)
            filepath: Output file path (defaults to auto-generated)
            
        Returns:
            Path to exported file
        """
        performance = self.get_weekly_performance(week_start)
        
        if filepath is None:
            week_str = performance.week_start.strftime("%Y%m%d")
            filepath = f"reports/paper_trading_week_{week_str}.json"
        
        # Ensure directory exists
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # Export
        with open(filepath, 'w') as f:
            json.dump(performance.to_dict(), f, indent=2)
        
        logger.info(f"Exported weekly report to {filepath}")
        return filepath
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get overall paper trading statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM paper_trades")
            total = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM paper_trades WHERE result = 'win'")
            wins = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM paper_trades WHERE result = 'loss'")
            losses = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT COUNT(*) FROM paper_trades WHERE result = 'open'")
            open_trades = cursor.fetchone()[0]
            
            cursor = conn.execute("SELECT AVG(pnl_points) FROM paper_trades WHERE result != 'open'")
            avg_pnl = cursor.fetchone()[0] or 0
            
            return {
                "total_trades": total,
                "wins": wins,
                "losses": losses,
                "open_trades": open_trades,
                "win_rate": (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0,
                "avg_pnl_points": round(avg_pnl, 2),
            }


# Convenience function
def create_paper_trade(
    event_id: str,
    event_name: str,
    event_time: datetime,
    trade_decision: TradeDecision,
    composite_score: float,
    confidence: float,
    entry_price: float,
    **kwargs
) -> PaperTrade:
    """
    Convenience function to create a paper trade.
    
    Args:
        event_id: Unique event identifier
        event_name: Name of the event
        event_time: Time of event release
        trade_decision: BUY_GOLD, SELL_GOLD, etc.
        composite_score: Impact engine composite score
        confidence: Confidence level (0-100)
        entry_price: Entry price for XAUUSD
        **kwargs: Optional overrides for TP/SL/holding period
        
    Returns:
        PaperTrade object
    """
    logger = PaperTradingLogger()
    return logger.create_trade(
        event_id=event_id,
        event_name=event_name,
        event_time=event_time,
        trade_decision=trade_decision,
        composite_score=composite_score,
        confidence=confidence,
        entry_price=entry_price,
        **kwargs
    )
