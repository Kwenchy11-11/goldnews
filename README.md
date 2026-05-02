# 🥇 Gold News Telegram Bots

โปรเจกต์นี้มี Telegram Bot **2 ตัว** พร้อม **Event Impact Engine** สำหรับวิเคราะห์ผลกระทบข่าวเศรษฐกิจต่อทองคำแบบ deterministic (ไม่ใช้ AI ตัดสินใจ):

| Bot | Token | คำสั่ง | หน้าที่ |
|-----|-------|--------|---------|
| **GoldNews Bot** | `8673794544:...` | รัน `python3 main.py` | ข่าวทอง + ปฏิทินเศรษฐกิจ อัตโนมัติ |
| **Predictions Bot** | `8639356568:...` | รัน `python3 predictions_bot.py` | Polymarket predictions ตามคำสั่ง |

---

## 🎯 Event Impact Scoring Engine (NEW!)

ระบบวิเคราะห์ผลกระทบข่าวเศรษฐกิจต่อทองคำแบบ **Rule-Based (Deterministic)** — ไม่มี AI Hallucination!

### หลักการทำงาน 5 Layers
```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1: Event Classifier                                  │
│  → จัดหมวดหมู่ข่าว (เงินเฟ้อ, แรงงาน, เฟด, ฯลฯ)            │
│  → ให้คะแนนพื้นฐาน (0-10)                                   │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Surprise Engine                                   │
│  → คำนวณ deviation: Actual vs Forecast                      │
│  → ให้คะแนน surprise (-10 ถึง +10)                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Consensus Layer                                   │
│  → ดึงข้อมูล Polymarket/Kalshi                              │
│  → เปรียบเทียบกับการคำนวณของเรา                             │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: Event Logger                                      │
│  → บันทึกข้อมูลลง SQLite (สำหรับ backtest)                  │
├─────────────────────────────────────────────────────────────┤
│  Layer 5: Composite Scorer                                  │
│  → รวมคะแนน: Surprise 70% + Base 20% + Consensus 10%        │
│  → ได้คะแนนสุดท้าย (-10 ถึง +10)                            │
└─────────────────────────────────────────────────────────────┘
```

### ข้อดีของระบบ
- ✅ **ไม่มี AI Hallucination** — ใช้ rule engine ตัดสินใจ 100%
- ✅ **Reproducible** — ข่าวเดียวกัน คะแนนเดียวกันเสมอ
- ✅ **Explainable** — บอกได้ว่าทำไมถึงได้คะแนนนี้
- ✅ **Fast** — ไม่ต้องรอ AI API
- ✅ **AI ใช้แค่ภาษา** — Gemini ใช้แปล Thai เท่านั้น

### Alert Types
1. **Pre-Event Alert** — แจ้งเตือนก่อนข่าวสำคัญ 15 นาที
2. **Post-Event Alert** — ส่งผลวิเคราะห์หลังข่าวออก พร้อม impact score

---

## 🤖 Bot 1: GoldNews Bot (@GoldNews_mifibot)

บอทแจ้งเตือนข่าวทองคำ (XAU/USD) แบบ real-time พร้อมวิเคราะห์ผลกระทบต่อราคาทองคำ

### ฟีเจอร์
- **📰 ข่าวสด Real-Time** — ดึงข่าวจาก MarketWatch, CNBC RSS feeds อัตโนมัติ
- **📅 ปฏิทินเศรษฐกิจ** — ดึงข้อมูลจาก ForexFactory economic calendar
- **🤖 AI วิเคราะห์** — ใช้ Gemini API วิเคราะห์ผลกระทบต่อทองคำแบบมีเงื่อนไข (Actual vs Forecast)
- **⚠️ คำเตือนข่าวชนกัน** — แจ้งเตือนเมื่อมีข่าว High Impact หลายตัวประกาศพร้อมกัน
- **🇹🇭 ภาษาไทย** — ข้อความทั้งหมดเป็นภาษาไทย พร้อมเวลา ICT
- **🔄 อัตโนมัติ** — ตรวจสอบข่าวทุก 30 นาที เฉพาะวันจันทร์-ศุกร์

### รัน GoldNews Bot
```bash
# รันทดสอบ (ส่งครั้งเดียว)
python3 main.py --once

# รันโหมด daemon (ส่งอัตโนมัติทุก 30 นาที)
python3 main.py
```

---

## 🎯 Bot 2: Predictions Bot

