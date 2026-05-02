"""
Tests for Backtest Report Generator
"""

import json
import os
import tempfile
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import pytest

# Import the modules we're testing
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.backtest_report import (
    ReportSection,
    BacktestReportGenerator,
    generate_backtest_report
)
from core.backtest_engine import BacktestResult, BacktestEngine, PredictionDirection, OutcomeResult, BacktestTrade


class TestReportSection:
    """Test ReportSection dataclass"""
    
    def test_creation(self):
        """Test creating a ReportSection"""
        section = ReportSection(
            title="Test Section",
            content="Test content here"
        )
        
        assert section.title == "Test Section"
        assert section.content == "Test content here"
        assert section.data is None
    
    def test_creation_with_data(self):
        """Test creating a ReportSection with data"""
        section = ReportSection(
            title="Stats",
            content="Stats content",
            data={'accuracy': 75.5}
        )
        
        assert section.data == {'accuracy': 75.5}


class TestBacktestReportGenerator:
    """Test BacktestReportGenerator"""
    
    def test_initialization(self):
        """Test generator initialization"""
        generator = BacktestReportGenerator()
        
        assert generator.engine is not None
        assert generator.sections == []
    
    def test_generate_report_empty(self):
        """Test report generation with no results"""
        generator = BacktestReportGenerator()
        generator.engine.results = []
        
        report = generator.generate_report()
        
        assert "BACKTEST REPORT" in report
        assert "Total Events Analyzed: 0" in report
    
    def test_generate_report_with_results(self):
        """Test report generation with results"""
        generator = BacktestReportGenerator()
        
        # Create test results
        generator.engine.results = [
            BacktestResult(
                event_id="1",
                event_title="CPI y/y",
                event_date=datetime(2024, 1, 15, 8, 30),
                event_category="USD",
                impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH,
                confidence=0.85,
                outcome_15m=OutcomeResult.CORRECT,
                trade_15m=BacktestTrade(2000, 2010, PredictionDirection.BULLISH)
            ),
            BacktestResult(
                event_id="2",
                event_title="NFP",
                event_date=datetime(2024, 1, 16, 8, 30),
                event_category="USD",
                impact_score=-5.0,
                predicted_direction=PredictionDirection.BEARISH,
                confidence=0.80,
                outcome_15m=OutcomeResult.INCORRECT,
                trade_15m=BacktestTrade(2000, 2010, PredictionDirection.BEARISH)
            )
        ]
        
        report = generator.generate_report()
        
        assert "BACKTEST REPORT" in report
        assert "Total Events Analyzed: 2" in report
        assert "OVERALL SUMMARY" in report
        assert "CPI y/y" in report
        assert "NFP" in report
    
    def test_categorize_events(self):
        """Test event categorization"""
        generator = BacktestReportGenerator()
        
        generator.engine.results = [
            BacktestResult(
                event_id="1", event_title="CPI y/y", event_date=datetime.now(),
                event_category="USD", impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8
            ),
            BacktestResult(
                event_id="2", event_title="NFP", event_date=datetime.now(),
                event_category="USD", impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8
            ),
            BacktestResult(
                event_id="3", event_title="FOMC Statement", event_date=datetime.now(),
                event_category="USD", impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8
            ),
            BacktestResult(
                event_id="4", event_title="GDP q/q", event_date=datetime.now(),
                event_category="USD", impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8
            ),
            BacktestResult(
                event_id="5", event_title="Retail Sales", event_date=datetime.now(),
                event_category="USD", impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8
            ),
            BacktestResult(
                event_id="6", event_title="Factory Orders", event_date=datetime.now(),
                event_category="USD", impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8
            )
        ]
        
        categories = generator._categorize_events()
        
        assert len(categories['CPI/Inflation']) == 1
        assert len(categories['NFP/Labor']) == 1
        assert len(categories['FOMC/Fed']) == 1
        assert len(categories['GDP/Growth']) == 1
        assert len(categories['Retail Sales']) == 1
        assert len(categories['Other']) == 1
    
    def test_create_accuracy_chart(self):
        """Test accuracy chart creation"""
        generator = BacktestReportGenerator()
        
        generator.engine.results = [
            BacktestResult(
                event_id="1", event_title="CPI", event_date=datetime.now(),
                event_category="USD", impact_score=7.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8,
                outcome_15m=OutcomeResult.CORRECT
            ),
            BacktestResult(
                event_id="2", event_title="NFP", event_date=datetime.now(),
                event_category="USD", impact_score=4.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8,
                outcome_15m=OutcomeResult.CORRECT
            ),
            BacktestResult(
                event_id="3", event_title="PPI", event_date=datetime.now(),
                event_category="USD", impact_score=2.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8,
                outcome_15m=OutcomeResult.INCORRECT
            )
        ]
        
        chart = generator._create_accuracy_chart('15m')
        
        assert 'High' in chart
        assert 'Med' in chart
        assert 'Low' in chart
        assert '100.0%' in chart  # High bucket should have 100% accuracy
    
    def test_export_json(self):
        """Test JSON export"""
        generator = BacktestReportGenerator()
        
        generator.engine.results = [
            BacktestResult(
                event_id="1", event_title="CPI", event_date=datetime(2024, 1, 15, 8, 30),
                event_category="USD", impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8
            )
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "report.json")
            generator.export_json(filepath)
            
            assert os.path.exists(filepath)
            
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            assert data['total_events'] == 1
            assert len(data['results']) == 1
    
    def test_export_csv(self):
        """Test CSV export"""
        generator = BacktestReportGenerator()
        
        generator.engine.results = [
            BacktestResult(
                event_id="1", event_title="CPI", event_date=datetime(2024, 1, 15, 8, 30),
                event_category="USD", impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8,
                outcome_15m=OutcomeResult.CORRECT
            )
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "report.csv")
            generator.export_csv(filepath)
            
            assert os.path.exists(filepath)
            
            with open(filepath, 'r') as f:
                content = f.read()
            
            assert 'Event ID' in content
            assert 'CPI' in content
    
    def test_export_text(self):
        """Test text export"""
        generator = BacktestReportGenerator()
        
        generator.engine.results = [
            BacktestResult(
                event_id="1", event_title="CPI", event_date=datetime.now(),
                event_category="USD", impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8
            )
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "report.txt")
            generator.export_text(filepath)
            
            assert os.path.exists(filepath)
            
            with open(filepath, 'r') as f:
                content = f.read()
            
            assert 'BACKTEST REPORT' in content
            assert 'CPI' in content
    
    def test_print_summary(self, capsys):
        """Test summary printing"""
        generator = BacktestReportGenerator()
        
        generator.engine.results = [
            BacktestResult(
                event_id="1", event_title="CPI", event_date=datetime.now(),
                event_category="USD", impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8,
                outcome_15m=OutcomeResult.CORRECT,
                trade_15m=BacktestTrade(2000, 2010, PredictionDirection.BULLISH)
            )
        ]
        
        generator.print_summary()
        
        captured = capsys.readouterr()
        assert 'BACKTEST SUMMARY' in captured.out
        assert 'Total Events' in captured.out
        assert 'Accuracy' in captured.out


