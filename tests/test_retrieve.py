from __future__ import annotations

from datetime import datetime, timezone

from quantera.lenses.news_sentiment.retrieve import retrieve_relevant_news
from tests.conftest import sample_news_item


def test_retrieval_ranks_top_n_and_preserves_provenance():
    older = sample_news_item(
        item_id="older",
        headline="Apple supplier note",
        source_url="https://www.reuters.com/markets/apple-supplier",
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        raw_relevance=0.0,
    )
    relevant = sample_news_item(
        item_id="relevant",
        headline="AAPL services demand improves",
        source_url="https://www.reuters.com/markets/apple-services",
        published_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        raw_relevance=0.9,
    )
    unrelated = sample_news_item(
        item_id="unrelated",
        headline="Broad market recap",
        summary_text="Indexes moved without company-specific Apple details.",
        source_url="https://www.reuters.com/markets/recap",
        published_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
        raw_relevance=0.0,
    )

    result = retrieve_relevant_news(
        [older, relevant, unrelated],
        "AAPL",
        company_name="Apple Inc.",
        top_n=2,
    )

    assert [item.id for item in result] == ["relevant", "unrelated"]
    assert result[0].source_name == "Reuters"
    assert result[0].source_url == "https://www.reuters.com/markets/apple-services"
