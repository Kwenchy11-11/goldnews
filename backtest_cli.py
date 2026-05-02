#!/usr/bin/env python3
"""
Backtest CLI Tool

Command-line interface for running backtests on historical events.

Usage:
    python backtest_cli.py --sample
    python backtest_cli.py --start 2024-01-01 --end 2024-03-31
    python backtest_cli.py --file events.json
    python backtest_cli.py --import results.json --report-only
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('backtest_cli')

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import DATA_DIR
from core.backtest_engine import BacktestEngine
from core.backtest_report import BacktestReportGenerator
from core.historical_event_loader import (
    HistoricalEventLoader, 
    load_sample_events,
    EventImpact
)


def parse_date(date_str: str) -> datetime:
    """Parse date string (YYYY-MM-DD) to datetime"""
    return datetime.strptime(date_str, '%Y-%m-%d')


def run_backtest_sample(args):
    """Run backtest using sample events"""
    logger.info("Loading sample events...")
    events = load_sample_events()
    logger.info(f"Loaded {len(events)} sample events")
    
    # Filter by impact if specified
    if args.impact:
        impact_levels = [EventImpact(i) for i in args.impact.split(',')]
        events = [e for e in events if e.impact in impact_levels]
        logger.info(f"Filtered to {len(events)} events with impact: {args.impact}")
    
    return run_backtest(events, args)


def run_backtest_date_range(args):
    """Run backtest for date range"""
    logger.info(f"Fetching events from {args.start} to {args.end}...")
    
    loader = HistoricalEventLoader()
    start = parse_date(args.start)
    end = parse_date(args.end)
    
    events = loader.fetch_forexfactory(start, end, use_cache=True)
    
    if not events:
        logger.error("No events found for the specified date range")
        return None
    
    logger.info(f"Found {len(events)} events")
    
    # Filter by impact if specified
    if args.impact:
        impact_levels = [EventImpact(i) for i in args.impact.split(',')]
        events = [e for e in events if e.impact in impact_levels]
        logger.info(f"Filtered to {len(events)} events with impact: {args.impact}")
    
    # Filter for USD events only by default
    if args.usd_only:
        events = loader.get_high_impact_usd_events(events)
        logger.info(f"Filtered to {len(events)} USD high-impact events")
    
    return run_backtest(events, args)


def run_backtest_from_file(args):
    """Run backtest from JSON file"""
    logger.info(f"Loading events from {args.file}...")
    
    loader = HistoricalEventLoader()
    events = loader.load_from_file(args.file)
    
    if not events:
        logger.error(f"No events found in {args.file}")
        return None
    
    logger.info(f"Loaded {len(events)} events from file")
    return run_backtest(events, args)


def run_backtest(events, args):
    """Run backtest on events"""
    if not events:
        logger.error("No events to backtest")
        return None
    
    logger.info("Initializing backtest engine...")
    engine = BacktestEngine()
    
    # Parse timeframes
    timeframes = [int(t.strip()) for t in args.timeframes.split(',')]
    
    logger.info(f"Running backtest with timeframes: {timeframes}")
    logger.info(f"Pre-event baseline: {args.pre_event} minutes")
    
    # Run backtest
    results = engine.run_backtest(
        events,
        pre_event_minutes=args.pre_event,
        timeframes=timeframes
    )
    
    logger.info(f"Backtest complete. Processed {len(results)} events.")
    
    return engine


def generate_and_save_report(engine, args):
    """Generate and save backtest report"""
    if not engine or not engine.results:
        logger.error("No results to generate report")
        return
    
    generator = BacktestReportGenerator(engine)
    
    # Generate text report
    if args.output:
        report_path = args.output
    else:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = os.path.join(DATA_DIR, f'backtest_report_{timestamp}.txt')
    
    logger.info(f"Generating report: {report_path}")
    generator.export_text(report_path)
    
    # Also export JSON
    json_path = report_path.replace('.txt', '.json')
    logger.info(f"Exporting JSON: {json_path}")
    generator.export_json(json_path)
    
    # Also export CSV
    csv_path = report_path.replace('.txt', '.csv')
    logger.info(f"Exporting CSV: {csv_path}")
    generator.export_csv(csv_path)
    
    # Print summary to console
    generator.print_summary()
    
    return report_path


def import_and_report(args):
    """Import existing results and generate report"""
    logger.info(f"Importing results from {args.import_file}...")
    
    engine = BacktestEngine()
    engine.import_results(args.import_file)
    
    logger.info(f"Imported {len(engine.results)} results")
    
    generate_and_save_report(engine, args)


def main():
    parser = argparse.ArgumentParser(
        description='Gold News Event Impact Engine - Backtest Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run backtest with sample events
  python backtest_cli.py --sample

  # Run backtest for specific date range
  python backtest_cli.py --start 2024-01-01 --end 2024-03-31

  # Run backtest from file
  python backtest_cli.py --file events.json

  # Import existing results and regenerate report
  python backtest_cli.py --import results.json --report-only

  # Only high impact events
  python backtest_cli.py --sample --impact High

  # Custom timeframes
  python backtest_cli.py --sample --timeframes "5,15,30,60"
        """
    )
    
    # Input sources (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--sample', action='store_true',
                            help='Use sample events for testing')
    input_group.add_argument('--start', type=str, metavar='DATE',
                            help='Start date (YYYY-MM-DD)')
    input_group.add_argument('--file', type=str, metavar='PATH',
                            help='Load events from JSON file')
    input_group.add_argument('--import-file', type=str, metavar='PATH', dest='import_file',
                            help='Import existing backtest results')
    
    # Date range (requires --start)
    parser.add_argument('--end', type=str, metavar='DATE',
                       help='End date (YYYY-MM-DD, default: today)')
    
    # Filters
    parser.add_argument('--impact', type=str, metavar='LEVELS',
                       help='Filter by impact levels (e.g., "High,Medium")')
    parser.add_argument('--usd-only', action='store_true',
                       help='Only USD high-impact events')
    
    # Backtest settings
    parser.add_argument('--pre-event', type=int, default=15, metavar='MINUTES',
                       help='Minutes before event for baseline price (default: 15)')
    parser.add_argument('--timeframes', type=str, default='5,15,30,60', metavar='LIST',
                       help='Comma-separated timeframes in minutes (default: 5,15,30,60)')
    
    # Output
    parser.add_argument('--output', type=str, metavar='PATH',
                       help='Output file path (default: auto-generated)')
    parser.add_argument('--report-only', action='store_true',
                       help='Only generate report from imported results')
    
    # Logging
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Only show errors')
    
    args = parser.parse_args()
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    elif args.quiet:
        logging.getLogger().setLevel(logging.ERROR)
    
    # Handle import-only mode
    if args.import_file:
        import_and_report(args)
        return
    
    # Validate arguments
    if args.start and not args.end:
        args.end = datetime.now().strftime('%Y-%m-%d')
    
    # Run backtest based on input source
    if args.sample:
        engine = run_backtest_sample(args)
    elif args.start:
        engine = run_backtest_date_range(args)
    elif args.file:
        engine = run_backtest_from_file(args)
    else:
        parser.error("Must specify one of: --sample, --start, --file, --import-file")
        return
    
    # Generate report
    if engine:
        report_path = generate_and_save_report(engine, args)
        logger.info(f"\nBacktest complete! Report saved to: {report_path}")


if __name__ == '__main__':
    main()
