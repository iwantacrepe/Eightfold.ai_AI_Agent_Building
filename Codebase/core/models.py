"""Dataclasses and enums describing the research workflow state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ConversationStage(str, Enum):
    """Possible stages of the multi-step assistant."""

    PLANNING = "planning"
    CONFIRMING_PLAN = "confirming_plan"
    RESEARCHING = "researching"
    ANALYZING = "analyzing"
    REVIEWING = "reviewing"
    EDITING = "editing"
    DONE = "done"


class PlanSection(str, Enum):
    """Sections comprising the final account plan."""

    OVERVIEW = "overview"
    INDUSTRY = "industry"
    FINANCIALS = "financials"
    TALENT = "talent"
    LEADERSHIP = "leadership"
    NEWS = "news"
    SWOT = "swot"
    OPPORTUNITIES = "opportunities"
    STRATEGY = "strategy"
    PLAN_30_60_90 = "plan_30_60_90"

    @classmethod
    def ordered(cls) -> List["PlanSection"]:
        """Return sections in the display order used by the UI/PDF."""

        return [
            cls.OVERVIEW,
            cls.INDUSTRY,
            cls.FINANCIALS,
            cls.TALENT,
            cls.LEADERSHIP,
            cls.NEWS,
            cls.SWOT,
            cls.OPPORTUNITIES,
            cls.STRATEGY,
            cls.PLAN_30_60_90,
        ]


@dataclass
class ResearchBundle:
    """Structured payload containing all collected research inputs."""

    company_name: str
    scope: Dict[str, Any]
    web_results: List[Dict[str, Any]] = field(default_factory=list)
    news_results: List[Dict[str, Any]] = field(default_factory=list)
    financials: Dict[str, Any] = field(default_factory=dict)
    hiring_trends: List[Dict[str, Any]] = field(default_factory=list)
    competitors: List[Dict[str, Any]] = field(default_factory=list)
    leadership: List[Dict[str, Any]] = field(default_factory=list)
    sentiment: Dict[str, Any] = field(default_factory=dict)
    raw_documents: List[str] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    wiki_summary: Dict[str, Any] = field(default_factory=dict)
    search_plan: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AccountPlan:
    """Final structured deliverable consumed by the UI and PDF builder."""

    company_name: str
    scope: Dict[str, Any]
    overview: str = ""
    industry: str = ""
    financials: str = ""
    talent: str = ""
    leadership: str = ""
    news: str = ""
    swot: str = ""
    opportunities: str = ""
    strategy: str = ""
    plan_30_60_90: str = ""
    version: int = 1


@dataclass
class SessionState:
    """Ephemeral in-memory context for an individual conversation."""

    session_id: str
    stage: ConversationStage = ConversationStage.PLANNING
    persona_mode: Optional[str] = None
    scope: Dict[str, Any] = field(default_factory=dict)
    desired_depth: Optional[str] = None
    workplan: Optional[str] = None
    research_bundle: Optional[ResearchBundle] = None
    account_plan: Optional[AccountPlan] = None
    progress_log: List[str] = field(default_factory=list)
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    search_tasks: List[Dict[str, Any]] = field(default_factory=list)
    research_activity: List[Dict[str, Any]] = field(default_factory=list)
