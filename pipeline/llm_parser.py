"""Stage 2 — LLM parsing: Markdown → Structured JSON.

Supports two backends:
  - LM Studio  (OpenAI-compatible local/remote server)
  - OpenRouter  (cloud API, model: liquid/lfm-2-24b-a2b)

Selected via LLM_BACKEND env var.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from pipeline.config import config, LLMBackendType
from pipeline.schema import build_system_prompt, Resume

logger = logging.getLogger(__name__)


# ── JSON cleanup ────────────────────────────────────────────────────────────

def _clean_json_output(raw: str) -> str:
    """Strip markdown fences and conversational preamble from LLM output.

    Attempts in order:
    1. Parse entire string as JSON directly.
    2. Extract content from ```json ... ``` fences.
    3. Extract content from ``` ... ``` fences.
    4. Find the first { and last } and return that slice.
    """
    raw = raw.strip()

    if raw.startswith("{"):
        return raw

    m = re.search(r"```json\s*(.*?)\s*```", raw, re.DOTALL)
    if m:
        return m.group(1).strip()

    m = re.search(r"```\s*(.*?)\s*```", raw, re.DOTALL)
    if m:
        return m.group(1).strip()

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1]

    return raw


# ── Abstract backend ────────────────────────────────────────────────────────

class LLMBackend(ABC):
    """Abstract base for LLM backends."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend identifier."""
        ...

    @abstractmethod
    async def parse_markdown(self, markdown: str) -> dict[str, Any]:
        """Send markdown to the LLM and return parsed resume dict.

        Raises:
            httpx.HTTPError: On network/API errors.
            json.JSONDecodeError: If LLM output is not valid JSON.
        """
        ...

    def _build_payload(self, model: str, temperature: float, max_tokens: int) -> dict:
        """Build the chat completion payload shared by both backends."""
        return {
            "model": model,
            "messages": [
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": None},  # filled per-call
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

    def _parse_response(self, raw_content: str) -> dict[str, Any]:
        """Clean, parse, and validate LLM output."""
        cleaned = _clean_json_output(raw_content)
        parsed = json.loads(cleaned)
        resume = Resume.model_validate(parsed)
        return resume.model_dump(exclude_none=True)


# ── LM Studio ───────────────────────────────────────────────────────────────

class LMStudioBackend(LLMBackend):
    """Calls a local or remote LM Studio server (OpenAI-compatible API)."""

    @property
    def name(self) -> str:
        return f"lmstudio/{config.lm_studio_model}"

    async def parse_markdown(self, markdown: str) -> dict[str, Any]:
        url = f"{config.lm_studio_base_url}/chat/completions"
        payload = self._build_payload(
            config.lm_studio_model,
            config.lm_studio_temperature,
            config.lm_studio_max_tokens,
        )
        payload["messages"][1]["content"] = (
            f"Extract the resume data from this markdown:\n\n{markdown}"
        )

        logger.info("LM Studio → %s (model=%s)", url, config.lm_studio_model)

        async with httpx.AsyncClient(timeout=config.lm_studio_timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        data = response.json()
        raw_content = data["choices"][0]["message"]["content"]
        logger.debug("LM Studio raw: %s", raw_content[:300])

        return self._parse_response(raw_content)


# ── OpenRouter ──────────────────────────────────────────────────────────────

class OpenRouterBackend(LLMBackend):
    """Calls OpenRouter API (liquid/lfm-2-24b-a2b or similar)."""

    @property
    def name(self) -> str:
        return f"openrouter/{config.openrouter_model}"

    async def parse_markdown(self, markdown: str) -> dict[str, Any]:
        url = f"{config.openrouter_base_url}/chat/completions"
        payload = self._build_payload(
            config.openrouter_model,
            config.openrouter_temperature,
            config.openrouter_max_tokens,
        )
        payload["messages"][1]["content"] = (
            f"Extract the resume data from this markdown:\n\n{markdown}"
        )

        headers = {
            "Authorization": f"Bearer {config.openrouter_api_key}",
            "HTTP-Referer": "http://localhost:8000",  # OpenRouter requires this
            "X-Title": "OCR Pipeline Resume Extractor",
        }

        logger.info("OpenRouter → %s (model=%s)", url, config.openrouter_model)

        async with httpx.AsyncClient(timeout=config.openrouter_timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()

        data = response.json()
        raw_content = data["choices"][0]["message"]["content"]
        logger.debug("OpenRouter raw: %s", raw_content[:300])

        return self._parse_response(raw_content)


# ── Backend factory ─────────────────────────────────────────────────────────

def get_backend() -> LLMBackend:
    """Return the configured LLM backend instance."""
    if config.llm_backend == LLMBackendType.OPENROUTER:
        if not config.openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required when LLM_BACKEND=openrouter"
            )
        return OpenRouterBackend()
    return LMStudioBackend()


# ── Convenience ─────────────────────────────────────────────────────────────

async def parse_markdown(markdown: str) -> tuple[dict[str, Any], str]:
    """Parse markdown using the configured backend.

    Returns (result_dict, backend_name) for logging/audit.
    """
    backend = get_backend()
    result = await backend.parse_markdown(markdown)
    return result, backend.name
