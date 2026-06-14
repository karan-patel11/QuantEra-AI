from __future__ import annotations

import json

from quantera.lenses.news_sentiment.sentiment import score_item_sentiment
from quantera.models_news import SentimentLabel
from tests.conftest import MockLLMClient, sample_news_item


def test_clean_item_scored_with_short_evidence_span():
    item = sample_news_item()

    def llm(system, user, max_tokens, temperature):
        payload = json.loads(user)
        return json.dumps(
            {
                "news_item_id": payload["id"],
                "label": "POSITIVE",
                "confidence": 0.82,
                "rationale": "The text highlights stronger services demand.",
                "evidence_span": "stronger services demand",
            }
        )

    result = score_item_sentiment(item, llm_client=MockLLMClient(llm))

    assert result.news_item_id == item.id
    assert result.label is SentimentLabel.POSITIVE
    assert result.confidence == 0.82
    assert len(result.evidence_span.split()) <= 12
    assert result.source_name == item.source_name
    assert result.source_url == item.source_url


def test_wrong_item_id_is_guarded_to_neutral():
    item = sample_news_item()

    def llm(system, user, max_tokens, temperature):
        return json.dumps(
            {
                "news_item_id": "wrong",
                "label": "NEGATIVE",
                "confidence": 0.9,
                "rationale": "The text is cautious.",
                "evidence_span": "profit outlook improved",
            }
        )

    result = score_item_sentiment(item, llm_client=MockLLMClient(llm))

    assert result.label is SentimentLabel.NEUTRAL
    assert result.rationale == "unscored: guardrail"


def test_invented_source_is_guarded_to_neutral():
    item = sample_news_item()

    def llm(system, user, max_tokens, temperature):
        payload = json.loads(user)
        return json.dumps(
            {
                "news_item_id": payload["id"],
                "label": "POSITIVE",
                "confidence": 0.9,
                "rationale": "Fake Outlet says the text is upbeat.",
                "evidence_span": "profit outlook improved",
                "source_name": "Fake Outlet",
            }
        )

    result = score_item_sentiment(item, llm_client=MockLLMClient(llm))

    assert result.label is SentimentLabel.NEUTRAL
    assert result.rationale == "unscored: guardrail"


def test_long_evidence_span_is_trimmed_short_when_grounded():
    phrase = "one two three four five six seven eight nine ten eleven twelve thirteen"
    item = sample_news_item(summary_text=f"The report says {phrase} for context.")

    def llm(system, user, max_tokens, temperature):
        payload = json.loads(user)
        return json.dumps(
            {
                "news_item_id": payload["id"],
                "label": "NEUTRAL",
                "confidence": 0.5,
                "rationale": "The text gives mixed context.",
                "evidence_span": phrase,
            }
        )

    result = score_item_sentiment(item, llm_client=MockLLMClient(llm))

    assert len(result.evidence_span.split()) <= 12
