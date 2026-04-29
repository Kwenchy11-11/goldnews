"""
Telegram Command Handler
========================
Handles user commands like /predictions, /help, /status.
Polls Telegram for updates and responds to commands.
"""

import logging
import time
from typing import Optional

import requests

import config
import polymarket_predictions
import formatter
import telegram_bot

logger = logging.getLogger('goldnews')

# Track last update_id to avoid processing old messages
_last_update_id: Optional[int] = None


def get_updates(offset: Optional[int] = None, timeout: int = 30) -> list:
    """
    Get updates from Telegram Bot API.

    Args:
        offset: Only get updates after this update_id
        timeout: Long polling timeout in seconds

    Returns:
        List of update dicts
    """
    url = f"{config.TELEGRAM_API_URL}/getUpdates"
    params = {
        'timeout': timeout,
        'allowed_updates': ['message'],
    }
    if offset is not None:
        params['offset'] = offset

    try:
        response = requests.get(url, params=params, timeout=timeout + 5)
        response.raise_for_status()
        data = response.json()
        return data.get('result', [])
    except Exception as e:
        logger.error(f"Failed to get Telegram updates: {e}")
        return []


def handle_predictions_command(chat_id: int) -> bool:
    """
    Handle /predictions command.
    Fetches Polymarket prediction markets and sends them to the user.

    Args:
        chat_id: Telegram chat ID to send to

    Returns:
        True if sent successfully
    """
    logger.info(f"Handling /predictions command for chat {chat_id}")

    # Fetch predictions
    predictions = polymarket_predictions.fetch_polymarket_predictions()

    if not predictions:
        message = (
            "🎯 <b>ตลาดคาดการณ์ (Polymarket)</b>\n\n"
            "ขณะนี้ยังไม่มีตลาดคาดการณ์ที่เกี่ยวข้องกับทองคำ/Fed/เศรษฐกิจ ที่ active อยู่\n\n"
            "ตลาด Polymarket จะเปิด-ปิดตามเหตุการณ์จริง บอทจะแสดงข้อมูลอัตโนมัติเมื่อมีตลาดใหม่ครับ\n\n"
            "💡 <b>Polymarket คืออะไร?</b>\n"
            "เป็นตลาดที่คนทั่วโลกมา \"เดิมพัน\" ว่าเหตุการณ์ต่างๆ จะเกิดขึ้นหรือไม่\n"
            "• % สูง = ตลาดมองว่ามีโอกาสเกิดสูง\n"
            "• ใช้เป็นข้อมูลประกอบการตัดสินใจเทรดทองคำได้"
        )
        return telegram_bot.send_message_with_retry(message, chat_id=chat_id)

    # Format predictions message
    message = (
        "🎯 <b>ตลาดคาดการณ์อะไรอยู่? (Polymarket)</b>\n"
        f"{'─' * 30}\n"
        "<i>ตัวเลข % = ความน่าจะเป็นที่ตลาดคาดการณ์</i>\n"
        "<i>🟢 = มีโอกาสสูง | 🟡 = เป็นไปได้ | 🔴 = โอกาสน้อย</i>\n\n"
    )

    # Group by category
    by_category = polymarket_predictions.get_predictions_by_category(predictions)
    category_order = ['fed', 'gold', 'inflation', 'employment', 'economy']

    for category in category_order:
        if category not in by_category:
            continue

        cat_markets = by_category[category][:3]  # Max 3 per category
        cat_info = polymarket_predictions.CATEGORY_INFO.get(category, {})
        cat_emoji = cat_info.get('emoji', '📌')
        cat_label = cat_info.get('label_th', category.capitalize())

        message += f"{cat_emoji} <b>{cat_label}</b>\n"

        for market in cat_markets:
            outcomes_str = _format_outcomes_for_command(market.outcomes, market.category)
            message += f"• {market.question_th}\n"
            message += f"{outcomes_str}\n"

        message += "\n"

    # Add explanation
    message += (
        f"💡 <b>อ่านยังไง?</b>\n"
        f"Polymarket คือตลาดที่คนทั่วโลกมา \"เดิมพัน\" ว่าเหตุการณ์ต่างๆ จะเกิดขึ้นหรือไม่\n"
        f"• ถ้า % สูง = ตลาดมองว่ามีโอกาสเกิดสูง\n"
        f"• ทองคำมัก <b>ขึ้น</b> เมื่อ Fed ลดดอกเบี้ย หรือเศรษฐกิจแย่\n"
        f"• ทองคำมัก <b>ลง</b> เมื่อ Fed ขึ้นดอกเบี้ย หรือเศรษฐกิจดี\n\n"
        f"<i>ข้อมูลนี้เป็นการคาดการณ์ล่วงหน้า ไม่ใช่ข่าวที่เกิดขึ้นแล้ว</i>"
    )

    # Build keyboard
    keyboard = telegram_bot.build_predictions_keyboard()

    return telegram_bot.send_message_with_retry(message, chat_id=chat_id, reply_markup=keyboard)


