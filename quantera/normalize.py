"""Pure normalization for source-mapped data."""

from __future__ import annotations

from datetime import date

from quantera import config
from quantera.models import FieldValue, Financials, FinancialsByPeriod, PriceBar, PriceHistory


# yfinance statement, market-cap, and price values are already reported in absolute
# currency units. Future adapters that report statement values in thousands/millions
# can be registered here without changing the downstream contract.
SOURCE_MONETARY_MULTIPLIERS: dict[str, float] = {
    "yfinance": 1.0,
}

MONETARY_FIELDS = (
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
    "operating_cash_flow",
    "free_cash_flow",
    "market_cap",
)

NON_NEGATIVE_FIELDS = (
    "total_assets",
    "total_liabilities",
    "total_debt",
    "cash_and_equivalents",
    "current_assets",
    "current_liabilities",
    "shares_outstanding",
    "market_cap",
)

POSITIVE_FIELDS = (
    "shares_outstanding",
    "market_price",
)


def normalize_financials(raw: Financials) -> Financials:
    normalized = raw.model_copy(deep=True)
    warnings = list(normalized.warnings)
    multiplier = SOURCE_MONETARY_MULTIPLIERS.get(normalized.source, 1.0)

    for field_name in MONETARY_FIELDS:
        field_value = getattr(normalized, field_name)
        setattr(normalized, field_name, _scale_field_value(field_value, multiplier))

    for field_name in Financials.LINE_ITEM_FIELDS:
        field_value = getattr(normalized, field_name)
        if not field_value.is_present and field_value.value is not None:
            setattr(
                normalized,
                field_name,
                FieldValue.missing(field_value.source, field_value.as_of),
            )

    warnings.extend(_sanity_warnings(normalized))
    normalized.warnings = _dedupe_preserve_order(warnings)
    return normalized


def normalize_financials_history(raw: FinancialsByPeriod) -> FinancialsByPeriod:
    return raw.model_copy(
        update={
            "periods": [
                normalize_financials(financials)
                for financials in raw.periods
            ]
        }
    )


def normalize_price_history(raw: PriceHistory) -> PriceHistory:
    by_date: dict[date, PriceBar] = {}
    for bar in raw.bars:
        if getattr(bar, "close", None) is None or getattr(bar, "adj_close", None) is None:
            continue
        by_date[bar.date] = bar
    return raw.model_copy(update={"bars": [by_date[key] for key in sorted(by_date)]})


def _scale_field_value(field_value: FieldValue, multiplier: float) -> FieldValue:
    if not field_value.is_present:
        return field_value
    if multiplier == 1.0:
        return field_value
    return field_value.model_copy(update={"value": field_value.value * multiplier})


def _sanity_warnings(financials: Financials) -> list[str]:
    warnings: list[str] = []
    for field_name in NON_NEGATIVE_FIELDS:
        field_value = getattr(financials, field_name)
        if field_value.is_present and field_value.value is not None and field_value.value < 0:
            warnings.append(f"{field_name} is negative")
    for field_name in POSITIVE_FIELDS:
        field_value = getattr(financials, field_name)
        if field_value.is_present and field_value.value is not None and field_value.value <= 0:
            warnings.append(f"{field_name} must be positive")

    assets = financials.total_assets
    liabilities = financials.total_liabilities
    equity = financials.total_equity
    if assets.is_present and liabilities.is_present and equity.is_present:
        assert assets.value is not None
        assert liabilities.value is not None
        assert equity.value is not None
        expected_assets = liabilities.value + equity.value
        denominator = max(abs(assets.value), 1.0)
        relative_gap = abs(assets.value - expected_assets) / denominator
        if relative_gap > config.VALUE_TOLERANCE:
            warnings.append("total_assets does not approximately equal total_liabilities + total_equity")
    return warnings


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output
