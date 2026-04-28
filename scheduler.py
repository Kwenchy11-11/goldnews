"""
Scheduler Module
===============
Runs the news cycle on a configurable interval.
Checks market hours and skips weekends.
"""

import time
import logging
from datetime import datetime
from typing import Optional

import config
import news_fetcher
import realtime_news
import analyzer
from analyzer import MarketSummary
import formatter
import telegram_bot

logger = logging.getLogger('goldnews')


def is_market_hours() -> bool:
    """
    Check if current time is within market hours.
    
    When MARKET_HOURS_ONLY is True, only runs Monday-Friday.
    When False, runs every day.
    """
    if not config.MARKET_HOURS_ONLY:
        return True
    
    now = datetime.now()
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    # Skip weekends (Saturday=5, Sunday=6)
    if weekday >= 5:
        logger.info(f"Weekend detected (day {weekday}), skipping news cycle")
        return False
    
    return True


def run_news_cycle() -> bool:
    """
    Run a complete news cycle:
    1. Fetch news from all sources
    2. Analyze ALL events in one Gemini call (batch analysis)
    3. Filter to HIGH impact only (most important for gold)
    4. Format messages with market summary
    5. Send to Telegram in batches of max 10
    
    Returns:
        True if cycle completed successfully, False otherwise
    """
    logger.info("Starting news cycle...")
    
    try:
        # Step 1: Fetch news
        news_data = news_fetcher.fetch_all_news()
        events = news_data.get('events', [])
        markets = news_data.get('markets', [])

        # Step 1b: Fetch real-time news from RSS feeds
        realtime_items = realtime_news.fetch_realtime_news()

        logger.info(f"Fetched {len(events)} events, {len(markets)} markets, {len(realtime_items)} real-time news")
        
        # Step 2: Batch analyze events (one Gemini call for all)
        if events:
            # Filter to HIGH/MEDIUM impact first to reduce API load
            important_events = [e for e in events if e.impact.upper() in ('HIGH', 'MEDIUM')]
            if not important_events:
                important_events = events  # Fallback to all if none match
            
            analyses, summary = analyzer.analyze_events_batch(important_events)
            logger.info(f"Batch analyzed {len(analyses)} events, overall bias: {summary.overall_bias}")
            
            # Step 3: Filter to HIGH impact only for notification
            high_analyses = [a for a in analyses if a.impact.upper() == 'HIGH']
            logger.info(f"Filtered to {len(high_analyses)} HIGH impact events (from {len(analyses)} total)")
        else:
            high_analyses = []
            summary = MarketSummary(
                overall_bias='NEUTRAL',
                gold_outlook='ไม่มีข่าวสำคัญ',
                key_times='-',
                usd_impact='-',
                confidence=0,
            )
            logger.info("No relevant events to analyze")
        
        # Step 4: Format and send messages in batches
        if high_analyses or markets:
            batch_size = 10
            batches = []
            
            if high_analyses:
                for i in range(0, len(high_analyses), batch_size):
                    batch = high_analyses[i:i + batch_size]
                    # Only include Polymarket data in the last batch
                    batch_markets = markets if i + batch_size >= len(high_analyses) else None
                    # Only include summary in the first batch
                    batch_summary = summary if i == 0 else None
                    # Only include real-time news in the first batch
                    batch_realtime = realtime_items if i == 0 else None
                    message = formatter.format_daily_summary(batch, batch_markets, batch_summary, batch_realtime)
                    batches.append(message)
            else:
                # Only Polymarket data, no events
                message = formatter.format_daily_summary([], markets, summary)
                batches.append(message)
            
            # Send each batch
            all_sent = True
            for i, msg in enumerate(batches):
                if i > 0:
                    time.sleep(2)  # Rate limit between messages
                success = telegram_bot.send_message_with_retry(msg)
                if not success:
                    all_sent = False
                    logger.error(f"Failed to send batch {i + 1}/{len(batches)}")
            
            if all_sent:
                logger.info("News alert sent successfully")
            else:
                logger.error("Failed to send some news alerts")
            return all_sent
        else:
            # No important news - skip sending to avoid noise
            logger.info("No HIGH impact events - skipping notification")
            return True
            
    except Exception as e:
        logger.error(f"Error in news cycle: {e}", exc_info=True)
        telegram_bot.send_error_alert(f"ข้อผิดพลาดในการตรวจสอบข่าว: {str(e)}")
        return False


def start_scheduler():
    """
    Start the main scheduler loop.
    
    Runs the news cycle every CHECK_INTERVAL minutes.
    Skips cycles outside market hours if MARKET_HOURS_ONLY is True.
    """
    logger.info(f"Starting Gold News Bot scheduler")
    logger.info(f"Check interval: {config.CHECK_INTERVAL} minutes")
    logger.info(f"Market hours only: {config.MARKET_HOURS_ONLY}")
    
    # Send startup message
    telegram_bot.send_startup_message()
    
    interval_seconds = config.CHECK_INTERVAL * 60
    
    while True:
        try:
            if is_market_hours():
                run_news_cycle()
            else:
                logger.info("Outside market hours, skipping cycle")
            
            logger.info(f"Sleeping for {config.CHECK_INTERVAL} minutes...")
            time.sleep(interval_seconds)
            
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error in scheduler loop: {e}", exc_info=True)
            # Sleep and try again
            time.sleep(60)  # Wait 1 minute before retrying on unexpected errors