"""Pure technical indicator computations.

All trend and return indicators use adjusted close (`adj_close`) so splits and
dividends do not silently distort the calculations. Raw close is only used by
the validation harness for structural OHLC checks.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from datetime import date
from statistics import stdev

from quantera.models import PriceBar, PriceHistory
from quantera.models_technicals import (
    Indicator,
    IndicatorStatus,
    TechnicalSeries,
    TechnicalSeriesPoint,
)


TRADING_DAYS_PER_YEAR = 252


def chart_series(price_history: PriceHistory) -> list[TechnicalSeries]:
    """Aligned chart series built from adjusted close and existing indicators."""

    series = {
        "adj_close": TechnicalSeries(
            name="adj_close",
            display_name="Adjusted Close",
            inputs_used=["adj_close"],
        ),
        "sma_50": TechnicalSeries(
            name="sma_50",
            display_name="50-Day SMA",
            window=50,
            inputs_used=["adj_close"],
        ),
        "sma_200": TechnicalSeries(
            name="sma_200",
            display_name="200-Day SMA",
            window=200,
            inputs_used=["adj_close"],
        ),
        "ema_20": TechnicalSeries(
            name="ema_20",
            display_name="20-Day EMA",
            window=20,
            inputs_used=["adj_close"],
        ),
        "rsi_14": TechnicalSeries(
            name="rsi_14",
            display_name="14-Day RSI",
            window=14,
            inputs_used=["adj_close"],
        ),
    }

    for index, bar in enumerate(price_history.bars):
        prefix = price_history.model_copy(update={"bars": price_history.bars[: index + 1]})
        series["adj_close"].points.append(
            _series_point(
                date_=bar.date,
                value=float(bar.adj_close),
                status=IndicatorStatus.OK,
                source=price_history.source,
                as_of=bar.date,
            )
        )
        for indicator in (
            sma(prefix, 50),
            sma(prefix, 200),
            ema(prefix, 20),
            rsi(prefix, 14),
        ):
            series[indicator.name].points.append(_series_point_from_indicator(bar.date, indicator))

    return [
        series["adj_close"],
        series["sma_50"],
        series["sma_200"],
        series["ema_20"],
        series["rsi_14"],
    ]


def sma(price_history: PriceHistory, window: int) -> Indicator:
    """Simple moving average over the latest `window` adjusted closes."""

    bars = price_history.bars
    if len(bars) < window:
        return _unavailable(
            price_history,
            name=f"sma_{window}",
            display_name=f"{window}-Day SMA",
            window=window,
            inputs_used=["adj_close"],
            bars_needed=window,
        )
    closes = _adj_closes(bars[-window:])
    return _ok(
        price_history,
        name=f"sma_{window}",
        display_name=f"{window}-Day SMA",
        value=sum(closes) / window,
        window=window,
        inputs_used=["adj_close"],
    )


def ema(price_history: PriceHistory, window: int) -> Indicator:
    """Exponential moving average over adjusted close with alpha=2/(window+1)."""

    bars = price_history.bars
    if len(bars) < window:
        return _unavailable(
            price_history,
            name=f"ema_{window}",
            display_name=f"{window}-Day EMA",
            window=window,
            inputs_used=["adj_close"],
            bars_needed=window,
        )

    closes = _adj_closes(bars)
    ema_value = sum(closes[:window]) / window
    alpha = 2 / (window + 1)
    for close in closes[window:]:
        ema_value = (close * alpha) + (ema_value * (1 - alpha))

    return _ok(
        price_history,
        name=f"ema_{window}",
        display_name=f"{window}-Day EMA",
        value=ema_value,
        window=window,
        inputs_used=["adj_close"],
    )


def rsi(price_history: PriceHistory, window: int = 14) -> Indicator:
    """Relative Strength Index using Wilder's smoothing method.

    The first average gain/loss is a simple average over the initial window of
    changes. Subsequent values apply Wilder smoothing:
    `(previous_average * (window - 1) + current_change) / window`.
    """

    bars = price_history.bars
    bars_needed = window + 1
    if len(bars) < bars_needed:
        return _unavailable(
            price_history,
            name=f"rsi_{window}",
            display_name=f"{window}-Day RSI",
            window=window,
            inputs_used=["adj_close"],
            bars_needed=bars_needed,
        )

    closes = _adj_closes(bars)
    changes = [closes[index] - closes[index - 1] for index in range(1, len(closes))]
    initial = changes[:window]
    average_gain = sum(max(change, 0.0) for change in initial) / window
    average_loss = sum(abs(min(change, 0.0)) for change in initial) / window

    for change in changes[window:]:
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))
        average_gain = ((average_gain * (window - 1)) + gain) / window
        average_loss = ((average_loss * (window - 1)) + loss) / window

    if average_loss == 0 and average_gain == 0:
        value = 50.0
    elif average_loss == 0:
        value = 100.0
    elif average_gain == 0:
        value = 0.0
    else:
        relative_strength = average_gain / average_loss
        value = 100 - (100 / (1 + relative_strength))

    return _ok(
        price_history,
        name=f"rsi_{window}",
        display_name=f"{window}-Day RSI",
        value=value,
        window=window,
        inputs_used=["adj_close"],
    )


def price_vs_sma(price_history: PriceHistory, window: int) -> Indicator:
    """Current adjusted close relative to its simple moving average."""

    bars = price_history.bars
    if len(bars) < window:
        return _unavailable(
            price_history,
            name=f"price_vs_sma_{window}",
            display_name=f"Price vs {window}-Day SMA",
            window=window,
            inputs_used=["adj_close"],
            bars_needed=window,
        )

    sma_value = sum(_adj_closes(bars[-window:])) / window
    if sma_value == 0:
        return Indicator(
            name=f"price_vs_sma_{window}",
            display_name=f"Price vs {window}-Day SMA",
            value=None,
            status=IndicatorStatus.UNAVAILABLE,
            window=window,
            inputs_used=["adj_close"],
            as_of=_as_of(price_history),
            source=price_history.source,
            note=f"{window}-day SMA is zero",
        )
    current = bars[-1].adj_close
    value = (current - sma_value) / sma_value
    return _ok(
        price_history,
        name=f"price_vs_sma_{window}",
        display_name=f"Price vs {window}-Day SMA",
        value=value,
        window=window,
        inputs_used=["adj_close"],
    )


def volatility(price_history: PriceHistory, window: int = 30) -> Indicator:
    """Annualized sample standard deviation of daily log returns."""

    bars = price_history.bars
    bars_needed = window + 1
    if len(bars) < bars_needed:
        return _unavailable(
            price_history,
            name=f"volatility_{window}",
            display_name=f"{window}-Day Annualized Volatility",
            window=window,
            inputs_used=["adj_close"],
            bars_needed=bars_needed,
        )

    closes = _adj_closes(bars[-bars_needed:])
    if any(close <= 0 for close in closes):
        return Indicator(
            name=f"volatility_{window}",
            display_name=f"{window}-Day Annualized Volatility",
            value=None,
            status=IndicatorStatus.UNAVAILABLE,
            window=window,
            inputs_used=["adj_close"],
            as_of=_as_of(price_history),
            source=price_history.source,
            note="Adjusted close must be positive for log returns",
        )

    returns = [
        math.log(closes[index] / closes[index - 1])
        for index in range(1, len(closes))
    ]
    daily_stdev = stdev(returns) if len(returns) > 1 else 0.0
    return _ok(
        price_history,
        name=f"volatility_{window}",
        display_name=f"{window}-Day Annualized Volatility",
        value=daily_stdev * math.sqrt(TRADING_DAYS_PER_YEAR),
        window=window,
        inputs_used=["adj_close"],
    )


def return_pct(price_history: PriceHistory, period_days: int) -> Indicator:
    """Trailing percentage return over `period_days` trading days."""

    bars = price_history.bars
    bars_needed = period_days + 1
    if len(bars) < bars_needed:
        return _unavailable(
            price_history,
            name=f"return_{period_days}d",
            display_name=f"{period_days}-Day Return",
            window=period_days,
            inputs_used=["adj_close"],
            bars_needed=bars_needed,
        )

    start = bars[-bars_needed].adj_close
    end = bars[-1].adj_close
    if start == 0:
        return Indicator(
            name=f"return_{period_days}d",
            display_name=f"{period_days}-Day Return",
            value=None,
            status=IndicatorStatus.UNAVAILABLE,
            window=period_days,
            inputs_used=["adj_close"],
            as_of=_as_of(price_history),
            source=price_history.source,
            note="Starting adjusted close is zero",
        )
    return _ok(
        price_history,
        name=f"return_{period_days}d",
        display_name=f"{period_days}-Day Return",
        value=(end - start) / start,
        window=period_days,
        inputs_used=["adj_close"],
    )


def avg_volume(price_history: PriceHistory, window: int = 30) -> Indicator:
    """Average raw daily volume over the latest `window` bars."""

    bars = price_history.bars
    if len(bars) < window:
        return _unavailable(
            price_history,
            name=f"avg_volume_{window}",
            display_name=f"{window}-Day Average Volume",
            window=window,
            inputs_used=["volume"],
            bars_needed=window,
        )
    volumes = [bar.volume for bar in bars[-window:]]
    return _ok(
        price_history,
        name=f"avg_volume_{window}",
        display_name=f"{window}-Day Average Volume",
        value=sum(volumes) / window,
        window=window,
        inputs_used=["volume"],
    )


def latest_volume(price_history: PriceHistory) -> Indicator:
    """Most recent raw daily volume."""

    bars = price_history.bars
    if not bars:
        return _unavailable(
            price_history,
            name="latest_volume",
            display_name="Latest Volume",
            window=None,
            inputs_used=["volume"],
            bars_needed=1,
        )
    return _ok(
        price_history,
        name="latest_volume",
        display_name="Latest Volume",
        value=float(bars[-1].volume),
        window=None,
        inputs_used=["volume"],
    )


def _series_point_from_indicator(date_: date, indicator: Indicator) -> TechnicalSeriesPoint:
    return _series_point(
        date_=date_,
        value=indicator.value,
        status=indicator.status,
        source=indicator.source,
        as_of=indicator.as_of,
        note=indicator.note,
    )


def _series_point(
    *,
    date_: date,
    value: float | None,
    status: IndicatorStatus,
    source: str,
    as_of: date,
    note: str | None = None,
) -> TechnicalSeriesPoint:
    if value is None or not math.isfinite(value):
        return TechnicalSeriesPoint(
            date=date_,
            value=None,
            status=IndicatorStatus.UNAVAILABLE,
            source=source,
            as_of=as_of,
            note=note or "Series value is unavailable",
        )
    return TechnicalSeriesPoint(
        date=date_,
        value=float(value),
        status=status,
        source=source,
        as_of=as_of,
        note=note,
    )


def _adj_closes(bars: Iterable[PriceBar]) -> list[float]:
    return [float(bar.adj_close) for bar in bars]


def _ok(
    price_history: PriceHistory,
    *,
    name: str,
    display_name: str,
    value: float,
    window: int | None,
    inputs_used: list[str],
) -> Indicator:
    if not math.isfinite(value):
        return Indicator(
            name=name,
            display_name=display_name,
            value=None,
            status=IndicatorStatus.UNAVAILABLE,
            window=window,
            inputs_used=inputs_used,
            as_of=_as_of(price_history),
            source=price_history.source,
            note="Computed indicator is not finite",
        )
    return Indicator(
        name=name,
        display_name=display_name,
        value=float(value),
        status=IndicatorStatus.OK,
        window=window,
        inputs_used=inputs_used,
        as_of=_as_of(price_history),
        source=price_history.source,
    )


def _unavailable(
    price_history: PriceHistory,
    *,
    name: str,
    display_name: str,
    window: int | None,
    inputs_used: list[str],
    bars_needed: int,
) -> Indicator:
    available = len(price_history.bars)
    return Indicator(
        name=name,
        display_name=display_name,
        value=None,
        status=IndicatorStatus.UNAVAILABLE,
        window=window,
        inputs_used=inputs_used,
        as_of=_as_of(price_history),
        source=price_history.source,
        note=f"Insufficient price history: need {bars_needed} bars, have {available}",
    )


def _as_of(price_history: PriceHistory) -> date:
    if price_history.bars:
        return price_history.bars[-1].date
    return date.min
