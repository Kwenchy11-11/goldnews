"""Tests for telegram_bot module."""
import pytest
from unittest.mock import patch, MagicMock


def test_send_message_success():
    """send_message should return True on successful API call."""
    from telegram_bot import send_message
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'ok': True}
    mock_response.raise_for_status = MagicMock()
    
    env_vars = {
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_CHAT_ID': 'test_chat_id',
    }
    with patch('telegram_bot.requests.post', return_value=mock_response), \
         patch.dict('os.environ', env_vars, clear=False), \
         patch('config.TELEGRAM_BOT_TOKEN', 'test_token'), \
         patch('config.TELEGRAM_CHAT_ID', 'test_chat_id'), \
         patch('config.TELEGRAM_API_URL', 'https://api.telegram.org/bottest_token'):
        result = send_message("Test message")
    
    assert result is True


def test_send_message_failure():
    """send_message should return False on API error."""
    from telegram_bot import send_message
    
    with patch('telegram_bot.requests.post', side_effect=Exception('Network error')):
        result = send_message("Test message")
    
    assert result is False


def test_send_message_with_retry_success_first_try():
    """send_message_with_retry should succeed on first try."""
    from telegram_bot import send_message_with_retry
    
    with patch('telegram_bot.send_message', return_value=True):
        result = send_message_with_retry("Test message", max_retries=3)
    
    assert result is True


def test_send_message_with_retry_success_after_retry():
    """send_message_with_retry should retry and eventually succeed."""
    from telegram_bot import send_message_with_retry
    
    with patch('telegram_bot.send_message', side_effect=[False, False, True]):
        result = send_message_with_retry("Test message", max_retries=3, retry_delay=0.01)
    
    assert result is True


def test_send_message_with_retry_all_fail():
    """send_message_with_retry should return False after all retries fail."""
    from telegram_bot import send_message_with_retry
    
    with patch('telegram_bot.send_message', return_value=False):
        result = send_message_with_retry("Test message", max_retries=3, retry_delay=0.01)
    
    assert result is False


def test_send_news_alert_formats_correctly():
    """send_news_alert should call send_message_with_retry with formatted text."""
    from telegram_bot import send_news_alert
    
    sent_messages = []
    
    def mock_send_with_retry(text, max_retries=3, retry_delay=5.0, parse_mode='HTML'):
        sent_messages.append(text)
        return True
    
    with patch('telegram_bot.send_message_with_retry', side_effect=mock_send_with_retry):
        result = send_news_alert("🔔 ข่าวสำคัญ: CPI", "รายละเอียดข่าว")
    
    assert result is True
    assert len(sent_messages) == 1
    assert "CPI" in sent_messages[0]