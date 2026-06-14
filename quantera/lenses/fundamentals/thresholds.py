"""Approximate deterministic thresholds for Phase 1 fundamentals verdicts."""

from __future__ import annotations

from dataclasses import dataclass


HIGHER_IS_BETTER = "higher_is_better"
LOWER_IS_BETTER = "lower_is_better"


@dataclass(frozen=True)
class ThresholdRule:
    direction: str
    strong: float
    weak: float
    unit: str = "ratio"


# These are coarse, sector-dependent defaults for deterministic Phase 1 behavior.
# They are not live market data and should be refined before production use.
ABSOLUTE_THRESHOLDS: dict[str, ThresholdRule] = {
    "pe_ratio": ThresholdRule(LOWER_IS_BETTER, strong=15.0, weak=30.0),
    "pb_ratio": ThresholdRule(LOWER_IS_BETTER, strong=2.0, weak=5.0),
    "ps_ratio": ThresholdRule(LOWER_IS_BETTER, strong=2.0, weak=6.0),
    "ev_ebitda": ThresholdRule(LOWER_IS_BETTER, strong=8.0, weak=15.0),
    "gross_margin": ThresholdRule(HIGHER_IS_BETTER, strong=0.40, weak=0.20),
    "net_margin": ThresholdRule(HIGHER_IS_BETTER, strong=0.15, weak=0.05),
    "roe": ThresholdRule(HIGHER_IS_BETTER, strong=0.15, weak=0.05),
    "roa": ThresholdRule(HIGHER_IS_BETTER, strong=0.08, weak=0.02),
    "debt_to_equity": ThresholdRule(LOWER_IS_BETTER, strong=0.50, weak=1.50),
    "current_ratio": ThresholdRule(HIGHER_IS_BETTER, strong=1.50, weak=1.00),
    "interest_coverage": ThresholdRule(HIGHER_IS_BETTER, strong=5.00, weak=2.00),
    "revenue_growth_yoy": ThresholdRule(HIGHER_IS_BETTER, strong=0.10, weak=0.00),
    "earnings_growth_yoy": ThresholdRule(HIGHER_IS_BETTER, strong=0.10, weak=0.00),
    "fcf_trend": ThresholdRule(HIGHER_IS_BETTER, strong=1.00, weak=0.00),
}


# Hand-entered broad-sector medians for Phase 1 comparisons. The medians are
# rounded approximations from public NYU Stern/Damodaran sector datasets and
# broad market data snapshots, documented in README. Use them only as comparison
# scaffolding for deterministic tests and first-pass research.
SECTOR_MEDIANS: dict[str, dict[str, float]] = {
    "Technology": {
        "pe_ratio": 28.0,
        "net_margin": 0.22,
        "debt_to_equity": 0.60,
    },
    "Financial Services": {
        "pe_ratio": 12.0,
        "net_margin": 0.25,
        "debt_to_equity": 1.80,
    },
    "Energy": {
        "pe_ratio": 12.0,
        "net_margin": 0.10,
        "debt_to_equity": 0.45,
    },
    "Healthcare": {
        "pe_ratio": 20.0,
        "net_margin": 0.14,
        "debt_to_equity": 0.55,
    },
    "Consumer Defensive": {
        "pe_ratio": 22.0,
        "net_margin": 0.08,
        "debt_to_equity": 0.75,
    },
    "Industrials": {
        "pe_ratio": 20.0,
        "net_margin": 0.09,
        "debt_to_equity": 0.90,
    },
    "Communication Services": {
        "pe_ratio": 18.0,
        "net_margin": 0.12,
        "debt_to_equity": 0.70,
    },
}
