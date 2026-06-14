from __future__ import annotations

from datetime import date

from quantera.news import ingest as ingest_module
from quantera.news.base import IngestedNews
from quantera.news.ingest import ingest_news
from quantera.news.whitelist import is_whitelisted
from tests.conftest import sample_news_item


class MockNewsSource:
    def __init__(self, items):
        self.items = items

    def get_company_news(self, ticker, since, until):
        return self.items


def test_whitelisted_item_kept_and_non_whitelisted_dropped():
    kept = sample_news_item(item_id="kept", source_name="Reuters")
    dropped = sample_news_item(
        item_id="dropped",
        source_name="Random Blog",
        source_url="https://example-blog.test/apple-rumor",
    )

    assert is_whitelisted(kept)
    assert not is_whitelisted(dropped)

    result = ingest_news(
        "aapl",
        7,
        source=MockNewsSource([kept, dropped]),
        until=date(2026, 1, 3),
        use_cache=False,
    )

    assert result.items_considered == 2
    assert result.items_after_whitelist == 1
    assert [item.id for item in result.items] == ["kept"]


def test_cached_news_is_rechecked_against_current_whitelist(monkeypatch):
    kept = sample_news_item(item_id="kept", source_name="Reuters")
    dropped = sample_news_item(
        item_id="dropped",
        source_name="Random Blog",
        source_url="https://example-blog.test/apple-rumor",
    )
    cached = IngestedNews(
        ticker="AAPL",
        since=date(2025, 12, 27),
        until=date(2026, 1, 3),
        items=[kept, dropped],
        items_considered=2,
        items_after_whitelist=2,
    ).model_dump(mode="json")
    monkeypatch.setattr(ingest_module, "cache_get", lambda key: cached)

    result = ingest_news(
        "aapl",
        7,
        source=MockNewsSource([]),
        until=date(2026, 1, 3),
        use_cache=True,
    )

    assert result.items_after_whitelist == 1
    assert [item.id for item in result.items] == ["kept"]
