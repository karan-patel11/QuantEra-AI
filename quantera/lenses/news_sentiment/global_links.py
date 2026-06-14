"""Strictly leashed macro/global-news hypothesis generation."""

from __future__ import annotations

import logging
import re
from typing import Any

from quantera.lenses.news_sentiment import explain
from quantera.llm.base import LLMClient
from quantera.models_news import GlobalConfidence, GlobalLink
from quantera.news.base import NewsItem


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You may propose macro/global hypotheses grounded only in provided news items.

Rules:
- Propose fewer links rather than weak links.
- Every claim must be framed as a hypothesis using may, could, might, possible, or potentially.
- Every claim must cite supporting_item_ids from the provided items only.
- Every claim must include confidence LOW, MEDIUM, or HIGH and a caveat.
- Never present cause and effect as fact. Never make investment advice or predictions.
- Do not mention sources, URLs, quotes, numbers, or facts outside the provided item text.
- Return strict JSON as {"global_links":[{"claim":...,"confidence":...,"supporting_item_ids":[...],"caveat":...}]}.
"""

HYPOTHESIS_PATTERN = re.compile(r"\b(may|could|might|possible|potentially|hypothesis)\b", re.I)


def propose_global_links(
    items: list[NewsItem],
    *,
    llm_client: LLMClient | None = None,
    max_links: int = 3,
) -> list[GlobalLink]:
    if not items:
        return []

    payload = {
        "items": [
            {
                "id": item.id,
                "headline": item.headline,
                "summary_text": item.summary_text,
            }
            for item in items
        ],
        "max_links": max_links,
    }
    try:
        raw_output = _call_llm(payload, llm_client=llm_client)
        parsed = explain.parse_json_response(raw_output)
    except Exception as exc:
        logger.info("No global links generated: %s", exc)
        return []
    return _validated_links(parsed, raw_output, payload, {item.id for item in items}, max_links)


def _call_llm(payload: dict[str, Any], llm_client: LLMClient | None = None) -> str:
    return explain.call_llm(payload, SYSTEM_PROMPT, max_tokens=500, llm_client=llm_client)


def _validated_links(
    parsed: Any,
    raw_output: str,
    payload: dict[str, Any],
    allowed_item_ids: set[str],
    max_links: int,
) -> list[GlobalLink]:
    if not isinstance(parsed, dict) or not isinstance(parsed.get("global_links"), list):
        return []
    if explain.urls_in_text(raw_output):
        return []

    links: list[GlobalLink] = []
    for raw_link in parsed["global_links"]:
        if len(links) >= max_links:
            break
        link = _validated_link(raw_link, payload, allowed_item_ids)
        if link is not None:
            links.append(link)
    return links


def _validated_link(
    raw_link: Any,
    payload: dict[str, Any],
    allowed_item_ids: set[str],
) -> GlobalLink | None:
    if not isinstance(raw_link, dict):
        return None
    required = {"claim", "confidence", "supporting_item_ids", "caveat"}
    if not required.issubset(raw_link):
        return None

    claim = " ".join(str(raw_link["claim"]).split())
    caveat = " ".join(str(raw_link["caveat"]).split())
    supporting_item_ids = [str(item_id) for item_id in raw_link.get("supporting_item_ids", [])]
    if not claim or not caveat or not supporting_item_ids:
        return None
    if not set(supporting_item_ids).issubset(allowed_item_ids):
        return None
    if not HYPOTHESIS_PATTERN.search(claim):
        return None
    if explain.contains_advice_language(claim) or explain.contains_advice_language(caveat):
        return None
    if explain.has_untraceable_number(claim, payload):
        return None
    if explain.has_untraceable_number(caveat, payload):
        return None

    try:
        confidence = GlobalConfidence(str(raw_link["confidence"]).upper())
    except ValueError:
        return None
    return GlobalLink(
        claim=claim,
        confidence=confidence,
        supporting_item_ids=supporting_item_ids,
        caveat=caveat,
    )
