"""
Configuration module for Gold News Telegram Bot.

Loads settings from environment variables with sensible defaults.
Uses python-dotenv to load from .env file if present.
"""

import os
import logging
from dotenv import load_dotenv
import pytz

# Load .env file if it exists
load_dotenv()

# Thailand timezone
THAI_TZ = pytz.timezone('Asia/Bangkok')

# Required settings
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')

# Predictions bot (separate bot for /predictions command only)
PREDICTIONS_BOT_TOKEN = os.getenv('PREDICTIONS_BOT_TOKEN', '')

# Auto-alert settings
ENABLE_AUTO_ALERTS = os.getenv('ENABLE_AUTO_ALERTS', 'false').lower() == 'true'
ALERT_CHECK_INTERVAL = int(os.getenv('ALERT_CHECK_INTERVAL', '15'))  # minutes - FOMC tonight: check every 15 min
ALERT_WINDOW_START = os.getenv('ALERT_WINDOW_START', '20:00')  # Thai time - Extended for FOMC
ALERT_WINDOW_END = os.getenv('ALERT_WINDOW_END', '23:00')    # Thai time - Extended for FOMC
ALERT_VOLUME_THRESHOLD = int(os.getenv('ALERT_VOLUME_THRESHOLD', '50000'))  # USD - Filter noise (was 20k, now 50k for higher quality)

# Predictions auto-push settings (once per day)
PREDICTIONS_DAILY_TIME = os.getenv('PREDICTIONS_DAILY_TIME', '08:00')  # HH:MM format (Thai time)
PREDICTIONS_DAILY_PUSH_ENABLED = os.getenv('PREDICTIONS_DAILY_PUSH_ENABLED', 'true').lower() == 'true'

# Optional settings with defaults
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '30'))  # minutes
MARKET_HOURS_ONLY = os.getenv('MARKET_HOURS_ONLY', 'true').lower() == 'true'
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# API URLs
FOREX_FACTORY_URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
POLYMARKET_URL = 'https://gamma-api.polymarket.com/markets'
TELEGRAM_API_URL = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}'
GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent'

# Thai keyword categories for gold-related news filtering
GOLD_KEYWORDS = ['gold', 'xau', 'xauusd', 'ทองคำ', 'ทอง', 'bullion', 'precious metal']
USD_KEYWORDS = ['fed', 'fomc', 'powell', 'ธนาคารกลาง', 'อัตราดอกเบี้ย', 'interest rate',
                'dollar', 'usd', 'dxy']
INFLATION_KEYWORDS = ['cpi', 'ppi', 'inflation', 'เงินเฟ้อ', 'ราคาผู้บริโภค', 'ราคาผู้ผลิต']
EMPLOYMENT_KEYWORDS = ['nfp', 'non-farm', 'unemployment', 'employment', 'จ้างงาน', 'ว่างงาน']

# All relevant keywords combined
RELEVANT_KEYWORDS = GOLD_KEYWORDS + USD_KEYWORDS + INFLATION_KEYWORDS + EMPLOYMENT_KEYWORDS

# Priority categories for display (hide politics/economy noise)
PRIORITY_CATEGORIES = ['fed', 'gold', 'inflation', 'geopolitics']
HIDDEN_CATEGORIES = ['politics', 'economy', 'employment']

# Smart alert keywords - immediate alert for new markets with these
SMART_ALERT_KEYWORDS = [
    'gold', 'xau', 'ทองคำ', 'ทอง',
    'fed', 'fomc', 'interest rate', 'ดอกเบี้ย',
    'ceasefire', 'หยุดยิง', 'cease-fire',
    'gaza', 'israel', 'hamas', 'ukraine', 'russia'
]

# Thai translations for common economic event titles
THAI_TRANSLATIONS = {
    'CPI': 'ดัชนีราคาผู้บริโภค',
    'Core CPI': 'ดัชนีราคาผู้บริโภค (Core)',
    'PPI': 'ดัชนีราคาผู้ผลิต',
    'Core PPI': 'ดัชนีราคาผู้ผลิต (Core)',
    'FOMC': 'การประชุม FOMC',
    'Fed': 'ธนาคารกลางสหรัฐ',
    'NFP': 'ตัวเลขการจ้างงานนอกภาคเกษตร',
    'Non-Farm Payrolls': 'ตัวเลขการจ้างงานนอกภาคเกษตร',
    'Unemployment Rate': 'อัตราการว่างงาน',
    'GDP': 'ผลิตภัณฑ์มวลรวมภายในประเทศ',
    'PMI': 'ดัชนีผู้จัดการฝ่ายจัดซื้อ',
    'Interest Rate': 'อัตราดอกเบี้ย',
    'Retail Sales': 'ยอดขายปลีก',
    'Industrial Production': 'การผลิตอุตสาหกรรม',
    'Housing Starts': 'การเริ่มต้นสร้างบ้าน',
    'Building Permits': 'ใบอนุญาตก่อสร้าง',
    'Consumer Confidence': 'ความเชื่อมั่นผู้บริโภค',
    'Durable Goods Orders': 'คำสั่งซื้อสินค้าคงทน',
    'Trade Balance': 'ดุลการค้า',
    'Initial Jobless Claims': 'จำนวนผู้ขอรับสวัสดิการว่างงาน',
}

