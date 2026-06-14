from __future__ import annotations

from datetime import date

from quantera.lenses.technicals.verdicts import make_verdict
from quantera.models_technicals import (
    Indicator,
    IndicatorStatus,
    VerdictLevel,
)


def indicator(name: str, value: float | None, status: IndicatorStatus = IndicatorStatus.OK) -> Indicator:
    return Indicator(
        name=name,
        display_name=name.replace("_", " ").title(),
        value=value,
        status=status,
        window=14,
        inputs_used=["adj_close"],
        as_of=date(2025, 1, 31),
        source="mock",
        note="not enough data" if status is IndicatorStatus.UNAVAILABLE else None,
    )


def test_rsi_band_boundaries_are_neutral():
    assert make_verdict(indicator("rsi_14", 29.9)).level is VerdictLevel.OVERSOLD
    assert make_verdict(indicator("rsi_14", 30.0)).level is VerdictLevel.NEUTRAL
    assert make_verdict(indicator("rsi_14", 70.0)).level is VerdictLevel.NEUTRAL
    assert make_verdict(indicator("rsi_14", 70.1)).level is VerdictLevel.OVERBOUGHT


def test_price_vs_sma_above_below_neutral():
    assert make_verdict(indicator("price_vs_sma_200", 0.02)).level is VerdictLevel.ABOVE
    assert make_verdict(indicator("price_vs_sma_200", -0.02)).level is VerdictLevel.BELOW
    assert make_verdict(indicator("price_vs_sma_200", 0.01)).level is VerdictLevel.NEUTRAL
    assert make_verdict(indicator("price_vs_sma_200", -0.01)).level is VerdictLevel.NEUTRAL


def test_unavailable_indicator_yields_unavailable_verdict():
    verdict = make_verdict(indicator("sma_200", None, IndicatorStatus.UNAVAILABLE))

    assert verdict.level is VerdictLevel.UNAVAILABLE
    assert verdict.rationale == "not enough data"
