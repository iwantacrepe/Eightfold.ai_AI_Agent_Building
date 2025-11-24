"""RSS-based news ingestion covering Google News, Reuters, CNBC, and TechCrunch."""

from __future__ import annotations

from typing import Dict, List
from urllib.parse import quote_plus

import feedparser
import requests
from bs4 import BeautifulSoup

DEFAULT_FEEDS = [
    {"name": "Google News", "url": "https://news.google.com/rss/search?q={query}", "use_query": True},
    {"name": "Reuters", "url": "https://feeds.reuters.com/reuters/businessNews", "use_query": False},
    {"name": "CNBC", "url": "https://www.cnbc.com/id/10001147/device/rss/rss.html", "use_query": False},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/", "use_query": False},
]

MAX_PER_FEED = 6
SCRAPE_TIMEOUT = 8


def fetch_rss_news(query: str, max_items: int = 12) -> List[Dict[str, str]]:
    """Gather news entries from curated RSS feeds, enriching with scraped summaries."""

    normalized_query = (query or "technology enterprise news").strip()
    collected: List[Dict[str, str]] = []

    for feed in DEFAULT_FEEDS:
        url = feed["url"]
        if feed.get("use_query"):
            url = url.format(query=quote_plus(normalized_query))
        parsed = feedparser.parse(url)
        entries = parsed.entries[:MAX_PER_FEED]
        for entry in entries:
            link = getattr(entry, "link", "")
            summary = (getattr(entry, "summary", None) or getattr(entry, "description", None) or "").strip()
            if not summary and link:
                summary = _scrape_article(link)
            collected.append(
                {
                    "title": getattr(entry, "title", ""),
                    "url": link,
                    "summary": summary,
                    "published": getattr(entry, "published", None),
                    "source": feed["name"],
                }
            )
            if len(collected) >= max_items:
                break
        if len(collected) >= max_items:
            break

    return collected


def _scrape_article(url: str) -> str:
    try:
        resp = requests.get(url, timeout=SCRAPE_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if p.get_text(strip=True)]
        return " ".join(paragraphs[:5])[:1500]
    except Exception:
        return ""
