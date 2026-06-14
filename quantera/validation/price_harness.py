"""Lightweight price-data validation harness."""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel

from quantera import config
from quantera.models import PriceBar, PriceHistory
from quantera.provider import DataProvider
from quantera.validation.price_reference import PRICE_REFERENCE_DATA


DEFAULT_ADJ_CLOSE_TOLERANCE = 0.01
MAX_MISSING_TRADING_DAYS = 5


class PriceSpotCheckStatus(StrEnum):
    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    MISSING = "MISSING"


class StructuralCheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class PriceSpotCheckResult(BaseModel):
    ticker: str
    check_type: str
    date: Date | None = None
    start_date: Date | None = None
    end_date: Date | None = None
    status: PriceSpotCheckStatus
    expected: float | int
    actual: float | int | None
    tolerance: float | None = None


class PriceStructuralCheckResult(BaseModel):
    ticker: str
    check_name: str
    status: StructuralCheckStatus
    detail: str


class TickerPriceValidationResult(BaseModel):
    ticker: str
    spot_checks: list[PriceSpotCheckResult]
    structural_checks: list[PriceStructuralCheckResult]


class PriceValidationReport(BaseModel):
    ticker_results: list[TickerPriceValidationResult]
    skipped_unverified: list[str]
    spot_check_count: int
    match_count: int
    mismatch_count: int
    missing_count: int
    structural_failure_count: int
    passed: bool


def run_price_validation(
    provider: DataProvider | None = None,
    reference_data: dict[str, Any] | None = None,
) -> PriceValidationReport:
    provider = provider or DataProvider()
    reference_data = reference_data or {
        ticker: PRICE_REFERENCE_DATA[ticker]
        for ticker in config.VALIDATION_TICKERS
        if ticker in PRICE_REFERENCE_DATA
    }

    ticker_results: list[TickerPriceValidationResult] = []
    skipped_unverified: list[str] = []
    for ticker, reference in reference_data.items():
        prices = provider.get_price_history(ticker)
        structural_checks = _structural_checks(ticker, prices)
        spot_checks: list[PriceSpotCheckResult] = []
        if _is_unverified_or_incomplete(reference):
            skipped_unverified.append(ticker)
        else:
            spot_checks = _spot_checks(ticker, prices, reference)
        ticker_results.append(
            TickerPriceValidationResult(
                ticker=ticker,
                spot_checks=spot_checks,
                structural_checks=structural_checks,
            )
        )

    report = _aggregate(ticker_results, skipped_unverified)
    _print_report(report)
    return report


def _is_unverified_or_incomplete(reference: dict[str, Any]) -> bool:
    if reference.get("verified_by_human") is not True or not reference.get("source_url"):
        return True
    for check in reference.get("adj_close_checks", []):
        if check.get("date") is None or check.get("expected_adj_close") is None:
            return True
    for check in reference.get("trading_day_count_checks", []):
        if (
            check.get("start_date") is None
            or check.get("end_date") is None
            or check.get("expected_count") is None
        ):
            return True
    return False


