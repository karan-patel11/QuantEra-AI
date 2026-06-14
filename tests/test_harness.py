from __future__ import annotations

from datetime import date

from quantera import config
from quantera.datasource.base import DataSource
from quantera.models import FinancialsByPeriod
from quantera.validation.harness import FieldResultStatus, run_validation
from tests.conftest import sample_financials, sample_price_history


class HarnessSource(DataSource):
    def __init__(self, fetched_at):
        self.fetched_at = fetched_at
        self.financial_calls: list[str] = []

    def get_financials(self, ticker):
        self.financial_calls.append(ticker)
        return self.get_financials_history(ticker).latest()

    def get_financials_history(self, ticker):
        self.financial_calls.append(ticker)
        if ticker == "MISSING":
            return FinancialsByPeriod(
                ticker=ticker,
                periods=[
                    sample_financials(
                        self.fetched_at,
                        ticker=ticker,
                        overrides={"revenue": None, "net_income": None, "total_assets": None},
                    )
                ],
            )
        if ticker == "HISTORY":
            return FinancialsByPeriod(
                ticker=ticker,
                periods=[
                    sample_financials(
                        self.fetched_at,
                        ticker=ticker,
                        fiscal_period="FY2025",
                        report_date=date(2025, 12, 31),
                        overrides={"revenue": 999.0, "net_income": 999.0},
                    ),
                    sample_financials(
                        self.fetched_at,
                        ticker=ticker,
                        fiscal_period="FY2024",
                        report_date=date(2024, 12, 31),
                        overrides={
                            "revenue": 100.0,
                            "net_income": 80.0,
                            "total_assets": None,
                        },
                    ),
                ],
            )
        return FinancialsByPeriod(
            ticker=ticker,
            periods=[
                sample_financials(
                    self.fetched_at,
                    ticker=ticker,
                    overrides={
                        "revenue": 100.0,
                        "net_income": 80.0,
                        "total_assets": 1000.0,
                    },
                )
            ],
        )

    def get_price_history(self, ticker, lookback_days):
        return sample_price_history(self.fetched_at)


def test_harness_classifies_match_mismatch_missing_and_pass_fail(
    tmp_path,
    monkeypatch,
    fetched_at,
):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "FIELD_PASS_RATE", 0.5)
    reference = {
        "MATCH": {
            "fiscal_period": "FY2025",
            "report_date": "2025-12-31",
            "source_url": "https://www.sec.gov/Archives/mock-match",
            "verified_by_human": True,
            "fields": {"revenue": 100.0, "net_income": 100.0},
        },
        "MISSING": {
            "fiscal_period": "FY2025",
            "report_date": "2025-12-31",
            "source_url": "https://www.sec.gov/Archives/mock-missing",
            "verified_by_human": True,
            "fields": {"revenue": 100.0},
        },
    }

    source = HarnessSource(fetched_at)
    report = run_validation(
        provider=__import__("quantera.provider", fromlist=["DataProvider"]).DataProvider(source=source),
        reference_data=reference,
    )

    statuses = [
        field.status
        for ticker_result in report.ticker_results
        for field in ticker_result.field_results
    ]
    assert statuses == [
        FieldResultStatus.MATCH,
        FieldResultStatus.MISMATCH,
        FieldResultStatus.MISSING,
    ]
    assert report.match_count == 1
    assert report.mismatch_count == 1
    assert report.missing_count == 1
    assert report.skipped_unverified == []
    assert report.passed is False


def test_harness_skips_unverified_or_incomplete_tickers(
    tmp_path,
    monkeypatch,
    fetched_at,
):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "FIELD_PASS_RATE", 0.5)
    reference = {
        "MATCH": {
            "fiscal_period": "FY2025",
            "report_date": "2025-12-31",
            "source_url": "https://www.sec.gov/Archives/mock-match",
            "verified_by_human": True,
            "fields": {"revenue": 100.0, "net_income": 100.0},
        },
        "UNVERIFIED": {
            "fiscal_period": None,
            "report_date": None,
            "source_url": "https://www.sec.gov/Archives/mock-unverified",
            "verified_by_human": False,
            "fields": {"revenue": 100.0},
        },
        "INCOMPLETE": {
            "fiscal_period": None,
            "report_date": None,
            "source_url": "https://www.sec.gov/Archives/mock-incomplete",
            "verified_by_human": True,
            "fields": {"revenue": None},
        },
        "NOURL": {
            "fiscal_period": None,
            "report_date": None,
            "source_url": "",
            "verified_by_human": True,
            "fields": {"revenue": 100.0},
        },
    }

    source = HarnessSource(fetched_at)
    report = run_validation(
        provider=__import__("quantera.provider", fromlist=["DataProvider"]).DataProvider(source=source),
        reference_data=reference,
    )

    assert source.financial_calls == ["MATCH"]
    assert report.skipped_unverified == ["UNVERIFIED", "INCOMPLETE", "NOURL"]
    assert report.total_fields == 2
    assert report.match_count == 1
    assert report.mismatch_count == 1
    assert report.missing_count == 0
    assert report.match_rate == 0.5
    assert report.passed is True


