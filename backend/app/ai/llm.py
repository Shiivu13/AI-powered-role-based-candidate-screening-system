"""LLM provider abstraction.

Every AI component asks the LLM for *structured JSON* via
:meth:`LLMClient.generate_json`. When no provider is configured (or a call
fails), components fall back to deterministic heuristics so the system stays
usable end to end. Every output records which path produced it
(``mode: "llm" | "heuristic"``) for traceability.
"""
from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod

from app.config import get_settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class LLMClient(ABC):
    name: str = "base"
    model: str = ""

    @property
    def available(self) -> bool:
        return True

    @abstractmethod
    def generate_json(self, system: str, user: str, *, temperature: float | None = None) -> dict:
        """Return a parsed JSON object or raise :class:`LLMError`."""


class OfflineLLM(LLMClient):
    name = "offline"
    model = "heuristic"

    @property
    def available(self) -> bool:
        return False

    def generate_json(self, system: str, user: str, *, temperature: float | None = None) -> dict:
        raise LLMError("No LLM provider configured (set GEMINI_API_KEY).")


def _extract_json(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise LLMError(f"LLM did not return JSON: {text[:200]}")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise LLMError("LLM JSON output is not an object")
    return data


class GeminiLLM(LLMClient):
    name = "gemini"

    def __init__(self, api_key: str, model: str, temperature: float, timeout: int):
        from google import genai
        from google.genai import types

        self._types = types
        # v1beta is required: the v1 endpoint rejects system instructions
        # ("Developer instruction is not enabled for api version v1").
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(api_version="v1beta", timeout=timeout * 1000)
        )
        self.model = model
        self.temperature = temperature

    def generate_json(self, system: str, user: str, *, temperature: float | None = None) -> dict:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=user,
                    config=self._types.GenerateContentConfig(
                        system_instruction=system,
                        temperature=self.temperature if temperature is None else temperature,
                        response_mime_type="application/json",
                    ),
                )
                return _extract_json(response.text or "")
            except LLMError as exc:
                last_error = exc
            except Exception as exc:  # network / quota / server errors
                last_error = exc
                if "429" in str(exc) or "503" in str(exc) or "quota" in str(exc).lower():
                    time.sleep(1.5 * (attempt + 1))
                    continue
                break
        logger.warning("Gemini call failed: %s", last_error)
        raise LLMError(str(last_error))


_LLM: LLMClient | None = None


def get_llm() -> LLMClient:
    global _LLM
    if _LLM is None:
        settings = get_settings()
        if settings.effective_llm_provider == "gemini" and settings.gemini_api_key:
            _LLM = GeminiLLM(
                settings.gemini_api_key,
                settings.llm_model,
                settings.llm_temperature,
                settings.llm_timeout_seconds,
            )
        else:
            _LLM = OfflineLLM()
        logger.info("LLM provider: %s (%s)", _LLM.name, _LLM.model)
    return _LLM


def set_llm(client: LLMClient | None) -> None:
    """Override the provider (used by tests)."""
    global _LLM
    _LLM = client
