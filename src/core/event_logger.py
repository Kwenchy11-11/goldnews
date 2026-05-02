"""Event Logger - Layer 5 of Event Impact Scoring Engine.

Provides historical logging of all economic events, their classifications,
surprise scores, and outcomes for future analysis and backtesting.
"""

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from event_classifier import EventCategory, ImpactScore
from surprise_engine import EconomicDataPoint, SurpriseResult


@dataclass
class LoggedEvent:
    """A logged economic event with all scoring data."""

    event_id: str
    timestamp: datetime
    event_name: str
    category: str
    source: str  # news source, RSS feed, etc.
    
    # Raw data
    raw_text: str
    actual_value: Optional[float]
    forecast_value: Optional[float]
    previous_value: Optional[float]
    unit: str
    
    # Classification
    classification_category: str
    base_impact_score: int
    gold_correlation: str
    typical_volatility: str
    key_drivers: str
    
    # Surprise calculation
    surprise_score: float
    deviation_pct: float
    direction: str
    significance: str
    gold_impact: str
    
    # Consensus (optional)
    market_consensus_available: bool
    consensus_aligned: Optional[bool]
    divergence_score: Optional[float]
    trading_signal: Optional[str]
    
    # Post-event tracking (filled in later)
    gold_price_before: Optional[float]
    gold_price_after: Optional[float]
    price_change_pct: Optional[float]
    prediction_accuracy: Optional[str]  # "correct", "incorrect", "partial"
    
    # Metadata
    processed_at: datetime
    version: str = "1.0"


