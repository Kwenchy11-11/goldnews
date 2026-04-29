# 🥇 Gold News Telegram Bots

โปรเจกต์นี้มี Telegram Bot **2 ตัว**:

| Bot | Token | คำสั่ง | หน้าที่ |
|-----|-------|--------|---------|
| **GoldNews Bot** | `8673794544:...` | รัน `python3 main.py` | ข่าวทอง + ปฏิทินเศรษฐกิจ อัตโนมัติ |
| **Predictions Bot** | `8639356568:...` | รัน `python3 predictions_bot.py` | Polymarket predictions ตามคำสั่ง |

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

### รัน Predictions Bot
```bash
python3 predictions_bot.py
```

### Auto Alert (optional)
ถ้าเปิด `ENABLE_AUTO_ALERTS=true` จะส่ง alert เมื่อมีตลาดใหม่ในช่วง 20:30-21:30 น.

---

## 📁 โครงสร้างโปรเจกต์

```
goldnews/
├── main.py              # GoldNews Bot entry point
├── predictions_bot.py   # Predictions Bot entry point
├── config.py            # Configuration (env vars, Thai translations)
├── news_fetcher.py      # ForexFactory economic calendar
├── realtime_news.py     # RSS feeds (MarketWatch, CNBC)
├── analyzer.py          # Gemini AI analysis
├── formatter.py         # Thai message formatting
├── telegram_bot.py      # Telegram API integration
├── scheduler.py         # 30-min interval scheduler
├── alert_monitor.py     # Polymarket new market alert monitor
├── polymarket_predictions.py  # Polymarket predictions fetcher
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
└── tests/               # Test suite (70+ tests)
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

## 📝 License

Private — สำหรับใช้งานส่วนตัว
