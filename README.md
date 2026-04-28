# 🥇 Gold News Telegram Bot

บอท Telegram แจ้งเตือนข่าวทองคำ (XAU/USD) แบบ real-time พร้อมวิเคราะห์ผลกระทบต่อราคาทองคำ

## ✨ ฟีเจอร์

- **📰 ข่าวสด Real-Time** — ดึงข่าวจาก MarketWatch, CNBC RSS feeds อัตโนมัติ
- **📅 ปฏิทินเศรษฐกิจ** — ดึงข้อมูลจาก ForexFactory economic calendar
- **🤖 AI วิเคราะห์** — ใช้ Gemini API วิเคราะห์ผลกระทบต่อทองคำแบบมีเงื่อนไข (Actual vs Forecast)
- **⚠️ คำเตือนข่าวชนกัน** — แจ้งเตือนเมื่อมีข่าว High Impact หลายตัวประกาศพร้อมกัน (ระวัง V-Shape)
- **🇹🇭 ภาษาไทย** — ข้อความทั้งหมดเป็นภาษาไทย พร้อมเวลา ICT
- **🔄 อัตโนมัติ** — ตรวจสอบข่าวทุก 30 นาที เฉพาะวันจันทร์-ศุกร์

## 📋 ตัวอย่างข้อความ

```
📋 สรุปข่าวทองคำ
📅 ข่าววันที่ 30 เมษายน 2569 (อัปเดต 23:50 น.)

⚠️ คำเตือน: ข่าวชนกัน!
   พฤหัสบดีที่ 30 เมษายน 2569 เวลา 19:30 น.: GDP + Core PCE + ECI
   🚨 ระวังความผันผวนรุนแรง (V-Shape)

⏳ กำลังจะมา
🔴 1. Federal Funds Rate ⏳ [กำลังจะมา]
   🏳️ ประเทศ: USD
   ⏰ เวลา: พฤหัสบดีที่ 30 เมษายน 2569 เวลา 01:00 น.
   💡 หากขึ้นดอกเบี้ย → USD แข็ง → 📉 ทองลง | ...

📰 ข่าวสดล่าสุด:
• UAE quits OPEC: Here's what it means for oil prices (2 ชม.ที่แล้ว)
```

## 🚀 การติดตั้ง

### 1. สร้าง Telegram Bot
1. เปิด Telegram แล้วคุยกับ `@BotFather`
2. ส่ง `/newbot` และตั้งชื่อ bot
3. เก็บ **Bot Token** ไว้

### 2. หา Chat ID
1. เปิด bot ที่สร้าง แล้วส่งข้อความอะไรก็ได้
2. เปิด `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. หา `"chat":{"id":123456789}` — นั่นคือ Chat ID

### 3. หา Gemini API Key
1. ไปที่ https://aistudio.google.com/
2. สร้าง API Key

### 4. ติดตั้งและรัน

```bash
# Clone repository
git clone https://github.com/<your-username>/goldnews.git
cd goldnews

# ติดตั้ง dependencies
pip3 install -r requirements.txt

# สร้างไฟล์ .env
cp .env.example .env

# แก้ไข .env ใส่ค่าของคุณ
# TELEGRAM_BOT_TOKEN=your_bot_token
# TELEGRAM_CHAT_ID=your_chat_id
# GEMINI_API_KEY=your_gemini_key

# รันทดสอบ (ส่งครั้งเดียว)
python3 main.py --once

# รันโหมด daemon (ส่งอัตโนมัติทุก 30 นาที)
python3 main.py
```

## 📁 โครงสร้างโปรเจกต์

```
goldnews/
├── main.py              # Entry point
├── config.py            # Configuration (env vars, Thai translations)
├── news_fetcher.py      # ForexFactory economic calendar
├── realtime_news.py     # RSS feeds (MarketWatch, CNBC)
├── analyzer.py          # Gemini AI analysis
├── formatter.py         # Thai message formatting
├── telegram_bot.py      # Telegram API integration
├── scheduler.py         # 30-min interval scheduler
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
└── tests/               # Test suite (38 tests)
```

## ⚙️ การตั้งค่า

| ตัวแปร | คำอธิบาย | ค่าเริ่มต้น |
|--------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | - |
| `TELEGRAM_CHAT_ID` | Chat ID ที่ต้องการส่งข่าว | - |
| `GEMINI_API_KEY` | Google Gemini API Key | - |
| `CHECK_INTERVAL` | ความถี่ในการตรวจสอบ (นาที) | 30 |
| `MARKET_HOURS_ONLY` | ส่งเฉพาะวันจันทร์-ศุกร์ | true |
| `LOG_LEVEL` | ระดับ logging | INFO |

## 🧪 ทดสอบ

```bash
python3 -m pytest tests/ -v
```

## 📊 แหล่งข้อมูล

- **ForexFactory** — Economic calendar (https://nfs.faireconomy.media/ff_calendar_thisweek.json)
- **MarketWatch** — RSS news feed
- **CNBC** — RSS news feed
- **Google Gemini** — AI analysis

## ⚠️ ข้อจำกัด

- ข่าวเศรษฐกิจสหรัฐฯ (GDP, CPI, PCE) = 19:30 หรือ 20:30 น. ICT
- ข่าว Fed/FOMC = 01:00 หรือ 02:00 น. ICT
- Gemini API มี rate limit — หากเกินจะใช้ fallback analysis แทน

## 📝 License

Private — สำหรับใช้งานส่วนตัว
