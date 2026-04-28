"""
News Fetcher Module
===================
Fetches gold-related news from ForexFactory economic calendar
and Polymarket prediction markets.
"""

import logging
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from dataclasses import dataclass, field

import requests

import config

logger = logging.getLogger('goldnews')


@dataclass
class EconomicEvent:
    """Structured economic calendar event."""
    title: str
    title_th: str
    country: str
    impact: str  # High, Medium, Low
    date: str
    time: str
    forecast: str
    previous: str
    source: str = 'ForexFactory'
    event_datetime: Optional[datetime] = None  # Parsed datetime for filtering


@dataclass
class PolymarketData:
    """Polymarket prediction market data."""
    title: str
    probability: float
    volume: float
    url: str
    source: str = 'Polymarket'


def is_relevant_event(event: Dict) -> bool:
    """
    Check if an economic event is relevant to gold trading.

    Strategy: Focus on USD events (gold is priced in USD).
    Non-USD events are only included if they explicitly mention gold/XAU.
    """
    title = event.get('title', '').lower()
    country = event.get('country', '').upper()
    impact = event.get('impact', '')

    # Always include USD HIGH impact events
    if country == 'USD' and impact == 'High':
        return True

    # Include USD HIGH and MEDIUM impact events
    if country == 'USD' and impact == 'Medium':
        return True

    # For non-USD events: only include if title explicitly mentions gold
    # This prevents AUD CPI, CAD BOC, GBP BOE, etc. from showing up
    gold_specific_keywords = ['gold price', 'gold hit', 'gold reach', 'gold above',
                              'gold below', 'gold at', 'gold close', 'gold end',
                              'gold finish', 'gold trade', 'gold market', 'gold ',
                              'gold demand', 'gold supply', 'gold reserve',
                              'xauusd', 'xau/usd', 'xau/ usd', 'bullion',
                              'precious metal']
    if country != 'USD' and any(kw in title for kw in gold_specific_keywords):
        return True

    return False


def _translate_title(title: str) -> str:
    """Translate common economic event titles to Thai."""
    for english, thai in config.THAI_TRANSLATIONS.items():
        if english.lower() in title.lower():
            return thai
    return title


