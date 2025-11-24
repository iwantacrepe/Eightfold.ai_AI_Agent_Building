"""LLM abstraction layer that hides provider-specific details."""

from __future__ import annotations

import json
import logging
import os
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

try:  # Optional import: OpenAI
    from langchain_openai import ChatOpenAI  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore

try:  # Optional import: Gemini via langchain-google-genai
    from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    ChatGoogleGenerativeAI = None  # type: ignore

try:  # Optional import: native google genai client for audio uploads
    from google import genai  # type: ignore[import-not-found]
    from google.genai import types as genai_types  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    genai = None  # type: ignore
    genai_types = None  # type: ignore


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

    def transcribe_audio(self, *_: Any, **__: Any) -> str:
        return ""


class LLMClient:
    """Small facade for whichever chat model the user selects."""

    INLINE_AUDIO_LIMIT_BYTES = 18 * 1024 * 1024  # stay comfortably under 20MB inline cap

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
        self._gemini_client: Optional[Any] = None
        self._logger = logging.getLogger(__name__)

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

        lc_messages: List[BaseMessage] = [SystemMessage(content=system_prompt)]
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
            if isinstance(response.content, str):
                return response.content
            return json.dumps(response.content, default=str)
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

    def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/webm") -> str:
        """Use Gemini to turn audio into text, switching to Files API for large payloads."""

        if not audio_bytes or not self.provider.startswith("gemini"):
            return ""

        client = self._ensure_gemini_client()
        if not client or not genai_types:
            return ""

        try:
            prompt = "Transcribe the user's speech exactly as text."
            if len(audio_bytes) > self.INLINE_AUDIO_LIMIT_BYTES:
                response = self._generate_content_with_file_upload(client, audio_bytes, mime_type or "audio/webm", prompt)
            else:
                audio_part = genai_types.Part.from_bytes(
                    data=audio_bytes,
                    mime_type=mime_type or "audio/webm",
                )
                response = client.models.generate_content(
                    model=self.gemini_model,
                    contents=[prompt, audio_part],
                )
            text = getattr(response, "text", None)
            if text:
                return text.strip()
            candidates = getattr(response, "candidates", None)
            if candidates:
                for candidate in candidates:
                    candidate_text = getattr(candidate, "content", None)
                    if isinstance(candidate_text, str) and candidate_text.strip():
                        return candidate_text.strip()
                    parts = getattr(candidate, "parts", None)
                    if parts:
                        combined = " ".join(str(part) for part in parts if str(part).strip())
                        if combined:
                            return combined.strip()
        except Exception as exc:  # pragma: no cover - API/mime failures
            self._logger.exception("Gemini audio transcription failed: %s", exc)
            return ""
        return ""

    def _ensure_gemini_client(self):
        if not genai or not os.getenv("GEMINI_API_KEY"):
            return None
        if not self._gemini_client:
            self._gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        return self._gemini_client

    def _generate_content_with_file_upload(self, client, audio_bytes: bytes, mime_type: str, prompt: str):
        """Upload large audio via Files API before calling generate_content."""

        suffix = self._extension_for_mime(mime_type)
        temp_path = None
        try:
            with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file.write(audio_bytes)
                temp_path = temp_file.name

            upload_kwargs = {"file": temp_path}
            if mime_type:
                upload_kwargs["mime_type"] = mime_type

            uploaded_file = client.files.upload(**upload_kwargs)
            return client.models.generate_content(
                model=self.gemini_model,
                contents=[prompt, uploaded_file],
            )
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    self._logger.warning("Failed to cleanup temp audio file: %%s", temp_path)

    @staticmethod
    def _extension_for_mime(mime_type: str) -> str:
        mapping = {
            "audio/webm": ".webm",
            "audio/webm;codecs=opus": ".webm",
            "audio/mp3": ".mp3",
            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/ogg": ".ogg",
        }
        return mapping.get(mime_type.lower(), ".bin")
