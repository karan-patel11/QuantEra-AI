from __future__ import annotations

import json
import re

from quantera.lenses.news_sentiment.lens import NewsSentimentLens
from tests.conftest import MockLLMClient, sample_news_item


class MockNewsSource:
    def __init__(self, items):
        self.items = items

    def get_company_news(self, ticker, since, until):
        return self.items


def test_news_lens_end_to_end_with_mock_source_and_llm():
    kept = sample_news_item(
        item_id="kept",
        source_url="https://www.reuters.com/markets/apple-good",
    )
    kept_second = sample_news_item(
        item_id="kept-second",
        headline="Apple update remains balanced",
        summary_text="The report says demand was balanced across segments.",
        source_url="https://www.reuters.com/markets/apple-balanced",
    )
    dropped = sample_news_item(
        item_id="dropped",
        source_name="Message Board",
        source_url="https://forum.example/apple",
    )
    sentiment_payload_ids: list[str] = []

    def llm(system, user, max_tokens, temperature):
        payload = json.loads(user)
        if "classify the tone" in system:
            return sentiment_llm(payload)
        if "macro/global hypotheses" in system:
            return global_llm(payload)
        if "guarded news-sentiment result" in system:
            return summary_llm(payload)
        raise AssertionError(f"unexpected system prompt: {system}")

    def sentiment_llm(payload):
        sentiment_payload_ids.append(payload["id"])
        if payload["id"] == "kept":
            return json.dumps(
                {
                    "news_item_id": payload["id"],
                    "label": "POSITIVE",
                    "confidence": 0.8,
                    "rationale": "The text highlights stronger services demand.",
                    "evidence_span": "stronger services demand",
                }
            )
        return json.dumps(
            {
                "news_item_id": payload["id"],
                "label": "NEUTRAL",
                "confidence": 0.4,
                "rationale": "The text is balanced.",
                "evidence_span": "demand was balanced",
            }
        )

    def global_llm(payload):
        return json.dumps(
            {
                "global_links": [
                    {
                        "claim": "Stronger services demand may support the company context.",
                        "confidence": "MEDIUM",
                        "supporting_item_ids": ["kept"],
                        "caveat": "Based on a limited item set.",
                    }
                ]
            }
        )

    def summary_llm(payload):
        return (
            "AAPL news sentiment is POSITIVE for research/education only, not "
            "financial advice or a prediction, citing "
            "[Reuters](https://www.reuters.com/markets/apple-good)."
        )

    result = NewsSentimentLens(
        MockNewsSource([dropped, kept_second, kept]),
        use_cache=False,
        llm_client=MockLLMClient(llm),
    ).analyze("aapl")

    assert result.ticker == "AAPL"
    assert result.items_considered == 3
    assert result.items_after_whitelist == 2
    assert len(result.item_sentiments) == 2
    assert set(sentiment_payload_ids) == {"kept", "kept-second"}
    assert "dropped" not in {sentiment.news_item_id for sentiment in result.item_sentiments}
    assert result.sources
    assert result.sources[0].name == "Reuters"
    assert result.summary
    assert not re.search(r"\b(buy|sell|hold|price target)\b", result.summary, re.I)
    assert result.global_links[0].confidence.value == "MEDIUM"
