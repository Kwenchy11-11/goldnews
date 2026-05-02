"""
Backtest Evaluation Module

Provides CLI tools for evaluating the Event Impact Scoring Engine performance.
"""

from .report import main, EvaluationReport

__all__ = ['main', 'EvaluationReport']
