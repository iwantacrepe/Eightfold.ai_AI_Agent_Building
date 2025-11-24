"""DuckDuckGo search helpers leveraging LangChain's native wrapper."""

from __future__ import annotations

from typing import Any, Dict, List

try:  # pragma: no cover - optional dependency provided by langchain-community
    from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
except Exception:  # pragma: no cover
    DuckDuckGoSearchAPIWrapper = None  # type: ignore


def _get_wrapper(backend: str) -> DuckDuckGoSearchAPIWrapper | None:  # type: ignore[name-defined]
    if not DuckDuckGoSearchAPIWrapper:
        return None
    try:
        return DuckDuckGoSearchAPIWrapper(region="wt-wt", safesearch="moderate", time="m", max_results=10, backend=backend)
    except Exception:  # pragma: no cover - wrapper init may fail if dependency missing
        return None


def search_web(query: str, max_results: int = 6) -> List[Dict[str, Any]]:
    """Return general web snippets from DuckDuckGo."""

    return _run_search(query, max_results=max_results, backend="text")


def search_news(query: str, max_results: int = 6) -> List[Dict[str, Any]]:
    """Return news-focused snippets from DuckDuckGo."""

    return _run_search(query, max_results=max_results, backend="news")


def _run_search(query: str, max_results: int, backend: str) -> List[Dict[str, Any]]:
    query = query.strip()
    if not query:
        return []

    wrapper = _get_wrapper(backend)
    if not wrapper:
        return []

    try:
        results = wrapper.results(query, max_results=max_results)
    except Exception:  # pragma: no cover - network/duckduckgo issues
        return []

    normalized: List[Dict[str, Any]] = []
    for item in results:
        normalized.append(
            {
                "title": item.get("title") or item.get("name") or query,
                "url": item.get("link") or item.get("url") or "",
                "snippet": item.get("body") or item.get("snippet") or "",
                "published": item.get("date") or item.get("published"),
            }
        )
    return normalized
