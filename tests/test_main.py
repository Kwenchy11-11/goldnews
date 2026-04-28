"""Tests for main module."""
import pytest
from unittest.mock import patch, MagicMock
import sys


def test_main_once_mode():
    """main() with --once flag should run a single news cycle."""
    with patch('sys.argv', ['main.py', '--once']), \
         patch('main.scheduler.run_news_cycle') as mock_cycle, \
         patch('main.config.TELEGRAM_BOT_TOKEN', 'test_token'), \
         patch('main.config.TELEGRAM_CHAT_ID', 'test_chat_id'):
        mock_cycle.return_value = True
        
        from main import main
        main()
        
        mock_cycle.assert_called_once()


def test_main_test_mode():
    """main() with --test flag should send a test message."""
    with patch('sys.argv', ['main.py', '--test']), \
         patch('main.telegram_bot.send_message') as mock_send, \
         patch('main.config.TELEGRAM_BOT_TOKEN', 'test_token'), \
         patch('main.config.TELEGRAM_CHAT_ID', 'test_chat_id'):
        mock_send.return_value = True
        
        from main import main
        main()
        
        mock_send.assert_called_once()
        # Check that test message contains Thai text
        call_args = mock_send.call_args
        assert 'ทองคำ' in call_args[0][0] or 'Gold' in call_args[0][0]