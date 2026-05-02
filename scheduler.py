"""
Scheduler Module
===============
Runs the news cycle on a configurable interval.
Checks market hours and skips weekends.

Now includes Event Impact Engine integration for:
- Pre-event alerts (15 minutes before major events)
- Post-event impact analysis (after data release)
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import config
import news_fetcher
import realtime_news
import analyzer
from analyzer import MarketSummary
import formatter
import telegram_bot
from event_classifier import classify_event

# Event Impact Engine imports (lazy-loaded to avoid circular imports)
_analyze_event_impact = None

def _get_analyze_event_impact():
    """Lazy load the analyze_event_impact function."""
    global _analyze_event_impact
    if _analyze_event_impact is None:
        from src.core.event_impact_engine import analyze_event_impact
        _analyze_event_impact = analyze_event_impact
    return _analyze_event_impact

logger = logging.getLogger('goldnews')

# Track events we've already alerted about to avoid duplicates
_pre_event_alerts_sent: Dict[str, datetime] = {}
_post_event_alerts_sent: Dict[str, datetime] = {}


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

        logger.info(f"Fetched {len(events)} events, {len(markets)} markets, "
                    f"{len(realtime_items)} real-time news")

        # Note: Polymarket predictions are now handled via /predictions command
        # They are NOT included in automatic messages
        
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
                    message = formatter.format_daily_summary(
                        batch, batch_markets, batch_summary, batch_realtime
                    )
                    batches.append(message)
            else:
                # Only Polymarket data, no events
                message = formatter.format_daily_summary([], markets, summary, realtime_items)
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
    Also runs the Event Impact Engine cycle for pre/post event alerts.
    Skips cycles outside market hours if MARKET_HOURS_ONLY is True.
    """
    logger.info(f"Starting Gold News Bot scheduler")
    logger.info(f"Check interval: {config.CHECK_INTERVAL} minutes")
    logger.info(f"Market hours only: {config.MARKET_HOURS_ONLY}")
    logger.info(f"Event Impact Engine: {'enabled' if config.ENABLE_IMPACT_ENGINE else 'disabled'}")
    
    if config.ENABLE_IMPACT_ENGINE:
        logger.info(f"  - Pre-event alerts: {'enabled' if config.ENABLE_PRE_EVENT_ALERTS else 'disabled'}")
        logger.info(f"  - Post-event alerts: {'enabled' if config.ENABLE_POST_EVENT_ALERTS else 'disabled'}")
    
    # Send startup message
    telegram_bot.send_startup_message()
    
    interval_seconds = config.CHECK_INTERVAL * 60
    
    while True:
        try:
            if is_market_hours():
                # Run main news cycle
                run_news_cycle()
                
                # Run Event Impact Engine cycle for alerts
                if config.ENABLE_IMPACT_ENGINE:
                    run_impact_event_cycle()
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


# ============================================================================
# EVENT IMPACT ENGINE SCHEDULING
# ============================================================================
# Functions for pre-event and post-event alerts using the Impact Engine


def _get_event_datetime(event) -> Optional[datetime]:
    """Safely get event datetime from event object."""
    if hasattr(event, 'event_datetime') and event.event_datetime:
        return event.event_datetime
    return None


def check_pre_event_alerts(events: List) -> int:
    """
    Check for events happening soon and send pre-event alerts.

    Sends alerts 15 minutes before high-impact events to give users
    time to prepare positions.

    Args:
        events: List of EconomicEvent objects

    Returns:
        Number of alerts sent
    """
    if not config.ENABLE_PRE_EVENT_ALERTS or not config.ENABLE_IMPACT_ENGINE:
        return 0

    now = datetime.now(config.THAI_TZ)
    alerts_sent = 0
    alert_window = timedelta(minutes=config.PRE_EVENT_ALERT_MINUTES)

    # Clean up old entries from tracking dict
    cutoff = now - timedelta(hours=1)
    for event_id in list(_pre_event_alerts_sent.keys()):
        if _pre_event_alerts_sent[event_id] < cutoff:
            del _pre_event_alerts_sent[event_id]

    for event in events:
        event_dt = _get_event_datetime(event)
        if not event_dt:
            continue

        # Make datetime timezone-aware if needed
        if event_dt.tzinfo is None:
            event_dt = config.THAI_TZ.localize(event_dt)

        # Only alert on high-impact events
        if event.impact.upper() != 'HIGH':
            continue

        # Create unique ID for this event
        event_id = f"{event.title}_{event_dt.isoformat()}"

        # Skip if already sent alert for this event
        if event_id in _pre_event_alerts_sent:
            continue

        # Check if event is coming up in the alert window
        time_until = event_dt - now

        if timedelta(0) < time_until <= alert_window:
            # Send pre-event alert
            try:
                # Use Event Impact Engine for classification
                classification = classify_event(event.title)

                message = formatter.format_pre_event_alert(
                    event_name=event.title,
                    forecast=getattr(event, 'forecast', None),
                    previous=getattr(event, 'previous', None),
                    category=classification.category.value,
                    event_time=event_dt
                )

                success = telegram_bot.send_message_with_retry(message)
                if success:
                    _pre_event_alerts_sent[event_id] = now.replace(tzinfo=config.THAI_TZ)
                    alerts_sent += 1
                    logger.info(f"Sent pre-event alert for {event.title}")

            except Exception as e:
                logger.error(f"Error sending pre-event alert for {event.title}: {e}")

    return alerts_sent


