"""Planner agent responsible for clarifications and workplan creation."""

from __future__ import annotations

import json
from typing import Tuple

from core.models import ConversationStage, SessionState
from llm.client import LLMClient
from llm import prompts


CONFIRMATION_KEYWORDS = {
    "go",
    "start",
    "looks good",
    "ok",
    "okay",
    "yes",
    "proceed",
    "ready",
    "yep",
    "yeah",
    "sure",
    "do it",
    "sounds good",
    "approved",
}
REVISION_KEYWORDS = {"change", "revise", "add", "update", "modify", "edit", "adjust"}


def handle_planning_stage(llm: LLMClient, session: SessionState) -> tuple[str, str | None]:
    """Gather clarifications first, then generate the workplan once ready."""

    clarification_prompt = _build_clarification_prompt(session)
    payload = llm.structured_chat(
        system_prompt=clarification_prompt,
        messages=session.chat_history,
    )
    scope_updates = payload.get("scope_updates") or {}
    if scope_updates:
        for key, value in scope_updates.items():
            if not value:
                continue
            if key == "company":
                session.scope["company_name"] = value
            else:
                session.scope[key] = value
        if scope_updates.get("persona_mode"):
            session.persona_mode = scope_updates["persona_mode"].lower()
        if scope_updates.get("depth"):
            session.desired_depth = scope_updates["depth"].lower()

    needs_more_info = bool(payload.get("needs_more_info", True))
    assistant_reply = payload.get("assistant_reply", "I'm processing your request.").strip()

    if needs_more_info:
        session.stage = ConversationStage.PLANNING
        return assistant_reply, None

    workplan_text = _generate_workplan(llm, session)
    if workplan_text:
        session.workplan = workplan_text
        session.stage = ConversationStage.CONFIRMING_PLAN
        combined_reply = workplan_text.strip()
        if assistant_reply:
            combined_reply = f"{assistant_reply}\n\n{combined_reply}".strip()
        return combined_reply, workplan_text

    session.stage = ConversationStage.PLANNING
    failure_reply = assistant_reply or "I wasn't able to build the workplan yet."
    failure_reply += "\n\nCould you restate the requirements so I can try again?"
    return failure_reply.strip(), None


def handle_confirming_plan_stage(llm: LLMClient, session: SessionState, user_message: str) -> Tuple[bool, str]:
    """Interpret the user's response to the generated workplan."""

    text = user_message.lower()
    if any(keyword in text for keyword in CONFIRMATION_KEYWORDS):
        return True, "Great! I will start researching now."
    if any(keyword in text for keyword in REVISION_KEYWORDS):
        session.stage = ConversationStage.PLANNING
        session.workplan = None
        revision_reply, _ = handle_planning_stage(llm, session)
        return False, revision_reply
    return False, "Happy to refine the plan. Let me know if anything should change before I begin."


def _build_clarification_prompt(session: SessionState) -> str:
    scope_context = _scope_snapshot(session)
    return f"{prompts.CLARIFICATION_SYSTEM_PROMPT}\n\nCurrent scope snapshot:\n{scope_context}"


def _build_workplan_prompt(session: SessionState) -> str:
    scope_context = _scope_snapshot(session)
    return f"{prompts.WORKPLAN_SYSTEM_PROMPT}\n\nFinal scope context:\n{scope_context}"


def _generate_workplan(llm: LLMClient, session: SessionState) -> str | None:
    workplan_prompt = _build_workplan_prompt(session)
    reply = llm.chat(system_prompt=workplan_prompt, messages=session.chat_history)
    cleaned = reply.strip()
    return cleaned or None


def _scope_snapshot(session: SessionState) -> str:
    snapshot = {
        "company": session.scope.get("company") or session.scope.get("company_name"),
        "region": session.scope.get("region"),
        "segment": session.scope.get("segment"),
        "product_focus": session.scope.get("product_focus"),
        "persona_mode": session.persona_mode or session.scope.get("persona_mode"),
        "depth": session.desired_depth or session.scope.get("depth"),
        "notes": session.scope.get("notes"),
        "raw_scope": session.scope,
    }
    try:
        return json.dumps(snapshot, indent=2, sort_keys=True, default=str)
    except TypeError:
        return str(snapshot)


