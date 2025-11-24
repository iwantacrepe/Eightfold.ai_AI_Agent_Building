"""Selective regeneration of individual account plan sections."""

from __future__ import annotations

import json

from core.models import ConversationStage, PlanSection, SessionState
from core.progress import log_progress, reset_progress
from llm.client import LLMClient

from agents.group2_analysis import generate_section


def regenerate_section(
    llm: LLMClient,
    session: SessionState,
    section: PlanSection,
    user_instruction: str | None = None,
) -> SessionState:
    """Regenerate a single plan section while leaving others untouched."""

    if not session.research_bundle or not session.account_plan:
        raise ValueError("Cannot regenerate without an existing research bundle and account plan.")

    reset_progress(session)
    session.stage = ConversationStage.EDITING
    human_label = section.value.replace("_", " ").title()
    log_progress(session, f"♻️ Regenerating {human_label}…")
    bundle_json = json.dumps(session.research_bundle.__dict__, default=str, ensure_ascii=False)

    updated_content = generate_section(
        llm=llm,
        section=section,
        bundle_json=bundle_json,
        session=session,
        instruction=user_instruction,
    )
    setattr(session.account_plan, section.value, updated_content.strip())
    session.account_plan.version += 1
    session.stage = ConversationStage.REVIEWING
    log_progress(session, f"✅ {human_label} updated.")
    return session
