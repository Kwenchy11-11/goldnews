"""Tests for analyzer module."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from dataclasses import dataclass


def _make_event(**kwargs):
    """Helper to create a mock event with event_datetime set."""
    event = MagicMock()
    event.title = kwargs.get('title', 'Test Event')
    event.title_th = kwargs.get('title_th', 'เหตุการณ์ทดสอบ')
    event.country = kwargs.get('country', 'USD')
    event.impact = kwargs.get('impact', 'High')
    event.forecast = kwargs.get('forecast', '')
    event.previous = kwargs.get('previous', '')
    # Set event_datetime to a future time so comparison works
    event.event_datetime = kwargs.get('event_datetime', datetime.utcnow() + timedelta(hours=1))
    return event


def test_analyze_event_returns_analysis():
    """analyze_event should return an AnalysisResult with expected fields."""
    from analyzer import analyze_event, AnalysisResult

    mock_gemini_response = """IMPACT: HIGH
BIAS: BEARISH
CONFIDENCE: 75%
REASONING: CPI สูงกว่าคาดหมายถึงเงินเฟ้อยังเป็นปัญหา เฟดอาจขึ้นดอกเบี้ย ทองคำจะได้รับผลกระทบเชิงลบ"""

    event = _make_event(
        title='CPI m/m',
        title_th='ดัชนีราคาผู้บริโภค',
        forecast='0.3%',
        previous='0.4%',
    )

    with patch('analyzer.call_gemini', return_value=mock_gemini_response):
        result = analyze_event(event)

    assert isinstance(result, AnalysisResult)
    assert result.impact == 'HIGH'
    assert result.bias == 'BEARISH'
    assert result.confidence == 75
    assert 'CPI' in result.reasoning or 'เงินเฟ้อ' in result.reasoning


def test_analyze_event_handles_gemini_error():
    """analyze_event should return fallback analysis when Gemini fails."""
    from analyzer import analyze_event, AnalysisResult

    event = _make_event(
        title='CPI m/m',
        title_th='ดัชนีราคาผู้บริโภค',
        forecast='0.3%',
        previous='0.4%',
    )

    with patch('analyzer.call_gemini', return_value=None):
        result = analyze_event(event)

    assert isinstance(result, AnalysisResult)
    assert result.impact == 'HIGH'  # Falls back to event's own impact
    # Fallback now uses conditional analysis (NEUTRAL with conditional reasoning)
    assert result.bias == 'NEUTRAL'
    assert result.confidence == 40  # Fallback confidence
    assert 'Actual' in result.reasoning or 'คาด' in result.reasoning  # Conditional reasoning


def test_parse_gemini_response_extracts_fields():
    """parse_gemini_response should extract IMPACT, BIAS, CONFIDENCE, REASONING."""
    from analyzer import parse_gemini_response

    response = """IMPACT: HIGH
BIAS: BULLISH
CONFIDENCE: 80%
REASONING: เฟดลดดอกเบี้ย ทองคำน่าจะขึ้น"""

    result = parse_gemini_response(response)

    assert result['impact'] == 'HIGH'
    assert result['bias'] == 'BULLISH'
    assert result['confidence'] == 80
    assert 'เฟดลดดอกเบี้ย' in result['reasoning']


def test_build_analysis_prompt_includes_event_details():
    """build_analysis_prompt should include event details in Thai."""
    from analyzer import build_analysis_prompt

    event = _make_event(
        title='Non-Farm Payrolls',
        title_th='ตัวเลขการจ้างงานนอกภาคเกษตร',
        forecast='200K',
        previous='180K',
    )

    prompt = build_analysis_prompt(event)

    assert 'Non-Farm Payrolls' in prompt
    assert 'ตัวเลขการจ้างงานนอกภาคเกษตร' in prompt
    assert 'ทองคำ' in prompt  # Thai for gold
    assert 'IMPACT' in prompt
    assert 'BIAS' in prompt


def test_analyze_events_batch_processes_multiple():
    """analyze_events should process a list of events and return results."""
    from analyzer import analyze_events, AnalysisResult

    events = [
        _make_event(title='CPI m/m', title_th='ดัชนีราคาผู้บริโภค',
                    forecast='0.3%', previous='0.4%'),
        _make_event(title='FOMC', title_th='การประชุม FOMC',
                    forecast='', previous=''),
    ]

    mock_response = """IMPACT: HIGH
BIAS: BEARISH
CONFIDENCE: 70%
REASONING: ข่าวสำคัญที่มีผลต่อทอง"""

    with patch('analyzer.call_gemini', return_value=mock_response):
        results = analyze_events(events)

    assert len(results) == 2
    assert all(isinstance(r, AnalysisResult) for r in results)
