# Fix Predictions Bot Daily Schedule with Thailand Timezone

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** เปลี่ยน predictions bot จากส่งทุกชั่วโมง เป็น **ส่งทุกวันเวลา 08:00 น. เวลาไทย** (Asia/Bangkok)

**Architecture:** แก้ไข `auto_push_predictions()` ใน `predictions_bot.py` ให้เช็คเวลาปัจจุบันตาม timezone ไทย แล้วส่งข้อความเมื่อถึงเวลาที่กำหนด (configurable)

**Tech Stack:** Python, pytz (timezone library)

---

## Files to Modify

1. `config.py` - เพิ่ม config สำหรับเวลาส่งรายวัน
2. `predictions_bot.py` - แก้ไข `auto_push_predictions()` ให้เช็ค timezone ไทยและส่งครั้งเดียวต่อวัน

---

## Task 1: Add Config for Daily Push Time

**Files:**
- Modify: `config.py:30-35`

- [ ] **Step 1: Add pytz import and daily time config**

Add after existing imports:
```python
import pytz

# Thailand timezone
THAI_TZ = pytz.timezone('Asia/Bangkok')
```

Add after auto-alert settings (around line 28):
```python
# Predictions auto-push settings (once per day)
PREDICTIONS_DAILY_TIME = os.getenv('PREDICTIONS_DAILY_TIME', '08:00')  # HH:MM format (Thai time)
PREDICTIONS_DAILY_PUSH_ENABLED = os.getenv('PREDICTIONS_DAILY_PUSH_ENABLED', 'true').lower() == 'true'
```

- [ ] **Step 2: Commit the config changes**

```bash
git add config.py
git commit -m "config: add daily push time settings for predictions bot"
```

---

## Task 2: Update auto_push_predictions to Use Thailand Timezone

**Files:**
- Modify: `predictions_bot.py:897-935`

- [ ] **Step 1: Import datetime and timezone at top of file**

Add imports after existing imports (around line 16-21):
```python
from datetime import datetime, timedelta
import pytz
```

- [ ] **Step 2: Replace auto_push_predictions function**

Replace the entire `auto_push_predictions()` function (lines 897-935) with:

```python
def auto_push_predictions():
    """
    Auto-push predictions once per day at configured time (Thai timezone).
    
    Checks every minute if it's time to send the daily update.
    Sends at PREDICTIONS_DAILY_TIME (default 08:00) Thailand time.
    """
    import threading

    def _run():
        last_sent_date = None
        thai_tz = pytz.timezone('Asia/Bangkok')
        
        logger.info(f"Auto-push scheduler started (daily at {config.PREDICTIONS_DAILY_TIME} Thai time)")
        
        while True:
            try:
                # Get current time in Thailand
                now = datetime.now(thai_tz)
                today_str = now.strftime('%Y-%m-%d')
                current_time = now.strftime('%H:%M')
                
                # Parse target time from config
                target_time = config.PREDICTIONS_DAILY_TIME
                
                # Check if it's time to send (and we haven't sent today)
                if current_time == target_time and last_sent_date != today_str:
                    if not config.PREDICTIONS_DAILY_PUSH_ENABLED:
                        logger.info("Daily push is disabled, skipping")
                        last_sent_date = today_str  # Mark as sent so we don't retry
                        time.sleep(60)
                        continue
                    
                    logger.info(f"Daily push time reached ({target_time}), fetching predictions...")
                    predictions = fetch_polymarket_predictions()

                    if not predictions:
                        logger.info("Daily push: No predictions to send")
                        last_sent_date = today_str
                        time.sleep(60)
                        continue

                    # Check for significant changes (>5%)
                    changes = price_monitor.check_significant_changes(predictions, threshold=5.0)

                    if changes:
                        # Send emergency alert for significant changes
                        prices = price_monitor.get_current_prices()
                        alert_msg = price_monitor.format_emergency_alert(changes, prices)
                        send_message(alert_msg)
                        logger.info(f"Emergency alert sent: {len(changes)} significant changes")

                    # Send regular predictions update
                    message = format_predictions_message(predictions)
                    send_message(message)
                    logger.info(f"Daily push: Predictions sent at {current_time}")
                    
                    # Mark as sent for today
                    last_sent_date = today_str
                
                # Sleep for 1 minute before checking again
                time.sleep(60)

            except Exception as e:
                logger.error(f"Auto-push error: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 minute before retrying

    thread = threading.Thread(target=_run, daemon=True, name="AutoPushDaily")
    thread.start()
    logger.info(f"Auto-push scheduler started (daily at {config.PREDICTIONS_DAILY_TIME} Thai time)")
```

- [ ] **Step 3: Update the startup log message**

In `start_bot()` function (around line 949), update the log message:

Find:
```python
    logger.info("Features: Auto-push every 1 hour, Emergency alerts on 5%+ changes")
```

Replace with:
```python
    logger.info(f"Features: Daily auto-push at {config.PREDICTIONS_DAILY_TIME} Thai time, Emergency alerts on 5%+ changes")
```

- [ ] **Step 4: Commit the changes**

```bash
git add predictions_bot.py
git commit -m "feat: change predictions auto-push to once per day at configured time (Thai timezone)"
```

---

## Task 3: Add pytz to Requirements

**Files:**
- Create/Modify: `requirements.txt`

- [ ] **Step 1: Check if requirements.txt exists and add pytz**

If `requirements.txt` exists, add `pytz>=2024.1` to it. If not, create it:

```bash
# Check if pytz is already in requirements
grep -q "pytz" requirements.txt 2>/dev/null || echo "pytz>=2024.1" >> requirements.txt
```

- [ ] **Step 2: Commit**

```bash
git add requirements.txt
git commit -m "deps: add pytz for timezone handling"
```

---

## Testing

- [ ] **Step 1: Test the timezone conversion**

Create a quick test:
```python
python3 -c "
from datetime import datetime
import pytz
thai_tz = pytz.timezone('Asia/Bangkok')
now = datetime.now(thai_tz)
print(f'Current Thai time: {now.strftime(\"%Y-%m-%d %H:%M:%S\")}')
print(f'Time check: {now.strftime(\"%H:%M\")}')
"
```

Expected output should show current time in Thailand (UTC+7).

- [ ] **Step 2: Verify config loading**

```python
python3 -c "
import config
print(f'Daily time: {config.PREDICTIONS_DAILY_TIME}')
print(f'Enabled: {config.PREDICTIONS_DAILY_PUSH_ENABLED}')
print(f'Timezone: {config.THAI_TZ}')
"
```

---

## Summary of Changes

1. **config.py**: Added `THAI_TZ`, `PREDICTIONS_DAILY_TIME`, `PREDICTIONS_DAILY_PUSH_ENABLED`
2. **predictions_bot.py**: Rewrote `auto_push_predictions()` to check every minute and send once per day at configured time
3. **requirements.txt**: Added `pytz` dependency

**Behavior after change:**
- Bot checks current time every minute
- When time matches `PREDICTIONS_DAILY_TIME` (default 08:00) and hasn't sent today yet → send predictions
- Uses Thailand timezone (Asia/Bangkok, UTC+7)
- Can customize time via `.env` file: `PREDICTIONS_DAILY_TIME=09:00`
- Can disable via `.env` file: `PREDICTIONS_DAILY_PUSH_ENABLED=false`