บอทสำหรับดูตลาดคาดการณ์จาก Polymarket พร้อมคำอธิบายภาษาไทย

### ฟีเจอร์
- **🎯 /predictions** — ดูตลาด Polymarket ล่าสุด (gold, fed, inflation, employment, economy)
- **🔔 /alerts** — ดูสถานะ auto-alert
- **🤖 AI วิเคราะห์** — คำอธิบาย beginner-friendly สำหรับมือใหม่
- **🇹🇭 ภาษาไทย** — ทั้งคำถามและคำอธิบายเป็นไทย
- **📅 Auto Push รายวัน** — ส่ง predictions อัตโนมัติทุกวัน เวลา 08:00 น. (เวลาไทย)
- **🌏 Timezone ไทย** — ใช้ Asia/Bangkok (UTC+7) ทั้งหมด

### รัน Predictions Bot
```bash
python3 predictions_bot.py
```

### Auto Alert (optional)
ถ้าเปิด `ENABLE_AUTO_ALERTS=true` จะส่ง alert เมื่อมีตลาดใหม่ในช่วง 20:30-21:30 น.

### Daily Predictions Push (NEW!)
- ส่ง predictions อัตโนมัติ **1 ครั้งต่อวัน เวลา 08:00 น.** (เวลาไทย)
- ใช้ timezone `Asia/Bangkok` (UTC+7) ตลอด
- ปรับเวลาได้ผ่าน `PREDICTIONS_DAILY_TIME` (เช่น `09:00` หรือ `07:30`)
- ปิดได้ผ่าน `PREDICTIONS_DAILY_PUSH_ENABLED=false`

---

## 📁 โครงสร้างโปรเจกต์

```
goldnews/
├── main.py                     # GoldNews Bot entry point
├── predictions_bot.py          # Predictions Bot entry point
├── config.py                   # Configuration (env vars, Thai translations)
│
├── Event Impact Engine (NEW!)
│   ├── src/core/
│   │   ├── event_classifier.py     # Layer 1: จัดหมวดหมู่ข่าว
│   │   ├── surprise_engine.py      # Layer 2: คำนวณ surprise
│   │   ├── consensus_engine.py     # Layer 3: ข้อมูลตลาด
│   │   ├── event_logger.py         # Layer 4: บันทึกข้อมูล
│   │   └── event_impact_engine.py  # Layer 5: รวมคะแนน
│   └── event_classifier.py         # (root) classification entry point
│
├── news_fetcher.py             # ForexFactory economic calendar
├── realtime_news.py            # RSS feeds (MarketWatch, CNBC)
├── analyzer.py                 # Gemini AI analysis + Impact Engine integration
├── formatter.py                # Thai message formatting
├── telegram_bot.py             # Telegram API integration
├── scheduler.py                # 30-min interval scheduler + impact alerts
├── alert_monitor.py            # Polymarket new market alert monitor
├── polymarket_predictions.py   # Polymarket predictions fetcher
├── requirements.txt            # Python dependencies
├── .env.example                # Environment variables template
└── tests/                      # Test suite (221+ tests)
    ├── test_event_classifier.py
    ├── test_surprise_engine.py
    ├── test_consensus_engine.py
    ├── test_event_logger.py
    ├── test_event_impact_engine.py
    ├── test_analyzer_integration.py
    ├── test_impact_formatters.py
    ├── test_impact_config.py
    └── test_scheduler_integration.py
```

---

## ⚙️ การตั้งค่า

### .env สำหรับ GoldNews Bot
```env
TELEGRAM_BOT_TOKEN=8673794544:...    # GoldNews Bot token
TELEGRAM_CHAT_ID=8681197630
GEMINI_API_KEY=your_gemini_key
CHECK_INTERVAL=30
MARKET_HOURS_ONLY=true
```

### .env สำหรับ Predictions Bot
```env
PREDICTIONS_BOT_TOKEN=8639356568:...  # Predictions Bot token
ENABLE_AUTO_ALERTS=true
ALERT_CHECK_INTERVAL=5
ALERT_WINDOW_START=20:30
ALERT_WINDOW_END=21:30
ALERT_VOLUME_THRESHOLD=10000

# Daily Push Settings
PREDICTIONS_DAILY_TIME=08:00              # เวลาส่งอัตโนมัติ (รูปแบบ HH:MM, เวลาไทย)
PREDICTIONS_DAILY_PUSH_ENABLED=true      # เปิด/ปิดการส่งอัตโนมัติ
```

