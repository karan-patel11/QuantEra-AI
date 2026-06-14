from __future__ import annotations

import pytest

from quantera.llm import get_llm_client
from quantera.llm.base import LLMError


def test_get_llm_client_defaults_to_groq(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)

    client = get_llm_client()

    assert client.__class__.__name__ == "GroqClient"
    assert client.__class__.__module__ == "quantera.llm.groq_client"


def test_get_llm_client_selects_anthropic(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")

    client = get_llm_client()

    assert client.__class__.__name__ == "AnthropicClient"
    assert client.__class__.__module__ == "quantera.llm.anthropic_client"


def test_get_llm_client_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unknown")

    with pytest.raises(LLMError):
        get_llm_client()
