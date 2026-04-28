"""
Real-Time News Fetcher Module
=============================
Fetches real-time gold and forex news from RSS feeds and news APIs.
Sources: ForexFactory news, Yahoo Finance, Investing.com
"""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

import requests

import config

logger = logging.getLogger('goldnews')


@dataclass
class RealTimeNewsItem:
    """A real-time news article."""
    title: str
    summary: str
    source: str  # 'ForexFactory', 'YahooFinance', 'Investing'
    url: str
    published: Optional[datetime] = None  # ICT time


# RSS feed URLs - tested and working
RSS_FEEDS = [
    {
        'name': 'MarketWatch',
        'url': 'https://feeds.content.dowjones.io/public/rss/mw_topstories',
        'source': 'MarketWatch',
    },
    {
        'name': 'CNBC',
        'url': 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114',
        'source': 'CNBC',
    },
]

# Keywords to filter gold/forex relevant news
GOLD_NEWS_KEYWORDS = [
    'gold', 'xau', 'xauusd', 'precious metal', 'bullion',
    'fed', 'federal reserve', 'interest rate', 'fomc',
    'inflation', 'cpi', 'ppi', 'pce',
    'dollar', 'usd', 'dxy', 'us dollar',
    'treasury', 'bond yield', 'yield',
    'gdp', 'employment', 'nonfarm', 'non-farm',
    'jobless', 'unemployment',
    'powell', 'jerome powell',
    'recession', 'economic', 'economy',
    'trade war', 'tariff',
    'geopolitical', 'war', 'conflict',
    'safe haven', 'central bank',
]


def _parse_rss_date(date_str: str) -> Optional[datetime]:
    """Parse RSS date string to datetime (UTC), then convert to ICT."""
    if not date_str:
        return None

    # Common RSS date formats
    formats = [
        '%a, %d %b %Y %H:%M:%S %z',  # RFC 822
        '%Y-%m-%dT%H:%M:%S%z',       # ISO 8601
        '%Y-%m-%d %H:%M:%S',         # Simple
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            # Convert to ICT (UTC+7)
            if dt.tzinfo:
                from datetime import timezone
                utc_dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                return utc_dt + timedelta(hours=7)
            else:
                # Assume UTC if no timezone
                return dt + timedelta(hours=7)
        except (ValueError, TypeError):
            continue

    return None


def _is_relevant_news(title: str, summary: str = '') -> bool:
    """Check if a news article is relevant to gold trading."""
    text = (title + ' ' + summary).lower()
    return any(kw in text for kw in GOLD_NEWS_KEYWORDS)


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    clean = re.sub(r'<[^>]+>', '', text)
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean


def fetch_rss_feed(feed: Dict) -> List[RealTimeNewsItem]:
    """
    Fetch and parse a single RSS feed.

    Args:
        feed: Dict with 'name', 'url', 'source' keys

    Returns:
        List of RealTimeNewsItem objects
    """
    items = []

    try:
        response = requests.get(
            feed['url'],
            timeout=15,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; GoldNewsBot/1.0)',
                'Accept': 'application/rss+xml, application/xml, text/xml',
            }
        )
        response.raise_for_status()

        # Simple RSS parsing (no external dependencies)
        content = response.text

        # Extract <item> blocks
        item_pattern = re.compile(r'<item>(.*?)</item>', re.DOTALL)
        title_pattern = re.compile(r'<title>(.*?)</title>', re.DOTALL)
        link_pattern = re.compile(r'<link>(.*?)</link>', re.DOTALL)
        desc_pattern = re.compile(r'<description>(.*?)</description>', re.DOTALL)
        date_pattern = re.compile(r'<pubDate>(.*?)</pubDate>', re.DOTALL)

        for item_block in item_pattern.findall(content):
            title_match = title_pattern.search(item_block)
            link_match = link_pattern.search(item_block)
            desc_match = desc_pattern.search(item_block)
            date_match = date_pattern.search(item_block)

            if not title_match:
                continue

            title = _strip_html(title_match.group(1))
            link = link_match.group(1).strip() if link_match else ''
            summary = _strip_html(desc_match.group(1)) if desc_match else ''
            published = _parse_rss_date(date_match.group(1)) if date_match else None

            # Filter for gold/forex relevance
            if not _is_relevant_news(title, summary):
                continue

            items.append(RealTimeNewsItem(
                title=title,
                summary=summary[:200] if summary else '',  # Truncate summary
                source=feed['source'],
                url=link,
                published=published,
            ))

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch RSS feed {feed['name']}: {e}")
    except Exception as e:
        logger.error(f"Error parsing RSS feed {feed['name']}: {e}")

    return items


def fetch_realtime_news() -> List[RealTimeNewsItem]:
    """
    Fetch real-time news from all RSS feeds.

    Returns:
        List of RealTimeNewsItem objects, sorted by published date (newest first)
    """
    all_items = []

    for feed in RSS_FEEDS:
        items = fetch_rss_feed(feed)
        all_items.extend(items)
        logger.info(f"Fetched {len(items)} relevant items from {feed['name']}")

    # Sort by published date (newest first), items without dates go last
    all_items.sort(key=lambda x: x.published or datetime.min, reverse=True)

    # Deduplicate by title (fuzzy match)
    seen_titles = set()
    unique_items = []
    for item in all_items:
        # Normalize title for dedup
        normalized = item.title.lower().strip()
        if normalized not in seen_titles:
            seen_titles.add(normalized)
            unique_items.append(item)

    logger.info(f"Total real-time news: {len(unique_items)} (from {len(all_items)} raw)")
    return unique_items


def format_realtime_news(items: List[RealTimeNewsItem], max_items: int = 5) -> str:
    """
    Format real-time news items into a Thai message section.

    Args:
        items: List of RealTimeNewsItem objects
        max_items: Maximum number of items to include

    Returns:
        Formatted Thai message section
    """
    if not items:
        return ""

    message = "\n📰 <b>ข่าวสดล่าสุด:</b>\n"

    for i, item in enumerate(items[:max_items], 1):
        time_label = ""
        if item.published:
            now = datetime.utcnow() + timedelta(hours=7)
            diff = now - item.published
            if diff.total_seconds() < 3600:
                mins = int(diff.total_seconds() / 60)
                time_label = f" ({mins} นาทีที่แล้ว)"
            elif diff.total_seconds() < 86400:
                hours = int(diff.total_seconds() / 3600)
                time_label = f" ({hours} ชม.ที่แล้ว)"
            else:
                time_label = f" ({item.published.strftime('%d/%m %H:%M')})"

        message += f"• {item.title}{time_label}\n"
        if item.summary:
            message += f"  {item.summary[:150]}...\n"
        message += "\n"

    return message
