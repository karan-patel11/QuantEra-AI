from __future__ import annotations

import math

import pytest

from quantera.lenses.fundamentals import ratios
from quantera.models_fundamentals import MetricStatus
from tests.conftest import sample_financials


def test_core_ratios_compute_known_values(fetched_at):
    financials = sample_financials(fetched_at)

    assert ratios.pe_ratio(financials).value == pytest.approx(2.5)
    assert ratios.pb_ratio(financials).value == pytest.approx(0.625)
    assert ratios.ps_ratio(financials).value == pytest.approx(0.25)
    assert ratios.gross_margin(financials).value == pytest.approx(0.4)
    assert ratios.net_margin(financials).value == pytest.approx(0.1)
    assert ratios.roe(financials).value == pytest.approx(0.25)
    assert ratios.roa(financials).value == pytest.approx(0.1)
    assert ratios.debt_to_equity(financials).value == pytest.approx(0.5)
    assert ratios.current_ratio(financials).value == pytest.approx(2.4)


def test_metric_preserves_inputs_and_provenance(fetched_at):
    financials = sample_financials(fetched_at, source="mock-source")

    metric = ratios.net_margin(financials)

    assert metric.inputs_used == ["net_income", "revenue"]
    assert metric.source == "mock-source"
    assert metric.as_of == fetched_at


def test_pe_ratio_falls_back_to_market_cap_over_net_income(fetched_at):
    financials = sample_financials(fetched_at, overrides={"eps": None})

    metric = ratios.pe_ratio(financials)

    assert metric.status is MetricStatus.OK
    assert metric.value == pytest.approx(2.5)
    assert metric.inputs_used == ["market_cap", "net_income"]


def test_missing_input_returns_unavailable_not_zero_or_nan(fetched_at):
    financials = sample_financials(fetched_at, overrides={"revenue": None})

    metric = ratios.gross_margin(financials)

    assert metric.status is MetricStatus.UNAVAILABLE
    assert metric.value is None
    assert metric.note is not None
    assert "revenue" in metric.note


def test_zero_denominator_is_guarded(fetched_at):
    financials = sample_financials(fetched_at, overrides={"current_liabilities": 0.0})

    metric = ratios.current_ratio(financials)

    assert metric.status is MetricStatus.UNAVAILABLE
    assert metric.value is None
    assert metric.note == "Denominator current_liabilities is zero"


def test_negative_equity_makes_roe_unavailable(fetched_at):
    financials = sample_financials(fetched_at, overrides={"total_equity": -10.0})

    metric = ratios.roe(financials)

    assert metric.status is MetricStatus.UNAVAILABLE
    assert metric.value is None
    assert metric.note == "Denominator total_equity must be positive"


def test_unavailable_ratios_never_return_inf_or_nan(fetched_at):
    financials = sample_financials(fetched_at, overrides={"total_equity": 0.0})

    metric = ratios.pb_ratio(financials)

    assert metric.value is None
    assert metric.status is MetricStatus.UNAVAILABLE
    assert metric.value is None or math.isfinite(metric.value)


def test_phase_zero_growth_and_optional_component_metrics_are_unavailable(fetched_at):
    financials = sample_financials(fetched_at)

    unavailable = [
        ratios.ev_ebitda(financials),
        ratios.interest_coverage(financials),
        ratios.revenue_growth_yoy(financials),
        ratios.earnings_growth_yoy(financials),
        ratios.fcf_trend(financials),
    ]

    assert all(metric.status is MetricStatus.UNAVAILABLE for metric in unavailable)
    assert "ebitda" in (unavailable[0].note or "")
    assert "interest_expense" in (unavailable[1].note or "")
    assert "Prior-period" in (unavailable[2].note or "")