### .env สำหรับ Event Impact Engine (NEW!)
```env
# Enable/Disable Features
ENABLE_IMPACT_ENGINE=true           # เปิดใช้งานระบบ impact scoring
ENABLE_PRE_EVENT_ALERTS=true        # แจ้งเตือนก่อนข่าว
ENABLE_POST_EVENT_ALERTS=true       # แจ้งเตือนหลังข่าว
ENABLE_EVENT_LOGGING=true           # บันทึกข้อมูล

# Scoring Weights (ต้องรวมกัน = 1.0)
IMPACT_WEIGHT_SURPRISE=0.7          # น้ำหนัก surprise (70%)
IMPACT_WEIGHT_BASE=0.2              # น้ำหนัก base impact (20%)
IMPACT_WEIGHT_CONSENSUS=0.1         # น้ำหนัก consensus (10%)

# Alert Thresholds
ALERT_THRESHOLD_IMMEDIATE=6.0       # แจ้งเตือนทันทีเมื่อคะแนน >= 6
ALERT_THRESHOLD_HIGH=4.0            # แจ้งเตือนระดับสูงเมื่อคะแนน >= 4
ALERT_THRESHOLD_NORMAL=2.0          # แจ้งเตือนปกติเมื่อคะแนน >= 2

# Timing
PRE_EVENT_ALERT_MINUTES=15          # แจ้งเตือนก่อนข่าวกี่นาที
POST_EVENT_DELAY_MINUTES=5          # รอกี่นาทีหลังข่าวก่อนวิเคราะห์

# Database
EVENT_LOG_DB_PATH=data/events.db    # ที่เก็บข้อมูล

# Category Multipliers (ปรับผลกระทบตามหมวดหมู่)
FED_POLICY_MULTIPLIER=1.2           # ข่าวเฟดมีผลกระทบ 1.2x
GEOPOLITICS_MULTIPLIER=1.1          # ข่าว geopolitics 1.1x
MANUFACTURING_MULTIPLIER=0.8        # ข่าว manufacturing 0.8x
```

---

## 🚀 การติดตั้ง (ครั้งเดียว)

```bash
# Clone repository
git clone https://github.com/Kwenchy11-11/goldnews.git
cd goldnews

# ติดตั้ง dependencies
pip3 install -r requirements.txt

# สร้างไฟล์ .env
cp .env.example .env

# แก้ไข .env ใส่ค่าของคุณ
```

---

## 🧪 ทดสอบ

```bash
python3 -m pytest tests/ -v
```

---

## 📊 แหล่งข้อมูล

- **ForexFactory** — Economic calendar
- **MarketWatch** — RSS news feed
- **CNBC** — RSS news feed
- **Polymarket** — Prediction markets
- **Google Gemini** — AI analysis

---

## 🆕 Updates ล่าสุด

### May 2026 — Event Impact Engine (Major Feature!)
- ✨ **Event Impact Scoring Engine 5 Layers** — วิเคราะห์ผลกระทบแบบ deterministic
- ✨ **Pre-event alerts** — แจ้งเตือน 15 นาทีก่อนข่าวสำคัญ
- ✨ **Post-event alerts** — ส่งผลวิเคราะห์หลังข่าวออก
- ✨ **Composite scoring** — น้ำหนัก 70/20/10 (Surprise/Base/Consensus)
- ✨ **Event logging** — บันทึกข้อมูลลง SQLite สำหรับ backtest
- ✨ **221 tests** — comprehensive test coverage
- ✨ **Configuration** — ปรับ weights, thresholds, multipliers ผ่าน env vars

### May 2026 — Daily Predictions Schedule + Thai Timezone
- ✨ **เปลี่ยน auto-push จากทุกชั่วโมง → ทุกวันเวลา 08:00 น.**
- ✨ **ใช้ timezone ไทย (Asia/Bangkok UTC+7)** ทั้งหมด
- ✨ **เพิ่ม config ปรับเวลาส่งได้** (`PREDICTIONS_DAILY_TIME`)
- ✨ **เพิ่ม pytz dependency** สำหรับจัดการ timezone

### April 2026 — Predictions Display Fixes
- 🔧 แก้ไขการแสดงผล predictions (แสดงคำถามภาษาอังกฤษพร้อมตัวเลข)
- 🔧 ปรับปรุง Gold Sentiment Score calculation
- 🔧 แก้ไข emoji และ formatting

---

## 📝 License

Private — สำหรับใช้งานส่วนตัว
