"""Deterministic verdict logic for fundamentals metrics."""

from __future__ import annotations

from quantera.lenses.fundamentals.thresholds import (
    ABSOLUTE_THRESHOLDS,
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
    SECTOR_MEDIANS,
    ThresholdRule,
)
from quantera.models_fundamentals import Metric, MetricStatus, Verdict, VerdictLevel


def make_verdict(metric: Metric, sector: str | None) -> Verdict:
    if metric.status is MetricStatus.UNAVAILABLE or metric.value is None:
        return Verdict(
            metric_name=metric.name,
            level=VerdictLevel.UNAVAILABLE,
            rationale=metric.note or "Metric is unavailable",
            comparison_basis="absolute_threshold",
        )

    sector_median = _sector_median(sector, metric.name)
    if sector_median is not None:
        level, phrase = _compare_to_median(metric.value, sector_median, metric.name)
        return Verdict(
            metric_name=metric.name,
            level=level,
            rationale=(
                f"{metric.display_name} {_fmt(metric.value)} vs sector median "
                f"{_fmt(sector_median)} -> {phrase}"
            ),
            comparison_basis="sector_median",
        )

    rule = ABSOLUTE_THRESHOLDS.get(metric.name)
    if rule is None:
        return Verdict(
            metric_name=metric.name,
            level=VerdictLevel.UNAVAILABLE,
            rationale=f"No deterministic threshold configured for {metric.name}",
            comparison_basis="absolute_threshold",
        )

    level, rationale = _compare_to_absolute(metric, rule)
    return Verdict(
        metric_name=metric.name,
        level=level,
        rationale=rationale,
        comparison_basis="absolute_threshold",
    )


def _sector_median(sector: str | None, metric_name: str) -> float | None:
    if sector is None:
        return None
    sector_key = _sector_key(sector)
    for configured_sector, medians in SECTOR_MEDIANS.items():
        if _sector_key(configured_sector) == sector_key:
            return medians.get(metric_name)
    return None


def _sector_key(sector: str) -> str:
    return sector.strip().casefold()


def _compare_to_median(
    value: float,
    median: float,
    metric_name: str,
) -> tuple[VerdictLevel, str]:
    direction = ABSOLUTE_THRESHOLDS.get(metric_name, ThresholdRule(HIGHER_IS_BETTER, 0.0, 0.0)).direction
    if direction == HIGHER_IS_BETTER:
        if value >= median * 1.10:
            return VerdictLevel.STRONG, "above typical range"
        if value >= median * 0.90:
            return VerdictLevel.NEUTRAL, "near typical range"
        return VerdictLevel.WEAK, "below typical range"

    if direction == LOWER_IS_BETTER:
        if value <= median * 0.90:
            return VerdictLevel.STRONG, "below typical range"
        if value <= median * 1.10:
            return VerdictLevel.NEUTRAL, "near typical range"
        return VerdictLevel.WEAK, "above typical range"

    return VerdictLevel.UNAVAILABLE, "direction is not configured"


def _compare_to_absolute(metric: Metric, rule: ThresholdRule) -> tuple[VerdictLevel, str]:
    assert metric.value is not None
    value = metric.value
    display = metric.display_name
    if rule.direction == HIGHER_IS_BETTER:
        if value >= rule.strong:
            return (
                VerdictLevel.STRONG,
                f"{display} {_fmt(value)} >= {_fmt(rule.strong)} strong threshold",
            )
        if value >= rule.weak:
            return (
                VerdictLevel.NEUTRAL,
                f"{display} {_fmt(value)} >= {_fmt(rule.weak)} neutral threshold",
            )
        return (
            VerdictLevel.WEAK,
            f"{display} {_fmt(value)} < {_fmt(rule.weak)} weak threshold",
        )

    if rule.direction == LOWER_IS_BETTER:
        if value < rule.strong:
            return (
                VerdictLevel.STRONG,
                f"{display} {_fmt(value)} < {_fmt(rule.strong)} strong threshold",
            )
        if value <= rule.weak:
            return (
                VerdictLevel.NEUTRAL,
                f"{display} {_fmt(value)} <= {_fmt(rule.weak)} neutral threshold",
            )
        return (
            VerdictLevel.WEAK,
            f"{display} {_fmt(value)} > {_fmt(rule.weak)} weak threshold",
        )

    return VerdictLevel.UNAVAILABLE, f"No direction configured for {metric.name}"


def _fmt(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return text if text else "0"
