# Gold News Telegram Bot - Design Spec

**Date:** 2026-04-28
**Status:** Approved

## Overview

A dedicated Telegram bot that sends real-time gold-related news alerts with AI-powered impact analysis. Monitors ForexFactory economic calendar and Polymarket prediction markets, analyzes each event's impact on gold prices using Gemini API, and delivers Thai-language alerts to Telegram.

## Requirements

1. Send real-time gold-related news to Telegram via push notifications
2. Analyze news impact on gold prices using AI (Gemini)
3. Cover news affecting USD (which inversely impacts gold)
4. New, separate Telegram bot (new token via @BotFather)
5. Thai language for all messages and AI analysis
6. Run as a daemon process, checking every 30 minutes during market hours (Mon-Fri)

## Architecture

```
goldnews/
├── main.py              # Entry point, starts the daemon
├── config.py            # Configuration (env vars, constants)
├── scheduler.py         # 30-min interval scheduler, market hours check
├── news_fetcher.py      # ForexFactory + Polymarket data fetching
├── analyzer.py          # Gemini API impact analysis
├── telegram_bot.py      # Telegram message sending
├── formatter.py         # Thai message formatting
├── requirements.txt     # Dependencies
├── .env.example         # Template for environment variables
└── README.md            # Setup and usage docs
```

### Module Responsibilities

- **main.py**: Entry point. Initializes all modules, starts the scheduler loop.
- **config.py**: Loads environment variables, provides configuration constants. Uses `python-dotenv`.
- **scheduler.py**: Runs the news cycle every 30 minutes. Skips weekends. Uses `schedule` library or `time.sleep` loop.
- **news_fetcher.py**: Fetches ForexFactory economic calendar events (high/medium impact) and Polymarket gold prediction data. Returns structured data objects.
- **analyzer.py**: Sends news events to Gemini API with Thai prompt for gold impact analysis. Returns impact level, bias, confidence, and reasoning.
- **telegram_bot.py**: Sends formatted messages to Telegram via Bot API. Handles rate limiting and errors.
- **formatter.py**: Creates Thai-language Telegram messages with emoji indicators, sections for event info, analysis, and market sentiment.

## Data Flow

```
Every 30 min (Mon-Fri, market hours):
  1. scheduler.py triggers the news cycle
  2. news_fetcher.py fetches:
     a. ForexFactory economic calendar → upcoming high/medium impact events
     b. Polymarket gold prediction markets → current sentiment data
  3. analyzer.py sends events to Gemini API:
     - Prompt (Thai): "วิเคราะห์ผลกระทบของข่าวนี้ต่อราคาทองคำ"
     - Returns: impact level (สูง/กลาง/ต่ำ), bias (bullish/bearish/neutral), confidence %, reasoning
  4. formatter.py creates Thai Telegram messages:
     - Event name, time, country
     - Impact analysis with emoji indicators
     - Polymarket sentiment summary
  5. telegram_bot.py sends formatted messages to configured chat
```

## Message Format

```
🔔 ข่าวสำคัญ: Non-Farm Payrolls
📅 เวลา: 20:30 ICT (ศุกร์)
🇺🇸 ประเทศ: สหรัฐอเมริกา
⚡ ระดับผลกระทบ: สูง

📊 วิเคราะห์ผลกระทบต่อทองคำ:
📈 ทิศทาง: Bullish (เชิงบวกสำหรับทอง)
🎯 ความมั่นใจ: 75%
💡 สาเหตุ: ตัวเลข NFP ต่ำกว่าคาดหมายถึงเศรษฐกิจอ่อนแอ ทำให้ทองคำน่าสนใจเป็นสินทรัพย์หลบภัย

🎲 Polymarket Sentiment:
ทองคำขึ้น: 68% | ทองคำลง: 32%
```

## Configuration

Environment variables (`.env` file):

```
TELEGRAM_BOT_TOKEN=<new bot token from @BotFather>
TELEGRAM_CHAT_ID=<your chat/channel ID>
GEMINI_API_KEY=<your Gemini API key>
CHECK_INTERVAL=30          # minutes
MARKET_HOURS_ONLY=true     # only run Mon-Fri
LOG_LEVEL=INFO
```

## Error Handling

- **Network failures**: Retry 3 times with exponential backoff, then skip cycle
- **Gemini API errors**: Log error, send simplified message without analysis
- **Telegram API errors**: Log and retry on next cycle
- **No new events**: Skip sending, log "no new events"
- **Process crashes**: Simple restart wrapper script

## News Sources

1. **ForexFactory Economic Calendar**: `https://nfs.faireconomy.media/ff_calendar_thisweek.json` — fetches upcoming economic events with impact levels, country, time, forecast vs previous values.
2. **Polymarket Gold Markets**: Fetches prediction market data for gold price direction sentiment.

## AI Analysis

- Uses Gemini API (matching existing project patterns)
- Thai-language prompt for analysis
- Returns structured analysis: impact level, directional bias, confidence percentage, reasoning
- Focuses on gold price impact, including USD-related events (inverse correlation)

## Dependencies

- `requests` — HTTP requests for Telegram API and news sources
- `google-generativeai` — Gemini API client
- `python-dotenv` — Environment variable loading
- `schedule` — Task scheduling (or use `time.sleep` loop)

## Deployment

- Run as a daemon process: `python main.py`
- No Docker, no systemd — simple background process
- Can add systemd service file later if needed