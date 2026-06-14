from __future__ import annotations

from datetime import date

from quantera.lenses.news_sentiment.summarize import compute_overall_tone, generate_summary
from quantera.models_news import ItemSentiment, NewsWindow, OverallTone, SentimentLabel
from tests.conftest import MockLLMClient, sample_news_item


def item_sentiment(item_id: str, label: SentimentLabel, confidence: float) -> ItemSentiment:
    return ItemSentiment(
        news_item_id=item_id,
        source_name="Reuters",
        source_url=f"https://www.reuters.com/markets/{item_id}",
        label=label,
        confidence=confidence,
        rationale="Grounded in the item text.",
        evidence_span="item text",
    )


def test_overall_tone_is_deterministic_from_labels():
    assert compute_overall_tone(
        [
            item_sentiment("one", SentimentLabel.POSITIVE, 0.8),
            item_sentiment("two", SentimentLabel.POSITIVE, 0.7),
            item_sentiment("three", SentimentLabel.NEGATIVE, 0.2),
        ]
    ) is OverallTone.POSITIVE

    assert compute_overall_tone(
        [
            item_sentiment("one", SentimentLabel.POSITIVE, 0.6),
            item_sentiment("two", SentimentLabel.NEGATIVE, 0.55),
        ]
    ) is OverallTone.MIXED


def test_summary_guardrail_falls_back_when_llm_cites_unknown_source():
    item = sample_news_item(item_id="one", source_url="https://www.reuters.com/markets/one")
    sentiment = item_sentiment("one", SentimentLabel.POSITIVE, 0.8)
    window = NewsWindow(since=date(2026, 1, 1), until=date(2026, 1, 3))

    def bad_llm(system, user, max_tokens, temperature):
        return (
            "This sentiment note cites [Fake Source](https://fake.example/story) "
            "for research/education only, not financial advice or a prediction."
        )

    output = generate_summary(
        "AAPL",
        window,
        [item],
        [sentiment],
        OverallTone.POSITIVE,
        [],
        llm_client=MockLLMClient(bad_llm),
    )

    assert "fake.example" not in output
    assert "https://www.reuters.com/markets/one" in output
    assert "research/education only" in output
