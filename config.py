"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True)
class Settings:
    debug: bool = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    secret_key: str = os.getenv("FLASK_SECRET_KEY", "change-me")
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


def get_settings() -> Settings:
    return Settings()
