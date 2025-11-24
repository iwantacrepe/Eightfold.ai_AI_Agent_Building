"""Translate approved workplans into concrete search tasks."""

from __future__ import annotations

import json
from typing import List, Dict, Any

from core.models import SessionState
from llm import prompts
from llm.client import LLMClient

MAX_TASKS = 12
SUPPORTED_CHANNELS = {"web", "news", "wikipedia", "finance", "leadership", "talent", "competitors"}


def build_search_tasks(llm: LLMClient, session: SessionState) -> List[Dict[str, Any]]:
    """Use the LLM to convert the approved workplan into structured search tasks."""

    if not session.workplan:
        return []

    scope_snapshot = json.dumps(session.scope, indent=2, sort_keys=True, default=str)
    workplan_text = session.workplan

    try:
        payload = llm.structured_chat(
            system_prompt=prompts.SEARCH_ROUTER_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Here is the confirmed scope and approved workplan. "
                        "Return JSON search tasks only.\n\n"
                        f"Scope:\n{scope_snapshot}\n\nWorkplan:\n{workplan_text}"
                    ),
                }
            ],
        )
    except Exception:  # pragma: no cover - defensive fallback
        return []

    raw_tasks = payload.get("search_tasks") or []
    normalized: List[Dict[str, Any]] = []
    for task in raw_tasks[:MAX_TASKS]:
        channel = (task.get("channel") or "web").strip().lower()
        if channel not in SUPPORTED_CHANNELS:
            continue
        normalized.append(
            {
                "phase": task.get("phase", ""),
                "goal": task.get("goal", ""),
                "channel": channel,
                "query": task.get("query", "").strip(),
                "agent": task.get("agent", "Research Agent").strip() or "Research Agent",
                "source": task.get("source", channel.title()).strip() or channel.title(),
            }
        )

    return normalized