def _parse_forex_factory_date(date_str: str, time_str: str) -> Optional[datetime]:
    """Parse ForexFactory date and time strings into datetime object.
    
    Supports both formats:
    - ISO format: "2026-04-28T21:30:00-04:00" (new API format)
    - US format: "04/28/2026" with separate time "8:30am" (legacy format)
    """
    if not date_str:
        return None
    
    # Try ISO format first (e.g., "2026-04-28T21:30:00-04:00")
    if 'T' in date_str:
        try:
            # Parse ISO format with timezone offset
            from datetime import timezone
            # Remove timezone offset for simple parsing
            iso_clean = date_str.split('+')[0].split('-')[0] if '+' in date_str[10:] else date_str
            # More robust: handle the full ISO string
            # Format: 2026-04-28T21:30:00-04:00
            # Extract date and time parts
            dt_part = date_str.split('T')
            if len(dt_part) == 2:
                date_part = dt_part[0]  # "2026-04-28"
                time_tz = dt_part[1]    # "21:30:00-04:00"
                
                # Parse date
                date_parts = date_part.split('-')
                year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])
                
                # Parse time (remove timezone for now, use UTC approximation)
                time_clean = time_tz.split('-')[0].split('+')[0]  # "21:30:00"
                time_parts = time_clean.split(':')
                hours = int(time_parts[0])
                minutes = int(time_parts[1]) if len(time_parts) > 1 else 0
                seconds = int(time_parts[2]) if len(time_parts) > 2 else 0
                
                # Handle timezone offset - convert to UTC
                tz_offset_hours = 0
                if '-' in time_tz[1:]:  # Negative offset like -04:00
                    tz_str = time_tz.split('-')[-1]
                    tz_parts = tz_str.split(':')
                    tz_offset_hours = int(tz_parts[0])
                elif '+' in time_tz:  # Positive offset
                    tz_str = time_tz.split('+')[-1]
                    tz_parts = tz_str.split(':')
                    tz_offset_hours = int(tz_parts[0])
                
                # Convert to UTC: local time + offset = UTC
                # e.g., 21:30 EDT (-4) = 21:30 + 4 = 01:30 UTC next day
                from datetime import timedelta as td
                event_utc = datetime(year, month, day, hours, minutes, seconds) + td(hours=tz_offset_hours)
                # Convert UTC to ICT (UTC+7)
                event_ict = event_utc + td(hours=7)
                return event_ict
        except (ValueError, IndexError):
            pass
    
    # Try US format: "04/28/2026" with separate time "8:30am"
    try:
        parts = date_str.split('/')
        if len(parts) != 3:
            return None
        month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
        
        if time_str and time_str.strip():
            # Time format: "8:30am" or "2:00pm"
            time_lower = time_str.lower().strip()
            is_pm = 'pm' in time_lower
            is_am = 'am' in time_lower
            time_clean = time_lower.replace('am', '').replace('pm', '').strip()
            
            time_parts = time_clean.split(':')
            hours = int(time_parts[0])
            minutes = int(time_parts[1]) if len(time_parts) > 1 else 0
            
            if is_pm and hours != 12:
                hours += 12
            if is_am and hours == 12:
                hours = 0
            
            # US format times are in US Eastern, convert to ICT
            # Approximate: treat as UTC then add 7 for ICT
            dt_utc = datetime(year, month, day, hours, minutes)
            return dt_utc + timedelta(hours=7)
        else:
            dt_utc = datetime(year, month, day, 0, 0)
            return dt_utc + timedelta(hours=7)
    except (ValueError, IndexError):
        return None


def fetch_forex_factory_events() -> List[EconomicEvent]:
    """
    Fetch economic calendar events from ForexFactory.

    Returns list of EconomicEvent objects, filtered to gold-relevant events.
    Retries up to 3 times with exponential backoff for rate limiting.
    """
    data = None
    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = requests.get(
                config.FOREX_FACTORY_URL,
                timeout=15,
                headers={
                    'Accept': 'application/json',
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                }
            )
            response.raise_for_status()
            data = response.json()
            break  # Success

        except requests.exceptions.HTTPError as e:
            if response.status_code == 429 and attempt < max_retries - 1:
                # Rate limited - wait and retry
                delay = 15 * (2 ** attempt)  # 15s, 30s, 60s
                logger.warning(f"ForexFactory rate limited (429), retry {attempt + 1}/{max_retries} in {delay}s...")
                import time
                time.sleep(delay)
            else:
                logger.error(f"Failed to fetch ForexFactory data: {e}")
                return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch ForexFactory data: {e}")
            return []
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse ForexFactory data: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching ForexFactory data: {e}")
            return []

    if data is None:
        return []
    
    events = []
    now = datetime.utcnow() + timedelta(hours=7)  # ICT time
    today = now.date()
    
    for item in data:
        try:
            title = item.get('title', '')
            country = item.get('country', '')
            impact = item.get('impact', '')
            date_str = item.get('date', '')
            time_str = item.get('time', '')
            forecast = item.get('forecast', '')
            previous = item.get('previous', '')
            
            # Build event dict for relevance check
            event_dict = {
                'title': title,
                'country': country,
                'impact': impact,
            }
            
            if not is_relevant_event(event_dict):
                continue
            
            # Parse date
            event_time = _parse_forex_factory_date(date_str, time_str)
            
            # Filter: only include events from today and the next 2 days
            # This prevents showing events that already passed or are far in the future
            if event_time:
                event_date = event_time.date()
                days_ahead = (event_date - today).days
                # Skip events that already ended (more than 1 hour ago)
                if event_time < now - timedelta(hours=1):
                    continue
                # Skip events more than 2 days away
                if days_ahead > 2:
                    continue
            elif date_str:
                # Can't parse date but have a date string - try to check date string
                try:
                    parts = date_str.split('/')
                    if len(parts) == 3:
                        event_date = datetime(int(parts[2]), int(parts[0]), int(parts[1])).date()
                        days_ahead = (event_date - today).days
                        if days_ahead > 2 or days_ahead < -1:
                            continue
                except (ValueError, IndexError):
                    pass  # Include if we can't parse date
            
            events.append(EconomicEvent(
                title=title,
                title_th=_translate_title(title),
                country=country,
                impact=impact,
                date=date_str,
                time=time_str,
                forecast=str(forecast) if forecast else '',
                previous=str(previous) if previous else '',
                event_datetime=event_time,
            ))
        except Exception as e:
            logger.warning(f"Error parsing ForexFactory event: {e}")
            continue
    
    # Sort by event_datetime (parsed), fallback to date string
    events.sort(key=lambda e: e.event_datetime or datetime.max)
    logger.info(f"Fetched {len(events)} relevant ForexFactory events (today + next 2 days)")
    return events


