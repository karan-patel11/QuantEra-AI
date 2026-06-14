from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

from quantera.news.finnhub_source import FinnhubNewsSource


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("NEWS_API_KEY"), reason="NEWS_API_KEY is not set")
def test_live_finnhub_news_returns_source_and_url():
    until = date.today()
    since = until - timedelta(days=7)
    items = FinnhubNewsSource().get_company_news("AAPL", since, until)
    if not items:
        pytest.skip("Finnhub returned no AAPL news items for the last seven days")

    assert items[0].source_name
    assert items[0].source_url.startswith("http")
    assert items[0].published_at
