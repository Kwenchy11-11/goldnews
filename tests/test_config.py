"""Tests for config module."""
import os
import pytest
from unittest.mock import patch


def test_config_loads_env_vars():
    """Config should load values from environment variables."""
    env_vars = {
        'TELEGRAM_BOT_TOKEN': 'test_token_123',
        'TELEGRAM_CHAT_ID': 'test_chat_456',
        'GEMINI_API_KEY': 'test_gemini_key',
        'CHECK_INTERVAL': '15',
        'MARKET_HOURS_ONLY': 'false',
        'LOG_LEVEL': 'DEBUG',
    }
    with patch.dict(os.environ, env_vars, clear=False):
        # Re-import to pick up new env vars
        import importlib
        import config
        importlib.reload(config)
        
        assert config.TELEGRAM_BOT_TOKEN == 'test_token_123'
        assert config.TELEGRAM_CHAT_ID == 'test_chat_456'
        assert config.GEMINI_API_KEY == 'test_gemini_key'
        assert config.CHECK_INTERVAL == 15
        assert config.MARKET_HOURS_ONLY is False
        assert config.LOG_LEVEL == 'DEBUG'


def test_config_defaults():
    """Config should use defaults when env vars are missing."""
    env_vars = {
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_CHAT_ID': 'test_chat',
        'GEMINI_API_KEY': 'test_key',
    }
    with patch.dict(os.environ, env_vars, clear=True):
        import importlib
        import config
        importlib.reload(config)
        
        assert config.CHECK_INTERVAL == 30
        assert config.MARKET_HOURS_ONLY is True
        assert config.LOG_LEVEL == 'INFO'


def test_config_validates_required_vars():
    """Config should have empty/None values when required vars are missing."""
    # Clear all env vars including .env file effects
    with patch.dict(os.environ, {
        'TELEGRAM_BOT_TOKEN': '',
        'TELEGRAM_CHAT_ID': '',
        'GEMINI_API_KEY': '',
    }, clear=True):
        import importlib
        import config
        importlib.reload(config)
        
        # When env vars are empty strings, config should have empty values
        assert config.TELEGRAM_BOT_TOKEN == ''
        assert config.TELEGRAM_CHAT_ID == ''
        assert config.GEMINI_API_KEY == ''