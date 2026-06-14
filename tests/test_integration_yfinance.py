from __future__ import annotations

import pytest

from quantera import config
from quantera.lenses.technicals import indicators
from quantera.models_technicals import IndicatorStatus
from quantera.provider import DataProvider


@pytest.mark.integration
def test_live_yfinance_aapl_financials_populated(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    provider = DataProvider()
    financials = provider.get_financials("AAPL")
    history = provider.get_financials_history("AAPL")

    assert financials.ticker == "AAPL"
    assert financials.source == "yfinance"
    assert financials.revenue.is_present
    assert financials.fetched_at is not None
    assert len(history.periods) > 1


@pytest.mark.integration
def test_live_yfinance_aapl_price_history_supports_200_day_sma(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)

    prices = DataProvider().get_price_history("AAPL")
    sma_200 = indicators.sma(prices, 200)

    assert prices.ticker == "AAPL"
    assert prices.source == "yfinance"
    assert len(prices.bars) >= 200
    assert sma_200.status is IndicatorStatus.OK
