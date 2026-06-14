"""Anthropic-backed LLM adapter."""

from __future__ import annotations

import os
from typing import Any

from quantera import config
from quantera.llm.base import LLMClient, LLMError


class AnthropicClient(LLMClient):
    """Map QuantEra's neutral LLM interface onto Anthropic messages."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key
        self.model = model or os.getenv("ANTHROPIC_MODEL", config.ANTHROPIC_MODEL)

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        api_key = self.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMError("Anthropic API key is missing; set ANTHROPIC_API_KEY")

        try:
            from anthropic import Anthropic

            client = Anthropic(api_key=api_key)
            message = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            text = _extract_message_text(message)
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Anthropic completion failed: {exc}") from exc

        if not text:
            raise LLMError("Anthropic completion did not contain text")
        return text


def _extract_message_text(message: Any) -> str:
    parts: list[str] = []
    for block in getattr(message, "content", []):
        if isinstance(block, dict):
            if block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            continue
        if getattr(block, "type", None) == "text":
            parts.append(str(getattr(block, "text", "")))
    return "\n".join(part for part in parts if part).strip()
