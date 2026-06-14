"""Deterministic tone aggregation and guarded news sentiment synthesis."""

from __future__ import annotations

import logging
from typing import Any

from quantera.lenses.news_sentiment import explain
from quantera.llm.base import LLMClient
from quantera.models_news import (
    GlobalLink,
    ItemSentiment,
    NewsWindow,
    OverallTone,
    SentimentLabel,
)
from quantera.news.base import NewsItem


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You narrate a guarded news-sentiment result.

Rules:
- Use ONLY the provided overall_tone, item sentiments, rationales, evidence spans, source names, URLs, dates, and global hypotheses.
- Treat all labels as sentiment about text, not facts and not stock predictions.
- Do not compute or override overall_tone; it was computed deterministically by code.
- Cite sources with markdown links using exactly the provided source_name and source_url.
- State that this is research/education only, not financial advice or a prediction.
- Do not use buy, sell, hold, price-target, entry, exit, or timing recommendation language.
- Keep it short and plain-language.
"""

def compute_overall_tone(sentiments: list[ItemSentiment]) -> OverallTone:
    if not sentiments:
        return OverallTone.NO_DATA

    positive = sum(
        sentiment.confidence
        for sentiment in sentiments
        if sentiment.label is SentimentLabel.POSITIVE
    )
    negative = sum(
        sentiment.confidence
        for sentiment in sentiments
        if sentiment.label is SentimentLabel.NEGATIVE
    )
    if positive == 0 and negative == 0:
        return OverallTone.NEUTRAL
    if positive > 0 and negative > 0 and abs(positive - negative) < 0.25:
        return OverallTone.MIXED
    if positive > negative:
        return OverallTone.POSITIVE
    if negative > positive:
        return OverallTone.NEGATIVE
    return OverallTone.MIXED


def generate_summary(
    ticker: str,
    window: NewsWindow,
    items: list[NewsItem],
    sentiments: list[ItemSentiment],
    overall_tone: OverallTone,
    global_links: list[GlobalLink],
    *,
    llm_client: LLMClient | None = None,
) -> str:
    payload = _summary_payload(ticker, window, items, sentiments, overall_tone, global_links)
    try:
        text = _call_llm(payload, llm_client=llm_client).strip()
    except Exception as exc:
        logger.info("Falling back to deterministic news summary: %s", exc)
        return render_template_summary(ticker, window, items, sentiments, overall_tone, global_links)

    if not _summary_passes_guardrails(text, payload):
        logger.warning("Discarded news summary because it failed source/number/advice guardrails")
        return render_template_summary(ticker, window, items, sentiments, overall_tone, global_links)
    return text


def render_template_summary(
    ticker: str,
    window: NewsWindow,
    items: list[NewsItem],
    sentiments: list[ItemSentiment],
    overall_tone: OverallTone,
    global_links: list[GlobalLink],
) -> str:
    lines = [
        (
            f"{ticker.upper()} news sentiment for {window.since.isoformat()} to "
            f"{window.until.isoformat()} is {overall_tone.value}. "
            "This is research/education only, not financial advice or a prediction."
        )
    ]
    sentiment_by_id = {sentiment.news_item_id: sentiment for sentiment in sentiments}
    for item in items:
        sentiment = sentiment_by_id.get(item.id)
        if sentiment is None:
            continue
        lines.append(
            f"{item.source_name} ({item.published_at.date().isoformat()}, {item.source_url}): "
            f"{sentiment.label.value}, confidence {sentiment.confidence:.2f}; "
            f"{sentiment.rationale}"
        )
    if global_links:
        links = [
            f"{link.claim} ({link.confidence.value}; caveat: {link.caveat})"
            for link in global_links
        ]
        lines.append("Hypotheses to check: " + "; ".join(links) + ".")
    return "\n".join(lines)


def _call_llm(payload: dict[str, Any], llm_client: LLMClient | None = None) -> str:
    return explain.call_llm(payload, SYSTEM_PROMPT, max_tokens=700, llm_client=llm_client)


def _summary_payload(
    ticker: str,
    window: NewsWindow,
    items: list[NewsItem],
    sentiments: list[ItemSentiment],
    overall_tone: OverallTone,
    global_links: list[GlobalLink],
) -> dict[str, Any]:
    item_by_id = {item.id: item for item in items}
    return {
        "ticker": ticker.upper(),
        "window": window.model_dump(mode="json"),
        "overall_tone": overall_tone.value,
        "item_sentiments": [
            {
                "news_item_id": sentiment.news_item_id,
                "source_name": sentiment.source_name,
                "source_url": sentiment.source_url,
                "published_at": item_by_id[sentiment.news_item_id].published_at.isoformat()
                if sentiment.news_item_id in item_by_id
                else None,
                "label": sentiment.label.value,
                "confidence": round(sentiment.confidence, 4),
                "rationale": sentiment.rationale,
                "evidence_span": sentiment.evidence_span,
            }
            for sentiment in sentiments
        ],
        "global_links": [link.model_dump(mode="json") for link in global_links],
    }


def _summary_passes_guardrails(text: str, payload: dict[str, Any]) -> bool:
    allowed_urls = {
        sentiment["source_url"]
        for sentiment in payload["item_sentiments"]
        if sentiment.get("source_url")
    }
    allowed_source_names = {
        sentiment["source_name"]
        for sentiment in payload["item_sentiments"]
        if sentiment.get("source_name")
    }
    if explain.has_disallowed_url(text, allowed_urls):
        return False
    if explain.has_bad_markdown_citation(text, allowed_source_names, allowed_urls):
        return False
    if explain.has_untraceable_number(text, payload):
        return False
    if explain.contains_advice_language(text):
        return False
    return True
