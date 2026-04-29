#!/usr/bin/env python3
"""
Gold News Telegram Bot
=====================
Main entry point for the gold news alert bot.
Sends automatic news alerts every 30 minutes (Mon-Fri).

For predictions only, use predictions_bot.py instead.

Usage:
    python main.py              # Start continuous daemon
    python main.py --once       # Run a single news cycle
    python main.py --test       # Send a test message
"""

import argparse
import logging
import sys

import config
import scheduler
import telegram_bot

logger = logging.getLogger('goldnews')


def main():
    """Main entry point for the Gold News Bot."""
    parser = argparse.ArgumentParser(
        description='Gold News Telegram Bot - ส่งข่าวทองคำไปยัง Telegram'
    )
    parser.add_argument(
        '--once', action='store_true',
        help='Run a single news cycle and exit'
    )
    parser.add_argument(
        '--test', action='store_true',
        help='Send a test message and exit'
    )

    args = parser.parse_args()

    # Validate configuration
    if not config.TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Please set it in .env file.")
        sys.exit(1)

    if not config.TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_CHAT_ID not set. Please set it in .env file.")
        sys.exit(1)

    logger.info("=" * 50)
    logger.info(" Gold News Telegram Bot")
    logger.info("=" * 50)
    logger.info(f"Check interval: {config.CHECK_INTERVAL} minutes")
    logger.info(f"Market hours only: {config.MARKET_HOURS_ONLY}")
    logger.info(f"Gemini API: {'configured' if config.GEMINI_API_KEY else 'NOT configured'}")

    if args.test:
        # Test mode: send a test message
        logger.info("Sending test message...")
        test_message = (
            "🧪 <b>Gold News Bot - ทดสอบ</b>\n\n"
            "บอททองคำทำงานได้ปกติ ✅\n"
            f"⏰ ตรวจสอบข่าวทุก {config.CHECK_INTERVAL} นาที\n"
            f"📅 วันจันทร์-ศุกร์ (เวลาตลาด)\n\n"
            "<i>ข่าวสำคัญจะถูกส่งมาให้อัตโนมัติ</i>"
        )
        success = telegram_bot.send_message(test_message)
        if success:
            logger.info("✅ Test message sent successfully!")
        else:
            logger.error("❌ Failed to send test message")
        return

    if args.once:
        # Single cycle mode
        logger.info("Running single news cycle...")
        success = scheduler.run_news_cycle()
        if success:
            logger.info("✅ News cycle completed successfully")
        else:
            logger.error("❌ News cycle failed")
        return

    # Continuous mode: run scheduler
    logger.info("Starting continuous mode...")
    logger.info("Gold News Bot will send alerts every 30 min (Mon-Fri)")
    logger.info("For predictions, run predictions_bot.py separately")

    scheduler.start_scheduler()


if __name__ == "__main__":
    main()