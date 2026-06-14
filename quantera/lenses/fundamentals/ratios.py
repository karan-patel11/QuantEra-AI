"""Pure financial ratio computations for the fundamentals lens."""

from __future__ import annotations

import math
from collections.abc import Iterable

from quantera.models import FieldValue, Financials
from quantera.models_fundamentals import Metric, MetricStatus


def pe_ratio(financials: Financials) -> Metric:
    """Price / earnings, preferring per-share inputs when available."""

    metric = _ratio(
        financials,
        name="pe_ratio",
        display_name="Price / Earnings",
        numerator="market_price",
        denominator="eps",
        denominator_must_be_positive=True,
        numerator_must_be_positive=True,
    )
    if metric.status is MetricStatus.OK:
        return metric

    fallback = _ratio(
        financials,
        name="pe_ratio",
        display_name="Price / Earnings",
        numerator="market_cap",
        denominator="net_income",
        denominator_must_be_positive=True,
        numerator_must_be_positive=True,
    )
    if fallback.status is MetricStatus.OK:
        return fallback

    return metric


def pb_ratio(financials: Financials) -> Metric:
    return _ratio(
        financials,
        name="pb_ratio",
        display_name="Price / Book",
        numerator="market_cap",
        denominator="total_equity",
        denominator_must_be_positive=True,
        numerator_must_be_non_negative=True,
    )


def ps_ratio(financials: Financials) -> Metric:
    return _ratio(
        financials,
        name="ps_ratio",
        display_name="Price / Sales",
        numerator="market_cap",
        denominator="revenue",
        denominator_must_be_positive=True,
        numerator_must_be_non_negative=True,
    )


def ev_ebitda(financials: Financials) -> Metric:
    fields = ("market_cap", "total_debt", "cash_and_equivalents", "ebitda")
    values, missing = _collect_fields(financials, fields)
    if missing:
        return _unavailable(
            financials,
            name="ev_ebitda",
            display_name="Enterprise Value / EBITDA",
            inputs_used=fields,
            field_values=values,
            note=f"Missing input(s): {', '.join(missing)}",
        )

    market_cap = _value(values["market_cap"])
    total_debt = _value(values["total_debt"])
    cash = _value(values["cash_and_equivalents"])
    ebitda = _value(values["ebitda"])
    if ebitda <= 0:
        return _unavailable(
            financials,
            name="ev_ebitda",
            display_name="Enterprise Value / EBITDA",
            inputs_used=fields,
            field_values=values.values(),
            note="Denominator ebitda must be positive",
        )

    enterprise_value = market_cap + total_debt - cash
    if enterprise_value < 0:
        return _unavailable(
            financials,
            name="ev_ebitda",
            display_name="Enterprise Value / EBITDA",
            inputs_used=fields,
            field_values=values.values(),
            note="Enterprise value is negative, so EV/EBITDA is not meaningful",
        )
    return _ok(
        name="ev_ebitda",
        display_name="Enterprise Value / EBITDA",
        value=enterprise_value / ebitda,
        inputs_used=fields,
        field_values=values.values(),
    )


def gross_margin(financials: Financials) -> Metric:
    return _ratio(
        financials,
        name="gross_margin",
        display_name="Gross Margin",
        numerator="gross_profit",
        denominator="revenue",
        denominator_must_be_positive=True,
    )


def net_margin(financials: Financials) -> Metric:
    return _ratio(
        financials,
        name="net_margin",
        display_name="Net Margin",
        numerator="net_income",
        denominator="revenue",
        denominator_must_be_positive=True,
    )


def roe(financials: Financials) -> Metric:
    return _ratio(
        financials,
        name="roe",
        display_name="Return on Equity",
        numerator="net_income",
        denominator="total_equity",
        denominator_must_be_positive=True,
    )


def roa(financials: Financials) -> Metric:
    return _ratio(
        financials,
        name="roa",
        display_name="Return on Assets",
        numerator="net_income",
        denominator="total_assets",
        denominator_must_be_positive=True,
    )


def debt_to_equity(financials: Financials) -> Metric:
    return _ratio(
        financials,
        name="debt_to_equity",
        display_name="Debt / Equity",
        numerator="total_debt",
        denominator="total_equity",
        denominator_must_be_positive=True,
        numerator_must_be_non_negative=True,
    )


def current_ratio(financials: Financials) -> Metric:
    return _ratio(
        financials,
        name="current_ratio",
        display_name="Current Ratio",
        numerator="current_assets",
        denominator="current_liabilities",
        denominator_must_be_positive=True,
        numerator_must_be_non_negative=True,
    )


def interest_coverage(financials: Financials) -> Metric:
    return _ratio(
        financials,
        name="interest_coverage",
        display_name="Interest Coverage",
        numerator="operating_income",
        denominator="interest_expense",
        denominator_must_be_positive=True,
    )


def revenue_growth_yoy(financials: Financials) -> Metric:
    return _growth_unavailable(
        financials,
        name="revenue_growth_yoy",
        display_name="Revenue Growth YoY",
        inputs_used=("revenue",),
    )


def earnings_growth_yoy(financials: Financials) -> Metric:
    return _growth_unavailable(
        financials,
        name="earnings_growth_yoy",
        display_name="Earnings Growth YoY",
        inputs_used=("net_income",),
    )


