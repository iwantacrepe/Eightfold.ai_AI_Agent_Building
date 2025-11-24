"""Web + article scraping helper."""

from __future__ import annotations

import os
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

try:  # pragma: no cover - optional dependency
    from langchain_community.tools.tavily_search import TavilySearchResults
except Exception:  # pragma: no cover
    TavilySearchResults = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from newspaper import Article
except Exception:  # pragma: no cover
    Article = None  # type: ignore

from tools import duckduckgo_search


def lookup_company(company: str, scope: Dict[str, Any], query: str | None = None) -> List[Dict[str, Any]]:
    """Return high-signal web search snippets from Tavily + DuckDuckGo."""

    query = (query or f"{company} {scope.get('region', '')} enterprise GTM overview").strip()
    combined: List[Dict[str, Any]] = []

    if TavilySearchResults and os.getenv("TAVILY_API_KEY"):
        tool = TavilySearchResults(max_results=5)
        try:
            results = tool.invoke({"query": query})
            for item in results:
                combined.append(_scrape_article(item.get("url"), fallback=item.get("content")))
        except Exception:
            combined.append(
                {
                    "title": "Tavily search failed",
                    "url": "",
                    "content": "",
                    "score": None,
                }
            )

    ddg_results = duckduckgo_search.search_web(query, max_results=6)
    for entry in ddg_results:
        if not entry.get("url"):
            continue
        combined.append(
            {
                "title": entry.get("title") or entry.get("url"),
                "url": entry.get("url"),
                "content": entry.get("snippet") or "",
                "score": None,
            }
        )

    if combined:
        return _dedupe_by_url(combined)

    # Offline fallback sample data
    return [
        {
            "title": f"{company} corporate overview",
            "url": "https://www.example.com/company-overview",
            "content": f"Summary placeholder for {company} in {scope.get('region', 'global')} region.",
            "score": 0.5,
        }
    ]


def collect_source_metadata(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Transform raw tool output into source attribution records."""

    seen = set()
    sources = []
    for entry in results:
        url = entry.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append({"title": entry.get("title"), "url": url, "type": "web"})
    return sources


def _dedupe_by_url(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    unique = []
    for item in items:
        url = item.get("url")
        if url and url in seen:
            continue
        if url:
            seen.add(url)
        unique.append(item)
    return unique


def _scrape_article(url: str | None, fallback: str | None = None) -> Dict[str, Any]:
    if not url:
        return {"title": "Unknown", "url": "", "content": fallback or "", "score": None}

    text = fallback or ""
    title = ""
    if Article:
        try:
            article = Article(url)
            article.download()
            article.parse()
            article.nlp()
            text = article.summary or article.text or fallback or ""
            title = article.title or ""
        except Exception:
            text = fallback or text

    if not text:
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            paragraphs = "\n".join(p.get_text(strip=True) for p in soup.find_all("p"))
            text = paragraphs[:2000]
            if not title:
                if soup.title and soup.title.string:
                    title = soup.title.string.strip()
        except Exception:
            text = fallback or ""

    return {
        "title": title or url,
        "url": url,
        "content": text,
        "score": None,
    }
