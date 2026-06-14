"""yfinance-backed data source adapter.

This is intentionally the only module that imports yfinance.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable

import yfinance as yf

from quantera.datasource.base import DataSource, DataSourceError
from quantera.models import FieldValue, Financials, FinancialsByPeriod, PriceBar, PriceHistory, utc_now


SOURCE_NAME = "yfinance"


class YFinanceSource(DataSource):
    """Map yfinance responses into the QuantEra contract shape."""

    def get_financials_history(self, ticker: str) -> FinancialsByPeriod:
        symbol = ticker.upper()
        fetched_at = utc_now()
        try:
            stock = yf.Ticker(symbol)
            info = self._safe_dict(getattr(stock, "info", {}))
            fast_info = self._safe_dict(getattr(stock, "fast_info", {}))
            income_stmt = self._statement(stock, ("income_stmt", "financials"))
            balance_sheet = self._statement(stock, ("balance_sheet", "balancesheet"))
            cash_flow = self._statement(stock, ("cashflow", "cash_flow"))
            columns = self._statement_columns(income_stmt, balance_sheet, cash_flow)

            currency = self._first_present(
                fast_info,
                info,
                ("currency", "financialCurrency", "quoteType"),
            )
            metadata = {
                "company_name": self._first_present(
                    info,
                    {},
                    ("longName", "shortName", "displayName"),
                ),
                "exchange": self._first_present(
                    info,
                    fast_info,
                    ("exchange", "fullExchangeName", "exchangeName"),
                ),
                "sector": self._first_present(info, {}, ("sector",)),
                "industry": self._first_present(info, {}, ("industry",)),
                "currency": currency,
            }
            latest_column = columns[0] if columns else None
            periods = [
                self._financials_for_period(
                    symbol=symbol,
                    column=column,
                    fetched_at=fetched_at,
                    income_stmt=income_stmt,
                    balance_sheet=balance_sheet,
                    cash_flow=cash_flow,
                    info=info,
                    fast_info=fast_info,
                    metadata=metadata,
                    include_market_fields=column == latest_column,
                )
                for column in columns
            ]

            return FinancialsByPeriod(ticker=symbol, periods=periods)
        except DataSourceError:
            raise
        except Exception as exc:
            raise DataSourceError(symbol, "Failed to fetch financials history", exc) from exc

    def get_price_history(self, ticker: str, lookback_days: int) -> PriceHistory:
        symbol = ticker.upper()
        fetched_at = utc_now()
        try:
            stock = yf.Ticker(symbol)
            start = date.today() - timedelta(days=lookback_days)
            history = stock.history(
                start=start.isoformat(),
                interval="1d",
                auto_adjust=False,
                actions=False,
            )
            bars: list[PriceBar] = []
            if history is not None and not history.empty:
                for raw_index, row in history.iterrows():
                    bar_date = raw_index.date()
                    open_value = self._coerce_number(row.get("Open"))
                    high_value = self._coerce_number(row.get("High"))
                    low_value = self._coerce_number(row.get("Low"))
                    adj_close = self._coerce_number(row.get("Adj Close"))
                    close = self._coerce_number(row.get("Close"))
                    volume = self._coerce_number(row.get("Volume"))
                    if None in (open_value, high_value, low_value, close, adj_close, volume):
                        continue
                    bars.append(
                        PriceBar(
                            date=bar_date,
                            open=open_value,
                            high=high_value,
                            low=low_value,
                            close=close,
                            adj_close=adj_close,
                            volume=int(volume),
                        )
                    )
            return PriceHistory(
                ticker=symbol,
                bars=bars,
                source=SOURCE_NAME,
                fetched_at=fetched_at,
            )
        except Exception as exc:
            raise DataSourceError(symbol, "Failed to fetch price history", exc) from exc

    def _statement(self, stock: Any, names: Iterable[str]) -> Any:
        for name in names:
            try:
                statement = getattr(stock, name)
            except Exception:
                continue
            if statement is not None and not getattr(statement, "empty", True):
                return statement
        return None

    def _financials_for_period(
        self,
        *,
        symbol: str,
        column: Any,
        fetched_at,
        income_stmt: Any,
        balance_sheet: Any,
        cash_flow: Any,
        info: dict[str, Any],
        fast_info: dict[str, Any],
        metadata: dict[str, Any],
        include_market_fields: bool,
    ) -> Financials:
        report_date = self._column_date(column)
        # yfinance annual statement columns are fiscal year-end dates; the internal
        # FY label uses that year directly, so a 2024-01-28 year-end is FY2024.
        fiscal_period = f"FY{report_date.year}" if report_date is not None else None
        values = {
            "revenue": self._statement_value(
                income_stmt,
                ("Total Revenue", "Operating Revenue"),
                column,
                fetched_at,
            ),
            "net_income": self._statement_value(
                income_stmt,
                ("Net Income", "Net Income Common Stockholders"),
                column,
                fetched_at,
            ),
            "gross_profit": self._statement_value(
                income_stmt,
                ("Gross Profit",),
                column,
                fetched_at,
            ),
            "operating_income": self._statement_value(
                income_stmt,
                ("Operating Income",),
                column,
                fetched_at,
            ),
            "total_assets": self._statement_value(
                balance_sheet,
                ("Total Assets",),
                column,
                fetched_at,
            ),
            "total_liabilities": self._statement_value(
                balance_sheet,
                (
                    "Total Liabilities Net Minority Interest",
                    "Total Liabilities",
                ),
                column,
                fetched_at,
            ),
            "total_equity": self._statement_value(
                balance_sheet,
                (
                    "Stockholders Equity",
                    "Total Equity Gross Minority Interest",
                    "Common Stock Equity",
                ),
                column,
                fetched_at,
            ),
            "total_debt": self._statement_value(
                balance_sheet,
                ("Total Debt", "Long Term Debt And Capital Lease Obligation"),
                column,
                fetched_at,
            ),
            "cash_and_equivalents": self._statement_value(
                balance_sheet,
                (
                    "Cash And Cash Equivalents",
                    "Cash Cash Equivalents And Short Term Investments",
                ),
                column,
                fetched_at,
            ),
            "current_assets": self._statement_value(
                balance_sheet,
                ("Current Assets", "Total Current Assets"),
                column,
                fetched_at,
            ),
            "current_liabilities": self._statement_value(
                balance_sheet,
                ("Current Liabilities", "Total Current Liabilities"),
                column,
                fetched_at,
            ),
            "operating_cash_flow": self._statement_value(
                cash_flow,
                (
                    "Operating Cash Flow",
                    "Total Cash From Operating Activities",
                ),
                column,
                fetched_at,
            ),
            "free_cash_flow": self._statement_value(
                cash_flow,
                ("Free Cash Flow",),
                column,
                fetched_at,
            ),
        }
        values.update(self._market_values(info, fast_info, fetched_at, include_market_fields))
        return Financials(
            ticker=symbol,
            fiscal_period=fiscal_period,
            report_date=report_date,
            source=SOURCE_NAME,
            fetched_at=fetched_at,
            **metadata,
            **values,
        )

    def _market_values(
        self,
        info: dict[str, Any],
        fast_info: dict[str, Any],
        fetched_at,
        include_market_fields: bool,
    ) -> dict[str, FieldValue]:
        if not include_market_fields:
            return {
                "shares_outstanding": FieldValue.missing(SOURCE_NAME, fetched_at),
                "eps": FieldValue.missing(SOURCE_NAME, fetched_at),
                "market_price": FieldValue.missing(SOURCE_NAME, fetched_at),
                "market_cap": FieldValue.missing(SOURCE_NAME, fetched_at),
            }
        return {
            "shares_outstanding": self._info_value(
                (fast_info, info),
                ("shares", "sharesOutstanding", "impliedSharesOutstanding"),
                fetched_at,
            ),
            "eps": self._info_value(
                (info,),
                ("trailingEps", "epsTrailingTwelveMonths", "forwardEps"),
                fetched_at,
            ),
            "market_price": self._info_value(
                (fast_info, info),
                (
                    "last_price",
                    "lastPrice",
                    "currentPrice",
                    "regularMarketPrice",
                    "previousClose",
                ),
                fetched_at,
            ),
            "market_cap": self._info_value(
                (fast_info, info),
                ("market_cap", "marketCap"),
                fetched_at,
            ),
        }

    def _statement_value(
        self,
        statement: Any,
        row_names: Iterable[str],
        column: Any,
        fetched_at,
    ) -> FieldValue:
        if statement is None or getattr(statement, "empty", True) or column not in statement.columns:
            return FieldValue.missing(SOURCE_NAME, fetched_at)
        for row_name in row_names:
            try:
                if row_name not in statement.index:
                    continue
                value = statement.loc[row_name, column]
            except Exception:
                continue
            value = self._first_numeric(value)
            if value is not None:
                return FieldValue.present(value, SOURCE_NAME, fetched_at)
        return FieldValue.missing(SOURCE_NAME, fetched_at)

    def _info_value(
        self,
        mappings: Iterable[dict[str, Any]],
        keys: Iterable[str],
        fetched_at,
    ) -> FieldValue:
        for mapping in mappings:
            for key in keys:
                value = self._mapping_get(mapping, key)
                numeric = self._coerce_number(value)
                if numeric is not None:
                    return FieldValue.present(numeric, SOURCE_NAME, fetched_at)
        return FieldValue.missing(SOURCE_NAME, fetched_at)

    def _statement_columns(self, *statements: Any) -> list[Any]:
        columns_by_date: dict[date, Any] = {}
        for statement in statements:
            if statement is None or getattr(statement, "empty", True):
                continue
            for column in statement.columns:
                column_date = self._column_date(column)
                if column_date is None:
                    continue
                columns_by_date.setdefault(column_date, column)
        return [
            columns_by_date[column_date]
            for column_date in sorted(columns_by_date, reverse=True)
        ]

    def _column_date(self, column: Any) -> date | None:
        try:
            return column.date()
        except AttributeError:
            if isinstance(column, date):
                return column
        return None

    def _first_numeric(self, value: Any) -> float | None:
        numeric = self._coerce_number(value)
        if numeric is not None:
            return numeric
        try:
            iterator = iter(value)
        except TypeError:
            return None
        for nested in iterator:
            numeric = self._coerce_number(nested)
            if numeric is not None:
                return numeric
        return None

    def _first_numeric_from_series(self, series: Any) -> float | None:
        try:
            ordered_series = series.sort_index(ascending=False)
        except Exception:
            ordered_series = series
        for value in ordered_series:
            numeric = self._coerce_number(value)
            if numeric is not None:
                return numeric
        return None

    def _safe_dict(self, maybe_mapping: Any) -> dict[str, Any]:
        if maybe_mapping is None:
            return {}
        try:
            return dict(maybe_mapping)
        except Exception:
            return {}

    def _first_present(
        self,
        primary: dict[str, Any],
        secondary: dict[str, Any],
        keys: Iterable[str],
    ) -> Any:
        for mapping in (primary, secondary):
            for key in keys:
                value = self._mapping_get(mapping, key)
                if value not in (None, ""):
                    return value
        return None

    def _mapping_get(self, mapping: dict[str, Any], key: str) -> Any:
        try:
            return mapping.get(key)
        except AttributeError:
            try:
                return mapping[key]
            except Exception:
                return None

    def _coerce_number(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            if value != value:
                return None
        except Exception:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
