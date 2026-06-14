"""Deterministic thresholds for descriptive technical verdicts."""

from __future__ import annotations


# Conventional RSI bands used as descriptive ranges, not predictive signals.
RSI_OVERSOLD = 30.0
RSI_OVERBOUGHT = 70.0

# Price-vs-SMA values are decimals, so 0.01 means within +/-1%.
PRICE_VS_SMA_NEUTRAL_BAND = 0.01
