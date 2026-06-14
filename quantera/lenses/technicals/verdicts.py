"""Deterministic verdict logic for technical indicators."""

from __future__ import annotations

from quantera.lenses.technicals.thresholds import (
    PRICE_VS_SMA_NEUTRAL_BAND,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
)
from quantera.models_technicals import (
    Indicator,
    IndicatorStatus,
    TechnicalVerdict,
    VerdictLevel,
)


def make_verdict(indicator: Indicator) -> TechnicalVerdict:
    if indicator.status is IndicatorStatus.UNAVAILABLE or indicator.value is None:
        return TechnicalVerdict(
            indicator_name=indicator.name,
            level=VerdictLevel.UNAVAILABLE,
            rationale=indicator.note or "Indicator is unavailable",
            comparison_basis="availability",
        )

    if indicator.name.startswith("rsi_"):
        return _rsi_verdict(indicator)
    if indicator.name.startswith("price_vs_sma_"):
        return _price_vs_sma_verdict(indicator)

    return TechnicalVerdict(
        indicator_name=indicator.name,
        level=VerdictLevel.NEUTRAL,
        rationale=f"{indicator.display_name} {_fmt(indicator.value)} is descriptive context",
        comparison_basis="descriptive_context",
    )


def _rsi_verdict(indicator: Indicator) -> TechnicalVerdict:
    assert indicator.value is not None
    value = indicator.value
    if value < RSI_OVERSOLD:
        return TechnicalVerdict(
            indicator_name=indicator.name,
            level=VerdictLevel.OVERSOLD,
            rationale=(
                f"{indicator.display_name} {_fmt(value)} < {_fmt(RSI_OVERSOLD)} "
                "oversold band"
            ),
            comparison_basis="rsi_bands",
        )
    if value > RSI_OVERBOUGHT:
        return TechnicalVerdict(
            indicator_name=indicator.name,
            level=VerdictLevel.OVERBOUGHT,
            rationale=(
                f"{indicator.display_name} {_fmt(value)} > {_fmt(RSI_OVERBOUGHT)} "
                "overbought band"
            ),
            comparison_basis="rsi_bands",
        )
    return TechnicalVerdict(
        indicator_name=indicator.name,
        level=VerdictLevel.NEUTRAL,
        rationale=(
            f"{indicator.display_name} {_fmt(value)} is between "
            f"{_fmt(RSI_OVERSOLD)} and {_fmt(RSI_OVERBOUGHT)} neutral band"
        ),
        comparison_basis="rsi_bands",
    )


def _price_vs_sma_verdict(indicator: Indicator) -> TechnicalVerdict:
    assert indicator.value is not None
    value = indicator.value
    band = PRICE_VS_SMA_NEUTRAL_BAND
    if value > band:
        return TechnicalVerdict(
            indicator_name=indicator.name,
            level=VerdictLevel.ABOVE,
            rationale=(
                f"{indicator.display_name} {_fmt_pct(value)} > {_fmt_pct(band)} "
                "above neutral band"
            ),
            comparison_basis="price_vs_sma_neutral_band",
        )
    if value < -band:
        return TechnicalVerdict(
            indicator_name=indicator.name,
            level=VerdictLevel.BELOW,
            rationale=(
                f"{indicator.display_name} {_fmt_pct(value)} < -{_fmt_pct(band)} "
                "below neutral band"
            ),
            comparison_basis="price_vs_sma_neutral_band",
        )
    return TechnicalVerdict(
        indicator_name=indicator.name,
        level=VerdictLevel.NEUTRAL,
        rationale=(
            f"{indicator.display_name} {_fmt_pct(value)} is within +/-{_fmt_pct(band)} "
            "neutral band"
        ),
        comparison_basis="price_vs_sma_neutral_band",
    )


def _fmt(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _fmt_pct(value: float) -> str:
    text = f"{value * 100:.2f}".rstrip("0").rstrip(".")
    return f"{text if text else '0'}%"
