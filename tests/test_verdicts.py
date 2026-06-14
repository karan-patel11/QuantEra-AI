from __future__ import annotations

from datetime import datetime, timezone

from quantera.lenses.fundamentals.verdicts import make_verdict
from quantera.models_fundamentals import Metric, MetricStatus, VerdictLevel


AS_OF = datetime(2026, 1, 1, tzinfo=timezone.utc)


def metric(name: str, value: float | None, status: MetricStatus = MetricStatus.OK) -> Metric:
    return Metric(
        name=name,
        display_name=name.replace("_", " ").title(),
        value=value,
        status=status,
        inputs_used=["mock"],
        source="mock",
        as_of=AS_OF,
        note="missing mock" if status is MetricStatus.UNAVAILABLE else None,
    )


def test_current_ratio_absolute_threshold_boundaries():
    assert make_verdict(metric("current_ratio", 1.5), None).level is VerdictLevel.STRONG
    assert make_verdict(metric("current_ratio", 1.0), None).level is VerdictLevel.NEUTRAL
    assert make_verdict(metric("current_ratio", 0.99), None).level is VerdictLevel.WEAK


def test_debt_to_equity_absolute_threshold_boundaries():
    assert make_verdict(metric("debt_to_equity", 0.49), None).level is VerdictLevel.STRONG
    assert make_verdict(metric("debt_to_equity", 0.5), None).level is VerdictLevel.NEUTRAL
    assert make_verdict(metric("debt_to_equity", 1.5), None).level is VerdictLevel.NEUTRAL
    assert make_verdict(metric("debt_to_equity", 1.51), None).level is VerdictLevel.WEAK


def test_sector_median_is_used_when_available():
    verdict = make_verdict(metric("pe_ratio", 32.0), "Technology")

    assert verdict.level is VerdictLevel.WEAK
    assert verdict.comparison_basis == "sector_median"
    assert "sector median" in verdict.rationale


def test_absolute_threshold_is_used_when_sector_unknown():
    verdict = make_verdict(metric("pe_ratio", 10.0), "Unknown")

    assert verdict.level is VerdictLevel.STRONG
    assert verdict.comparison_basis == "absolute_threshold"


def test_direction_is_metric_specific():
    high_margin = make_verdict(metric("net_margin", 0.30), None)
    high_debt = make_verdict(metric("debt_to_equity", 2.0), None)

    assert high_margin.level is VerdictLevel.STRONG
    assert high_debt.level is VerdictLevel.WEAK


def test_unavailable_metric_gets_unavailable_verdict():
    verdict = make_verdict(metric("net_margin", None, MetricStatus.UNAVAILABLE), "Technology")

    assert verdict.level is VerdictLevel.UNAVAILABLE
    assert verdict.rationale == "missing mock"
