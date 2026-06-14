"""Public provider API for Phase 0."""

from __future__ import annotations

from quantera import config
from quantera.cache import cache_get, cache_set
from quantera.datasource.base import DataSource
from quantera.models import Financials, FinancialsByPeriod, PriceHistory
from quantera.normalize import normalize_financials_history, normalize_price_history


class DataProvider:
    """Fetch, normalize, cache, and return contract models."""

    def __init__(self, source: DataSource | None = None):
        if source is None:
            from quantera.datasource.yfinance_source import YFinanceSource

            source = YFinanceSource()
        self.source = source

    def get_financials(self, ticker: str) -> Financials:
        history = self.get_financials_history(ticker)
        latest = history.latest()
        if latest is None:
            raise ValueError(f"No financial periods available for {ticker.upper()}")
        return latest

    def get_financials_history(self, ticker: str) -> FinancialsByPeriod:
        symbol = ticker.upper()
        key = f"financials_history:{symbol}"
        cached = cache_get(key)
        if cached is not None:
            return FinancialsByPeriod.model_validate(cached)

        financials = normalize_financials_history(self.source.get_financials_history(symbol))
        cache_set(
            key,
            financials.model_dump(mode="json"),
            config.FUNDAMENTALS_TTL_SECONDS,
        )
        return financials

    def get_price_history(
        self,
        ticker: str,
        lookback_days: int = config.PRICE_LOOKBACK_DAYS,
    ) -> PriceHistory:
        symbol = ticker.upper()
        key = f"prices:{symbol}:{lookback_days}"
        cached = cache_get(key)
        if cached is not None:
            return PriceHistory.model_validate(cached)

        price_history = normalize_price_history(
            self.source.get_price_history(symbol, lookback_days)
        )
        cache_set(
            key,
            price_history.model_dump(mode="json"),
            config.PRICES_TTL_SECONDS,
        )
        return price_history
