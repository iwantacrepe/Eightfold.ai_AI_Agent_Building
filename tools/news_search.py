"""News search helper using scraping fallbacks."""

from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

try:  # pragma: no cover
    from langchain_community.tools.tavily_search import TavilySearchResults
except Exception:  # pragma: no cover
    TavilySearchResults = None  # type: ignore

try:  # pragma: no cover
    from newspaper import Article
except Exception:  # pragma: no cover
    Article = None  # type: ignore

from tools import duckduckgo_search, rss_news


NEWS_WINDOW_DAYS = 90


def lookup_recent_news(company: str, scope: Dict[str, Any], query: str | None = None) -> List[Dict[str, Any]]:
    """Search for recents news referencing the company."""

    query = (query or f"{company} news {scope.get('region', '')} last 90 days").strip()
    cutoff = dt.date.today() - dt.timedelta(days=NEWS_WINDOW_DAYS)
    combined: List[Dict[str, Any]] = []
    if TavilySearchResults and os.getenv("TAVILY_API_KEY"):
        tool = TavilySearchResults(max_results=5, search_depth="advanced")
        try:
            results = tool.invoke({"query": query})
            for item in results:
                combined.append(_scrape_news(item.get("url"), fallback=item.get("content")))
        except Exception:
            pass

    ddg_news = duckduckgo_search.search_news(query, max_results=6)
    for entry in ddg_news:
        url = entry.get("url")
        if not url:
            continue
        combined.append(
            {
                "title": entry.get("title") or url,
                "url": url,
                "summary": entry.get("snippet") or "",
                "published": entry.get("published") or cutoff.isoformat(),
            }
        )

    rss_results = rss_news.fetch_rss_news(query, max_items=12)
    for entry in rss_results:
        if not entry.get("url"):
            continue
        combined.append(
            {
                "title": entry.get("title") or entry.get("url"),
                "url": entry["url"],
                "summary": entry.get("summary") or "",
                "published": entry.get("published") or cutoff.isoformat(),
            }
        )

    if combined:
        return _dedupe_by_url(combined)

    return [
        {
            "title": f"{company} announces regional expansion",
            "url": "https://www.example.com/news",
            "summary": f"Placeholder news result for {company} covering {scope.get('region', 'global')} initiatives.",
            "published": cutoff.isoformat(),
        }
    ]


def collect_source_metadata(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {"title": entry.get("title"), "url": entry.get("url"), "type": "news"}
        for entry in results
        if entry.get("url")
    ]


def _scrape_news(url: str | None, fallback: str | None = None) -> Dict[str, Any]:
    if not url:
        return {
            "title": "Unknown news",
            "url": "",
            "summary": fallback or "",
            "published": None,
        }

    summary = fallback or ""
    published = None
    title = ""
    if Article:
        try:
            article = Article(url)
            article.download()
            article.parse()
            title = article.title or ""
            summary = article.summary or article.text or fallback or ""
            published = article.publish_date.isoformat() if article.publish_date else None
        except Exception:
            summary = fallback or summary

    if not summary:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            paragraphs = " ".join(p.get_text(strip=True) for p in soup.find_all("p"))
            summary = paragraphs[:1200]
            if not title and soup.title and soup.title.string:
                title = soup.title.string.strip()
        except Exception:
            summary = fallback or ""

    return {
        "title": title or url,
        "url": url,
        "summary": summary,
        "published": published,
    }


def _dedupe_by_url(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    unique = []
    for entry in items:
        url = entry.get("url")
        if url and url in seen:
            continue
        if url:
            seen.add(url)
        unique.append(entry)
    return unique
