"""Lightweight Wikipedia helper with graceful fallbacks."""

from __future__ import annotations

from typing import Any, Dict

try:  # pragma: no cover - optional dependency
    import wikipedia  # type: ignore
except Exception:  # pragma: no cover
    wikipedia = None  # type: ignore

try:  # pragma: no cover - LangChain convenience wrapper
    from langchain_community.utilities import WikipediaAPIWrapper
except Exception:  # pragma: no cover
    WikipediaAPIWrapper = None  # type: ignore

_WRAPPER: WikipediaAPIWrapper | None = None  # type: ignore[name-defined]


def fetch_summary(topic: str) -> Dict[str, Any]:
    """Return a concise encyclopedia-style summary for the topic."""

    topic = topic.strip() or "Public company overview"
    wrapper = _get_wrapper()
    if wrapper:
        try:
            docs = wrapper.load(topic)
            if docs:
                doc = docs[0]
                return {
                    "title": doc.metadata.get("title") or topic.title(),
                    "summary": doc.page_content[:1200],
                    "url": doc.metadata.get("source") or doc.metadata.get("pageid"),
                }
        except Exception:
            pass

    if wikipedia:
        try:
            summary = wikipedia.summary(topic, sentences=4, auto_suggest=False)
            page = wikipedia.page(topic, auto_suggest=False)
            return {"title": page.title, "summary": summary, "url": page.url}
        except Exception:
            pass

    return {
        "title": f"{topic} overview",
        "summary": f"Placeholder encyclopedia summary for {topic}.",
        "url": f"https://wikipedia.org/wiki/{topic.replace(' ', '_')}",
    }


def source_metadata(entry: Dict[str, Any]) -> Dict[str, Any]:
    return {"title": entry.get("title"), "url": entry.get("url"), "type": "wikipedia"}


def _get_wrapper() -> WikipediaAPIWrapper | None:  # type: ignore[name-defined]
    global _WRAPPER
    if _WRAPPER is not None:
        return _WRAPPER
    if not WikipediaAPIWrapper:
        return None
    try:
        _WRAPPER = WikipediaAPIWrapper(wiki_client=None, lang="en", top_k_results=1, doc_content_chars_max=2000)
    except Exception:
        _WRAPPER = None
    return _WRAPPER
