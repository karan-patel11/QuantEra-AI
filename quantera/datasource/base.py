"""Abstract data source interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from quantera.models import Financials, FinancialsByPeriod, PriceHistory


class DataSourceError(RuntimeError):
    """Raised when an external data source cannot return a complete response."""

    def __init__(self, ticker: str, message: str, cause: Exception | None = None):
        self.ticker = ticker
        self.cause = cause
        detail = f"{message} for ticker {ticker}"
        if cause is not None:
            detail = f"{detail}: {cause}"
        super().__init__(detail)


class DataSource(ABC):
    """Swappable interface consumed by the provider."""

    def get_financials(self, ticker: str) -> Financials:
        history = self.get_financials_history(ticker)
        latest = history.latest()
        if latest is None:
            raise DataSourceError(ticker, "No financial periods returned")
        return latest

    @abstractmethod
    def get_financials_history(self, ticker: str) -> FinancialsByPeriod:
        raise NotImplementedError

    @abstractmethod
    def get_price_history(self, ticker: str, lookback_days: int) -> PriceHistory:
        raise NotImplementedError