def test_harness_period_mismatch_is_distinct_and_excluded_from_match_rate(
    tmp_path,
    monkeypatch,
    fetched_at,
    capsys,
):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "FIELD_PASS_RATE", 0.5)
    reference = {
        "MATCH": {
            "fiscal_period": "FY2025",
            "report_date": "2025-12-31",
            "source_url": "https://www.sec.gov/Archives/mock-match",
            "verified_by_human": True,
            "fields": {"revenue": 100.0, "net_income": 100.0},
        },
        "PERIOD": {
            "fiscal_period": "FY2024",
            "report_date": "2024-12-31",
            "source_url": "https://www.sec.gov/Archives/mock-period",
            "verified_by_human": True,
            "fields": {"revenue": 100.0, "net_income": 80.0},
        },
    }

    source = HarnessSource(fetched_at)
    report = run_validation(
        provider=__import__("quantera.provider", fromlist=["DataProvider"]).DataProvider(source=source),
        reference_data=reference,
    )

    period_result = next(result for result in report.ticker_results if result.ticker == "PERIOD")
    assert [field.status for field in period_result.field_results] == [
        FieldResultStatus.PERIOD_MISMATCH,
        FieldResultStatus.PERIOD_MISMATCH,
    ]
    assert period_result.period_aligned_field_count == 0
    assert period_result.period_mismatch_count == 2
    assert period_result.match_rate == 0.0

    assert report.total_fields == 4
    assert report.period_aligned_field_count == 2
    assert report.match_count == 1
    assert report.mismatch_count == 1
    assert report.period_mismatch_count == 2
    assert report.match_rate == 0.5
    assert report.period_mismatch_rate == 0.5
    assert report.passed is True
    assert "FY2025 / 2025-12-31" in capsys.readouterr().out


def test_harness_selects_reference_period_from_history(
    tmp_path,
    monkeypatch,
    fetched_at,
):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(config, "FIELD_PASS_RATE", 0.2)
    reference = {
        "HISTORY": {
            "fiscal_period": "FY2024",
            "report_date": "2024-12-31",
            "source_url": "https://www.sec.gov/Archives/mock-history",
            "verified_by_human": True,
            "fields": {
                "revenue": 100.0,
                "net_income": 100.0,
                "total_assets": 1000.0,
            },
        },
    }

    source = HarnessSource(fetched_at)
    report = run_validation(
        provider=__import__("quantera.provider", fromlist=["DataProvider"]).DataProvider(source=source),
        reference_data=reference,
    )

    statuses = [
        field.status
        for ticker_result in report.ticker_results
        for field in ticker_result.field_results
    ]
    assert statuses == [
        FieldResultStatus.MATCH,
        FieldResultStatus.MISMATCH,
        FieldResultStatus.MISSING,
    ]
    assert source.financial_calls == ["HISTORY"]
    assert report.total_fields == 3
    assert report.period_aligned_field_count == 3
    assert report.period_mismatch_count == 0
    assert report.match_rate == 1 / 3


def test_harness_cannot_pass_when_no_tickers_are_verified(
    tmp_path,
    monkeypatch,
    fetched_at,
    capsys,
):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    reference = {
        "UNVERIFIED": {
            "fiscal_period": None,
            "report_date": None,
            "source_url": "",
            "verified_by_human": False,
            "fields": {"revenue": None},
        },
    }

    source = HarnessSource(fetched_at)
    report = run_validation(
        provider=__import__("quantera.provider", fromlist=["DataProvider"]).DataProvider(source=source),
        reference_data=reference,
    )

    captured = capsys.readouterr()
    assert source.financial_calls == []
    assert report.skipped_unverified == ["UNVERIFIED"]
    assert report.total_fields == 0
    assert report.match_rate == 0.0
    assert report.passed is False
    assert "No human-verified reference data exists yet" in captured.out
