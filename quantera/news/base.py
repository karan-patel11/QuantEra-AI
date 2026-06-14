"""Abstract news source interface and normalized news item contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime

from pydantic import BaseModel, Field


class NewsError(RuntimeError):
    """Raised when an external news source cannot return usable company news."""

    def __init__(self, ticker: str, message: str, cause: Exception | None = None):
        self.ticker = ticker
        self.cause = cause
        detail = f"{message} for ticker {ticker}"
        if cause is not None:
            detail = f"{detail}: {cause}"
        super().__init__(detail)


class NewsItem(BaseModel):
    """One normalized company-news item with durable provenance."""

    id: str
    ticker: str
    headline: str
    summary_text: str
    source_name: str
    source_url: str
    published_at: datetime
    retrieved_at: datetime
    raw_relevance: float | None = Field(default=None, ge=0)


class IngestedNews(BaseModel):
    """Whitelisted and normalized news plus audit counts from ingestion."""

    ticker: str
    since: date
    until: date
    items: list[NewsItem] = Field(default_factory=list)
    items_considered: int
    items_after_whitelist: int


class NewsSource(ABC):
    """Swappable company-news interface consumed by the news sentiment lens."""

    @abstractmethod
    def get_company_news(
        self,
        ticker: str,
        since: date,
        until: date,
    ) -> list[NewsItem]:
        raise NotImplementedError
