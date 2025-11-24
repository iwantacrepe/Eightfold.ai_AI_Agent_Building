"""LLM abstraction layer that hides provider-specific details."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

try:  # Optional import: OpenAI
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore

try:  # Optional import: Gemini via langchain-google-genai
    from langchain_google_genai import ChatGoogleGenerativeAI
except Exception:  # pragma: no cover
    ChatGoogleGenerativeAI = None  # type: ignore


class DummyLLM:
    """Lightweight fallback when no provider keys are configured."""

    def __init__(self) -> None:
        self.model_name = "dummy-local-model"

    def invoke(self, messages: List[Any], **_: Any) -> AIMessage:
        last_user = ""
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                last_user = message.content
                break
        summary = f"I am using an offline fallback. Received: {last_user[:200]}"
        return AIMessage(content=summary)


class LLMClient:
    """Small facade for whichever chat model the user selects."""

    def __init__(
        self,
        provider: Optional[str] = None,
        temperature: float = 0.2,
        openai_model: str = "gpt-4o-mini",
        gemini_model: str = "gemini-2.5-flash",
    ) -> None:
        self.provider = (provider or os.getenv("LLM_PROVIDER") or "gemini").lower()
        self.temperature = temperature
        self.openai_model = openai_model
        self.gemini_model = gemini_model
        self._client = self._build_client()

    def _build_client(self):
        if self.provider == "openai" and ChatOpenAI and os.getenv("OPENAI_API_KEY"):
            return ChatOpenAI(model=self.openai_model, temperature=self.temperature)
        if self.provider in {"gemini", "google", "google-gemini"} and ChatGoogleGenerativeAI and os.getenv(
            "GEMINI_API_KEY"
        ):
            return ChatGoogleGenerativeAI(model=self.gemini_model, temperature=self.temperature)
        return DummyLLM()

    def chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        response_format: Optional[str] = None,
    ) -> str:
        """Send a chat conversation and optionally ask for JSON output."""

        lc_messages = [SystemMessage(content=system_prompt)]
        for item in messages:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        extra_kwargs: Dict[str, Any] = {}
        if response_format == "json":
            if self.provider == "openai" and ChatOpenAI:
                extra_kwargs["response_format"] = {"type": "json_object"}
            elif self.provider.startswith("gemini") and ChatGoogleGenerativeAI:
                extra_kwargs["response_mime_type"] = "application/json"

        response = self._client.invoke(lc_messages, **extra_kwargs)
        if isinstance(response, AIMessage):
            return response.content
        if isinstance(response, str):
            return response
        return json.dumps(response, default=str)

    def structured_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Return a JSON object. Falls back to empty dict on parse failure."""

        raw = self.chat(system_prompt=system_prompt, messages=messages, response_format="json")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"assistant_reply": raw}
