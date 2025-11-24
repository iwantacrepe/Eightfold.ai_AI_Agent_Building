"""Research agent group orchestrating data acquisition."""

from __future__ import annotations

import html
import re
from typing import Any, Dict, List

from core.activity import complete_activity, fail_activity, reset_activity, start_activity
from core.models import ConversationStage, ResearchBundle, SessionState
from core.progress import log_progress, reset_progress
from llm.client import LLMClient
from tools import news_search, web_search, wiki_fetch, yahoo_finance

MANDATORY_CHANNELS = ("web", "news", "finance", "leadership", "talent", "competitors")

CHANNEL_META = {
    "web": {"agent": "Web Scout", "source": "Tavily", "emoji": "🔎"},
    "news": {"agent": "News Radar", "source": "Reuters/Bloomberg", "emoji": "📰"},
    "finance": {"agent": "Finance Lens", "source": "Financial filings", "emoji": "📈"},
    "leadership": {"agent": "Org Mapper", "source": "Executive bios", "emoji": "🤝"},
    "talent": {"agent": "Talent Scout", "source": "Hiring trackers", "emoji": "🧠"},
    "competitors": {"agent": "Battlecard", "source": "Competitive intel", "emoji": "⚔️"},
    "wikipedia": {"agent": "Knowledge Base", "source": "Wikipedia", "emoji": "📚"},
}


def run_group1_research(llm: LLMClient, session: SessionState, search_tasks: List[Dict[str, Any]] | None = None) -> SessionState:
    """Collect information via multiple specialized agents and build a bundle."""

    _ = llm  # reserved for future advanced tooling integrations
    reset_progress(session)
    reset_activity(session)
    company = session.scope.get("company_name") or session.scope.get("company") or "the company"
    bundle = ResearchBundle(company_name=company, scope=dict(session.scope))

    tasks = _normalize_tasks(company, search_tasks)
    bundle.search_plan = tasks
    session.search_tasks = tasks

    log_progress(session, "🚀 Launching research agents…")
    for task in tasks:
        _execute_task(bundle, session, company, task)

    bundle.sources = _dedupe_sources(bundle.sources)
    session.research_bundle = bundle
    session.stage = ConversationStage.ANALYZING
    log_progress(session, "📦 Research bundle ready for analysis.")
    return session


def _execute_task(bundle: ResearchBundle, session: SessionState, company: str, task: Dict[str, Any]) -> None:
    channel = task.get("channel", "web").lower()
    meta = CHANNEL_META.get(channel, CHANNEL_META["web"])
    handler = CHANNEL_HANDLERS.get(channel, _handle_web)
    goal = task.get("goal") or f"{channel.title()} sweep"
    query = task.get("query") or _default_query(channel, company)

    log_progress(session, f"{meta['emoji']} {meta['agent']} – {goal}")
    event_id = start_activity(
        session,
        agent=task.get("agent", meta["agent"]),
        channel=channel,
        source=task.get("source", meta["source"]),
        query=query,
        goal=goal,
    )

    try:
        result = handler(company, session.scope, query)
        _merge_bundle(bundle, result.get("bundle_key"), result.get("payload"))
        bundle.sources.extend(result.get("sources", []))
        complete_activity(session, event_id, results=result.get("display", []))
    except Exception as exc:  # pragma: no cover - defensive
        fail_activity(session, event_id, str(exc))