def check_post_event_alerts(events: List) -> int:
    """
    Check for recently released events and send post-event impact analysis.

    Analyzes events that just released actual data and sends impact assessment.

    Args:
        events: List of EconomicEvent objects

    Returns:
        Number of alerts sent
    """
    if not config.ENABLE_POST_EVENT_ALERTS or not config.ENABLE_IMPACT_ENGINE:
        return 0

    now = datetime.now(config.THAI_TZ)
    alerts_sent = 0
    check_window = timedelta(minutes=config.POST_EVENT_DELAY_MINUTES + 5)

    # Clean up old entries
    cutoff = now - timedelta(hours=2)
    for event_id in list(_post_event_alerts_sent.keys()):
        if _post_event_alerts_sent[event_id] < cutoff:
            del _post_event_alerts_sent[event_id]

    for event in events:
        event_dt = _get_event_datetime(event)
        if not event_dt:
            continue

        # Make datetime timezone-aware if needed
        if event_dt.tzinfo is None:
            event_dt = config.THAI_TZ.localize(event_dt)

        # Only alert on high-impact events
        if event.impact.upper() != 'HIGH':
            continue

        # Create unique ID
        event_id = f"{event.title}_{event_dt.isoformat()}"

        # Skip if already sent
        if event_id in _post_event_alerts_sent:
            continue

        # Check if event just happened (within check window after event time)
        time_since = now - event_dt

        if timedelta(0) < time_since <= check_window:
            # Check if we have actual data (post-event)
            actual = getattr(event, 'actual', None)
            forecast = getattr(event, 'forecast', None)

            # Only send if we have actual data
            if actual:
                try:
                    # Use Event Impact Engine for analysis
                    classification = classify_event(event.title)

                    # Parse values
                    actual_val = _parse_value(actual)
                    forecast_val = _parse_value(forecast) if forecast else None
                    previous_val = _parse_value(getattr(event, 'previous', None))

                    # Analyze impact
                    analyze_fn = _get_analyze_event_impact()
                    impact_result = analyze_fn(
                        event_name=event.title,
                        category=classification.category.value,
                        forecast=forecast_val,
                        actual=actual_val,
                        previous=previous_val
                    )

                    # Only send if significant impact
                    if abs(impact_result.composite_score) >= config.ALERT_THRESHOLD_NORMAL:
                        message = formatter.format_post_event_alert(
                            event_name=event.title,
                            actual=actual,
                            forecast=forecast,
                            previous=getattr(event, 'previous', None),
                            composite_score=impact_result.composite_score,
                            alert_message=impact_result.alert_message
                        )

                        success = telegram_bot.send_message_with_retry(message)
                        if success:
                            _post_event_alerts_sent[event_id] = now.replace(tzinfo=config.THAI_TZ)
                            alerts_sent += 1
                            logger.info(f"Sent post-event alert for {event.title}")

                except Exception as e:
                    logger.error(f"Error sending post-event alert for {event.title}: {e}")

    return alerts_sent


def _parse_value(value) -> Optional[float]:
    """Parse a numeric value from string."""
    if value is None:
        return None

    try:
        # Remove common suffixes
        cleaned = str(value).strip().replace('%', '').replace('K', '').replace('M', '')
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def run_impact_event_cycle():
    """
    Run the Event Impact Engine alert cycle.

    Checks for upcoming and recently released high-impact events
    and sends alerts accordingly.
    """
    if not config.ENABLE_IMPACT_ENGINE:
        return

    try:
        # Fetch current events
        news_data = news_fetcher.fetch_all_news()
        events = news_data.get('events', [])

        if not events:
            return

        # Check for pre-event alerts (15 min before)
        pre_alerts = check_pre_event_alerts(events)
        if pre_alerts > 0:
            logger.info(f"Sent {pre_alerts} pre-event alerts")

        # Check for post-event alerts (after release)
        post_alerts = check_post_event_alerts(events)
        if post_alerts > 0:
            logger.info(f"Sent {post_alerts} post-event alerts")

    except Exception as e:
        logger.error(f"Error in impact event cycle: {e}", exc_info=True)