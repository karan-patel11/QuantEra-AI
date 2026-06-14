"""Leashed LLM explanation for fundamentals results."""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any

from quantera.llm import get_llm_client
from quantera.llm.base import LLMClient
from quantera.models_fundamentals import FundamentalsResult, MetricStatus


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You explain deterministic financial-ratio results.

Rules:
- Explain what the provided metrics mean in plain language for a non-expert.
- Use ONLY the numbers and verdicts provided in the input. Never compute, infer, or introduce any number not in the input.
- Never override or soften a verdict. Carry through UNAVAILABLE metrics as data not available.
- Do not convert decimals into percentages or use numbered lists.
- State explicitly that this is research/education, not financial advice.
- Be concise and neutral. Do not make buy, sell, hold, price-target, or timing recommendations.
"""

NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])[-+]?\d+(?:,\d{3})*(?:\.\d+)?%?")


def generate_explanation(result: FundamentalsResult, llm_client: LLMClient | None = None) -> str:
    payload = _serialize_result(result)
    allowed_numbers = _allowed_numbers(payload)
    try:
        text = _call_llm(payload, llm_client=llm_client)
    except Exception as exc:
        logger.info("Falling back to template fundamentals summary: %s", exc)
        return render_template_summary(result)

    if _has_untraceable_number(text, allowed_numbers):
        logger.warning("Discarded fundamentals LLM explanation because it introduced an untraceable number")
        return render_template_summary(result)
    return text.strip()


def render_template_summary(result: FundamentalsResult) -> str:
    lines = [
        f"{result.ticker} fundamentals summary for research/education only, not financial advice.",
    ]
    for category in result.categories:
        fragments: list[str] = []
        verdict_by_metric = {verdict.metric_name: verdict for verdict in category.verdicts}
        for metric in category.metrics:
            verdict = verdict_by_metric[metric.name]
            if metric.status is MetricStatus.UNAVAILABLE:
                fragments.append(f"{metric.display_name}: data not available ({verdict.level.value})")
            else:
                fragments.append(f"{metric.display_name}: {_fmt(metric.value)} ({verdict.level.value})")
        lines.append(f"{category.category.title()}: " + "; ".join(fragments) + ".")
    return "\n".join(lines)


def _call_llm(payload: dict[str, Any], llm_client: LLMClient | None = None) -> str:
    client = llm_client or get_llm_client()
    return client.complete(
        system=SYSTEM_PROMPT,
        user=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        max_tokens=600,
        temperature=0.0,
    )


def _serialize_result(result: FundamentalsResult) -> dict[str, Any]:
    categories: list[dict[str, Any]] = []
    for category in result.categories:
        verdict_by_metric = {verdict.metric_name: verdict for verdict in category.verdicts}
        metrics: list[dict[str, Any]] = []
        for metric in category.metrics:
            verdict = verdict_by_metric[metric.name]
            metrics.append(
                {
                    "name": metric.name,
                    "display_name": metric.display_name,
                    "value": _round_metric(metric.value),
                    "status": metric.status.value,
                    "verdict_level": verdict.level.value,
                    "rationale": verdict.rationale,
                    "comparison_basis": verdict.comparison_basis,
                }
            )
        categories.append({"category": category.category, "metrics": metrics})

    return {
        "ticker": result.ticker,
        "company_name": result.company_name,
        "sector": result.sector,
        "categories": categories,
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


def _round_metric(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 4)


def _fmt(value: float | None) -> str:
    if value is None:
        return "data not available"
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text else "0"
