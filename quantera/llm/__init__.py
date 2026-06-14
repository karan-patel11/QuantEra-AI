"""Swappable LLM client factory."""

from __future__ import annotations

import os

from quantera import config
from quantera.llm.base import LLMClient, LLMError


def get_llm_client() -> LLMClient:
    provider = os.getenv("LLM_PROVIDER", config.LLM_PROVIDER).strip().lower()
    if provider == "groq":
        from quantera.llm.groq_client import GroqClient

        return GroqClient()
    if provider == "anthropic":
        from quantera.llm.anthropic_client import AnthropicClient

        return AnthropicClient()
    raise LLMError("Unsupported LLM_PROVIDER; use 'groq' or 'anthropic'")


__all__ = ["LLMClient", "LLMError", "get_llm_client"]
