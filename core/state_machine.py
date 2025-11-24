"""High-level orchestration of the conversational flow."""

from __future__ import annotations

from typing import Optional

from agents import group1_research, group2_analysis, planner_agent, search_planner, selective_update
from core.models import ConversationStage, PlanSection, SessionState
from core.progress import log_progress
from llm.client import LLMClient


def handle_user_message(session: SessionState, llm: LLMClient, user_message: str) -> tuple[SessionState, str]:
    """Route a user message to the appropriate stage handler."""

    session.chat_history.append({"role": "user", "content": user_message})
    stage = session.stage

    if stage == ConversationStage.PLANNING:
        assistant_reply, _ = planner_agent.handle_planning_stage(llm, session)
    elif stage == ConversationStage.CONFIRMING_PLAN:
        assistant_reply = _handle_confirming_stage(session, llm, user_message)
    elif stage in {ConversationStage.RESEARCHING, ConversationStage.ANALYZING}:
        assistant_reply = "I'm still executing the research workflow. You'll see progress updates as each agent completes."
    elif stage == ConversationStage.REVIEWING:
        assistant_reply = _handle_reviewing_stage(session, llm, user_message)
    elif stage == ConversationStage.EDITING:
        assistant_reply = "I'm updating the requested section. Give me a second and I'll share the revision."
    else:
        assistant_reply = "The plan is complete. Ask for edits or start a new company brief whenever you're ready."

    session.chat_history.append({"role": "assistant", "content": assistant_reply})
    return session, assistant_reply


def _handle_confirming_stage(session: SessionState, llm: LLMClient, user_message: str) -> str:
    confirmed, reply = planner_agent.handle_confirming_plan_stage(llm, session, user_message)
    if not confirmed:
        return reply

    session.stage = ConversationStage.RESEARCHING
    log_progress(session, "🧭 Translating the workplan into research runs…")
    session.search_tasks = search_planner.build_search_tasks(llm, session)
    if not session.search_tasks:
        log_progress(session, "⚙️ Using default research sweep.")
    group1_research.run_group1_research(llm, session, session.search_tasks)

    session.stage = ConversationStage.ANALYZING
    log_progress(session, "🧠 Handing insights to strategy agents…")
    group2_analysis.run_group2_analysis(llm, session)

    return (
        "I've completed the research and created your account plan. "
        "Review it in the Account Plan tab and tell me if you'd like to refine any section."
    )


def _handle_reviewing_stage(session: SessionState, llm: LLMClient, user_message: str) -> str:
    section = _detect_section_from_text(user_message)
    if not section:
        return (
            "Your plan is ready. Ask me to regenerate a section (e.g., 'Update opportunities to focus on healthcare AI') "
            "or request a PDF export when you're happy."
        )

    selective_update.regenerate_section(llm, session, section, user_instruction=user_message)
    return f"I've updated the {section.value.replace('_', ' ')} section. Anything else?"


def _detect_section_from_text(text: str) -> Optional[PlanSection]:
    normalized = text.lower()
    for section in PlanSection:
        if section.value in normalized or section.name.lower() in normalized:
            return section
        label = section.value.replace("_", " ")
        if label in normalized:
            return section
    return None