def _spot_checks(
    ticker: str,
    prices: PriceHistory,
    reference: dict[str, Any],
) -> list[PriceSpotCheckResult]:
    by_date = {bar.date: bar for bar in prices.bars}
    results: list[PriceSpotCheckResult] = []

    for check in reference.get("adj_close_checks", []):
        check_date = _parse_date(check["date"])
        expected = float(check["expected_adj_close"])
        tolerance = float(check.get("tolerance", DEFAULT_ADJ_CLOSE_TOLERANCE))
        bar = by_date.get(check_date)
        if bar is None:
            status = PriceSpotCheckStatus.MISSING
            actual = None
        else:
            actual = bar.adj_close
            status = (
                PriceSpotCheckStatus.MATCH
                if abs(actual - expected) <= tolerance
                else PriceSpotCheckStatus.MISMATCH
            )
        results.append(
            PriceSpotCheckResult(
                ticker=ticker,
                check_type="adj_close",
                date=check_date,
                status=status,
                expected=expected,
                actual=actual,
                tolerance=tolerance,
            )
        )

    for check in reference.get("trading_day_count_checks", []):
        start_date = _parse_date(check["start_date"])
        end_date = _parse_date(check["end_date"])
        expected_count = int(check["expected_count"])
        actual_count = sum(
            start_date <= bar.date <= end_date
            for bar in prices.bars
        )
        status = (
            PriceSpotCheckStatus.MATCH
            if actual_count == expected_count
            else PriceSpotCheckStatus.MISMATCH
        )
        results.append(
            PriceSpotCheckResult(
                ticker=ticker,
                check_type="trading_day_count",
                start_date=start_date,
                end_date=end_date,
                status=status,
                expected=expected_count,
                actual=actual_count,
            )
        )
    return results


def _structural_checks(ticker: str, prices: PriceHistory) -> list[PriceStructuralCheckResult]:
    return [
        _chronological_and_unique_check(ticker, prices.bars),
        _positive_prices_check(ticker, prices.bars),
        _raw_close_within_ohlc_check(ticker, prices.bars),
        _gap_check(ticker, prices.bars),
    ]


def _chronological_and_unique_check(
    ticker: str,
    bars: list[PriceBar],
) -> PriceStructuralCheckResult:
    dates = [bar.date for bar in bars]
    duplicate_count = len(dates) - len(set(dates))
    out_of_order = any(current <= previous for previous, current in zip(dates, dates[1:]))
    if duplicate_count or out_of_order:
        details: list[str] = []
        if duplicate_count:
            details.append(f"{duplicate_count} duplicate date(s)")
        if out_of_order:
            details.append("dates are not strictly chronological")
        return PriceStructuralCheckResult(
            ticker=ticker,
            check_name="chronological_unique",
            status=StructuralCheckStatus.FAIL,
            detail=", ".join(details),
        )
    return PriceStructuralCheckResult(
        ticker=ticker,
        check_name="chronological_unique",
        status=StructuralCheckStatus.PASS,
        detail=f"{len(bars)} bars are strictly chronological and de-duplicated",
    )


def _positive_prices_check(ticker: str, bars: list[PriceBar]) -> PriceStructuralCheckResult:
    bad = [
        f"{bar.date}:{field_name}={getattr(bar, field_name)}"
        for bar in bars
        for field_name in ("open", "high", "low", "close", "adj_close")
        if getattr(bar, field_name) <= 0
    ]
    if bad:
        return PriceStructuralCheckResult(
            ticker=ticker,
            check_name="positive_prices",
            status=StructuralCheckStatus.FAIL,
            detail="Non-positive price(s): " + "; ".join(bad[:5]),
        )
    return PriceStructuralCheckResult(
        ticker=ticker,
        check_name="positive_prices",
        status=StructuralCheckStatus.PASS,
        detail="All OHLC and adjusted-close prices are positive",
    )


def _raw_close_within_ohlc_check(
    ticker: str,
    bars: list[PriceBar],
) -> PriceStructuralCheckResult:
    bad = [
        f"{bar.date}: close={bar.close}, low={bar.low}, high={bar.high}"
        for bar in bars
        if not (bar.low <= bar.close <= bar.high)
    ]
    if bad:
        return PriceStructuralCheckResult(
            ticker=ticker,
            check_name="raw_close_within_ohlc",
            status=StructuralCheckStatus.FAIL,
            detail="Raw close outside raw low/high: " + "; ".join(bad[:5]),
        )
    return PriceStructuralCheckResult(
        ticker=ticker,
        check_name="raw_close_within_ohlc",
        status=StructuralCheckStatus.PASS,
        detail="Raw close is within raw low/high for every bar",
    )


