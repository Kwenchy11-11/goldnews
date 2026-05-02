# tests/test_event_classifier.py
import pytest
from event_classifier import classify_event, EventCategory, ImpactScore

def test_classify_cpi_event():
    """CPI should be classified as INFLATION with high impact."""
    event = {
        'title': 'Core CPI MoM',
        'country': 'USD',
        'impact': 'High'
    }
    result = classify_event(event)
    assert result.category == EventCategory.INFLATION
    assert result.base_impact_score >= 8
    assert result.gold_correlation == 'negative'

def test_classify_nfp_event():
    """Non-Farm Payrolls should be LABOR with high impact."""
    event = {
        'title': 'Non-Farm Employment Change',
        'country': 'USD',
        'impact': 'High'
    }
    result = classify_event(event)
    assert result.category == EventCategory.LABOR
    assert result.base_impact_score >= 7

def test_classify_gdp_event():
    """GDP should be GROWTH with medium-high impact."""
    event = {
        'title': 'GDP QoQ',
        'country': 'USD',
        'impact': 'Medium'
    }
    result = classify_event(event)
    assert result.category == EventCategory.GROWTH

def test_unknown_event_returns_safe_defaults():
    """Unknown events should return neutral classification."""
    event = {
        'title': 'Random Unknown Event',
        'country': 'AUD',
        'impact': 'Low'
    }
    result = classify_event(event)
    assert result.category == EventCategory.UNKNOWN
    assert result.base_impact_score == 2
