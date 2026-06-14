from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from statistics import stdev

import pytest

from quantera.lenses.technicals import indicators
from quantera.models import PriceBar, PriceHistory
from quantera.models_technicals import IndicatorStatus


def make_history(
    closes: list[float],
    *,
    volumes: list[int] | None = None,
    source: str = "mock",
) -> PriceHistory:
    start = date(2025, 1, 1)
    volumes = volumes or [1000 + index for index in range(len(closes))]
    return PriceHistory(
        ticker="MOCK",
        source=source,
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        bars=[
            PriceBar(
                date=start + timedelta(days=index),
                open=close - 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                adj_close=close,
                volume=volumes[index],
            )
            for index, close in enumerate(closes)
        ],
    )


def test_sma_matches_hand_computed_average():
    indicator = indicators.sma(make_history([10, 11, 12, 13]), 3)

    assert indicator.status is IndicatorStatus.OK
    assert indicator.value == pytest.approx(12.0)
    assert indicator.inputs_used == ["adj_close"]


def test_ema_matches_hand_computed_value():
    indicator = indicators.ema(make_history([10, 11, 12, 13, 14]), 3)

    # Initial SMA is 11; alpha is 0.5; updates are 12 and then 13.
    assert indicator.status is IndicatorStatus.OK
    assert indicator.value == pytest.approx(13.0)


def test_rsi_uses_wilder_smoothing():
    indicator = indicators.rsi(make_history([10, 11, 12, 11, 13, 14]), 3)

    assert indicator.status is IndicatorStatus.OK
    assert indicator.value == pytest.approx(2900 / 33)


def test_rsi_edge_cases_all_gains_and_all_losses():
    all_gains = indicators.rsi(make_history([1, 2, 3, 4]), 3)
    all_losses = indicators.rsi(make_history([4, 3, 2, 1]), 3)
    unchanged = indicators.rsi(make_history([1, 1, 1, 1]), 3)

    assert all_gains.value == pytest.approx(100.0)
    assert all_losses.value == pytest.approx(0.0)
    assert unchanged.value == pytest.approx(50.0)


def test_price_vs_sma_uses_current_adjusted_close_relative_to_sma():
    indicator = indicators.price_vs_sma(make_history([10, 10, 12]), 3)

    assert indicator.status is IndicatorStatus.OK
    assert indicator.value == pytest.approx(0.125)


def test_return_pct_requires_start_and_end_bar():
    indicator = indicators.return_pct(make_history([100, 110, 121]), 2)

    assert indicator.status is IndicatorStatus.OK
    assert indicator.value == pytest.approx(0.21)


def test_volatility_matches_sample_stdev_of_log_returns():
    closes = [100, 110, 99, 108.9]
    log_returns = [math.log(1.1), math.log(0.9), math.log(1.1)]

    indicator = indicators.volatility(make_history(closes), 3)

    assert indicator.status is IndicatorStatus.OK
    assert indicator.value == pytest.approx(stdev(log_returns) * math.sqrt(252))


def test_volume_indicators_use_volume_input():
    history = make_history([10, 11, 12], volumes=[100, 200, 300])

    average = indicators.avg_volume(history, 2)
    latest = indicators.latest_volume(history)

    assert average.value == pytest.approx(250.0)
    assert average.inputs_used == ["volume"]
    assert latest.value == pytest.approx(300.0)


def test_insufficient_bars_returns_unavailable_with_note():
    indicator = indicators.sma(make_history([10, 11]), 5)

    assert indicator.status is IndicatorStatus.UNAVAILABLE
    assert indicator.value is None
    assert indicator.note == "Insufficient price history: need 5 bars, have 2"


def test_return_pct_insufficient_bars_counts_start_and_end():
    indicator = indicators.return_pct(make_history([100, 101]), 2)

    assert indicator.status is IndicatorStatus.UNAVAILABLE
    assert indicator.note == "Insufficient price history: need 3 bars, have 2"


def test_chart_series_latest_points_match_scalar_indicator_functions():
    history = make_history([100 + index for index in range(260)])
    series_by_name = {
        series.name: series
        for series in indicators.chart_series(history)
    }

    assert list(series_by_name) == ["adj_close", "sma_50", "sma_200", "ema_20", "rsi_14"]
    assert series_by_name["adj_close"].points[-1].value == pytest.approx(history.bars[-1].adj_close)
    assert series_by_name["sma_50"].points[-1].value == pytest.approx(
        indicators.sma(history, 50).value
    )
    assert series_by_name["sma_200"].points[-1].value == pytest.approx(
        indicators.sma(history, 200).value
    )
    assert series_by_name["ema_20"].points[-1].value == pytest.approx(
        indicators.ema(history, 20).value
    )
    assert series_by_name["rsi_14"].points[-1].value == pytest.approx(
        indicators.rsi(history, 14).value
    )
    assert series_by_name["sma_200"].points[198].status is IndicatorStatus.UNAVAILABLE
    assert series_by_name["sma_200"].points[199].status is IndicatorStatus.OK
