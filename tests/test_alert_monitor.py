"""Tests for alert_monitor module."""
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
from datetime import datetime

import pytest

import alert_monitor


class TestShouldCheckNow:
    """Tests for should_check_now function."""

    def test_disabled_returns_false(self):
        """When ENABLE_AUTO_ALERTS is False, should return False."""
        with patch.object(alert_monitor.config, 'ENABLE_AUTO_ALERTS', False):
            result = alert_monitor.should_check_now()
            assert result == False

    def test_during_window_returns_true(self):
        """During 20:30-21:30 TH, should return True."""
        with patch.object(alert_monitor.config, 'ENABLE_AUTO_ALERTS', True):
            with patch.object(alert_monitor, 'is_in_alert_window', return_value=True):
                result = alert_monitor.should_check_now()
                assert result == True

    def test_outside_window_no_last_check_returns_true(self):
        """Outside window with no last_check file, should return True (first check)."""
        with patch.object(alert_monitor.config, 'ENABLE_AUTO_ALERTS', True):
            with patch.object(alert_monitor, 'is_in_alert_window', return_value=False):
                with patch.object(alert_monitor, 'load_seen_markets', return_value={'seen_ids': [], 'last_check': ''}):
                    result = alert_monitor.should_check_now()
                    assert result == True


class TestLoadSeenMarkets:
    """Tests for load_seen_markets function."""

    def test_creates_file_if_not_exists(self, tmp_path):
        """If seen_markets.json doesn't exist, creates empty."""
        test_file = tmp_path / "seen_markets.json"

        # Mock the file path
        with patch.object(alert_monitor, 'SEEN_MARKETS_FILE', str(test_file)):
            result = alert_monitor.load_seen_markets()

        assert 'seen_ids' in result
        assert isinstance(result['seen_ids'], list)

    def test_loads_existing_file(self, tmp_path):
        """Loads existing file correctly."""
        test_file = tmp_path / "seen_markets.json"
        test_data = {'seen_ids': ['market1', 'market2'], 'last_check': '2026-04-29T10:00:00'}
        test_file.write_text(json.dumps(test_data))

        with patch.object(alert_monitor, 'SEEN_MARKETS_FILE', str(test_file)):
            result = alert_monitor.load_seen_markets()

        assert result['seen_ids'] == ['market1', 'market2']


class TestMarketAlert:
    """Tests for MarketAlert dataclass."""

    def test_market_alert_creation(self):
        """Can create a MarketAlert."""
        alert = alert_monitor.MarketAlert(
            market_id="test123",
            question="Will Fed cut rates?",
            question_th="เฟดจะลดดอกเบี้ยหรือไม่?",
            outcomes=[{'name': 'Yes', 'price': 0.6}, {'name': 'No', 'price': 0.4}],
            volume=50000,
            url="https://polymarket.com/event/test",
            category="fed",
        )

        assert alert.market_id == "test123"
        assert alert.question_th == "เฟดจะลดดอกเบี้ยหรือไม่?"
        assert alert.volume == 50000


class TestFormatAlertMessage:
    """Tests for format_alert_message function."""

    def test_format_alert_message(self):
        """Formats alert correctly."""
        alert = alert_monitor.MarketAlert(
            market_id="test123",
            question="Will Fed cut rates?",
            question_th="เฟดจะลดดอกเบี้ยหรือไม่?",
            outcomes=[{'name': 'Yes', 'price': 0.6}, {'name': 'No', 'price': 0.4}],
            volume=50000,
            url="https://polymarket.com/event/test",
            category="fed",
        )

        message = alert_monitor.format_alert_message(alert)

        assert "ตลาดใหม่!" in message
        assert "เฟดจะลดดอกเบี้ยหรือไม่?" in message
        assert "$50,000" in message
        assert "ดูตลาด" in message


class TestCategorizeMarket:
    """Tests for _categorize_market function."""

    def test_categorizes_fed(self):
        """Correctly categorizes Fed markets."""
        result = alert_monitor._categorize_market("Will Fed cut rates?", "")
        assert result == "fed"

    def test_categorizes_gold(self):
        """Correctly categorizes gold markets."""
        result = alert_monitor._categorize_market("Gold price above $3000?", "")
        assert result == "gold"

    def test_categorizes_inflation(self):
        """Correctly categorizes inflation markets."""
        result = alert_monitor._categorize_market("Will CPI be above 3%?", "")
        assert result == "inflation"
