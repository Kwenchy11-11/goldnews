"""
Evaluation Dashboard for Event Impact Scoring Engine

Generates evaluation reports showing whether the engine is "real" or "hallucinating".
Shows actual performance metrics with event-by-event breakdown.

Usage:
    python -m src.backtest.report --from 2024-01-01 --to 2025-12-31
    python -m src.backtest.report --sample  # Use sample/mock data
"""

import argparse
import csv
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# Add paths for imports - project root must be in path for config and root-level modules
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_script_dir))

if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Import from project root
from config import DATA_DIR

# All imports are optional - we'll work with sample data if imports fail
EventClassifier = None
SurpriseEngine = None
EventImpactEngine = None
GoldPriceFetcher = None
EventLogger = None

try:
    from event_classifier import EventClassifier
except ImportError:
    pass
    
try:
    from surprise_engine import SurpriseEngine
except ImportError:
    pass
    
try:
    from event_impact_engine import EventImpactEngine
except ImportError:
    pass
    
try:
    from gold_price_fetcher import GoldPriceFetcher
except ImportError:
    pass

try:
    from event_logger import EventLogger
except ImportError:
    try:
        from src.core.event_logger import EventLogger
    except ImportError:
        pass

logger = logging.getLogger(__name__)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'  # Clean output for CLI
)


@dataclass
class EvaluatedEvent:
    """Single event with evaluation results"""
    event_id: str
    event_date: datetime
    event_name: str
    category: str
    actual: Optional[float]
    forecast: Optional[float]
    previous: Optional[float]
    surprise_score: float
    composite_score: float
    gold_bias: str  # BULLISH, BEARISH, NEUTRAL
    xau_price_before: Optional[float]
    xau_price_15m: Optional[float]
    xau_price_60m: Optional[float]
    price_change_15m: Optional[float]
    price_change_60m: Optional[float]
    prediction_correct: Optional[bool]
    confidence: str  # HIGH, MEDIUM, LOW


@dataclass
class CategoryStats:
    """Statistics for a single category"""
    category: str
    total_events: int
    correct_predictions: int
    accuracy_pct: float
    avg_composite_score: float
    avg_price_move_15m: float
    avg_price_move_60m: float


@dataclass
class EvaluationSummary:
    """Overall evaluation summary"""
    total_events: int
    overall_accuracy: float
    high_confidence_accuracy: float
    medium_confidence_accuracy: float
    low_confidence_accuracy: float
    false_alarm_rate: float
    best_category: str
    worst_category: str
    category_stats: List[CategoryStats]


