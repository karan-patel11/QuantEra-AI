from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable

import pytest

from quantera.models import FieldValue, Financials, FinancialsByPeriod, PriceBar, PriceHistory
from quantera.news.base import NewsItem


class MockLLMClient:
    def __init__(self, responder: Callable[..., str]):
        self.responder = responder
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        self.calls.append(
            {
                "system": system,
                "user": user,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        return self.responder(system, user, max_tokens, temperature)


@pytest.fixture
def fetched_at() -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc)


def fv(value: float | None, fetched_at: datetime, source: str = "mock") -> FieldValue:
    if value is None:
        return FieldValue.missing(source, fetched_at)
    return FieldValue.present(value, source, fetched_at)


def sample_financials(
    fetched_at: datetime,
    *,
    ticker: str = "MOCK",
    source: str = "mock",
    fiscal_period: str = "FY2025",
    report_date: date = date(2025, 12, 31),
    overrides: dict[str, float | None] | None = None,
) -> Financials:
    values: dict[str, float | None] = {
        "revenue": 1000.0,
        "net_income": 100.0,
        "gross_profit": 400.0,
        "operating_income": 150.0,
        "total_assets": 1000.0,
        "total_liabilities": 600.0,
        "total_equity": 400.0,
        "total_debt": 200.0,
        "cash_and_equivalents": 50.0,
        "current_assets": 300.0,
        "current_liabilities": 125.0,
        "shares_outstanding": 10.0,
        "eps": 10.0,
        "operating_cash_flow": 120.0,
        "free_cash_flow": 80.0,
        "market_price": 25.0,
        "market_cap": 250.0,
    }
    if overrides:
        values.update(overrides)
    return Financials(
        ticker=ticker,
        company_name="Mock Co.",
        exchange="NYSE",
        sector="Testing",
        industry="Mocks",
        fiscal_period=fiscal_period,
        report_date=report_date,
        currency="USD",
        source=source,
        fetched_at=fetched_at,
        **{
            field_name: fv(value, fetched_at, source)
            for field_name, value in values.items()
        },
    )


def sample_financials_history(
    fetched_at: datetime,
    *,
    ticker: str = "MOCK",
    source: str = "mock",
) -> FinancialsByPeriod:
    return FinancialsByPeriod(
        ticker=ticker,
        periods=[
            sample_financials(
                fetched_at,
                ticker=ticker,
                source=source,
                fiscal_period="FY2025",
                report_date=date(2025, 12, 31),
            ),
            sample_financials(
                fetched_at,
                ticker=ticker,
                source=source,
                fiscal_period="FY2024",
                report_date=date(2024, 12, 31),
                overrides={
                    "revenue": 100.0,
                    "net_income": 80.0,
                    "total_assets": 1000.0,
                },
            ),
        ],
    )


def sample_price_history(fetched_at: datetime) -> PriceHistory:
    return PriceHistory(
        ticker="MOCK",
        source="mock",
        fetched_at=fetched_at,
        bars=[
            PriceBar(
                date=date(2025, 1, 2),
                open=10.0,
                high=11.0,
                low=9.0,
                close=10.5,
                adj_close=10.4,
                volume=1000,
            )
        ],
    )


def sample_news_item(
    *,
    item_id: str = "news-1",
    ticker: str = "AAPL",
    headline: str = "Apple profit outlook improved",
    summary_text: str = "The report says profit outlook improved after stronger services demand.",
    source_name: str = "Reuters",
    source_url: str = "https://www.reuters.com/markets/apple-profit-outlook",
    published_at: datetime | None = None,
    retrieved_at: datetime | None = None,
    raw_relevance: float | None = None,
) -> NewsItem:
    timestamp = datetime(2026, 1, 2, tzinfo=timezone.utc)
    return NewsItem(
        id=item_id,
        ticker=ticker,
        headline=headline,
        summary_text=summary_text,
        source_name=source_name,
        source_url=source_url,
        published_at=published_at or timestamp,
        retrieved_at=retrieved_at or datetime(2026, 1, 3, tzinfo=timezone.utc),
        raw_relevance=raw_relevance,
    )
