"""Leashed LLM explanation for technicals results."""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

from quantera.llm import get_llm_client
from quantera.llm.base import LLMClient
from quantera.models_technicals import IndicatorStatus, TechnicalsResult


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You explain deterministic price-technical results.

Rules:
- Explain what the provided indicators mean in plain language for a non-expert.
- Use ONLY the numbers and verdicts provided in the input. Never compute, infer, or introduce any number not in the input.
- Never override or soften a verdict. Carry through UNAVAILABLE indicators as data not available.
- Do not convert decimals into percentages or use numbered lists.
- Describe current state only. Do not make buy, sell, hold, price-target, timing, entry, or exit recommendations.
- State explicitly that this is research/education, not financial advice.
- Be concise and neutral.
"""

NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:,\d{3})*(?:\.\d+)?%?")


def generate_explanation(result: TechnicalsResult, llm_client: LLMClient | None = None) -> str:
    payload = _serialize_result(result)
    allowed_numbers = _allowed_numbers(payload)
    try:
        text = _call_llm(payload, llm_client=llm_client)
    except Exception as exc:
        logger.info("Falling back to template technicals summary: %s", exc)
        return render_template_summary(result)

    if _has_untraceable_number(text, allowed_numbers):
        logger.warning("Discarded technicals LLM explanation because it introduced an untraceable number")
        return render_template_summary(result)
    return text.strip()


def render_template_summary(result: TechnicalsResult) -> str:
    lines = [
        f"{result.ticker} technicals summary for research/education only, not financial advice.",
    ]
    verdict_by_indicator = {
        verdict.indicator_name: verdict
        for verdict in result.verdicts
    }
    fragments: list[str] = []
    for indicator in result.indicators:
        verdict = verdict_by_indicator[indicator.name]
        if indicator.status is IndicatorStatus.UNAVAILABLE:
            fragments.append(f"{indicator.display_name}: data not available ({verdict.level.value})")
        else:
            fragments.append(f"{indicator.display_name}: {_fmt(indicator.value)} ({verdict.level.value})")
    lines.append("; ".join(fragments) + ".")
    return "\n".join(lines)


def _call_llm(payload: dict[str, Any], llm_client: LLMClient | None = None) -> str:
    client = llm_client or get_llm_client()
    return client.complete(
        system=SYSTEM_PROMPT,
        user=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        max_tokens=600,
        temperature=0.0,
    )


def _serialize_result(result: TechnicalsResult) -> dict[str, Any]:
    verdict_by_indicator = {
        verdict.indicator_name: verdict
        for verdict in result.verdicts
    }
    serialized_indicators: list[dict[str, Any]] = []
    for indicator in result.indicators:
        verdict = verdict_by_indicator[indicator.name]
        serialized_indicators.append(
            {
                "name": indicator.name,
                "display_name": indicator.display_name,
                "value": _round_indicator(indicator.value),
                "status": indicator.status.value,
                "verdict_level": verdict.level.value,
                "rationale": verdict.rationale,
                "comparison_basis": verdict.comparison_basis,
            }
        )
    return {
        "ticker": result.ticker,
        "indicators": serialized_indicators,
    }


def _allowed_numbers(payload: dict[str, Any]) -> set[float]:
    numbers: set[float] = set()

    def visit(value: Any) -> None:
        if isinstance(value, bool) or value is None:
            return
        if isinstance(value, int | float):
            if math.isfinite(float(value)):
                numbers.add(float(value))
            return
        if isinstance(value, str):
            numbers.update(_numbers_in_text(value))
            return
        if isinstance(value, dict):
            for nested in value.values():
                visit(nested)
            return
        if isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(payload)
    return numbers


def _has_untraceable_number(text: str, allowed_numbers: set[float]) -> bool:
    for output_number in _numbers_in_text(text):
        if not _is_allowed(output_number, allowed_numbers):
            return True
    return False


def _numbers_in_text(text: str) -> list[float]:
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


def _is_allowed(output_number: float, allowed_numbers: set[float]) -> bool:
    for allowed in allowed_numbers:
        if output_number == allowed:
            return True
        decimal_places = (0, 1, 2, 3, 4) if abs(allowed) >= 1 else (1, 2, 3, 4)
        if output_number in {round(allowed, places) for places in decimal_places}:
            return True
    return False


def _round_indicator(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def _fmt(value: float | None) -> str:
    if value is None:
        return "data not available"
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text else "0"