class EvaluationReport:
    """
    Generate evaluation dashboard for the Impact Engine
    
    Shows whether predictions are real or hallucinated by comparing
    composite scores against actual gold price movements.
    """
    
    def __init__(self):
        self.classifier = EventClassifier() if EventClassifier else None
        self.surprise_engine = SurpriseEngine() if SurpriseEngine else None
        self.impact_engine = EventImpactEngine() if EventImpactEngine else None
        self.price_fetcher = GoldPriceFetcher() if GoldPriceFetcher else None
        self.logger = EventLogger() if EventLogger else None
        self.events: List[EvaluatedEvent] = []
        
    def load_from_database(self, from_date: datetime, to_date: datetime) -> List[EvaluatedEvent]:
        """Load events from event logger database"""
        if self.logger is None:
            logger.warning("EventLogger not available, cannot load from database")
            return []
        
        logged_events = self.logger.get_events_by_date_range(from_date, to_date)
        
        evaluated = []
        for event in logged_events:
            # Get category from event name
            category = self._detect_category(event.event_name)
            
            # Calculate price changes
            price_before = event.gold_price_before
            price_15m = event.gold_price_15m_after
            price_60m = event.gold_price_60m_after
            
            change_15m = None
            change_60m = None
            
            if price_before and price_15m:
                change_15m = ((price_15m - price_before) / price_before) * 100
            if price_before and price_60m:
                change_60m = ((price_60m - price_before) / price_before) * 100
            
            # Determine if prediction was correct
            predicted_direction = event.predicted_direction
            correct = None
            
            if predicted_direction and change_15m is not None:
                if predicted_direction == 'bullish' and change_15m > 0:
                    correct = True
                elif predicted_direction == 'bearish' and change_15m < 0:
                    correct = True
                elif predicted_direction == 'neutral' and abs(change_15m) < 0.1:
                    correct = True
                else:
                    correct = False
            
            evaluated.append(EvaluatedEvent(
                event_id=event.event_id,
                event_date=event.event_date,
                event_name=event.event_name,
                category=category,
                actual=event.actual_value,
                forecast=event.forecast_value,
                previous=event.previous_value,
                surprise_score=event.surprise_score or 0,
                composite_score=event.composite_score or 0,
                gold_bias=event.predicted_direction or 'NEUTRAL',
                xau_price_before=price_before,
                xau_price_15m=price_15m,
                xau_price_60m=price_60m,
                price_change_15m=change_15m,
                price_change_60m=change_60m,
                prediction_correct=correct,
                confidence=event.confidence or 'LOW'
            ))
        
        self.events = evaluated
        return evaluated
    
    def load_sample_data(self) -> List[EvaluatedEvent]:
        """Load sample/mock data for demonstration"""
        sample_events = [
            {
                'name': 'US CPI y/y',
                'date': datetime(2024, 1, 10, 8, 30),
                'category': 'INFLATION',
                'actual': 3.4,
                'forecast': 3.2,
                'previous': 3.1,
                'surprise': 6.25,
                'composite': 5.8,
                'bias': 'BEARISH',
                'price_before': 2025.50,
                'price_15m': 2018.30,
                'price_60m': 2012.80,
                'correct': True,
                'confidence': 'HIGH'
            },
            {
                'name': 'Non-Farm Payrolls',
                'date': datetime(2024, 1, 5, 8, 30),
                'category': 'LABOR',
                'actual': 216,
                'forecast': 170,
                'previous': 173,
                'surprise': 27.1,
                'composite': 6.2,
                'bias': 'BEARISH',
                'price_before': 2045.20,
                'price_15m': 2038.50,
                'price_60m': 2042.10,
                'correct': True,
                'confidence': 'HIGH'
            },
            {
                'name': 'FOMC Statement',
                'date': datetime(2024, 1, 31, 14, 0),
                'category': 'FED_POLICY',
                'actual': None,
                'forecast': None,
                'previous': None,
                'surprise': 0,
                'composite': 4.5,
                'bias': 'NEUTRAL',
                'price_before': 2030.00,
                'price_15m': 2032.50,
                'price_60m': 2035.20,
                'correct': False,
                'confidence': 'MEDIUM'
            },
            {
                'name': 'PPI m/m',
                'date': datetime(2024, 1, 12, 8, 30),
                'category': 'INFLATION',
                'actual': 0.1,
                'forecast': 0.2,
                'previous': 0.0,
                'surprise': -5.0,
                'composite': 3.2,
                'bias': 'BULLISH',
                'price_before': 2028.40,
                'price_15m': 2031.20,
                'price_60m': 2033.80,
                'correct': True,
                'confidence': 'MEDIUM'
            },
            {
                'name': 'Retail Sales m/m',
                'date': datetime(2024, 1, 17, 8, 30),
                'category': 'RETAIL',
                'actual': 0.6,
                'forecast': 0.4,
                'previous': 0.3,
                'surprise': 5.0,
                'composite': 2.8,
                'bias': 'BEARISH',
                'price_before': 2015.60,
                'price_15m': 2012.40,
                'price_60m': 2018.90,
                'correct': False,
                'confidence': 'LOW'
            },
            {
                'name': 'GDP q/q',
                'date': datetime(2024, 1, 25, 8, 30),
                'category': 'GDP',
                'actual': 3.3,
                'forecast': 2.0,
                'previous': 4.9,
                'surprise': 65.0,
                'composite': 7.1,
                'bias': 'BEARISH',
                'price_before': 2018.00,
                'price_15m': 2009.50,
                'price_60m': 2005.30,
                'correct': True,
                'confidence': 'HIGH'
            },
            {
                'name': 'Fed Chair Speech',
                'date': datetime(2024, 2, 5, 13, 0),
                'category': 'FED_POLICY',
                'actual': None,
                'forecast': None,
                'previous': None,
                'surprise': 0,
                'composite': 2.1,
                'bias': 'NEUTRAL',
                'price_before': 2035.00,
                'price_15m': 2037.20,
                'price_60m': 2034.80,
                'correct': False,
                'confidence': 'LOW'
            },
            {
                'name': 'Unemployment Rate',
                'date': datetime(2024, 2, 2, 8, 30),
                'category': 'LABOR',
                'actual': 3.7,
                'forecast': 3.8,
                'previous': 3.7,
                'surprise': 2.6,
                'composite': 3.5,
                'bias': 'BULLISH',
                'price_before': 2050.00,
                'price_15m': 2053.40,
                'price_60m': 2056.20,
                'correct': True,
                'confidence': 'MEDIUM'
            },
            {
                'name': 'Core CPI m/m',
                'date': datetime(2024, 2, 13, 8, 30),
                'category': 'INFLATION',
                'actual': 0.4,
                'forecast': 0.3,
                'previous': 0.3,
                'surprise': 3.3,
                'composite': 4.8,
                'bias': 'BEARISH',
                'price_before': 2010.50,
                'price_15m': 2005.20,
                'price_60m': 2002.80,
                'correct': True,
                'confidence': 'HIGH'
            },
            {
                'name': 'ISM Manufacturing',
                'date': datetime(2024, 2, 1, 10, 0),
                'category': 'MANUFACTURING',
                'actual': 49.1,
                'forecast': 47.0,
                'previous': 47.4,
                'surprise': 10.9,
                'composite': 3.9,
                'bias': 'BEARISH',
                'price_before': 2040.00,
                'price_15m': 2035.50,
                'price_60m': 2038.20,
                'correct': True,
                'confidence': 'MEDIUM'
            },
        ]
        
        evaluated = []
        for i, sample in enumerate(sample_events):
            price_before = sample['price_before']
            price_15m = sample['price_15m']
            price_60m = sample['price_60m']
            
            change_15m = ((price_15m - price_before) / price_before) * 100
            change_60m = ((price_60m - price_before) / price_before) * 100
            
            evaluated.append(EvaluatedEvent(
                event_id=f"SAMPLE_{i:03d}",
                event_date=sample['date'],
                event_name=sample['name'],
                category=sample['category'],
                actual=sample['actual'],
                forecast=sample['forecast'],
                previous=sample['previous'],
                surprise_score=sample['surprise'],
                composite_score=sample['composite'],
                gold_bias=sample['bias'],
                xau_price_before=price_before,
                xau_price_15m=price_15m,
                xau_price_60m=price_60m,
                price_change_15m=change_15m,
                price_change_60m=change_60m,
                prediction_correct=sample['correct'],
                confidence=sample['confidence']
            ))
        
        self.events = evaluated
        return evaluated
    
    def _detect_category(self, event_name: str) -> str:
        """Detect event category from name"""
        name_upper = event_name.upper()
        
        if any(kw in name_upper for kw in ['CPI', 'PPI', 'INFLATION']):
            return 'INFLATION'
        elif any(kw in name_upper for kw in ['NFP', 'PAYROLL', 'EMPLOYMENT', 'UNEMPLOYMENT', 'JOBLESS', 'LABOR']):
            return 'LABOR'
        elif any(kw in name_upper for kw in ['FOMC', 'FED', 'POWELL', 'STATEMENT', 'MINUTES']):
            return 'FED_POLICY'
        elif any(kw in name_upper for kw in ['GDP']):
            return 'GDP'
        elif any(kw in name_upper for kw in ['RETAIL SALES']):
            return 'RETAIL'
        elif any(kw in name_upper for kw in ['HOUSING', 'HOME', 'BUILDING']):
            return 'HOUSING'
        elif any(kw in name_upper for kw in ['ISM', 'MANUFACTURING', 'PMI', 'PRODUCTION']):
            return 'MANUFACTURING'
        elif any(kw in name_upper for kw in ['TRADE', 'IMPORT', 'EXPORT']):
            return 'TRADE'
        else:
            return 'OTHER'
    
    def calculate_summary(self) -> EvaluationSummary:
        """Calculate overall evaluation summary"""
        if not self.events:
            return EvaluationSummary(0, 0, 0, 0, 0, 0, 'N/A', 'N/A', [])
        
        # Overall accuracy
        total = len(self.events)
        correct = sum(1 for e in self.events if e.prediction_correct)
        overall_accuracy = (correct / total * 100) if total > 0 else 0
        
        # Accuracy by confidence level
        high_conf = [e for e in self.events if e.confidence == 'HIGH']
        med_conf = [e for e in self.events if e.confidence == 'MEDIUM']
        low_conf = [e for e in self.events if e.confidence == 'LOW']
        
        high_acc = (sum(1 for e in high_conf if e.prediction_correct) / len(high_conf) * 100) if high_conf else 0
        med_acc = (sum(1 for e in med_conf if e.prediction_correct) / len(med_conf) * 100) if med_conf else 0
        low_acc = (sum(1 for e in low_conf if e.prediction_correct) / len(low_conf) * 100) if low_conf else 0
        
        # False alarm rate (high confidence but wrong)
        high_conf_wrong = sum(1 for e in high_conf if e.prediction_correct == False)
        false_alarm_rate = (high_conf_wrong / len(high_conf) * 100) if high_conf else 0
        
        # Category stats
        category_map: Dict[str, List[EvaluatedEvent]] = {}
        for event in self.events:
            cat = event.category
            if cat not in category_map:
                category_map[cat] = []
            category_map[cat].append(event)
        
        category_stats = []
        for cat, events in category_map.items():
            cat_total = len(events)
            cat_correct = sum(1 for e in events if e.prediction_correct)
            cat_accuracy = (cat_correct / cat_total * 100) if cat_total > 0 else 0
            avg_score = sum(e.composite_score for e in events) / cat_total
            
            # Average price moves
            moves_15m = [e.price_change_15m for e in events if e.price_change_15m is not None]
            moves_60m = [e.price_change_60m for e in events if e.price_change_60m is not None]
            avg_15m = sum(moves_15m) / len(moves_15m) if moves_15m else 0
            avg_60m = sum(moves_60m) / len(moves_60m) if moves_60m else 0
            
            category_stats.append(CategoryStats(
                category=cat,
                total_events=cat_total,
                correct_predictions=cat_correct,
                accuracy_pct=cat_accuracy,
                avg_composite_score=avg_score,
                avg_price_move_15m=avg_15m,
                avg_price_move_60m=avg_60m
            ))
        
        # Sort by accuracy to find best/worst
        sorted_stats = sorted(category_stats, key=lambda x: x.accuracy_pct, reverse=True)
        best_category = sorted_stats[0].category if sorted_stats else 'N/A'
        worst_category = sorted_stats[-1].category if sorted_stats else 'N/A'
        
        return EvaluationSummary(
            total_events=total,
            overall_accuracy=overall_accuracy,
            high_confidence_accuracy=high_acc,
            medium_confidence_accuracy=med_acc,
            low_confidence_accuracy=low_acc,
            false_alarm_rate=false_alarm_rate,
            best_category=best_category,
            worst_category=worst_category,
            category_stats=sorted_stats
        )
    
    def get_top_predictions(self, n: int = 10, best: bool = True) -> List[EvaluatedEvent]:
        """Get top N best or worst predictions"""
        if not self.events:
            return []
        
        # Sort by composite score magnitude and whether correct
        scored_events = []
        for event in self.events:
            if event.prediction_correct is None:
                continue
            
            score = abs(event.composite_score)
            # Best = high score + correct | Worst = high score + wrong
            if best and event.prediction_correct:
                scored_events.append((score, event))
            elif not best and not event.prediction_correct:
                scored_events.append((score, event))
        
        scored_events.sort(reverse=True, key=lambda x: x[0])
        return [e[1] for e in scored_events[:n]]
    
    def get_score_buckets(self) -> Dict[str, Dict[str, Any]]:
        """Group events by composite score buckets and calculate avg price moves"""
        buckets = {
            'Very High (≥6)': [],
            'High (4-6)': [],
            'Medium (2-4)': [],
            'Low (<2)': []
        }
        
        for event in self.events:
            score = abs(event.composite_score)
            if score >= 6:
                buckets['Very High (≥6)'].append(event)
            elif score >= 4:
                buckets['High (4-6)'].append(event)
            elif score >= 2:
                buckets['Medium (2-4)'].append(event)
            else:
                buckets['Low (<2)'].append(event)
        
        results = {}
        for bucket_name, events in buckets.items():
            if not events:
                continue
            
            moves_15m = [e.price_change_15m for e in events if e.price_change_15m is not None]
            moves_60m = [e.price_change_60m for e in events if e.price_change_60m is not None]
            correct = sum(1 for e in events if e.prediction_correct)
            
            results[bucket_name] = {
                'count': len(events),
                'avg_move_15m': sum(moves_15m) / len(moves_15m) if moves_15m else 0,
                'avg_move_60m': sum(moves_60m) / len(moves_60m) if moves_60m else 0,
                'accuracy': (correct / len(events) * 100) if events else 0,
                'total': len(events)
            }
        
        return results
    
    def print_dashboard(self):
        """Print evaluation dashboard to terminal"""
        summary = self.calculate_summary()
        
        # Header
        print("\n" + "="*80)
        print("           EVENT IMPACT ENGINE - EVALUATION DASHBOARD")
        print("="*80)
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Total Events Evaluated: {summary.total_events}")
        print("="*80)
        
        # Overall Summary
        print("\n📊 OVERALL PERFORMANCE")
        print("─"*80)
        print(f"  Directional Accuracy:     {summary.overall_accuracy:.1f}%")
        print(f"  High-Confidence Accuracy: {summary.high_confidence_accuracy:.1f}%")
        print(f"  Medium-Confidence Acc:    {summary.medium_confidence_accuracy:.1f}%")
        print(f"  Low-Confidence Acc:       {summary.low_confidence_accuracy:.1f}%")
        print(f"  High-Impact False Alarm:  {summary.false_alarm_rate:.1f}%")
        
        # Category Breakdown
        print("\n📈 ACCURACY BY CATEGORY")
        print("─"*80)
        print(f"{'Category':<20} {'Events':<8} {'Accuracy':<10} {'Avg Score':<12} {'Avg Move 15m':<12}")
        print("─"*80)
        
        for stat in summary.category_stats:
            move_str = f"{stat.avg_price_move_15m:+.2f}%"
            print(f"{stat.category:<20} {stat.total_events:<8} {stat.accuracy_pct:>6.1f}%   "
                  f"{stat.avg_composite_score:>6.2f}      {move_str:>10}")
        
        print("\n" + "─"*80)
        print(f"  ✅ Best Category:  {summary.best_category}")
        print(f"  ❌ Worst Category: {summary.worst_category}")
        
        # Score Buckets
        print("\n🎯 GOLD MOVEMENT BY COMPOSITE SCORE BUCKET")
        print("─"*80)
        print(f"{'Score Bucket':<20} {'Count':<8} {'Accuracy':<10} {'Avg Move 15m':<14} {'Avg Move 60m':<14}")
        print("─"*80)
        
        buckets = self.get_score_buckets()
        for bucket_name, data in buckets.items():
            move_15m = f"{data['avg_move_15m']:+.3f}%"
            move_60m = f"{data['avg_move_60m']:+.3f}%"
            print(f"{bucket_name:<20} {data['count']:<8} {data['accuracy']:>6.1f}%   "
                  f"{move_15m:>12} {move_60m:>12}")
        
        # Top 10 Best
        print("\n🏆 TOP 10 BEST PREDICTIONS")
        print("─"*80)
        print(f"{'Event':<25} {'Category':<15} {'Score':<8} {'15m Move':<12} {'Correct'}")
        print("─"*80)
        
        best = self.get_top_predictions(10, best=True)
        for event in best:
            move_str = f"{event.price_change_15m:+.2f}%" if event.price_change_15m else "N/A"
            print(f"{event.event_name[:24]:<25} {event.category:<15} "
                  f"{event.composite_score:>6.2f}  {move_str:>10}  {'✓'}")
        
        # Top 10 Worst
        print("\n💥 TOP 10 WORST PREDICTIONS (Hallucinations?)")
        print("─"*80)
        print(f"{'Event':<25} {'Category':<15} {'Score':<8} {'15m Move':<12} {'Result'}")
        print("─"*80)
        
        worst = self.get_top_predictions(10, best=False)
        for event in worst:
            move_str = f"{event.price_change_15m:+.2f}%" if event.price_change_15m else "N/A"
            print(f"{event.event_name[:24]:<25} {event.category:<15} "
                  f"{event.composite_score:>6.2f}  {move_str:>10}  {'✗ WRONG'}")
        
        # Detailed Event Table
        print("\n📋 ALL EVENTS DETAIL")
        print("="*80)
        print(f"{'Event':<25} {'Category':<12} {'Actual':<8} {'Fcst':<8} {'Surprise':<10} "
              f"{'Score':<8} {'Bias':<10} {'+15m':<10} {'Correct'}")
        print("="*80)
        
        for event in sorted(self.events, key=lambda x: x.event_date):
            actual_str = f"{event.actual:.2f}" if event.actual else "N/A"
            fcst_str = f"{event.forecast:.2f}" if event.forecast else "N/A"
            surprise_str = f"{event.surprise_score:+.1f}" if event.surprise_score else "0"
            move_str = f"{event.price_change_15m:+.2f}%" if event.price_change_15m else "N/A"
            correct_str = "✓" if event.prediction_correct else "✗" if event.prediction_correct == False else "?"
            
            print(f"{event.event_name[:24]:<25} {event.category:<12} "
                  f"{actual_str:<8} {fcst_str:<8} {surprise_str:<10} "
                  f"{event.composite_score:>6.2f}  {event.gold_bias:<10} "
                  f"{move_str:<10} {correct_str}")
        
        print("="*80)
        
        # Verdict
        print("\n🔍 VERDICT: Is the Engine REAL or HALLUCINATING?")
        print("="*80)
        
        if summary.overall_accuracy >= 60:
            verdict = "✅ REAL - Shows genuine predictive ability"
        elif summary.overall_accuracy >= 45:
            verdict = "⚠️  MIXED - Some signal, needs improvement"
        else:
            verdict = "❌ HALLUCINATING - Random guessing level"
        
        print(f"  {verdict}")
        print(f"  • High-confidence predictions are {'reliable' if summary.high_confidence_accuracy >= 65 else 'unreliable'}")
        print(f"  • Engine performs best on: {summary.best_category}")
        print(f"  • Engine struggles with: {summary.worst_category}")
        print(f"  • False alarm rate: {summary.false_alarm_rate:.1f}% (lower is better)")
        print("="*80 + "\n")
    
    def export_summary_csv(self, filepath: str):
        """Export summary statistics to CSV"""
        summary = self.calculate_summary()
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Overall stats
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Total Events', summary.total_events])
            writer.writerow(['Overall Accuracy', f"{summary.overall_accuracy:.2f}"])
            writer.writerow(['High-Confidence Accuracy', f"{summary.high_confidence_accuracy:.2f}"])
            writer.writerow(['Medium-Confidence Accuracy', f"{summary.medium_confidence_accuracy:.2f}"])
            writer.writerow(['Low-Confidence Accuracy', f"{summary.low_confidence_accuracy:.2f}"])
            writer.writerow(['False Alarm Rate', f"{summary.false_alarm_rate:.2f}"])
            writer.writerow(['Best Category', summary.best_category])
            writer.writerow(['Worst Category', summary.worst_category])
            writer.writerow([])
            
            # Category breakdown
            writer.writerow(['Category', 'Events', 'Accuracy', 'Avg Score', 'Avg Move 15m', 'Avg Move 60m'])
            for stat in summary.category_stats:
                writer.writerow([
                    stat.category,
                    stat.total_events,
                    f"{stat.accuracy_pct:.2f}",
                    f"{stat.avg_composite_score:.2f}",
                    f"{stat.avg_price_move_15m:.4f}",
                    f"{stat.avg_price_move_60m:.4f}"
                ])
            writer.writerow([])
            
            # Score buckets
            writer.writerow(['Score Bucket', 'Count', 'Accuracy', 'Avg Move 15m', 'Avg Move 60m'])
            buckets = self.get_score_buckets()
            for bucket_name, data in buckets.items():
                writer.writerow([
                    bucket_name,
                    data['count'],
                    f"{data['accuracy']:.2f}",
                    f"{data['avg_move_15m']:.4f}",
                    f"{data['avg_move_60m']:.4f}"
                ])
        
        logger.info(f"Exported summary to {filepath}")
    
    def export_details_csv(self, filepath: str):
        """Export detailed event data to CSV"""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'Event ID', 'Date', 'Event Name', 'Category',
                'Actual', 'Forecast', 'Previous', 'Surprise Score',
                'Composite Score', 'Gold Bias', 'Confidence',
                'XAU Before', 'XAU +15m', 'XAU +60m',
                'Price Change 15m', 'Price Change 60m',
                'Prediction Correct'
            ])
            
            # Data
            for event in self.events:
                writer.writerow([
                    event.event_id,
                    event.event_date.strftime('%Y-%m-%d %H:%M:%S'),
                    event.event_name,
                    event.category,
                    event.actual if event.actual else '',
                    event.forecast if event.forecast else '',
                    event.previous if event.previous else '',
                    f"{event.surprise_score:.2f}",
                    f"{event.composite_score:.2f}",
                    event.gold_bias,
                    event.confidence,
                    event.xau_price_before if event.xau_price_before else '',
                    event.xau_price_15m if event.xau_price_15m else '',
                    event.xau_price_60m if event.xau_price_60m else '',
                    f"{event.price_change_15m:.4f}" if event.price_change_15m else '',
                    f"{event.price_change_60m:.4f}" if event.price_change_60m else '',
                    'YES' if event.prediction_correct else 'NO' if event.prediction_correct == False else 'N/A'
                ])
        
        logger.info(f"Exported details to {filepath}")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='Evaluation Dashboard for Event Impact Scoring Engine',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.backtest.report --from 2024-01-01 --to 2025-12-31
  python -m src.backtest.report --sample
  python -m src.backtest.report --sample --export-dir ./my_reports
        """
    )
    
    parser.add_argument(
        '--from', dest='from_date',
        help='Start date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--to', dest='to_date',
        help='End date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--sample', action='store_true',
        help='Use sample/mock data instead of database'
    )
    parser.add_argument(
        '--export-dir', default='reports',
        help='Directory for CSV exports (default: reports)'
    )
    parser.add_argument(
        '--summary-only', action='store_true',
        help='Only print summary, skip detailed table'
    )
    
    args = parser.parse_args()
    
    # Initialize report
    report = EvaluationReport()
    
    # Load data
    if args.sample:
        print("Loading sample data...")
        report.load_sample_data()
    elif args.from_date and args.to_date:
        try:
            from_date = datetime.strptime(args.from_date, '%Y-%m-%d')
            to_date = datetime.strptime(args.to_date, '%Y-%m-%d') + timedelta(days=1)
            print(f"Loading events from {args.from_date} to {args.to_date}...")
            report.load_from_database(from_date, to_date)
        except ValueError as e:
            print(f"Error parsing dates: {e}")
            sys.exit(1)
    else:
        print("Error: Must specify either --sample or --from and --to dates")
        parser.print_help()
        sys.exit(1)
    
    if not report.events:
        print("No events found for the specified period.")
        sys.exit(0)
    
    # Print dashboard
    report.print_dashboard()
    
    # Export CSV files
    export_dir = Path(args.export_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    
    summary_path = export_dir / 'backtest_summary.csv'
    details_path = export_dir / 'backtest_details.csv'
    
    report.export_summary_csv(str(summary_path))
    report.export_details_csv(str(details_path))
    
    print(f"\n📁 CSV Exports:")
    print(f"  Summary: {summary_path.absolute()}")
    print(f"  Details: {details_path.absolute()}")


if __name__ == '__main__':
    main()
