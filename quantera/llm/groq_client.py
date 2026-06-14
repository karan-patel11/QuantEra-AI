"""Groq-backed LLM adapter.

This is intentionally the only production module that imports the Groq SDK or
makes Groq chat-completions calls.
"""

from __future__ import annotations

import os
from typing import Any

from quantera import config
from quantera.llm.base import LLMClient, LLMError


class GroqClient(LLMClient):
    """Map QuantEra's neutral LLM interface onto Groq chat completions."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key
        self.model = model or os.getenv("GROQ_MODEL", config.GROQ_MODEL)

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        api_key = self.api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise LLMError("Groq API key is missing; set GROQ_API_KEY")

        try:
            from groq import Groq

            client = Groq(api_key=api_key)
            completion = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            text = _extract_chat_text(completion)
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Groq completion failed: {exc}") from exc

        if not text:
            raise LLMError("Groq completion did not contain text")
        return text


def _extract_chat_text(completion: Any) -> str:
    choices = getattr(completion, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", "") if message is not None else ""
    if isinstance(content, list):
        return "\n".join(
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") in (None, "text")
        ).strip()
    return str(content).strip()