class EventLogger:
    """Logs economic events to SQLite for historical analysis and backtesting."""
    
    def __init__(self, db_path: Union[str, Path] = "data/events.db"):
        """Initialize the EventLogger.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source TEXT,
                    raw_text TEXT,
                    actual_value REAL,
                    forecast_value REAL,
                    previous_value REAL,
                    unit TEXT,
                    classification_category TEXT,
                    base_impact_score INTEGER,
                    gold_correlation TEXT,
                    typical_volatility TEXT,
                    key_drivers TEXT,
                    surprise_score REAL,
                    deviation_pct REAL,
                    direction TEXT,
                    significance TEXT,
                    gold_impact TEXT,
                    market_consensus_available INTEGER,
                    consensus_aligned INTEGER,
                    divergence_score REAL,
                    trading_signal TEXT,
                    gold_price_before REAL,
                    gold_price_after REAL,
                    price_change_pct REAL,
                    prediction_accuracy TEXT,
                    processed_at TEXT NOT NULL,
                    version TEXT
                )
            """)
            
            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON events(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_category 
                ON events(category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_gold_impact 
                ON events(gold_impact)
            """)
            conn.commit()
    
    def log_event(
        self,
        event_id: str,
        timestamp: datetime,
        event_name: str,
        category: EventCategory,
        source: str,
        raw_text: str,
        impact_score: ImpactScore,
        surprise_result: SurpriseResult,
        data_point: EconomicDataPoint,
        consensus_aligned: Optional[bool] = None,
        divergence_score: Optional[float] = None,
        trading_signal: Optional[str] = None,
    ) -> LoggedEvent:
        """Log a processed event to the database.
        
        Args:
            event_id: Unique identifier for this event
            timestamp: When the event occurred/released
            event_name: Name of the economic indicator
            category: Event category classification
            source: Source of the event data
            raw_text: Raw text content
            impact_score: Classification impact score
            surprise_result: Surprise calculation result
            data_point: Economic data point with values
            consensus_aligned: Whether market consensus aligned with forecast
            divergence_score: Divergence between consensus and forecast
            trading_signal: Generated trading signal
            
        Returns:
            LoggedEvent object
        """
        logged = LoggedEvent(
            event_id=event_id,
            timestamp=timestamp,
            event_name=event_name,
            category=category.value,
            source=source,
            raw_text=raw_text[:1000] if raw_text else "",  # Limit text length
            actual_value=data_point.actual,
            forecast_value=data_point.forecast,
            previous_value=data_point.previous,
            unit=data_point.unit,
            classification_category=impact_score.category.value,
            base_impact_score=impact_score.base_impact_score,
            gold_correlation=impact_score.gold_correlation,
            typical_volatility=impact_score.typical_volatility,
            key_drivers=json.dumps(impact_score.key_drivers),
            surprise_score=surprise_result.surprise_score,
            deviation_pct=surprise_result.deviation_pct,
            direction=surprise_result.direction,
            significance=surprise_result.significance,
            gold_impact=surprise_result.gold_impact,
            market_consensus_available=consensus_aligned is not None,
            consensus_aligned=consensus_aligned,
            divergence_score=divergence_score,
            trading_signal=trading_signal,
            gold_price_before=None,
            gold_price_after=None,
            price_change_pct=None,
            prediction_accuracy=None,
            processed_at=datetime.utcnow(),
        )
        
        self._insert_event(logged)
        return logged
    
    def _insert_event(self, event: LoggedEvent):
        """Insert a logged event into the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO events VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
            """, (
                event.event_id,
                event.timestamp.isoformat(),
                event.event_name,
                event.category,
                event.source,
                event.raw_text,
                event.actual_value,
                event.forecast_value,
                event.previous_value,
                event.unit,
                event.classification_category,
                event.base_impact_score,
                event.gold_correlation,
                event.typical_volatility,
                event.key_drivers,
                event.surprise_score,
                event.deviation_pct,
                event.direction,
                event.significance,
                event.gold_impact,
                int(event.market_consensus_available),
                int(event.consensus_aligned) if event.consensus_aligned is not None else None,
                event.divergence_score,
                event.trading_signal,
                event.gold_price_before,
                event.gold_price_after,
                event.price_change_pct,
                event.prediction_accuracy,
                event.processed_at.isoformat(),
                event.version,
            ))
            conn.commit()
    
    def update_outcome(
        self,
        event_id: str,
        gold_price_before: Optional[float] = None,
        gold_price_after: Optional[float] = None,
        price_change_pct: Optional[float] = None,
        prediction_accuracy: Optional[str] = None,
    ):
        """Update an event with post-event outcome data.
        
        Args:
            event_id: ID of the event to update
            gold_price_before: Gold price before event
            gold_price_after: Gold price after event
            price_change_pct: Percentage change in gold price
            prediction_accuracy: Whether prediction was correct
        """
        updates = []
        params = []
        
        if gold_price_before is not None:
            updates.append("gold_price_before = ?")
            params.append(gold_price_before)
        if gold_price_after is not None:
            updates.append("gold_price_after = ?")
            params.append(gold_price_after)
        if price_change_pct is not None:
            updates.append("price_change_pct = ?")
            params.append(price_change_pct)
        if prediction_accuracy is not None:
            updates.append("prediction_accuracy = ?")
            params.append(prediction_accuracy)
        
        if not updates:
            return
        
        params.append(event_id)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE events SET {', '.join(updates)} WHERE event_id = ?",
                params
            )
            conn.commit()
    
    def get_event(self, event_id: str) -> Optional[LoggedEvent]:
        """Retrieve a specific event by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM events WHERE event_id = ?",
                (event_id,)
            ).fetchone()
            
            if row:
                return self._row_to_logged_event(row)
            return None
    
    def get_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        category: Optional[str] = None,
        gold_impact: Optional[str] = None,
        significance: Optional[str] = None,
        limit: int = 100,
    ) -> List[LoggedEvent]:
        """Query events with filters.
        
        Args:
            start_date: Filter events after this date
            end_date: Filter events before this date
            category: Filter by event category
            gold_impact: Filter by gold impact (bullish/bearish/neutral)
            significance: Filter by significance level
            limit: Maximum number of results
            
        Returns:
            List of matching LoggedEvent objects
        """
        query = "SELECT * FROM events WHERE 1=1"
        params = []
        
        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date.isoformat())
        if end_date:
            query += " AND timestamp <= ?"
            params.append(end_date.isoformat())
        if category:
            query += " AND category = ?"
            params.append(category)
        if gold_impact:
            query += " AND gold_impact = ?"
            params.append(gold_impact)
        if significance:
            query += " AND significance = ?"
            params.append(significance)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_logged_event(row) for row in rows]
    
    def _row_to_logged_event(self, row: sqlite3.Row) -> LoggedEvent:
        """Convert a database row to LoggedEvent."""
        return LoggedEvent(
            event_id=row["event_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            event_name=row["event_name"],
            category=row["category"],
            source=row["source"],
            raw_text=row["raw_text"],
            actual_value=row["actual_value"],
            forecast_value=row["forecast_value"],
            previous_value=row["previous_value"],
            unit=row["unit"],
            classification_category=row["classification_category"],
            base_impact_score=row["base_impact_score"],
            gold_correlation=row["gold_correlation"],
            typical_volatility=row["typical_volatility"],
            key_drivers=row["key_drivers"],
            surprise_score=row["surprise_score"],
            deviation_pct=row["deviation_pct"],
            direction=row["direction"],
            significance=row["significance"],
            gold_impact=row["gold_impact"],
            market_consensus_available=bool(row["market_consensus_available"]),
            consensus_aligned=bool(row["consensus_aligned"]) if row["consensus_aligned"] is not None else None,
            divergence_score=row["divergence_score"],
            trading_signal=row["trading_signal"],
            gold_price_before=row["gold_price_before"],
            gold_price_after=row["gold_price_after"],
            price_change_pct=row["price_change_pct"],
            prediction_accuracy=row["prediction_accuracy"],
            processed_at=datetime.fromisoformat(row["processed_at"]),
            version=row["version"],
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get summary statistics of logged events.
        
        Returns:
            Dictionary with statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            # Total events
            total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            
            # By category
            categories = conn.execute(
                "SELECT category, COUNT(*) FROM events GROUP BY category"
            ).fetchall()
            
            # By gold impact
            impacts = conn.execute(
                "SELECT gold_impact, COUNT(*) FROM events GROUP BY gold_impact"
            ).fetchall()
            
            # By significance
            sigs = conn.execute(
                "SELECT significance, COUNT(*) FROM events GROUP BY significance"
            ).fetchall()
            
            # Prediction accuracy (only for events with outcomes)
            accuracy = conn.execute(
                """SELECT prediction_accuracy, COUNT(*) 
                   FROM events 
                   WHERE prediction_accuracy IS NOT NULL 
                   GROUP BY prediction_accuracy"""
            ).fetchall()
            
            # Average surprise score by category
            avg_surprise = conn.execute(
                """SELECT category, AVG(ABS(surprise_score)) 
                   FROM events 
                   GROUP BY category"""
            ).fetchall()
            
        return {
            "total_events": total,
            "by_category": dict(categories),
            "by_gold_impact": dict(impacts),
            "by_significance": dict(sigs),
            "prediction_accuracy": dict(accuracy),
            "avg_surprise_by_category": dict(avg_surprise),
        }
    
    def export_to_json(self, filepath: Union[str, Path], 
                      start_date: Optional[datetime] = None,
                      end_date: Optional[datetime] = None):
        """Export events to JSON file.
        
        Args:
            filepath: Path to output JSON file
            start_date: Optional start date filter
            end_date: Optional end date filter
        """
        events = self.get_events(start_date=start_date, end_date=end_date, limit=10000)
        
        data = []
        for event in events:
            event_dict = asdict(event)
            # Convert datetime to ISO format
            event_dict["timestamp"] = event.timestamp.isoformat()
            event_dict["processed_at"] = event.processed_at.isoformat()
            data.append(event_dict)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def delete_old_events(self, days: int = 365):
        """Delete events older than specified days.
        
        Args:
            days: Delete events older than this many days
        """
        cutoff = datetime.utcnow() - __import__('datetime').timedelta(days=days)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM events WHERE timestamp < ?",
                (cutoff.isoformat(),)
            )
            conn.commit()
