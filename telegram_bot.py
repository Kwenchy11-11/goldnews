"""
Telegram Bot Module
==================
Sends formatted messages to Telegram via Bot API.
Handles rate limiting, retries, and error handling.
"""

import time
import logging
from typing import List, Optional

import requests

import config

logger = logging.getLogger('goldnews')


def send_message(text: str, parse_mode: str = 'HTML') -> bool:
    """
    Send a message to the configured Telegram chat.
    Automatically splits messages that exceed Telegram's 4096 character limit.
    
    Args:
        text: Message text (HTML formatted)
        parse_mode: Parse mode (HTML, Markdown, MarkdownV2)
        
    Returns:
        True if sent successfully, False otherwise
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.warning("Telegram bot token or chat ID not configured")
        return False
    
    # Telegram's max message length
    MAX_LENGTH = 4096
    
    # If message fits, send as-is
    if len(text) <= MAX_LENGTH:
        return _send_single_message(text, parse_mode)
    
    # Split long messages into chunks
    chunks = split_message(text, MAX_LENGTH)
    all_sent = True
    
    for i, chunk in enumerate(chunks):
        if i > 0:
            time.sleep(1)  # Rate limit between chunks
        if not _send_single_message(chunk, parse_mode):
            all_sent = False
    
    return all_sent


def _send_single_message(text: str, parse_mode: str = 'HTML') -> bool:
    """
    Send a single message to Telegram (internal helper).
    
    Args:
        text: Message text
        parse_mode: Parse mode
        
    Returns:
        True if sent successfully, False otherwise
    """
    url = f"{config.TELEGRAM_API_URL}/sendMessage"
    
    payload = {
        'chat_id': config.TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': True,
    }
    
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
                            parse_mode: str = 'HTML') -> bool:
    """
    Send a message with exponential backoff retry.
    
    Args:
        text: Message text
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries (doubles each time)
        parse_mode: Parse mode for Telegram
        
    Returns:
        True if sent successfully within retries, False otherwise
    """
    for attempt in range(max_retries):
        if send_message(text, parse_mode):
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
        f"⏰ ตรวจสอบข่าวทุก {config.CHECK_INTERVAL} นาที\n"
        f"📅 วันจันทร์-ศุกร์ (เวลาตลาด)\n\n"
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