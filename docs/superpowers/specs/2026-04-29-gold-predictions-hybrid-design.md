# Gold Predictions Bot v2 — Hybrid Discovery + Auto-Alert

## Overview

Enhance the existing Gold Predictions Bot to use better market discovery (Hybrid approach) and add automatic alerts when new Fed/Gold/Econ markets appear.

## Current State

- `predictions_bot.py` — Standalone bot with `/predictions`, `/help`, `/start` commands
- Gamma API used for market data (no CLOB keys needed)
- Fetches markets via `tag_id=107` + query search
- Currently 45 relevant markets found (Fed rate cuts, recession)

## Problems to Solve

1. **Discovery gaps** — Some relevant markets may be missed by current keyword/filter approach
2. **No auto-alerts** — User must manually type `/predictions` to see data
3. **No market tracking** — Bot doesn't remember which markets it's already shown

## What to Build

### Part 1: Improved Market Discovery

Improve the `fetch_polymarket_predictions()` function in `predictions_bot.py`:

- Use `tag_id=107` (Economics) with limit=500 — **already done**
- Add search queries for specific market categories:
  - `fed funds rate`, `federal reserve`, `interest rate decision`
  - `core pce`, `core cpi`, `pce inflation`
  - `jobless claims`, `payroll`, `unemployment rate`
  - `treasury yield`, `dollar index`
- Track seen markets in a `seen_markets` set (by market ID, not question — questions can repeat across different markets)
- Better Thai translations:
  - "12 or more" → "12 ครั้งขึ้นไป" — **already done**
  - Show year when available
  - Show specific month when available (e.g., "May 2026 FOMC")

### Part 2: Auto-Alert System

Add background alert system that monitors for new markets:

**New config vars:**
```python
ENABLE_AUTO_ALERTS= true          # Enable/disable auto alerts
ALERT_CHECK_INTERVAL=5            # Minutes between checks
ALERT_WINDOW_START=20:30          # Thai time window start (when US data releases)
ALERT_WINDOW_END=21:30            # Thai time window end
ALERT_HIGH_VOLUME_ONLY=true       # Only alert if volume > threshold
ALERT_VOLUME_THRESHOLD=10000      # USD volume minimum
```

**New file: `alert_monitor.py`**
- Background thread that checks for new markets every `ALERT_CHECK_INTERVAL` minutes
- Maintains `seen_market_ids` set persisted to `data/seen_markets.json`
- During `ALERT_WINDOW_START` to `ALERT_WINDOW_END` (Thai time):
  - Check every `ALERT_CHECK_INTERVAL` minutes
- Outside window:
  - Check every 30 minutes
- When new market found:
  - Filter: Fed/Gold/Inflation/Employment keywords
  - Filter: Must have volume > `ALERT_VOLUME_THRESHOLD` if enabled
  - Send Telegram alert with market info
  - Add to seen set

**Alert message format:**
```
🎯 <b>ตลาดใหม่!</b>

• คำถาม: [Thai translation]
• ความน่าจะเป็น: [Yes/No with %]
• Volume: $[volume]

🔗 [Link to market]
```

### Part 3: Update predictions_bot.py

Integrate alert monitor into existing bot:
- On startup, optionally start alert monitor thread if `ENABLE_AUTO_ALERTS=true`
- Keep existing command handler for `/predictions`, `/help`, `/start`
- Add new command `/ alerts` to toggle alerts on/off

## File Changes

1. **Modify** `predictions_bot.py`:
   - Import `alert_monitor`
   - Start alert thread on boot if enabled
   - Add `/alerts` command

2. **Create** `alert_monitor.py`:
   - `AlertMonitor` class
   - `check_for_new_markets()` method
   - `should_check_now()` — considers time window
   - `send_new_market_alert()` method
   - Persist seen markets to JSON

3. **Create** `data/seen_markets.json`:
   - Initially empty `{"seen_ids": []}`

4. **Modify** `config.py`:
   - Add new env vars above

5. **Modify** `.env.example`:
   - Add new env vars

## Architecture

```
predictions_bot.py
├── predictions_bot.py (main)
│   ├── fetch_polymarket_predictions() — improved discovery
│   ├── format_predictions_message() — current
│   └── command_handler + alert_monitor thread
│
├── alert_monitor.py (new)
│   ├── AlertMonitor class
│   ├── check_for_new_markets()
│   ├── send_new_market_alert()
│   └── seen_market_ids (persisted)
│
└── data/seen_markets.json — tracks already-seen markets
```

## Implementation Order

1. Add new config vars
2. Create `alert_monitor.py` with basic polling
3. Integrate into `predictions_bot.py`
4. Improve `fetch_polymarket_predictions()` discovery
5. Test end-to-end

## Out of Scope

- CLOB Client V2 (requires API keys, Gamma API sufficient)
- Trading functionality
- Multiple chat IDs (single user for now)
