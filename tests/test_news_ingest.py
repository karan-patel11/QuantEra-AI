from __future__ import annotations

from datetime import date, datetime, timezone

from quantera.news.ingest import ingest_news
from tests.conftest import sample_news_item


class MockNewsSource:
    def __init__(self, items):
        self.items = items

    def get_company_news(self, ticker, since, until):
        return self.items


def test_ingest_dedupes_by_url_and_near_identical_headline_then_sorts():
    newest = sample_news_item(
        item_id="newest",
        headline="Apple services demand strengthens",
        source_url="https://www.reuters.com/markets/apple-services",
        published_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
    )
    duplicate_url = sample_news_item(
        item_id="dupe-url",
        headline="Different headline with duplicate URL",
        source_url="https://www.reuters.com/markets/apple-services?utm_source=test",
        published_at=datetime(2026, 1, 4, tzinfo=timezone.utc),
    )
    oldest = sample_news_item(
        item_id="oldest",
        headline="Apple supply update",
        source_url="https://www.reuters.com/markets/apple-supply",
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    duplicate_headline = sample_news_item(
        item_id="dupe-headline",
        headline="Apple supply update!",
        source_url="https://www.reuters.com/markets/apple-supply-second",
        published_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )

    result = ingest_news(
        "AAPL",
        7,
        source=MockNewsSource([oldest, duplicate_headline, duplicate_url, newest]),
        until=date(2026, 1, 6),
        use_cache=False,
    )

    assert result.items_considered == 4
    assert result.items_after_whitelist == 4
    assert [item.id for item in result.items] == ["newest", "dupe-headline"]
