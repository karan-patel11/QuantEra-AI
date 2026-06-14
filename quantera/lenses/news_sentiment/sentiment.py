"""Leashed per-item sentiment scoring for whitelisted news."""

from __future__ import annotations

import logging
from typing import Any

from quantera.lenses.news_sentiment import explain
from quantera.llm.base import LLMClient
from quantera.models_news import ItemSentiment, SentimentLabel
from quantera.news.base import NewsItem


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You classify the tone of one company-news text.

Rules:
- Use ONLY the provided id, headline, and summary_text.
- Classify the TEXT's tone as POSITIVE, NEUTRAL, or NEGATIVE. This is not a stock prediction.
- Return confidence as a number from 0 to 1.
- The rationale must be one short sentence grounded in the provided text.
- evidence_span must be an exact short snippet from the provided headline or summary_text, at most 12 words.
- Do not mention, invent, or infer a source, URL, quote, outlet, number, or fact outside the provided text.
- Do not use buy, sell, hold, price-target, entry, exit, or timing recommendation language.
- Return strict JSON with exactly these keys:
  news_item_id, label, confidence, rationale, evidence_span.
"""

def score_item_sentiments(
    items: list[NewsItem],
    *,
    llm_client: LLMClient | None = None,
) -> list[ItemSentiment]:
    return [score_item_sentiment(item, llm_client=llm_client) for item in items]


def score_item_sentiment(
    item: NewsItem,
    *,
    llm_client: LLMClient | None = None,
) -> ItemSentiment:
    payload = {
        "id": item.id,
        "headline": item.headline,
        "summary_text": item.summary_text,
    }
    try:
        raw_output = _call_llm(payload, llm_client=llm_client)
        parsed = explain.parse_json_response(raw_output)
        return _validated_sentiment(item, payload, raw_output, parsed)
    except Exception as exc:
        logger.info("Falling back to neutral item sentiment for %s: %s", item.id, exc)
        return _neutral_item(item, "unscored: guardrail")


def _call_llm(payload: dict[str, Any], llm_client: LLMClient | None = None) -> str:
    return explain.call_llm(payload, SYSTEM_PROMPT, max_tokens=350, llm_client=llm_client)


def _validated_sentiment(
    item: NewsItem,
    payload: dict[str, Any],
    raw_output: str,
    parsed: Any,
) -> ItemSentiment:
    if not isinstance(parsed, dict):
        raise ValueError("sentiment response must be a JSON object")
    allowed_keys = {"news_item_id", "label", "confidence", "rationale", "evidence_span"}
    if set(parsed) != allowed_keys:
        raise ValueError("sentiment response used unexpected keys")
    if str(parsed["news_item_id"]) != item.id:
        raise ValueError("sentiment response returned the wrong item id")
    if explain.urls_in_text(raw_output):
        raise ValueError("sentiment response referenced a URL")

    label = SentimentLabel(str(parsed["label"]).upper())
    try:
        confidence = float(parsed["confidence"])
    except (TypeError, ValueError) as exc:
        raise ValueError("sentiment confidence must be numeric") from exc
    if not 0 <= confidence <= 1:
        raise ValueError("sentiment confidence must be between 0 and 1")

    rationale = " ".join(str(parsed["rationale"]).split())
    evidence_span = explain.trim_words(str(parsed["evidence_span"]))
    allowed_text = f"{payload['headline']} {payload['summary_text']}"
    if not evidence_span or not explain.text_contains_span(allowed_text, evidence_span):
        raise ValueError("sentiment evidence span was not found in the input text")
    if explain.has_untraceable_number(rationale, payload):
        raise ValueError("sentiment rationale introduced an untraceable number")
    if explain.has_untraceable_number(evidence_span, payload):
        raise ValueError("sentiment evidence introduced an untraceable number")
    if explain.contains_advice_language(rationale):
        raise ValueError("sentiment rationale used advice language")

    return ItemSentiment(
        news_item_id=item.id,
        headline=item.headline,
        source_name=item.source_name,
        source_url=item.source_url,
        label=label,
        confidence=confidence,
        rationale=rationale,
        evidence_span=evidence_span,
    )


def _neutral_item(item: NewsItem, rationale: str) -> ItemSentiment:
    return ItemSentiment(
        news_item_id=item.id,
        headline=item.headline,
        source_name=item.source_name,
        source_url=item.source_url,
        label=SentimentLabel.NEUTRAL,
        confidence=0.0,
        rationale=rationale,
        evidence_span="",
    )