def fetch_polymarket_gold() -> List[PolymarketData]:
    """
    Fetch gold-related prediction markets from Polymarket.
    
    Returns list of PolymarketData objects for gold-related markets.
    Only returns markets that are clearly about gold/XAUUSD prices.
    """
    # Strict gold keywords - must be specifically about gold prices
    gold_keywords = ['gold price', 'xauusd', 'xau/usd', 'gold hit', 'gold reach', 
                     'gold above', 'gold below', 'gold at', 'gold close',
                     'gold end', 'gold finish', 'gold trade', 'gold market',
                     'bullion price', 'precious metal price']
    # Exclude keywords - markets about sports, politics, etc.
    exclude_keywords = ['nhl', 'nba', 'nfl', 'mlb', 'soccer', 'football', 'hockey',
                       'basketball', 'baseball', 'stanley cup', 'super bowl',
                       'olympics', 'world cup', 'championship', 'election',
                       'president', 'senate', 'congress', 'governor']
    
    try:
        response = requests.get(
            config.POLYMARKET_URL,
            params={'active': 'true', 'closed': 'false', 'limit': '50'},
            timeout=15,
            headers={'Accept': 'application/json'}
        )
        response.raise_for_status()
        data = response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch Polymarket data: {e}")
        return []
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Failed to parse Polymarket data: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching Polymarket data: {e}")
        return []
    
    markets = []
    market_list = data.get('markets', data) if isinstance(data, dict) else data
    
    for market in market_list:
        try:
            question = market.get('question', '')
            description = market.get('description', '') or ''
            question_lower = question.lower()
            desc_lower = description.lower()
            combined = question_lower + ' ' + desc_lower
            
            # Skip excluded topics (sports, politics, etc.)
            if any(kw in combined for kw in exclude_keywords):
                continue
            
            # Only include if clearly about gold prices
            if any(kw in combined for kw in gold_keywords):
                markets.append(PolymarketData(
                    title=question,
                    probability=float(market.get('probability', 0)),
                    volume=float(market.get('volume', 0)),
                    url=f"https://polymarket.com/event/{market.get('slug', '')}",
                ))
        except Exception as e:
            logger.warning(f"Error parsing Polymarket market: {e}")
            continue
    
    logger.info(f"Fetched {len(markets)} gold-related Polymarket markets")
    return markets


def fetch_all_news() -> Dict[str, list]:
    """
    Fetch all news sources and return combined data.
    
    Returns dict with 'events' (ForexFactory) and 'markets' (Polymarket) keys.
    """
    events = fetch_forex_factory_events()
    markets = fetch_polymarket_gold()
    
    logger.info(f"Total: {len(events)} events, {len(markets)} markets")
    return {
        'events': events,
        'markets': markets,
    }