def _gap_check(ticker: str, bars: list[PriceBar]) -> PriceStructuralCheckResult:
    sorted_dates = sorted({bar.date for bar in bars})
    largest_gap = 0
    largest_pair: tuple[Date, Date] | None = None
    for previous, current in zip(sorted_dates, sorted_dates[1:]):
        missing = _missing_weekdays_between(previous, current)
        if missing > largest_gap:
            largest_gap = missing
            largest_pair = (previous, current)
    if largest_gap > MAX_MISSING_TRADING_DAYS and largest_pair is not None:
        return PriceStructuralCheckResult(
            ticker=ticker,
            check_name="trading_day_gaps",
            status=StructuralCheckStatus.FAIL,
            detail=(
                f"{largest_gap} missing weekday(s) between "
                f"{largest_pair[0]} and {largest_pair[1]}"
            ),
        )
    return PriceStructuralCheckResult(
        ticker=ticker,
        check_name="trading_day_gaps",
        status=StructuralCheckStatus.PASS,
        detail=f"No gap exceeded {MAX_MISSING_TRADING_DAYS} missing weekday(s)",
    )


def _missing_weekdays_between(previous: Date, current: Date) -> int:
    missing = 0
    cursor = previous + timedelta(days=1)
    while cursor < current:
        if cursor.weekday() < 5:
            missing += 1
        cursor += timedelta(days=1)
    return missing


def _aggregate(
    ticker_results: list[TickerPriceValidationResult],
    skipped_unverified: list[str],
) -> PriceValidationReport:
    spot_checks = [
        spot_check
        for ticker_result in ticker_results
        for spot_check in ticker_result.spot_checks
    ]
    structural_checks = [
        structural_check
        for ticker_result in ticker_results
        for structural_check in ticker_result.structural_checks
    ]
    matches = sum(check.status == PriceSpotCheckStatus.MATCH for check in spot_checks)
    mismatches = sum(check.status == PriceSpotCheckStatus.MISMATCH for check in spot_checks)
    missing = sum(check.status == PriceSpotCheckStatus.MISSING for check in spot_checks)
    structural_failures = sum(
        check.status == StructuralCheckStatus.FAIL
        for check in structural_checks
    )
    return PriceValidationReport(
        ticker_results=ticker_results,
        skipped_unverified=skipped_unverified,
        spot_check_count=len(spot_checks),
        match_count=matches,
        mismatch_count=mismatches,
        missing_count=missing,
        structural_failure_count=structural_failures,
        passed=(
            len(spot_checks) > 0
            and mismatches == 0
            and missing == 0
            and structural_failures == 0
        ),
    )


def _print_report(report: PriceValidationReport) -> None:
    print("QuantEra Phase 2 price validation")
    print(
        f"Spot checks: total={report.spot_check_count}; matches={report.match_count}; "
        f"mismatches={report.mismatch_count}; missing={report.missing_count}"
    )
    print(
        f"Structural failures: {report.structural_failure_count}; "
        f"skipped unverified references: {len(report.skipped_unverified)}"
    )
    if report.spot_check_count == 0:
        print("No human-verified price spot checks exist yet; validation cannot pass.")

    for ticker_result in report.ticker_results:
        print(f"{ticker_result.ticker}")
        for check in ticker_result.structural_checks:
            print(f"- {check.check_name}: {check.status.value} ({check.detail})")
        for check in ticker_result.spot_checks:
            label = check.date or f"{check.start_date}..{check.end_date}"
            print(
                f"- {check.check_type} {label}: {check.status.value} "
                f"expected={check.expected} actual={check.actual}"
            )
    if report.skipped_unverified:
        print("SKIPPED PRICE REFERENCES (unverified or incomplete)")
        for ticker in report.skipped_unverified:
            print(f"- {ticker}")
    print(f"TOTAL {'PASS' if report.passed else 'FAIL'}")


def _parse_date(value: str | Date) -> Date:
    if isinstance(value, Date):
        return value
    return Date.fromisoformat(value)
