"""Orchestration for the fundamentals lens."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from quantera.lenses.fundamentals import explain, ratios
from quantera.lenses.fundamentals.verdicts import make_verdict
from quantera.llm.base import LLMClient
from quantera.models import Financials
from quantera.models_fundamentals import CategoryResult, FundamentalsResult, Metric
from quantera.provider import DataProvider


MetricFunction = Callable[[Financials], Metric]


CATEGORY_METRICS: dict[str, tuple[MetricFunction, ...]] = {
    "valuation": (
        ratios.pe_ratio,
        ratios.pb_ratio,
        ratios.ps_ratio,
        ratios.ev_ebitda,
    ),
    "profitability": (
        ratios.gross_margin,
        ratios.net_margin,
        ratios.roe,
        ratios.roa,
    ),
    "health": (
        ratios.debt_to_equity,
        ratios.current_ratio,
        ratios.interest_coverage,
    ),
    "growth": (
        ratios.revenue_growth_yoy,
        ratios.earnings_growth_yoy,
        ratios.fcf_trend,
    ),
}


class FundamentalsLens:
    """Analyze company fundamentals from normalized Phase 0 financials."""

    def __init__(self, provider: DataProvider, llm_client: LLMClient | None = None):
        self.provider = provider
        self.llm_client = llm_client

    def analyze(self, ticker: str, with_explanation: bool = True) -> FundamentalsResult:
        financials = self.provider.get_financials(ticker)
        categories: list[CategoryResult] = []

        for category, metric_functions in CATEGORY_METRICS.items():
            metrics = [metric_function(financials) for metric_function in metric_functions]
            verdicts = [make_verdict(metric, financials.sector) for metric in metrics]
            categories.append(
                CategoryResult(
                    category=category,
                    metrics=metrics,
                    verdicts=verdicts,
                )
            )

        result = FundamentalsResult(
            ticker=financials.ticker,
            company_name=financials.company_name,
            sector=financials.sector,
            categories=categories,
            explanation=None,
            generated_at=datetime.now(timezone.utc),
            data_as_of=_data_as_of(financials),
        )

        if with_explanation:
            result.explanation = explain.generate_explanation(result, llm_client=self.llm_client)
        return result


def _data_as_of(financials: Financials) -> datetime:
    present_dates = [
        getattr(financials, field_name).as_of
        for field_name in Financials.LINE_ITEM_FIELDS
        if getattr(financials, field_name).is_present
    ]
    if not present_dates:
        return financials.fetched_at
    return max(present_dates)