class TestConvenienceFunctions:
    """Test convenience functions"""
    
    def test_generate_backtest_report_text(self):
        """Test generate_backtest_report with text format"""
        engine = BacktestEngine()
        engine.results = [
            BacktestResult(
                event_id="1", event_title="CPI", event_date=datetime.now(),
                event_category="USD", impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8
            )
        ]
        
        report = generate_backtest_report(engine, format='text')
        
        assert 'BACKTEST REPORT' in report
        assert 'CPI' in report
    
    def test_generate_backtest_report_json(self):
        """Test generate_backtest_report with JSON format"""
        engine = BacktestEngine()
        engine.results = [
            BacktestResult(
                event_id="1", event_title="CPI", event_date=datetime.now(),
                event_category="USD", impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8
            )
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "report.json")
            result = generate_backtest_report(engine, output_path=filepath, format='json')
            
            assert result == ""  # JSON returns empty string
            assert os.path.exists(filepath)
    
    def test_generate_backtest_report_csv(self):
        """Test generate_backtest_report with CSV format"""
        engine = BacktestEngine()
        engine.results = [
            BacktestResult(
                event_id="1", event_title="CPI", event_date=datetime.now(),
                event_category="USD", impact_score=5.0,
                predicted_direction=PredictionDirection.BULLISH, confidence=0.8
            )
        ]
        
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "report.csv")
            result = generate_backtest_report(engine, output_path=filepath, format='csv')
            
            assert result == ""  # CSV returns empty string
            assert os.path.exists(filepath)