def fcf_trend(financials: Financials) -> Metric:
    return _growth_unavailable(
        financials,
        name="fcf_trend",
        display_name="Free Cash Flow Trend",
        inputs_used=("free_cash_flow",),
    )


def _ratio(
    financials: Financials,
    *,
    name: str,
    display_name: str,
    numerator: str,
    denominator: str,
    denominator_must_be_positive: bool = False,
    numerator_must_be_positive: bool = False,
    numerator_must_be_non_negative: bool = False,
) -> Metric:
    fields = (numerator, denominator)
    values, missing = _collect_fields(financials, fields)
    if missing:
        return _unavailable(
            financials,
            name=name,
            display_name=display_name,
            inputs_used=fields,
            field_values=values,
            note=f"Missing input(s): {', '.join(missing)}",
        )

    numerator_value = _value(values[numerator])
    denominator_value = _value(values[denominator])
    if not math.isfinite(numerator_value) or not math.isfinite(denominator_value):
        return _unavailable(
            financials,
            name=name,
            display_name=display_name,
            inputs_used=fields,
            field_values=values.values(),
            note="Input value is not finite",
        )
    if denominator_value == 0:
        return _unavailable(
            financials,
            name=name,
            display_name=display_name,
            inputs_used=fields,
            field_values=values.values(),
            note=f"Denominator {denominator} is zero",
        )
    if denominator_must_be_positive and denominator_value <= 0:
        return _unavailable(
            financials,
            name=name,
            display_name=display_name,
            inputs_used=fields,
            field_values=values.values(),
            note=f"Denominator {denominator} must be positive",
        )
    if numerator_must_be_positive and numerator_value <= 0:
        return _unavailable(
            financials,
            name=name,
            display_name=display_name,
            inputs_used=fields,
            field_values=values.values(),
            note=f"Numerator {numerator} must be positive",
        )
    if numerator_must_be_non_negative and numerator_value < 0:
        return _unavailable(
            financials,
            name=name,
            display_name=display_name,
            inputs_used=fields,
            field_values=values.values(),
            note=f"Numerator {numerator} must be non-negative",
        )

    ratio_value = numerator_value / denominator_value
    if not math.isfinite(ratio_value):
        return _unavailable(
            financials,
            name=name,
            display_name=display_name,
            inputs_used=fields,
            field_values=values.values(),
            note="Computed ratio is not finite",
        )
    return _ok(
        name=name,
        display_name=display_name,
        value=ratio_value,
        inputs_used=fields,
        field_values=values.values(),
    )


def _growth_unavailable(
    financials: Financials,
    *,
    name: str,
    display_name: str,
    inputs_used: tuple[str, ...],
) -> Metric:
    field_values = [getattr(financials, field_name) for field_name in inputs_used]
    return _unavailable(
        financials,
        name=name,
        display_name=display_name,
        inputs_used=inputs_used,
        field_values=field_values,
        note="Prior-period financials are not available from Phase 0",
    )


def _collect_fields(
    financials: Financials,
    field_names: Iterable[str],
) -> tuple[dict[str, FieldValue], list[str]]:
    values: dict[str, FieldValue] = {}
    missing: list[str] = []
    for field_name in field_names:
        field_value = getattr(financials, field_name, None)
        if isinstance(field_value, FieldValue):
            values[field_name] = field_value
            if not field_value.is_present:
                missing.append(field_name)
            continue
        if not isinstance(field_value, FieldValue):
            missing.append(field_name)
            continue
    return values, missing


def _value(field_value: FieldValue) -> float:
    assert field_value.value is not None
    return field_value.value


def _ok(
    *,
    name: str,
    display_name: str,
    value: float,
    inputs_used: Iterable[str],
    field_values: Iterable[FieldValue],
) -> Metric:
    source, as_of = _provenance(field_values)
    return Metric(
        name=name,
        display_name=display_name,
        value=float(value),
        status=MetricStatus.OK,
        inputs_used=list(inputs_used),
        source=source,
        as_of=as_of,
    )


def _unavailable(
    financials: Financials,
    *,
    name: str,
    display_name: str,
    inputs_used: Iterable[str],
    field_values: Iterable[FieldValue] | dict[str, FieldValue],
    note: str,
) -> Metric:
    values = list(field_values.values()) if isinstance(field_values, dict) else list(field_values)
    source, as_of = _provenance(values, default_source=financials.source, default_as_of=financials.fetched_at)
    return Metric(
        name=name,
        display_name=display_name,
        value=None,
        status=MetricStatus.UNAVAILABLE,
        inputs_used=list(inputs_used),
        source=source,
        as_of=as_of,
        note=note,
    )


def _provenance(
    field_values: Iterable[FieldValue],
    *,
    default_source: str = "unknown",
    default_as_of=None,
) -> tuple[str, object]:
    values = list(field_values)
    if not values:
        if default_as_of is None:
            raise ValueError("default_as_of is required when no fields are available")
        return default_source, default_as_of
    sources = sorted({field_value.source for field_value in values})
    as_of = max(field_value.as_of for field_value in values)
    return "+".join(sources), as_of
