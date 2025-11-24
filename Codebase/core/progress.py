"""Helpers for recording and retrieving long-running progress updates."""

from __future__ import annotations

from typing import Iterable, List

from core.models import SessionState


def log_progress(session: SessionState, message: str) -> None:
    """Append a progress message if it differs from the latest entry."""

    message = message.strip()
    if not message:
        return
    if not session.progress_log or session.progress_log[-1] != message:
        session.progress_log.append(message)


def extend_progress(session: SessionState, messages: Iterable[str]) -> None:
    """Append multiple progress messages in order."""

    for msg in messages:
        log_progress(session, msg)


def get_progress_log(session: SessionState) -> List[str]:
    """Return a copy of the current progress log."""

    return list(session.progress_log)


def reset_progress(session: SessionState) -> None:
    """Clear progress indicators when a new phase begins."""

    session.progress_log.clear()
