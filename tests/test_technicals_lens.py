from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from quantera.lenses.technicals import lens
from quantera.lenses.technicals.lens import TechnicalsLens
from quantera.models import PriceBar, PriceHistory
from quantera.models_technicals import IndicatorStatus


class MockProvider:
    def __init__(self, prices: PriceHistory):
        self.prices = prices
        self.calls: list[str] = []

    def get_price_history(self, ticker: str):
        self.calls.append(ticker)
        return self.prices


def make_history(closes: list[float]) -> PriceHistory:
    start = date(2025, 1, 1)
    return PriceHistory(
        ticker="MOCK",
        source="mock",
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        bars=[
            PriceBar(
                date=start + timedelta(days=index),
                open=close - 0.25,
                high=close + 0.5,
                low=close - 0.5,
                close=close,
                adj_close=close,
                volume=1000 + index,
            )
            for index, close in enumerate(closes)
        ],
    )


def test_lens_assembles_indicators_and_verdicts():
    prices = make_history([100 + index for index in range(260)])
    provider = MockProvider(prices)

    result = TechnicalsLens(provider).analyze("mock", with_explanation=False)

    assert provider.calls == ["mock"]
    assert result.ticker == "MOCK"
    assert result.explanation is None
    assert result.price_as_of == prices.bars[-1].date
    assert result.bars_used == 260
    assert [indicator.name for indicator in result.indicators] == [
        "sma_50",
        "sma_200",
        "ema_20",
        "rsi_14",
        "price_vs_sma_50",
        "price_vs_sma_200",
        "volatility_30",
        "return_21d",
        "return_63d",
        "return_252d",
        "avg_volume_30",
        "latest_volume",
    ]
    assert [verdict.indicator_name for verdict in result.verdicts] == [
        indicator.name for indicator in result.indicators
    ]
    assert [series.name for series in result.chart_series] == [
        "adj_close",
        "sma_50",
        "sma_200",
        "ema_20",
        "rsi_14",
    ]
    assert all(len(series.points) == 260 for series in result.chart_series)


def test_lens_short_history_yields_ok_and_unavailable_without_crashing():
    prices = make_history([100 + index for index in range(31)])

    result = TechnicalsLens(MockProvider(prices)).analyze("mock", with_explanation=False)
    statuses = [indicator.status for indicator in result.indicators]
    series_by_name = {
        series.name: series
        for series in result.chart_series
    }

    assert IndicatorStatus.OK in statuses
    assert IndicatorStatus.UNAVAILABLE in statuses
    assert result.bars_used == 31
    assert all(point.status is IndicatorStatus.UNAVAILABLE for point in series_by_name["sma_200"].points)
    assert any(point.status is IndicatorStatus.OK for point in series_by_name["ema_20"].points)


def test_lens_calls_explanation_when_enabled(monkeypatch):
    prices = make_history([100 + index for index in range(260)])
    monkeypatch.setattr(
        lens.explain,
        "generate_explanation",
        lambda result, llm_client=None: "technical summary",
    )

    result = TechnicalsLens(MockProvider(prices)).analyze("mock", with_explanation=True)

    assert result.explanation == "technical summary"
