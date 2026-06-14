from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from quantera.models import PriceBar, PriceHistory
from quantera.validation.price_harness import (
    PriceSpotCheckStatus,
    StructuralCheckStatus,
    run_price_validation,
)


class MockProvider:
    def __init__(self, histories: dict[str, PriceHistory]):
        self.histories = histories

    def get_price_history(self, ticker: str):
        return self.histories[ticker]


def make_history(
    ticker: str = "MOCK",
    *,
    start: date = date(2025, 1, 1),
    closes: list[float] | None = None,
) -> PriceHistory:
    closes = closes or [10.0, 11.0, 12.0]
    return PriceHistory(
        ticker=ticker,
        source="mock",
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        bars=[
            PriceBar(
                date=start + timedelta(days=index),
                open=close,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                adj_close=close,
                volume=1000 + index,
            )
            for index, close in enumerate(closes)
        ],
    )


def test_unverified_spot_check_is_skipped_and_cannot_pass():
    history = make_history("AAPL")
    reference_data = {
        "AAPL": {
            "verified_by_human": False,
            "source_url": "",
            "adj_close_checks": [{"date": "2025-01-01", "expected_adj_close": None}],
            "trading_day_count_checks": [],
        }
    }

    report = run_price_validation(MockProvider({"AAPL": history}), reference_data)

    assert report.skipped_unverified == ["AAPL"]
    assert report.spot_check_count == 0
    assert report.passed is False
    assert report.structural_failure_count == 0


def test_verified_spot_checks_can_pass():
    history = make_history("AAPL")
    reference_data = {
        "AAPL": {
            "verified_by_human": True,
            "source_url": "https://example.com/reference",
            "adj_close_checks": [
                {
                    "date": "2025-01-02",
                    "expected_adj_close": 11.0,
                    "tolerance": 0.001,
                }
            ],
            "trading_day_count_checks": [
                {
                    "start_date": "2025-01-01",
                    "end_date": "2025-01-03",
                    "expected_count": 3,
                }
            ],
        }
    }

    report = run_price_validation(MockProvider({"AAPL": history}), reference_data)

    assert report.passed is True
    assert report.match_count == 2
    assert {
        check.status
        for result in report.ticker_results
        for check in result.spot_checks
    } == {PriceSpotCheckStatus.MATCH}


def test_structural_sanity_checks_flag_bad_series():
    bad_history = PriceHistory(
        ticker="BAD",
        source="mock",
        fetched_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        bars=[
            PriceBar(
                date=date(2025, 1, 10),
                open=10.0,
                high=11.0,
                low=9.0,
                close=10.0,
                adj_close=10.0,
                volume=1000,
            ),
            PriceBar(
                date=date(2025, 1, 2),
                open=-1.0,
                high=1.0,
                low=-2.0,
                close=-1.0,
                adj_close=-1.0,
                volume=1000,
            ),
            PriceBar(
                date=date(2025, 1, 23),
                open=12.0,
                high=13.0,
                low=11.0,
                close=12.0,
                adj_close=12.0,
                volume=1000,
            ),
        ],
    )
    reference_data = {
        "BAD": {
            "verified_by_human": False,
            "source_url": "",
            "adj_close_checks": [{"date": "2025-01-02", "expected_adj_close": None}],
            "trading_day_count_checks": [],
        }
    }

    report = run_price_validation(MockProvider({"BAD": bad_history}), reference_data)
    failed = {
        check.check_name
        for result in report.ticker_results
        for check in result.structural_checks
        if check.status is StructuralCheckStatus.FAIL
    }

    assert "chronological_unique" in failed
    assert "positive_prices" in failed
    assert "trading_day_gaps" in failed
    assert report.structural_failure_count >= 3
