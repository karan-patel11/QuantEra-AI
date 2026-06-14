from __future__ import annotations

import logging
import os

import pytest

from quantera import config
from quantera.lenses.fundamentals import lens
from quantera.lenses.fundamentals.lens import FundamentalsLens
from quantera.models_fundamentals import MetricStatus
from quantera.provider import DataProvider
from tests.conftest import sample_financials


class MockProvider:
    def __init__(self, financials):
        self.financials = financials
        self.calls: list[str] = []

    def get_financials(self, ticker: str):
        self.calls.append(ticker)
        return self.financials


def test_lens_assembles_metrics_and_verdicts_by_category(fetched_at):
    financials = sample_financials(fetched_at)
    result = FundamentalsLens(MockProvider(financials)).analyze("mock", with_explanation=False)

    assert result.ticker == "MOCK"
    assert result.company_name == "Mock Co."
    assert result.sector == "Testing"
    assert result.explanation is None
    assert result.data_as_of == fetched_at
    assert [category.category for category in result.categories] == [
        "valuation",
        "profitability",
        "health",
        "growth",
    ]

    valuation = result.categories[0]
    assert [metric.name for metric in valuation.metrics] == [
        "pe_ratio",
        "pb_ratio",
        "ps_ratio",
        "ev_ebitda",
    ]
    assert [verdict.metric_name for verdict in valuation.verdicts] == [
        "pe_ratio",
        "pb_ratio",
        "ps_ratio",
        "ev_ebitda",
    ]


def test_lens_partial_data_yields_ok_and_unavailable_without_crashing(fetched_at):
    financials = sample_financials(
        fetched_at,
        overrides={"revenue": None, "total_equity": None},
    )

    result = FundamentalsLens(MockProvider(financials)).analyze("mock", with_explanation=False)
    statuses = [
        metric.status
        for category in result.categories
        for metric in category.metrics
    ]

    assert MetricStatus.OK in statuses
    assert MetricStatus.UNAVAILABLE in statuses


def test_lens_calls_explanation_when_enabled(monkeypatch, fetched_at):
    financials = sample_financials(fetched_at)
    monkeypatch.setattr(
        lens.explain,
        "generate_explanation",
        lambda result, llm_client=None: "mock explanation",
    )

    result = FundamentalsLens(MockProvider(financials)).analyze("mock", with_explanation=True)

    assert result.explanation == "mock explanation"


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("GROQ_API_KEY"), reason="GROQ_API_KEY is not set")
def test_full_lens_real_provider_aapl_with_llm(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(config, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("LLM_PROVIDER", "groq")

    with caplog.at_level(logging.WARNING):
        result = FundamentalsLens(DataProvider()).analyze("AAPL")

    assert result.ticker == "AAPL"
    assert result.categories
    assert result.explanation
    assert "untraceable number" not in caplog.text
