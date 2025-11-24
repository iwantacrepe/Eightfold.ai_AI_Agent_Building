"""Analysis agent group turning research bundles into structured plans."""

from __future__ import annotations

import json

from typing import List, Optional

from core.models import AccountPlan, ConversationStage, PlanSection, ResearchBundle, SessionState
from core.progress import log_progress
from llm.client import LLMClient
from llm import prompts

SECTION_PROGRESS = {
    PlanSection.OVERVIEW: "🧠 Building overview…",
    PlanSection.INDUSTRY: "🌐 Mapping industry dynamics…",
    PlanSection.FINANCIALS: "💰 Summarizing financials…",
    PlanSection.TALENT: "👥 Assessing talent trends…",
    PlanSection.LEADERSHIP: "🤝 Profiling leadership…",
    PlanSection.NEWS: "📰 Compiling news triggers…",
    PlanSection.SWOT: "⚖️ Drafting SWOT…",
    PlanSection.OPPORTUNITIES: "🚀 Identifying opportunities…",
    PlanSection.STRATEGY: "📋 Designing strategy…",
    PlanSection.PLAN_30_60_90: "🗓️ Framing 30-60-90 plan…",
}


def run_group2_analysis(llm: LLMClient, session: SessionState) -> SessionState:
    """Generate each account plan section via dedicated prompts."""

    if not session.research_bundle:
        raise ValueError("Research bundle missing. Run Group 1 before Group 2.")

    bundle_json = json.dumps(session.research_bundle.__dict__, default=str, ensure_ascii=False)
    plan = AccountPlan(company_name=session.research_bundle.company_name, scope=session.research_bundle.scope)

    for section in PlanSection.ordered():
        log_progress(session, SECTION_PROGRESS.get(section, f"Generating {section.value}…"))
        try:
            content = generate_section(llm, section, bundle_json, session)
        except Exception as exc:  # pragma: no cover - defensive fallback
            log_progress(session, f"Fallback used for {section.value.replace('_', ' ')}: {exc}")
            content = build_fallback_section(section, session.research_bundle, exc)
        setattr(plan, section.value, content.strip())

    session.account_plan = plan
    session.stage = ConversationStage.REVIEWING
    log_progress(session, "📄 Account plan ready. You can review it now.")
    return session


def generate_section(
    llm: LLMClient,
    section: PlanSection,
    bundle_json: str,
    session: SessionState,
    instruction: Optional[str] = None,
) -> str:
    """Call the LLM to transform the research bundle into a section string."""

    system_prompt = "You are an enterprise GTM strategist producing a structured report."
    persona_line = f"Persona mode: {session.persona_mode or 'analyst'} | Depth: {session.desired_depth or 'detailed'}"
    instruction_line = f"Additional direction from user: {instruction}\n" if instruction else ""
    user_prompt = f"""
{prompts.SECTION_PROMPTS[section]}

Context:
{bundle_json}

{persona_line}
{instruction_line}
"""
    return llm.chat(system_prompt=system_prompt, messages=[{"role": "user", "content": user_prompt}])


def build_fallback_section(section: PlanSection, bundle: ResearchBundle, error: Exception) -> str:
    """Return a graceful text block when the LLM call fails."""

    label = section.value.replace("_", " ").title()
    lines: List[str] = [f"{label}", "", "Automated fallback summary while the strategy agents retry."]
    insights = _section_insights(section, bundle)
    if insights:
        lines.extend(insights)
    else:
        lines.append("- Review the Research Feed for supporting evidence from Group 1.")
    lines.append(f"(Reason: {error})")
    return "\n".join(lines)


def _section_insights(section: PlanSection, bundle: ResearchBundle) -> List[str]:
    highlights: List[str] = []
    if section == PlanSection.FINANCIALS and bundle.financials:
        summary = bundle.financials.get("summary")
        if summary:
            highlights.append(f"- { _truncate(summary) }")
        metrics = bundle.financials.get("metrics") or {}
        for label, value in list(metrics.items())[:4]:
            highlights.append(f"- {label.replace('_', ' ').title()}: {value}")
        return highlights

    if section == PlanSection.NEWS and bundle.news_results:
        for article in bundle.news_results[:3]:
            title = article.get("title") or "News"
            snippet = article.get("summary") or article.get("content") or "Recent development"
            highlights.append(f"- {title}: { _truncate(snippet) }")
        return highlights

    if section == PlanSection.LEADERSHIP and bundle.leadership:
        for leader in bundle.leadership[:4]:
            name = leader.get("title") or leader.get("name") or "Leader"
            focus = leader.get("focus") or leader.get("summary") or leader.get("content")
            snippet = _truncate(focus) if focus else "Priority captured in research feed."
            highlights.append(f"- {name}: {snippet}")
        return highlights

    if section == PlanSection.TALENT and bundle.hiring_trends:
        for trend in bundle.hiring_trends[:3]:
            role = trend.get("title") or trend.get("role") or "Hiring note"
            snippet = trend.get("summary") or trend.get("content") or trend.get("description")
            highlights.append(f"- {role}: { _truncate(snippet or 'Hiring insight available.') }")
        return highlights

    if section == PlanSection.OPPORTUNITIES and bundle.competitors:
        for rival in bundle.competitors[:3]:
            name = rival.get("title") or rival.get("name") or "Competitor"
            snippet = rival.get("summary") or rival.get("content") or "Differentiation angle"
            highlights.append(f"- {name}: { _truncate(snippet) }")
        return highlights

    snippet = _first_snippet(bundle)
    if snippet:
        highlights.append(f"- {snippet}")

    coverage = _coverage_summary(bundle)
    if coverage:
        highlights.append(f"- Coverage: {coverage}")
    return highlights


def _first_snippet(bundle: ResearchBundle) -> str:
    """Pick the first meaningful snippet from available sources."""

    pools: List[List[dict]] = []
    if bundle.wiki_summary:
        pools.append([bundle.wiki_summary])
    if bundle.web_results:
        pools.append(bundle.web_results)
    if bundle.news_results:
        pools.append(bundle.news_results)
    for pool in pools:
        for record in pool:
            for key in ("summary", "content", "snippet", "description"):
                value = record.get(key)
                if isinstance(value, str) and value.strip():
                    return _truncate(value)
    return ""


def _coverage_summary(bundle: ResearchBundle) -> str:
    counts = {
        "web": len(bundle.web_results),
        "news": len(bundle.news_results),
        "leaders": len(bundle.leadership),
        "talent": len(bundle.hiring_trends),
        "competitors": len(bundle.competitors),
    }
    parts = [f"{label}: {count}" for label, count in counts.items() if count]
    return ", ".join(parts)


def _truncate(text: str, limit: int = 240) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"
