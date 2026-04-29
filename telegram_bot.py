"""
Telegram Bot Module
==================
Sends formatted messages to Telegram via Bot API.
Handles rate limiting, retries, error handling, and inline keyboards.
"""

import time
import logging
from typing import List, Optional

import requests

import config

logger = logging.getLogger('goldnews')


def send_message(text: str, parse_mode: str = 'HTML',
                 reply_markup: Optional[dict] = None,
                 chat_id: Optional[str] = None) -> bool:
    """
    Send a message to the configured Telegram chat.
    Automatically splits messages that exceed Telegram's 4096 character limit.

    Args:
        text: Message text (HTML formatted)
        parse_mode: Parse mode (HTML, Markdown, MarkdownV2)
        reply_markup: Optional inline keyboard markup
        chat_id: Override chat ID (for command responses)

    Returns:
        True if sent successfully, False otherwise
    """
    if not config.TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token not configured")
        return False

    target_chat_id = chat_id or config.TELEGRAM_CHAT_ID
    if not target_chat_id:
        logger.warning("No chat ID configured")
        return False

    # Telegram's max message length
    MAX_LENGTH = 4096

    # If message fits, send as-is
    if len(text) <= MAX_LENGTH:
        return _send_single_message(text, parse_mode, reply_markup, target_chat_id)

    # Split long messages into chunks
    chunks = split_message(text, MAX_LENGTH)
    all_sent = True

    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(1)  # Rate limit between chunks
        # Only attach keyboard to first chunk
        markup = reply_markup if i == 0 else None
        if not _send_single_message(chunk, parse_mode, markup, target_chat_id):
            all_sent = False

    return all_sent


def _send_single_message(text: str, parse_mode: str = 'HTML',
                         reply_markup: Optional[dict] = None,
                         chat_id: Optional[str] = None) -> bool:
    """
    Send a single message to Telegram (internal helper).

    Args:
        text: Message text
        parse_mode: Parse mode
        reply_markup: Optional inline keyboard markup
        chat_id: Target chat ID

    Returns:
        True if sent successfully, False otherwise
    """
    url = f"{config.TELEGRAM_API_URL}/sendMessage"

    payload = {
        'chat_id': chat_id or config.TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True,
    }

    if reply_markup:
        payload['reply_markup'] = reply_markup

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        logger.info("Telegram message sent successfully")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending Telegram message: {e}")
        return False


def build_predictions_keyboard(predictions_url: str = '') -> dict:
    """
    Build an inline keyboard for prediction markets.

    Creates buttons like:
    [📊 ดูคำอธิบาย] [🔄 อัปเดตข้อมูล]
    [🔗 ดู Polymarket]

    Args:
        predictions_url: URL to Polymarket event page

    Returns:
        Reply markup dict for Telegram
    """
    buttons = []

    # Row 1: Help + Refresh
    buttons.append([
        {'text': '📊 คำอธิบาย', 'callback_data': 'explain_predictions'},
        {'text': '🔄 อัปเดต', 'callback_data': 'refresh_predictions'},
    ])

    # Row 2: Link to Polymarket (if URL available)
    if predictions_url:
        buttons.append([
            {'text': '🔗 ดูใน Polymarket', 'url': predictions_url},
        ])

    return {'inline_keyboard': buttons}


def build_category_keyboard(categories: List[str]) -> dict:
    """
    Build an inline keyboard to filter by category.

    Args:
        categories: List of category keys (fed, gold, inflation, etc.)

    Returns:
        Reply markup dict for Telegram
    """
    emoji_map = {
        'fed': '🏦',
        'gold': '🥇',
        'inflation': '💰',
        'employment': '👷',
        'economy': '📊',
    }

    buttons = []
    row = []
    for cat in categories[:5]:  # Max 5 buttons
        emoji = emoji_map.get(cat, '📌')
        row.append({
            'text': f'{emoji} {cat.capitalize()}',
            'callback_data': f'filter_{cat}',
        })
        if len(row) >= 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    return {'inline_keyboard': buttons}


def split_message(text: str, max_length: int = 4096) -> List[str]:
    """
    Split a long message into chunks that fit within Telegram's character limit.
    Tries to split at double newlines (paragraph breaks) to keep content coherent.
    
    Args:
        text: Full message text
        max_length: Maximum characters per chunk
        
    Returns:
        List of message chunks
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    remaining = text
    
    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break
        
        # Find a good split point: double newline within the limit
        split_point = remaining.rfind('\n\n', 0, max_length)
        
        if split_point == -1:
            # No double newline found, try single newline
            split_point = remaining.rfind('\n', 0, max_length)
        
        if split_point == -1 or split_point < max_length // 2:
            # No good split point, force split at max_length
            split_point = max_length
        
        chunks.append(remaining[:split_point].strip())
        remaining = remaining[split_point:].strip()
    
    return chunks


def send_message_with_retry(text: str, max_retries: int = 3, retry_delay: float = 5.0,
                            parse_mode: str = 'HTML',
                            reply_markup: Optional[dict] = None,
                            chat_id: Optional[str] = None) -> bool:
    """
    Send a message with exponential backoff retry.

    Args:
        text: Message text
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries (doubles each time)
        parse_mode: Parse mode for Telegram
        reply_markup: Optional inline keyboard markup
        chat_id: Override chat ID (for command responses)

    Returns:
        True if sent successfully within retries, False otherwise
    """
    for attempt in range(max_retries):
        if send_message(text, parse_mode, reply_markup, chat_id):
            return True

        if attempt < max_retries - 1:
            delay = retry_delay * (2 ** attempt)  # Exponential backoff
            logger.warning(f"Retry {attempt + 1}/{max_retries} in {delay:.1f}s...")
            time.sleep(delay)

    logger.error(f"Failed to send message after {max_retries} attempts")
    return False


def send_news_alert(title: str, body: str) -> bool:
    """
    Send a news alert message.
    
    Args:
        title: Alert title
        body: Alert body text
        
    Returns:
        True if sent successfully
    """
    message = f"{title}\n\n{body}"
    return send_message_with_retry(message)


def send_startup_message() -> bool:
    """Send a startup notification to confirm the bot is running."""
    message = (
        "🟡 <b>Gold News Bot เริ่มทำงาน</b>\n\n"
        f" ตรวจสอบข่าวทุก {config.CHECK_INTERVAL} นาที\n"
        f"📅 วันจันทร์-ศุกร์ (เวลาตลาด)\n\n"
        " <b>คำสั่งที่ใช้ได้:</b>\n"
        "🎯 /predictions — ดูตลาดคาดการณ์ Polymarket\n"
        " /news — ดึงข่าวล่าสุดทันที\n"
        "📊 /status — ดูสถานะบอท\n"
        "❓ /help — แสดงคำสั่งทั้งหมด\n\n"
        "<i>บอทพร้อมส่งข่าวสำคัญที่มีผลต่อราคาทองคำ</i>"
    )
    return send_message(message)


def send_error_alert(error_message: str) -> bool:
    """Send an error alert to notify of issues."""
    message = (
        f"🚨 <b>Gold News Bot Error</b>\n\n"
        f"{error_message}\n\n"
        f"<i>บอทจะลองใหม่ในรอบถัดไป</i>"
    )
    return send_message(message)