from __future__ import annotations

import os

import pytest

from quantera.llm import get_llm_client


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("GROQ_API_KEY"), reason="GROQ_API_KEY is not set")
def test_live_groq_smoke_returns_text(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")

    output = get_llm_client().complete(
        system="You are concise.",
        user="Reply with the single word OK.",
        max_tokens=8,
        temperature=0.0,
    )
    print(output)

    assert "OK" in output.upper()
