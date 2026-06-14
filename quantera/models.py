"""Pydantic data contract for Phase 0."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FieldValue(BaseModel):
    """A single raw numeric figure with provenance."""

    value: float | None
    is_present: bool
    source: str
    as_of: datetime

    @model_validator(mode="after")
    def _missing_is_explicit(self) -> "FieldValue":
        if self.value is None and self.is_present:
            raise ValueError("FieldValue with value=None must set is_present=False")
        if self.value is not None and not self.is_present:
            raise ValueError("FieldValue with is_present=False must have value=None")
        return self

    @classmethod
    def present(cls, value: float, source: str, as_of: datetime) -> "FieldValue":
        return cls(value=float(value), is_present=True, source=source, as_of=as_of)

    @classmethod
    def missing(cls, source: str, as_of: datetime) -> "FieldValue":
        return cls(value=None, is_present=False, source=source, as_of=as_of)


class Financials(BaseModel):
    """Raw company financial facts in the fixed internal shape."""

    model_config = ConfigDict(validate_assignment=True)

    LINE_ITEM_FIELDS: ClassVar[tuple[str, ...]] = (
        "revenue",
        "net_income",
        "gross_profit",
        "operating_income",
        "total_assets",
        "total_liabilities",
        "total_equity",
        "total_debt",
        "cash_and_equivalents",
        "current_assets",
        "current_liabilities",
        "shares_outstanding",
        "eps",
        "operating_cash_flow",
        "free_cash_flow",
        "market_price",
        "market_cap",
    )

    revenue: FieldValue
    net_income: FieldValue
    gross_profit: FieldValue
    operating_income: FieldValue
    total_assets: FieldValue
    total_liabilities: FieldValue
    total_equity: FieldValue
    total_debt: FieldValue
    cash_and_equivalents: FieldValue
    current_assets: FieldValue
    current_liabilities: FieldValue
    shares_outstanding: FieldValue
    eps: FieldValue
    operating_cash_flow: FieldValue
    free_cash_flow: FieldValue
    market_price: FieldValue
    market_cap: FieldValue

    ticker: str
    company_name: str | None
    exchange: str | None
    sector: str | None
    industry: str | None
    fiscal_period: str | None
    report_date: date | None
    currency: str | None
    source: str
    fetched_at: datetime
    warnings: list[str] = Field(default_factory=list)

    def missing_fields(self) -> list[str]:
        return [
            field_name
            for field_name in self.LINE_ITEM_FIELDS
            if not getattr(self, field_name).is_present
        ]


class FinancialsByPeriod(BaseModel):
    """Annual financial facts across available fiscal periods."""

    ticker: str
    periods: list[Financials] = Field(default_factory=list)

    def latest(self) -> Financials | None:
        if not self.periods:
            return None
        return max(
            self.periods,
            key=lambda financials: (
                financials.report_date or date.min,
                financials.fiscal_period or "",
            ),
        )

    def get_period(self, fiscal_period: str) -> Financials | None:
        for financials in self.periods:
            if financials.fiscal_period == fiscal_period:
                return financials
        return None

    def available_periods(self) -> list[str]:
        return [
            f"{financials.fiscal_period or '-'} / {financials.report_date or '-'}"
            for financials in sorted(
                self.periods,
                key=lambda item: (item.report_date or date.min, item.fiscal_period or ""),
                reverse=True,
            )
        ]


class PriceBar(BaseModel):
    """One daily OHLCV bar.

    The contract is numeric. The normalizer defensively handles source objects
    constructed with null close values so they can be dropped before downstream use.
    """

    date: date
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: int


class PriceHistory(BaseModel):
    ticker: str
    bars: list[PriceBar]
    source: str
    fetched_at: datetime


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
