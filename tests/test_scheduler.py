"""Tests for scheduler module."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


def test_is_market_hours_weekday():
    """is_market_hours should return True on weekdays."""
    from scheduler import is_market_hours
    
    # Monday through Friday
    for weekday in range(5):
        with patch('scheduler.datetime') as mock_dt:
            mock_now = MagicMock()
            mock_now.weekday.return_value = weekday
            mock_dt.now.return_value = mock_now
            assert is_market_hours() is True


def test_is_market_hours_weekend():
    """is_market_hours should return False on weekends when MARKET_HOURS_ONLY is True."""
    from scheduler import is_market_hours
    
    with patch('scheduler.config.MARKET_HOURS_ONLY', True):
        # Saturday (5) and Sunday (6)
        for weekday in [5, 6]:
            with patch('scheduler.datetime') as mock_dt:
                mock_now = MagicMock()
                mock_now.weekday.return_value = weekday
                mock_dt.now.return_value = mock_now
                assert is_market_hours() is False


def test_is_market_hours_weekend_no_restriction():
    """is_market_hours should return True on weekends when MARKET_HOURS_ONLY is False."""
    from scheduler import is_market_hours
    
    with patch('scheduler.config.MARKET_HOURS_ONLY', False):
        assert is_market_hours() is True


def test_run_news_cycle_calls_all_steps():
    """run_news_cycle should fetch news, analyze, format, and send."""
    from scheduler import run_news_cycle
    from analyzer import AnalysisResult, MarketSummary
    
    mock_event = MagicMock(title='CPI', title_th='ดัชนีราคาผู้บริโภค', impact='High', country='USD', forecast='0.3%', previous='0.4%')
    mock_analysis = AnalysisResult(
        event_title='CPI', event_title_th='ดัชนีราคาผู้บริโภค',
        impact='HIGH', bias='BULLISH', confidence=75,
        reasoning='CPI สูงกว่าคาด', country='USD', forecast='0.3%', previous='0.4%'
    )
    mock_summary = MarketSummary(
        overall_bias='BULLISH', gold_outlook='ทองคำมีแนวโน้มขึ้น',
        key_times='20:30 FOMC', usd_impact='USD อ่อนตัว', confidence=70
    )
    mock_market = MagicMock(title='Gold above $3000')
    
    with patch('scheduler.news_fetcher.fetch_all_news') as mock_fetch, \
         patch('scheduler.analyzer.analyze_events_batch') as mock_analyze, \
         patch('scheduler.formatter.format_daily_summary') as mock_format, \
         patch('scheduler.telegram_bot.send_message_with_retry') as mock_send:
        
        mock_fetch.return_value = {'events': [mock_event], 'markets': [mock_market]}
        mock_analyze.return_value = ([mock_analysis], mock_summary)
        mock_format.return_value = "Test message"
        mock_send.return_value = True
        
        result = run_news_cycle()
        
        mock_fetch.assert_called_once()
        mock_analyze.assert_called_once()
        mock_format.assert_called_once()
        mock_send.assert_called_once()
        assert result is True


def test_run_news_cycle_handles_no_events():
    """run_news_cycle should handle case with no relevant events."""
    from scheduler import run_news_cycle
    
    with patch('scheduler.news_fetcher.fetch_all_news') as mock_fetch, \
         patch('scheduler.analyzer.analyze_events_batch') as mock_analyze, \
         patch('scheduler.formatter.format_daily_summary') as mock_format, \
         patch('scheduler.telegram_bot.send_message_with_retry') as mock_send:
        
        mock_fetch.return_value = {'events': [], 'markets': []}
        mock_format.return_value = "No events message"
        mock_send.return_value = True
        
        result = run_news_cycle()
        
        assert result is True


def test_run_news_cycle_handles_fetch_error():
    """run_news_cycle should handle fetch errors gracefully."""
    from scheduler import run_news_cycle
    
    with patch('scheduler.news_fetcher.fetch_all_news', side_effect=Exception('API error')), \
         patch('scheduler.telegram_bot.send_error_alert') as mock_error:
        
        mock_error.return_value = True
        
        result = run_news_cycle()
        
        assert result is False