# Impact level Thai translations
IMPACT_THAI = {
    'High': 'สูง',
    'Medium': 'กลาง',
    'Low': 'ต่ำ',
}

# Bias Thai translations
BIAS_THAI = {
    'BULLISH': 'เชิงบวก (ทองขึ้น)',
    'BEARISH': 'เชิงลบ (ทองลง)',
    'NEUTRAL': 'เป็นกลาง',
}

# Day names in Thai
DAY_THAI = {
    0: 'จันทร์',
    1: 'อังคาร',
    2: 'พุธ',
    3: 'พฤหัสบดี',
    4: 'ศุกร์',
    5: 'เสาร์',
    6: 'อาทิตย์',
}

# Event Impact Engine Configuration
# =============================================================================

# Composite score weights (must sum to 1.0)
IMPACT_WEIGHT_SURPRISE = float(os.getenv('IMPACT_WEIGHT_SURPRISE', '0.7'))  # Layer 2
IMPACT_WEIGHT_BASE = float(os.getenv('IMPACT_WEIGHT_BASE', '0.2'))        # Layer 1
IMPACT_WEIGHT_CONSENSUS = float(os.getenv('IMPACT_WEIGHT_CONSENSUS', '0.1'))  # Layer 3

# Alert thresholds (composite score thresholds)
ALERT_THRESHOLD_IMMEDIATE = float(os.getenv('ALERT_THRESHOLD_IMMEDIATE', '6.0'))
ALERT_THRESHOLD_HIGH = float(os.getenv('ALERT_THRESHOLD_HIGH', '4.0'))
ALERT_THRESHOLD_NORMAL = float(os.getenv('ALERT_THRESHOLD_NORMAL', '2.0'))

# Event logging database path
EVENT_LOG_DB_PATH = os.getenv('EVENT_LOG_DB_PATH', 'data/events.db')

# Pre-event alert timing (minutes before event)
PRE_EVENT_ALERT_MINUTES = int(os.getenv('PRE_EVENT_ALERT_MINUTES', '15'))

# Post-event analysis delay (minutes after event for data availability)
POST_EVENT_DELAY_MINUTES = int(os.getenv('POST_EVENT_DELAY_MINUTES', '5'))

# Impact engine feature flags
ENABLE_IMPACT_ENGINE = os.getenv('ENABLE_IMPACT_ENGINE', 'true').lower() == 'true'
ENABLE_PRE_EVENT_ALERTS = os.getenv('ENABLE_PRE_EVENT_ALERTS', 'true').lower() == 'true'
ENABLE_POST_EVENT_ALERTS = os.getenv('ENABLE_POST_EVENT_ALERTS', 'true').lower() == 'true'
ENABLE_EVENT_LOGGING = os.getenv('ENABLE_EVENT_LOGGING', 'true').lower() == 'true'

# Category-specific impact multipliers (adjust base scores by category)
CATEGORY_IMPACT_MULTIPLIERS = {
    'inflation': float(os.getenv('INFLATION_MULTIPLIER', '1.0')),
    'labor': float(os.getenv('LABOR_MULTIPLIER', '1.0')),
    'fed_policy': float(os.getenv('FED_POLICY_MULTIPLIER', '1.2')),  # Fed events are high impact
    'growth': float(os.getenv('GROWTH_MULTIPLIER', '1.0')),
    'yields': float(os.getenv('YIELDS_MULTIPLIER', '0.9')),
    'geopolitics': float(os.getenv('GEOPOLITICS_MULTIPLIER', '1.1')),
    'consumer': float(os.getenv('CONSUMER_MULTIPLIER', '0.9')),
    'manufacturing': float(os.getenv('MANUFACTURING_MULTIPLIER', '0.8')),
    'unknown': float(os.getenv('UNKNOWN_MULTIPLIER', '0.7')),
}

# Gold impact descriptions in Thai
GOLD_IMPACT_THAI = {
    'strong-bullish': 'ทองคำมีแนวโน้มขึ้นแรง',
    'bullish': 'ทองคำมีแนวโน้มขึ้น',
    'neutral': 'ผลกระทบต่อทองคำเป็นกลาง',
    'bearish': 'ทองคำมีแนวโน้มลง',
    'strong-bearish': 'ทองคำมีแนวโน้มลงแรง',
}

# Alert priority translations
ALERT_PRIORITY_THAI = {
    'immediate': 'ทันที',
    'high': 'สูง',
    'normal': 'ปกติ',
    'low': 'ต่ำ',
}

# Event category Thai names
CATEGORY_THAI = {
    'inflation': 'เงินเฟ้อ',
    'labor': 'ตลาดแรงงาน',
    'fed_policy': 'นโยบายเฟด',
    'growth': 'การเติบโต',
    'yields': 'ผลตอบแทนพันธบัตร',
    'geopolitics': 'ภูมิรัฐศาสตร์',
    'consumer': 'ผู้บริโภค',
    'manufacturing': 'การผลิต',
    'unknown': 'อื่นๆ',
}

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('goldnews')