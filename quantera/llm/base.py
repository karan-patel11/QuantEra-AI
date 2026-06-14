"""Provider-neutral LLM client interface."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMError(RuntimeError):
    """Raised when an LLM provider cannot return a usable text response."""


class LLMClient(ABC):
    """Minimal provider-neutral text completion interface."""

    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        raise NotImplementedError