def _format_outcomes_for_command(outcomes: list, category: str) -> str:
    """Format outcomes for command response."""
    lines = []
    for outcome in outcomes[:3]:
        name = outcome.get('name', '')
        price = outcome.get('price', 0)
        pct = price * 100

        name_th = formatter._translate_outcome_name(name, category)

        if pct >= 60:
            indicator = '🟢'
        elif pct >= 40:
            indicator = '🟡'
        else:
            indicator = ''

        lines.append(f"  {indicator} {name_th}: {pct:.0f}%")

    return '\n'.join(lines)


def handle_help_command(chat_id: int) -> bool:
    """Handle /help command."""
    message = (
        "🤖 <b>Gold News Bot - คำสั่งที่ใช้ได้</b>\n\n"
        "📰 <b>/news</b> — ดูข่าวล่าสุดที่มีผลต่อทองคำ\n"
        "🎯 <b>/predictions</b> — ดูตลาดคาดการณ์ Polymarket\n"
        "📊 <b>/status</b> — ดูสถานะบอท\n"
        "❓ <b>/help</b> — แสดงคำสั่งทั้งหมด\n\n"
        "<i>บอทจะส่งข่าวอัตโนมัติทุก 30 นาที (จ-ศ)</i>"
    )
    return telegram_bot.send_message_with_retry(message, chat_id=chat_id)


def handle_status_command(chat_id: int) -> bool:
    """Handle /status command."""
    message = (
        " <b>สถานะ Gold News Bot</b>\n\n"
        f"✅ บอททำงานปกติ\n"
        f" ตรวจสอบข่าวทุก {config.CHECK_INTERVAL} นาที\n"
        f"📅 วันจันทร์-ศุกร์ (เวลาตลาด)\n"
        f"🔑 Gemini API: {'✅ configured' if config.GEMINI_API_KEY else ' not set'}\n"
        f"📱 Telegram: {'✅ configured' if config.TELEGRAM_BOT_TOKEN else '❌ not set'}"
    )
    return telegram_bot.send_message_with_retry(message, chat_id=chat_id)


def handle_news_command(chat_id: int) -> bool:
    """Handle /news command - trigger a news cycle immediately."""
    import scheduler
    message = "🔄 กำลังดึงข่าวล่าสุด..."
    telegram_bot.send_message(message, chat_id=chat_id)

    success = scheduler.run_news_cycle()

    if success:
        telegram_bot.send_message("✅ ส่งข่าวเรียบร้อยแล้ว", chat_id=chat_id)
    else:
        telegram_bot.send_message("❌ เกิดข้อผิดพลาดในการดึงข่าว", chat_id=chat_id)

    return success


def process_update(update: dict) -> bool:
    """
    Process a single Telegram update.

    Args:
        update: Update dict from Telegram API

    Returns:
        True if a command was handled
    """
    global _last_update_id

    update_id = update.get('update_id')
    message = update.get('message', {})
    chat_id = message.get('chat', {}).get('id')
    text = message.get('text', '').strip().lower()

    # Skip if we've already processed this update
    if _last_update_id is not None and update_id <= _last_update_id:
        return False

    _last_update_id = update_id

    if not text.startswith('/'):
        return False

    # Route commands
    if text == '/predictions' or text == '/prediction':
        return handle_predictions_command(chat_id)
    elif text == '/help' or text == '/start':
        return handle_help_command(chat_id)
    elif text == '/status':
        return handle_status_command(chat_id)
    elif text == '/news':
        return handle_news_command(chat_id)

    return False


def start_command_handler():
    """
    Start the command handler loop.
    Polls Telegram for updates and handles commands.
    """
    global _last_update_id

    logger.info("Starting Telegram command handler...")

    # Get initial offset (skip old messages)
    updates = get_updates(timeout=1)
    if updates:
        _last_update_id = updates[-1].get('update_id')
        logger.info(f"Skipping {_last_update_id} old updates")

    while True:
        try:
            updates = get_updates(offset=_last_update_id, timeout=30)

            for update in updates:
                try:
                    process_update(update)
                except Exception as e:
                    logger.error(f"Error processing update: {e}", exc_info=True)

        except KeyboardInterrupt:
            logger.info("Command handler stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in command handler loop: {e}", exc_info=True)
            time.sleep(10)  # Wait before retrying
