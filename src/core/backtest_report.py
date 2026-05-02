"""
Backtest Report Generator

Generates detailed reports from backtest results:
- Summary statistics (accuracy, P&L, win rate)
- Breakdown by event type (CPI, NFP, FOMC, etc.)
- Performance by timeframe
- Visual charts (ASCII/text-based)
- Export to multiple formats (JSON, CSV, TXT)
"""

import csv
import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from config import DATA_DIR
from core.backtest_engine import BacktestResult, BacktestEngine

logger = logging.getLogger(__name__)


@dataclass
class ReportSection:
    """A section of the report"""
    title: str
    content: str
    data: Optional[Dict[str, Any]] = None


class BacktestReportGenerator:
    """
    Generate comprehensive backtest reports
    
    Creates formatted reports with statistics, charts, and insights
    from backtest results.
    """
    
    def __init__(self, backtest_engine: Optional[BacktestEngine] = None):
        self.engine = backtest_engine or BacktestEngine()
        self.sections: List[ReportSection] = []
    
    def generate_report(
        self,
        timeframes: List[str] = None,
        include_charts: bool = True,
        include_details: bool = True
    ) -> str:
        """
        Generate full text report
        
        Args:
            timeframes: List of timeframes to include ['5m', '15m', '30m', '60m']
            include_charts: Whether to include ASCII charts
            include_details: Whether to include individual trade details
        
        Returns:
            Formatted report string
        """
        if timeframes is None:
            timeframes = ['15m', '30m', '60m']
        
        self.sections = []
        
        # Header
        self._add_header()
        
        # Overall summary
        self._add_overall_summary()
        
        # Stats by timeframe
        for tf in timeframes:
            self._add_timeframe_section(tf, include_charts)
        
        # Stats by event type
        self._add_event_type_breakdown()
        
        # Individual results (if requested)
        if include_details:
            self._add_trade_details()
        
        # Conclusions
        self._add_conclusions()
        
        # Combine all sections
        return '\n\n'.join(section.content for section in self.sections)
    
    def _add_header(self):
        """Add report header"""
        header = f"""
{'='*70}
              G EVENT IMPACT ENGINE - BACKTEST REPORT
{'='*70}

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Total Events Analyzed: {len(self.engine.results)}

"""
        self.sections.append(ReportSection("Header", header))
    
    def _add_overall_summary(self):
        """Add overall summary section"""
        if not self.engine.results:
            content = "No backtest results available.\n"
            self.sections.append(ReportSection("Summary", content))
            return
        
        # Get stats for primary timeframe (15m)
        stats = self.engine.get_statistics('15m')
        
        content = f"""
{'─'*70}
                           OVERALL SUMMARY
{'─'*70}

Key Performance Metrics (15-minute timeframe):

  Accuracy Rate:           {stats.get('accuracy', 0):.1f}%
  Total P&L:               ${stats.get('total_pnl', 0):,.2f}
  Average P&L per Trade:   ${stats.get('avg_pnl', 0):,.2f}
  Win Rate:                {stats.get('win_rate', 0):.1f}%
  Profit Factor:           {stats.get('profit_factor', 0):.2f}

Trade Distribution:
  Total Trades:            {stats.get('total_trades', 0)}
  Winning Trades:          {len([r for r in self.engine.results if r.was_correct('15m')])}
  Losing Trades:           {stats.get('total_trades', 0) - len([r for r in self.engine.results if r.was_correct('15m')])}
  Average Win:             ${stats.get('avg_win', 0):,.2f}
  Average Loss:            ${stats.get('avg_loss', 0):,.2f}

"""
        self.sections.append(ReportSection("Summary", content, stats))
    
    def _add_timeframe_section(self, timeframe: str, include_chart: bool = True):
        """Add section for a specific timeframe"""
        stats = self.engine.get_statistics(timeframe)
        
        if not stats or stats.get('total_events', 0) == 0:
            return
        
        content = f"""
{'─'*70}
                    TIMEFRAME: {timeframe.replace('m', ' MINUTES')}
{'─'*70}

Performance Metrics:
  Accuracy:                {stats.get('accuracy', 0):.1f}%
  Total P&L:               ${stats.get('total_pnl', 0):,.2f}
  Average P&L:             ${stats.get('avg_pnl', 0):,.2f}
  Win Rate:                {stats.get('win_rate', 0):.1f}%

"""
        
        if include_chart:
            chart = self._create_accuracy_chart(timeframe)
            content += f"\nAccuracy Distribution:\n{chart}\n"
        
        self.sections.append(ReportSection(f"Timeframe {timeframe}", content, stats))
    
    def _add_event_type_breakdown(self):
        """Add breakdown by event type/category"""
        if not self.engine.results:
            return
        
        # Group results by event title keywords
        categories = self._categorize_events()
        
        content = f"""
{'─'*70}
                      PERFORMANCE BY EVENT TYPE
{'─'*70}

"""
        
        # Create table
        content += "Category          | Trades | Accuracy | Total P&L | Avg P&L\n"
        content += "─" * 70 + "\n"
        
        for cat_name, results in sorted(categories.items()):
            if not results:
                continue
            
            # Temporarily set results and get stats
            original_results = self.engine.results
            self.engine.results = results
            stats = self.engine.get_statistics('15m')
            self.engine.results = original_results
            
            if stats.get('total_trades', 0) > 0:
                content += f"{cat_name:<16} | {stats['total_trades']:>6} | {stats['accuracy']:>7.1f}% | ${stats['total_pnl']:>8.2f} | ${stats['avg_pnl']:>7.2f}\n"
        
        content += "\n"
        self.sections.append(ReportSection("Event Types", content))
    
    def _add_trade_details(self):
        """Add individual trade details"""
        if not self.engine.results:
            return
        
        content = f"""
{'─'*70}
                         INDIVIDUAL TRADE DETAILS
{'─'*70}

#   Date       | Event              | Pred | Result | P&L    | Score
{'─'*70}
"""
        
        for i, result in enumerate(self.engine.results[:50], 1):  # Limit to 50
            date_str = result.event_date.strftime('%m/%d')
            event_name = result.event_title[:18]
            pred = result.predicted_direction.value[:4].upper()
            
            # Determine result symbol
            if result.was_correct('15m'):
                result_str = "✓ WIN"
            elif result.was_correct('15m') is False:
                result_str = "✗ LOSS"
            else:
                result_str = "— N/A"
            
            pnl = result.get_pnl('15m')
            pnl_str = f"${pnl:>6.2f}" if pnl is not None else "   N/A"
            
            content += f"{i:>3} {date_str} | {event_name:<18} | {pred:>4} | {result_str:>6} | {pnl_str} | {result.impact_score:>5.1f}\n"
        
        if len(self.engine.results) > 50:
            content += f"\n... and {len(self.engine.results) - 50} more trades\n"
        
        content += "\n"
        self.sections.append(ReportSection("Trade Details", content))
    
    def _add_conclusions(self):
        """Add conclusions and recommendations"""
        stats_15m = self.engine.get_statistics('15m')
        stats_60m = self.engine.get_statistics('60m')
        
        content = f"""
{'='*70}
                           CONCLUSIONS
{'='*70}

Based on the backtest results:

1. OVERALL PERFORMANCE
   • The engine achieved {stats_15m.get('accuracy', 0):.1f}% accuracy at 15-minute timeframe
   • Profit factor of {stats_15m.get('profit_factor', 0):.2f} indicates {'profitable' if stats_15m.get('profit_factor', 0) > 1 else 'unprofitable'} trading
   • {'Higher' if stats_60m.get('accuracy', 0) > stats_15m.get('accuracy', 0) else 'Lower'} accuracy at 60-minute ({stats_60m.get('accuracy', 0):.1f}%) vs 15-minute

2. RECOMMENDATIONS
   • {'Consider' if stats_15m.get('accuracy', 0) > 55 else 'Improve prediction thresholds before'} live trading
   • Focus on events with |impact score| >= 3 for better signal quality
   • {'Longer' if stats_60m.get('accuracy', 0) > stats_15m.get('accuracy', 0) else 'Shorter'} timeframes show better prediction accuracy

3. LIMITATIONS
   • Backtest uses historical data which may not reflect future performance
   • Slippage and spread not accounted for in simulated trades
   • Market conditions during backtest period may differ from current regime

{'='*70}
"""
        self.sections.append(ReportSection("Conclusions", content))
    
    def _categorize_events(self) -> Dict[str, List[BacktestResult]]:
        """Group results by event category"""
        categories = {
            'CPI/Inflation': [],
            'NFP/Labor': [],
            'FOMC/Fed': [],
            'GDP/Growth': [],
            'Retail Sales': [],
            'Other': []
        }
        
        for result in self.engine.results:
            title_upper = result.event_title.upper()
            
            if any(kw in title_upper for kw in ['CPI', 'PPI', 'INFLATION']):
                categories['CPI/Inflation'].append(result)
            elif any(kw in title_upper for kw in ['NFP', 'PAYROLL', 'EMPLOYMENT', 'UNEMPLOYMENT', 'JOBLESS']):
                categories['NFP/Labor'].append(result)
            elif any(kw in title_upper for kw in ['FOMC', 'FED', 'INTEREST RATE']):
                categories['FOMC/Fed'].append(result)
            elif any(kw in title_upper for kw in ['GDP']):
                categories['GDP/Growth'].append(result)
            elif any(kw in title_upper for kw in ['RETAIL SALES']):
                categories['Retail Sales'].append(result)
            else:
                categories['Other'].append(result)
        
        return categories
    
    def _create_accuracy_chart(self, timeframe: str, width: int = 50) -> str:
        """Create ASCII bar chart for accuracy distribution"""
        if not self.engine.results:
            return "No data available"
        
        # Group by prediction confidence buckets
        buckets = {
            'High (|score| >= 6)': [],
            'Med (|score| 3-6)': [],
            'Low (|score| < 3)': []
        }
        
        for result in self.engine.results:
            abs_score = abs(result.impact_score)
            if abs_score >= 6:
                buckets['High (|score| >= 6)'].append(result)
            elif abs_score >= 3:
                buckets['Med (|score| 3-6)'].append(result)
            else:
                buckets['Low (|score| < 3)'].append(result)
        
        lines = []
        for bucket_name, results in buckets.items():
            if not results:
                continue
            
            # Calculate accuracy for this bucket
            correct = sum(1 for r in results if r.was_correct(timeframe))
            accuracy = (correct / len(results) * 100) if results else 0
            
            # Create bar
            bar_length = int(accuracy / 2)  # Scale to max 50 chars for 100%
            bar = '█' * bar_length + '░' * (25 - bar_length)
            
            lines.append(f"  {bucket_name:<20} |{bar}| {accuracy:.1f}% ({len(results)} trades)")
        
        return '\n'.join(lines) if lines else "No data available"
    
    def export_json(self, filepath: str):
        """Export report data to JSON"""
        data = {
            'report_date': datetime.now().isoformat(),
            'total_events': len(self.engine.results),
            'overall_stats': self.engine.get_statistics('15m'),
            'stats_by_timeframe': {
                '5m': self.engine.get_statistics('5m'),
                '15m': self.engine.get_statistics('15m'),
                '30m': self.engine.get_statistics('30m'),
                '60m': self.engine.get_statistics('60m')
            },
            'results': [r.to_dict() for r in self.engine.results]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported JSON report to {filepath}")
    
    def export_csv(self, filepath: str):
        """Export results to CSV"""
        if not self.engine.results:
            logger.warning("No results to export")
            return
        
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                'Event ID', 'Date', 'Title', 'Category', 'Impact Score',
                'Prediction', 'Outcome 15m', 'P&L 15m', 'Outcome 60m', 'P&L 60m'
            ])
            
            # Data
            for result in self.engine.results:
                writer.writerow([
                    result.event_id,
                    result.event_date.strftime('%Y-%m-%d %H:%M'),
                    result.event_title,
                    result.event_category,
                    result.impact_score,
                    result.predicted_direction.value,
                    result.outcome_15m.value,
                    result.get_pnl('15m') or 0,
                    result.outcome_60m.value,
                    result.get_pnl('60m') or 0
                ])
        
        logger.info(f"Exported CSV report to {filepath}")
    
    def export_text(self, filepath: str, **kwargs):
        """Export formatted text report"""
        report = self.generate_report(**kwargs)
        
        with open(filepath, 'w') as f:
            f.write(report)
        
        logger.info(f"Exported text report to {filepath}")
    
    def print_summary(self):
        """Print quick summary to console"""
        stats = self.engine.get_statistics('15m')
        
        print("\n" + "="*60)
        print("       BACKTEST SUMMARY (15-minute timeframe)")
        print("="*60)
        print(f"  Total Events:     {stats.get('total_events', 0)}")
        print(f"  Accuracy:         {stats.get('accuracy', 0):.1f}%")
        print(f"  Total P&L:        ${stats.get('total_pnl', 0):,.2f}")
        print(f"  Win Rate:         {stats.get('win_rate', 0):.1f}%")
        print(f"  Profit Factor:    {stats.get('profit_factor', 0):.2f}")
        print("="*60 + "\n")


# Convenience functions
def generate_backtest_report(
    backtest_engine: BacktestEngine,
    output_path: Optional[str] = None,
    format: str = 'text'
) -> str:
    """
    Generate and optionally save a backtest report
    
    Args:
        backtest_engine: Engine with results
        output_path: Path to save report (optional)
        format: 'text', 'json', or 'csv'
    
    Returns:
        Report content (for text format)
    """
    generator = BacktestReportGenerator(backtest_engine)
    
    if format == 'json':
        if output_path:
            generator.export_json(output_path)
        return ""
    elif format == 'csv':
        if output_path:
            generator.export_csv(output_path)
        return ""
    else:
        report = generator.generate_report()
        if output_path:
            generator.export_text(output_path)
        return report
