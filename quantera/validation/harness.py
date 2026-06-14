"""Reusable validation harness for data-source accuracy."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from quantera import config
from quantera.models import Financials, FinancialsByPeriod
from quantera.provider import DataProvider
from quantera.validation.reference_data import REFERENCE_DATA


class FieldResultStatus(StrEnum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    MISSING = "MISSING"
    PERIOD_MISMATCH = "PERIOD_MISMATCH"


class FieldValidationResult(BaseModel):
    field: str
    status: FieldResultStatus
    expected: float
    actual: float | None
    relative_error: float | None


class TickerValidationResult(BaseModel):
    ticker: str
    fiscal_period_expected: str | None
    fiscal_period_actual: str | None
    report_date_expected: date | None
    report_date_actual: date | None
    source_available_periods: list[str]
    field_results: list[FieldValidationResult]
    total_fields: int
    period_aligned_field_count: int
    match_count: int
    mismatch_count: int
    missing_count: int
    period_mismatch_count: int
    match_rate: float
    mismatch_rate: float
    missing_rate: float
    period_mismatch_rate: float


class ValidationReport(BaseModel):
    ticker_results: list[TickerValidationResult]
    skipped_unverified: list[str]
    total_fields: int
    period_aligned_field_count: int
    match_count: int
    mismatch_count: int
    missing_count: int
    period_mismatch_count: int
    match_rate: float
    mismatch_rate: float
    missing_rate: float
    period_mismatch_rate: float
    passed: bool


def run_validation(
    provider: DataProvider | None = None,
    reference_data: dict[str, Any] | None = None,
) -> ValidationReport:
    provider = provider or DataProvider()
    reference_data = reference_data or {
        ticker: REFERENCE_DATA[ticker]
        for ticker in config.VALIDATION_TICKERS
        if ticker in REFERENCE_DATA
    }

    ticker_results = []
    skipped_unverified = []
    for ticker, reference in reference_data.items():
        if _is_unverified_or_incomplete(reference):
            skipped_unverified.append(ticker)
            continue
        financials_history = provider.get_financials_history(ticker)
        ticker_results.append(_validate_ticker(ticker, financials_history, reference))

    report = _aggregate(ticker_results, skipped_unverified)
    _print_report(report)
    return report


def _is_unverified_or_incomplete(reference: dict[str, Any]) -> bool:
    fields = reference.get("fields", {})
    return (
        reference.get("verified_by_human") is not True
        or not reference.get("source_url")
        or any(value is None for value in fields.values())
    )


def _validate_ticker(
    ticker: str,
    financials_history: FinancialsByPeriod,
    reference: dict[str, Any],
) -> TickerValidationResult:
    expected_report_date = _parse_date(reference.get("report_date"))
    financials = _select_reference_period(financials_history, reference, expected_report_date)
    source_available_periods = financials_history.available_periods()

    if financials is None:
        return _period_mismatch_result(
            ticker=ticker,
            reference=reference,
            expected_report_date=expected_report_date,
            source_available_periods=source_available_periods,
        )

    field_results = []
    for field_name, expected in reference["fields"].items():
        actual_field = getattr(financials, field_name)
        if not actual_field.is_present:
            status = FieldResultStatus.MISSING
            actual = None
            relative_error = None
        else:
            actual = actual_field.value
            assert actual is not None
            relative_error = _relative_error(actual, expected)
            status = (
                FieldResultStatus.MATCH
                if relative_error <= config.VALUE_TOLERANCE
                else FieldResultStatus.MISMATCH
            )
        field_results.append(
            FieldValidationResult(
                field=field_name,
                status=status,
                expected=float(expected),
                actual=actual,
                relative_error=relative_error,
            )
        )

    total = len(field_results)
    matches = sum(result.status == FieldResultStatus.MATCH for result in field_results)
    mismatches = sum(result.status == FieldResultStatus.MISMATCH for result in field_results)
    missing = sum(result.status == FieldResultStatus.MISSING for result in field_results)
    period_mismatches = sum(
        result.status == FieldResultStatus.PERIOD_MISMATCH
        for result in field_results
    )
    period_aligned = total - period_mismatches
    return TickerValidationResult(
        ticker=ticker,
        fiscal_period_expected=reference.get("fiscal_period"),
        fiscal_period_actual=financials.fiscal_period,
        report_date_expected=expected_report_date,
        report_date_actual=financials.report_date,
        source_available_periods=source_available_periods,
        field_results=field_results,
        total_fields=total,
        period_aligned_field_count=period_aligned,
        match_count=matches,
        mismatch_count=mismatches,
        missing_count=missing,
        period_mismatch_count=period_mismatches,
        match_rate=matches / period_aligned if period_aligned else 0.0,
        mismatch_rate=mismatches / period_aligned if period_aligned else 0.0,
        missing_rate=missing / period_aligned if period_aligned else 0.0,
        period_mismatch_rate=period_mismatches / total if total else 0.0,
    )


def _select_reference_period(
    financials_history: FinancialsByPeriod,
    reference: dict[str, Any],
    expected_report_date: date | None,
) -> Financials | None:
    fiscal_period = reference.get("fiscal_period")
    if fiscal_period is None and expected_report_date is None:
        return financials_history.latest()

    candidates = financials_history.periods
    if fiscal_period is not None:
        candidates = [
            financials
            for financials in candidates
            if financials.fiscal_period == fiscal_period
        ]
    if expected_report_date is not None:
        candidates = [
            financials
            for financials in candidates
            if _same_reporting_period(financials.report_date, expected_report_date)
        ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda financials: (
            financials.report_date or date.min,
            financials.fiscal_period or "",
        ),
    )


def _period_mismatch_result(
    *,
    ticker: str,
    reference: dict[str, Any],
    expected_report_date: date | None,
    source_available_periods: list[str],
) -> TickerValidationResult:
    field_results = [
        FieldValidationResult(
            field=field_name,
            status=FieldResultStatus.PERIOD_MISMATCH,
            expected=float(expected),
            actual=None,
            relative_error=None,
        )
        for field_name, expected in reference["fields"].items()
    ]
    total = len(field_results)
    return TickerValidationResult(
        ticker=ticker,
        fiscal_period_expected=reference.get("fiscal_period"),
        fiscal_period_actual=None,
        report_date_expected=expected_report_date,
        report_date_actual=None,
        source_available_periods=source_available_periods,
        field_results=field_results,
        total_fields=total,
        period_aligned_field_count=0,
        match_count=0,
        mismatch_count=0,
        missing_count=0,
        period_mismatch_count=total,
        match_rate=0.0,
        mismatch_rate=0.0,
        missing_rate=0.0,
        period_mismatch_rate=1.0 if total else 0.0,
    )


def _aggregate(
    ticker_results: list[TickerValidationResult],
    skipped_unverified: list[str],
) -> ValidationReport:
    field_results = [
        field_result
        for ticker_result in ticker_results
        for field_result in ticker_result.field_results
    ]
    total = len(field_results)
    matches = sum(result.status == FieldResultStatus.MATCH for result in field_results)
    mismatches = sum(result.status == FieldResultStatus.MISMATCH for result in field_results)
    missing = sum(result.status == FieldResultStatus.MISSING for result in field_results)
    period_mismatches = sum(
        result.status == FieldResultStatus.PERIOD_MISMATCH
        for result in field_results
    )
    period_aligned = total - period_mismatches
    match_rate = matches / period_aligned if period_aligned else 0.0
    return ValidationReport(
        ticker_results=ticker_results,
        skipped_unverified=skipped_unverified,
        total_fields=total,
        period_aligned_field_count=period_aligned,
        match_count=matches,
        mismatch_count=mismatches,
        missing_count=missing,
        period_mismatch_count=period_mismatches,
        match_rate=match_rate,
        mismatch_rate=mismatches / period_aligned if period_aligned else 0.0,
        missing_rate=missing / period_aligned if period_aligned else 0.0,
        period_mismatch_rate=period_mismatches / total if total else 0.0,
        passed=period_aligned > 0 and match_rate >= config.FIELD_PASS_RATE,
    )


def _print_report(report: ValidationReport) -> None:
    print("QuantEra Phase 0 validation")
    print(
        f"Reference data: verified tickers: {len(report.ticker_results)}; "
        f"skipped unverified: {len(report.skipped_unverified)}"
    )
    if not report.ticker_results:
        print("No human-verified reference data exists yet; validation cannot pass.")
    print(
        "Rates: Match/Mismatch/Missing use period-aligned fields as the denominator; "
        "PeriodMismatch uses all verified fields."
    )
    print("Ticker  Match%  Mismatch%  Missing%  PeriodMismatch%  Expected Period        Source Period          Available Periods")
    print("------  ------  ---------  --------  ---------------  ---------------------  ---------------------  -----------------")
    for result in report.ticker_results:
        expected_period = _period_label(result.fiscal_period_expected, result.report_date_expected)
        actual_period = _period_label(result.fiscal_period_actual, result.report_date_actual)
        available_periods = ", ".join(result.source_available_periods) or "-"
        print(
            f"{result.ticker:<6}  "
            f"{result.match_rate:>6.1%}  "
            f"{result.mismatch_rate:>9.1%}  "
            f"{result.missing_rate:>8.1%}  "
            f"{result.period_mismatch_rate:>15.1%}  "
            f"{expected_period:<21}  "
            f"{actual_period:<21}  "
            f"{available_periods}"
        )
    print("------  ------  ---------  --------  ---------------  ---------------------  ---------------------  -----------------")
    print(
        f"TOTAL   {report.match_rate:>6.1%}  "
        f"{report.mismatch_rate:>9.1%}  "
        f"{report.missing_rate:>8.1%}  "
        f"{report.period_mismatch_rate:>15.1%}  "
        f"{'PASS' if report.passed else 'FAIL'}"
    )
    print(
        f"Fields: total verified={report.total_fields}; "
        f"period-aligned denominator={report.period_aligned_field_count}; "
        f"period mismatches={report.period_mismatch_count}"
    )
    if report.skipped_unverified:
        print("SKIPPED (unverified)")
        for ticker in report.skipped_unverified:
            print(f"- {ticker}")


def _relative_error(actual: float, expected: float) -> float:
    denominator = max(abs(expected), 1.0)
    return abs(actual - expected) / denominator


def _parse_date(value: str | date | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _same_reporting_period(actual: date | None, expected: date | None) -> bool:
    if expected is None:
        return True
    if actual is None:
        return False
    return actual.year == expected.year and actual.month == expected.month


def _period_label(fiscal_period: str | None, report_date: date | None) -> str:
    return f"{fiscal_period or '-'} / {report_date or '-'}"
