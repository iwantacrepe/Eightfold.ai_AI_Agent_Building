"""Utilities for tracking real-time research activity events."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from core.models import SessionState


def _timestamp() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def reset_activity(session: SessionState) -> None:
    session.research_activity.clear()


def start_activity(
    session: SessionState,
    *,
    agent: str,
    channel: str,
    source: str,
    query: str,
    goal: str = "",
) -> str:
    event = {
        "id": str(uuid4()),
        "agent": agent,
        "channel": channel,
        "source": source,
        "query": query,
        "goal": goal,
        "status": "running",
        "results": [],
        "started_at": _timestamp(),
        "completed_at": None,
    }
    session.research_activity.append(event)
    return event["id"]


def complete_activity(
    session: SessionState,
    event_id: str,
    *,
    results: Optional[List[Dict[str, Any]]] = None,
    status: str = "complete",
) -> None:
    for event in session.research_activity:
        if event.get("id") == event_id:
            event["status"] = status
            event["completed_at"] = _timestamp()
            if results is not None:
                event["results"] = results
            return


def fail_activity(session: SessionState, event_id: str, error: str) -> None:
    complete_activity(session, event_id, results=[{"title": "Error", "snippet": error, "url": ""}], status="error")
