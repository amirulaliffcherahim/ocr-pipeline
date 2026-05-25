"""Centralized configuration via environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class LLMBackendType(str, Enum):
    LM_STUDIO = "lmstudio"
    OPENROUTER = "openrouter"


@dataclass
class Config:
    # ── LLM Backend selection ───────────────────────────────────────────────
    llm_backend: LLMBackendType = LLMBackendType(os.getenv("LLM_BACKEND", "lmstudio"))

    # ── LM Studio (local/remote) ────────────────────────────────────────────
    lm_studio_base_url: str = os.getenv(
        "LM_STUDIO_BASE_URL",
        "http://ai.amirulaliff.com:1234/v1",
    )
    lm_studio_model: str = os.getenv("LM_STUDIO_MODEL", "gemma-3-4b-it")
    lm_studio_timeout: int = int(os.getenv("LM_STUDIO_TIMEOUT", "120"))
    lm_studio_temperature: float = float(os.getenv("LM_STUDIO_TEMPERATURE", "0.0"))
    lm_studio_max_tokens: int = int(os.getenv("LM_STUDIO_MAX_TOKENS", "4096"))

    # ── OpenRouter ──────────────────────────────────────────────────────────
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_base_url: str = os.getenv(
        "OPENROUTER_BASE_URL",
        "https://openrouter.ai/api/v1",
    )
    openrouter_model: str = os.getenv(
        "OPENROUTER_MODEL",
        "liquid/lfm-2-24b-a2b",
    )
    openrouter_timeout: int = int(os.getenv("OPENROUTER_TIMEOUT", "120"))
    openrouter_temperature: float = float(os.getenv("OPENROUTER_TEMPERATURE", "0.0"))
    openrouter_max_tokens: int = int(os.getenv("OPENROUTER_MAX_TOKENS", "4096"))

    # ── General ─────────────────────────────────────────────────────────────
    file_size_limit: int = 10 * 1024 * 1024  # 10 MB

    @property
    def is_llm_configured(self) -> bool:
        """Check if the selected backend has required credentials."""
        if self.llm_backend == LLMBackendType.OPENROUTER:
            return bool(self.openrouter_api_key)
        return True  # LM Studio requires no auth


# Singleton
config = Config()