def _normalize_tasks(company: str, tasks: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen = set()
    for task in tasks or []:
        channel = (task.get("channel") or "web").strip().lower()
        seen.add(channel)
        normalized.append(
            {
                "phase": task.get("phase", ""),
                "goal": task.get("goal", ""),
                "channel": channel,
                "query": task.get("query") or _default_query(channel, company),
                "agent": task.get("agent") or CHANNEL_META.get(channel, CHANNEL_META["web"])["agent"],
                "source": task.get("source") or CHANNEL_META.get(channel, CHANNEL_META["web"])["source"],
            }
        )

    for channel in MANDATORY_CHANNELS:
        if channel not in seen:
            meta = CHANNEL_META[channel]
            normalized.append(
                {
                    "phase": "Coverage",
                    "goal": f"Baseline {channel} insights",
                    "channel": channel,
                    "query": _default_query(channel, company),
                    "agent": meta["agent"],
                    "source": meta["source"],
                }
            )

    return normalized[:20]


def _default_query(channel: str, company: str) -> str:
    if channel == "news":
        return f"{company} latest earnings and partnerships"
    if channel == "finance":
        return f"{company} revenue guidance"
    if channel == "leadership":
        return f"{company} executive priorities"
    if channel == "talent":
        return f"{company} hiring plans"
    if channel == "competitors":
        return f"{company} competitive landscape"
    if channel == "wikipedia":
        return company
    return f"{company} enterprise go-to-market"


def _merge_bundle(bundle: ResearchBundle, key: str | None, data: Any) -> None:
    if not key or data is None:
        return
    current = getattr(bundle, key)
    if isinstance(current, list):
        current.extend(data if isinstance(data, list) else [data])
    elif isinstance(current, dict):
        if isinstance(data, dict):
            current.update(data)
        else:
            current["value"] = data
    else:
        setattr(bundle, key, data)


def _dedupe_sources(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped = []
    for item in sources:
        key = item.get("url") or item.get("title")
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def _handle_web(company: str, scope: Dict[str, Any], query: str) -> Dict[str, Any]:
    results = web_search.lookup_company(company, scope, query=query)
    return {
        "bundle_key": "web_results",
        "payload": results,
        "display": _standard_display(results, text_key="content"),
        "sources": web_search.collect_source_metadata(results),
    }


def _handle_news(company: str, scope: Dict[str, Any], query: str) -> Dict[str, Any]:
    results = news_search.lookup_recent_news(company, scope, query=query)
    return {
        "bundle_key": "news_results",
        "payload": results,
        "display": _standard_display(results, text_key="summary"),
        "sources": news_search.collect_source_metadata(results),
    }


def _web_topic_payload(
    company: str,
    scope: Dict[str, Any],
    query: str,
    bundle_key: str,
    source_type: str,
) -> Dict[str, Any]:
    results = web_search.lookup_company(company, scope, query=query)
    sources = web_search.collect_source_metadata(results)
    for entry in sources:
        entry["type"] = source_type
    return {
        "bundle_key": bundle_key,
        "payload": results,
        "display": _standard_display(results, text_key="content"),
        "sources": sources,
    }


def _handle_finance(company: str, scope: Dict[str, Any], query: str) -> Dict[str, Any]:
    snapshot = yahoo_finance.fetch_financials(company, scope)
    metrics = snapshot.get("metrics", {})
    source_url = snapshot.get("source") or ""
    display = []
    if snapshot.get("summary"):
        display.append({"title": "Context", "snippet": snapshot["summary"][:280], "url": source_url})
    for label, value in metrics.items():
        display.append(
            {
                "title": label.replace("_", " ").title(),
                "snippet": str(value),
                "url": source_url,
            }
        )
    sources = []
    if source_url:
        sources.append({"title": f"Yahoo Finance ({snapshot.get('symbol') or company})", "url": source_url, "type": "finance"})
    return {
        "bundle_key": "financials",
        "payload": snapshot,
        "display": display or [{"title": "Financials", "snippet": "No structured data available", "url": ""}],
        "sources": sources,
    }


def _handle_leadership(company: str, scope: Dict[str, Any], query: str) -> Dict[str, Any]:
    return _web_topic_payload(company, scope, query, "leadership", "leadership")


def _handle_talent(company: str, scope: Dict[str, Any], query: str) -> Dict[str, Any]:
    return _web_topic_payload(company, scope, query, "hiring_trends", "talent")


def _handle_competitors(company: str, scope: Dict[str, Any], query: str) -> Dict[str, Any]:
    return _web_topic_payload(company, scope, query, "competitors", "competitor")


def _handle_wikipedia(company: str, scope: Dict[str, Any], query: str) -> Dict[str, Any]:
    summary = wiki_fetch.fetch_summary(query)
    return {
        "bundle_key": "wiki_summary",
        "payload": summary,
        "display": [{"title": summary.get("title"), "snippet": summary.get("summary"), "url": summary.get("url") or ""}],
        "sources": [wiki_fetch.source_metadata(summary)],
    }


CHANNEL_HANDLERS = {
    "web": _handle_web,
    "news": _handle_news,
    "finance": _handle_finance,
    "leadership": _handle_leadership,
    "talent": _handle_talent,
    "competitors": _handle_competitors,
    "wikipedia": _handle_wikipedia,
}


def _standard_display(results: List[Dict[str, Any]], text_key: str) -> List[Dict[str, Any]]:
    display = []
    for item in results[:5]:
        title_value = item.get("title") or item.get("name") or item.get("url")
        snippet_value = item.get(text_key) or item.get("content") or item.get("summary")
        display.append(
            {
                "title": _clean_text(title_value) or (item.get("url") or "Result"),
                "snippet": _clean_text(snippet_value),
                "url": item.get("url", ""),
            }
        )
    return display


_TAG_PATTERN = re.compile(r"<[^>]+>")


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if "<" in text and ">" in text:
        text = _TAG_PATTERN.sub(" ", text)
    text = html.unescape(text)
    return " ".join(text.split())
