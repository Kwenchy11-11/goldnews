"""
Polymarket Integration Module

Deterministic integration with Polymarket for market consensus data.
Uses public APIs only - no authentication required.

APIs:
- Gamma API: Market/event discovery
- CLOB API: Prices, spreads, price history
"""

from .client import PolymarketClient

__all__ = ['PolymarketClient']
