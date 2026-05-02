"""
Event Classifier Module (Layer 1)
=================================
Classifies economic events into categories and assigns base impact scores.
Uses deterministic keyword matching - no AI hallucination risk.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class EventCategory(Enum):
    """Categories of economic events that affect gold prices."""
    INFLATION = "inflation"
    LABOR = "labor"
    FED_POLICY = "fed_policy"
    GROWTH = "growth"
    YIELDS = "yields"
    GEOPOLITICS = "geopolitics"
    CONSUMER = "consumer"
    MANUFACTURING = "manufacturing"
    UNKNOWN = "unknown"


@dataclass
class ImpactScore:
    """Classification result for an economic event."""
    category: EventCategory
    base_impact_score: int
    gold_correlation: str
    typical_volatility: str
    key_drivers: list


EVENT_RULES: Dict[str, dict] = {
    'cpi': {
        'category': EventCategory.INFLATION,
        'base_score': 9,
        'correlation': 'negative',
        'volatility': 'high',
        'drivers': ['Fed rate expectations', 'USD strength', 'real yields']
    },
    'ppi': {
        'category': EventCategory.INFLATION,
        'base_score': 7,
        'correlation': 'negative',
        'volatility': 'medium',
        'drivers': ['Producer price pressures', 'pipeline inflation']
    },
    'pce': {
        'category': EventCategory.INFLATION,
        'base_score': 9,
        'correlation': 'negative',
        'volatility': 'high',
        'drivers': ["Fed's preferred inflation gauge", 'policy implications']
    },
    'core pce': {
        'category': EventCategory.INFLATION,
        'base_score': 10,
        'correlation': 'negative',
        'volatility': 'high',
        'drivers': ['Fed policy decisions', 'rate path']
    },
    'inflation': {
        'category': EventCategory.INFLATION,
        'base_score': 7,
        'correlation': 'negative',
        'volatility': 'medium',
        'drivers': ['Price pressures', 'purchasing power']
    },
    'non-farm': {
        'category': EventCategory.LABOR,
        'base_score': 9,
        'correlation': 'negative',
        'volatility': 'high',
        'drivers': ['Fed dual mandate', 'wage pressures', 'economic health']
    },
    'nfp': {
        'category': EventCategory.LABOR,
        'base_score': 9,
        'correlation': 'negative',
        'volatility': 'high',
        'drivers': ['Employment trend', 'wage growth', 'Fed policy']
    },
    'unemployment': {
        'category': EventCategory.LABOR,
        'base_score': 8,
        'correlation': 'positive',
        'volatility': 'high',
        'drivers': ['Labor market slack', 'economic weakness']
    },
    'jobless claims': {
        'category': EventCategory.LABOR,
        'base_score': 6,
        'correlation': 'positive',
        'volatility': 'medium',
        'drivers': ['Weekly labor data', 'trend indicator']
    },
    'wage': {
        'category': EventCategory.LABOR,
        'base_score': 7,
        'correlation': 'negative',
        'volatility': 'medium',
        'drivers': ['Inflation pressure', 'consumer spending']
    },
    'federal funds rate': {
        'category': EventCategory.FED_POLICY,
        'base_score': 10,
        'correlation': 'negative',
        'volatility': 'high',
        'drivers': ['Direct rate impact', 'USD strength', 'yield curve']
    },
    'fomc': {
        'category': EventCategory.FED_POLICY,
        'base_score': 10,
        'correlation': 'negative',
        'volatility': 'high',
        'drivers': ['Policy statement', 'dot plot', 'Powell guidance']
    },
    'fed chair': {
        'category': EventCategory.FED_POLICY,
        'base_score': 8,
        'correlation': 'negative',
        'volatility': 'high',
        'drivers': ['Forward guidance', 'policy bias']
    },
    'gdp': {
        'category': EventCategory.GROWTH,
        'base_score': 7,
        'correlation': 'negative',
        'volatility': 'medium',
        'drivers': ['Economic health', 'safe haven demand']
    },
    'treasury': {
        'category': EventCategory.YIELDS,
        'base_score': 6,
        'correlation': 'negative',
        'volatility': 'medium',
        'drivers': ['Real yields', 'opportunity cost of gold']
    },
    '10-year': {
        'category': EventCategory.YIELDS,
        'base_score': 6,
        'correlation': 'negative',
        'volatility': 'medium',
        'drivers': ['Benchmark yield', 'inflation expectations']
    },
    'retail sales': {
        'category': EventCategory.CONSUMER,
        'base_score': 7,
        'correlation': 'negative',
        'volatility': 'medium',
        'drivers': ['Consumer spending', 'economic momentum']
    },
    'consumer confidence': {
        'category': EventCategory.CONSUMER,
        'base_score': 5,
        'correlation': 'negative',
        'volatility': 'low',
        'drivers': ['Sentiment indicator', 'spending outlook']
    },
    'pmi': {
        'category': EventCategory.MANUFACTURING,
        'base_score': 6,
        'correlation': 'negative',
        'volatility': 'medium',
        'drivers': ['Manufacturing health', 'economic cycle']
    },
    'ism': {
        'category': EventCategory.MANUFACTURING,
        'base_score': 6,
        'correlation': 'negative',
        'volatility': 'medium',
        'drivers': ['Business activity', 'new orders']
    },
    'industrial production': {
        'category': EventCategory.MANUFACTURING,
        'base_score': 5,
        'correlation': 'negative',
        'volatility': 'low',
        'drivers': ['Output levels', 'capacity utilization']
    },
}


def classify_event(event: dict) -> ImpactScore:
    """Classify an economic event and assign impact score."""
    title_lower = event.get('title', '').lower()
    country = event.get('country', '').upper()
    impact = event.get('impact', '').upper()
    
    if country != 'USD':
        return ImpactScore(
            category=EventCategory.UNKNOWN,
            base_impact_score=2,
            gold_correlation='unknown',
            typical_volatility='low',
            key_drivers=['Non-USD event - limited XAU/USD impact']
        )
    
    matched_rule = None
    matched_keyword = ''
    
    for keyword, rule in EVENT_RULES.items():
        if keyword in title_lower:
            if len(keyword) > len(matched_keyword):
                matched_rule = rule
                matched_keyword = keyword
    
    if matched_rule:
        ff_impact_multiplier = {
            'HIGH': 1.0,
            'MEDIUM': 0.8,
            'LOW': 0.5
        }.get(impact, 0.8)
        
        adjusted_score = int(matched_rule['base_score'] * ff_impact_multiplier)
        adjusted_score = max(1, min(10, adjusted_score))
        
        return ImpactScore(
            category=matched_rule['category'],
            base_impact_score=adjusted_score,
            gold_correlation=matched_rule['correlation'],
            typical_volatility=matched_rule['volatility'],
            key_drivers=matched_rule['drivers']
        )
    
    return ImpactScore(
        category=EventCategory.UNKNOWN,
        base_impact_score=4,
        gold_correlation='mixed',
        typical_volatility='medium',
        key_drivers=['Unknown event type - monitor for surprises']
    )


def get_category_thai(category: EventCategory) -> str:
    """Get Thai translation for event category."""
    translations = {
        EventCategory.INFLATION: 'เงินเฟ้อ',
        EventCategory.LABOR: 'ตลาดแรงงาน',
        EventCategory.FED_POLICY: 'นโยบายเฟด',
        EventCategory.GROWTH: 'การเติบโต',
        EventCategory.YIELDS: 'อัตราผลตอบแทน',
        EventCategory.GEOPOLITICS: 'ภูมิรัฐศาสตร์',
        EventCategory.CONSUMER: 'ผู้บริโภค',
        EventCategory.MANUFACTURING: 'การผลิต',
        EventCategory.UNKNOWN: 'ไม่ระบุประเภท'
    }
    return translations.get(category, 'อื่นๆ')
