from __future__ import annotations

from quantera import config
from quantera.datasource.base import DataSource
from quantera.provider import DataProvider
from tests.conftest import sample_financials, sample_financials_history, sample_price_history


class MockSource(DataSource):
    def __init__(self, fetched_at):
        self.fetched_at = fetched_at
        self.financial_calls = 0
        self.price_calls = 0

    def get_financials(self, ticker):
        self.financial_calls += 1
        return sample_financials(self.fetched_at, ticker=ticker)

    def get_financials_history(self, ticker):
        self.financial_calls += 1
        return sample_financials_history(self.fetched_at, ticker=ticker)

    def get_price_history(self, ticker, lookback_days):
        self.price_calls += 1
        return sample_price_history(self.fetched_at)


def test_financials_cache_miss_then_hit(tmp_path, monkeypatch, fetched_at):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    source = MockSource(fetched_at)
    provider = DataProvider(source=source)

    first = provider.get_financials("mock")
    second = provider.get_financials("MOCK")

    assert first == second
    assert source.financial_calls == 1


def test_financials_history_cache_miss_then_hit(tmp_path, monkeypatch, fetched_at):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    source = MockSource(fetched_at)
    provider = DataProvider(source=source)

    first = provider.get_financials_history("mock")
    second = provider.get_financials_history("MOCK")

    assert first == second
    assert len(first.periods) == 2
    assert first.get_period("FY2024") is not None
    assert source.financial_calls == 1


def test_price_history_cache_miss_then_hit(tmp_path, monkeypatch, fetched_at):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    source = MockSource(fetched_at)
    provider = DataProvider(source=source)

    first = provider.get_price_history("mock", lookback_days=10)
    second = provider.get_price_history("MOCK", lookback_days=10)

    assert first == second
    assert source.price_calls == 1


def test_yfinance_import_is_isolated_to_adapter():
    import pathlib

    project_root = pathlib.Path(__file__).resolve().parents[1]
    offenders = []
    for path in project_root.joinpath("quantera").rglob("*.py"):
        if path.name == "yfinance_source.py":
            continue
        if "import yfinance" in path.read_text(encoding="utf-8"):
            offenders.append(path)

    assert offenders == []
