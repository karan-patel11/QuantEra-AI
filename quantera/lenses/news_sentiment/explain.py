"""Shared LLM and guardrail utilities for the news sentiment lens."""

from __future__ import annotations

import json
import math
import re
from typing import Any
from urllib.parse import urlparse

from quantera.llm import get_llm_client
from quantera.llm.base import LLMClient

URL_PATTERN = re.compile(r"https?://[^\s)\]}>,\"']+", re.IGNORECASE)
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:,\d{3})*(?:\.\d+)?%?")
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
ADVICE_PATTERN = re.compile(
    r"\b(buy|sell|hold|short|go long|go short|price target|entry point|exit point|"
    r"take profit|stop loss)\b",
    re.IGNORECASE,
)


def call_llm(
    payload: dict[str, Any],
    system_prompt: str,
    max_tokens: int = 600,
    llm_client: LLMClient | None = None,
) -> str:
    client = llm_client or get_llm_client()
    return client.complete(
        system=system_prompt,
        user=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        max_tokens=max_tokens,
        temperature=0.0,
    )


def parse_json_response(text: str) -> Any:
    """Parse strict JSON, tolerating a surrounding markdown code fence."""

    stripped = text.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)```", stripped, re.IGNORECASE | re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    for start_char, end_char in (("{", "}"), ("[", "]")):
        start = stripped.find(start_char)
        end = stripped.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            return json.loads(stripped[start : end + 1])
    raise ValueError("LLM response was not valid JSON")


def urls_in_text(text: str) -> list[str]:
    return [match.group(0).rstrip(".,;:") for match in URL_PATTERN.finditer(text)]


def citations_in_text(text: str) -> list[tuple[str, str]]:
    return [
        (match.group(1).strip(), match.group(2).strip().rstrip(".,;:"))
        for match in MARKDOWN_LINK_PATTERN.finditer(text)
    ]


def has_disallowed_url(text: str, allowed_urls: set[str]) -> bool:
    normalized_allowed = {_normalize_url(url) for url in allowed_urls}
    return any(_normalize_url(url) not in normalized_allowed for url in urls_in_text(text))


def has_bad_markdown_citation(
    text: str,
    allowed_source_names: set[str],
    allowed_urls: set[str],
) -> bool:
    normalized_allowed_urls = {_normalize_url(url) for url in allowed_urls}
    normalized_names = {_normalize_name(name) for name in allowed_source_names}
    for citation_name, citation_url in citations_in_text(text):
        if _normalize_url(citation_url) not in normalized_allowed_urls:
            return True
        normalized_citation = _normalize_name(citation_name)
        if not any(name and name in normalized_citation for name in normalized_names):
            return True
    return False


def has_untraceable_number(text: str, allowed_payload: Any) -> bool:
    allowed_numbers = _allowed_numbers(allowed_payload)
    for output_number in numbers_in_text(text):
        if not _is_allowed(output_number, allowed_numbers):
            return True
    return False


def numbers_in_text(text: str) -> list[float]:
    numbers: list[float] = []
    for match in NUMBER_PATTERN.finditer(text):
        raw = match.group(0).replace(",", "")
        if raw.endswith("%"):
            raw = raw[:-1]
        try:
            value = float(raw)
        except ValueError:
            continue
        if math.isfinite(value):
            numbers.append(value)
    return numbers


def contains_advice_language(text: str) -> bool:
    return ADVICE_PATTERN.search(text) is not None


def text_contains_span(text: str, span: str) -> bool:
    normalized_text = _normalize_span(text)
    normalized_span = _normalize_span(span)
    return bool(normalized_span) and normalized_span in normalized_text


def trim_words(text: str, max_words: int = 12, max_chars: int = 160) -> str:
    words = text.strip().split()
    trimmed = " ".join(words[:max_words])
    if len(trimmed) > max_chars:
        trimmed = trimmed[:max_chars].rsplit(" ", maxsplit=1)[0]
    return trimmed.strip()


def _allowed_numbers(payload: Any) -> set[float]:
    numbers: set[float] = set()

    def visit(value: Any) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, int | float):
            if math.isfinite(float(value)):
                numbers.add(float(value))
            return
        if isinstance(value, str):
            numbers.update(numbers_in_text(value))
            return
        if isinstance(value, dict):
            for nested in value.values():
                visit(nested)
            return
        if isinstance(value, list | tuple):
            for nested in value:
                visit(nested)

    visit(payload)
    return numbers


def _is_allowed(output_number: float, allowed_numbers: set[float]) -> bool:
    for allowed in allowed_numbers:
        if output_number == allowed:
            return True
        decimal_places = (0, 1, 2, 3, 4) if abs(allowed) >= 1 else (1, 2, 3, 4)
        if output_number in {round(allowed, places) for places in decimal_places}:
            return True
    return False


def _normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme.lower()}://{netloc}{path}"


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _normalize_span(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
