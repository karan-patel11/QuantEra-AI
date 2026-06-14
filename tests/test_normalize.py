from __future__ import annotations

from datetime import date

from quantera.models import PriceBar, PriceHistory
from quantera.normalize import normalize_financials, normalize_price_history
from tests.conftest import sample_financials


def test_unit_conversion_uses_registered_source_multiplier(fetched_at, monkeypatch):
    monkeypatch.setitem(
        __import__("quantera.normalize", fromlist=["SOURCE_MONETARY_MULTIPLIERS"]).SOURCE_MONETARY_MULTIPLIERS,
        "mock_thousands",
        1000.0,
    )
    raw = sample_financials(
        fetched_at,
        source="mock_thousands",
        overrides={"revenue": 123.0, "market_price": 42.0},
    )

    normalized = normalize_financials(raw)

    assert normalized.revenue.value == 123_000.0
    assert normalized.market_price.value == 42.0


def test_missing_values_stay_missing_and_never_become_zero(fetched_at):
    raw = sample_financials(fetched_at, overrides={"free_cash_flow": None})

    normalized = normalize_financials(raw)

    assert normalized.free_cash_flow.value is None
    assert normalized.free_cash_flow.is_present is False


def test_accounting_identity_warning_fires(fetched_at):
    raw = sample_financials(
        fetched_at,
        overrides={
            "total_assets": 1000.0,
            "total_liabilities": 400.0,
            "total_equity": 400.0,
        },
    )

    normalized = normalize_financials(raw)

    assert "total_assets does not approximately equal total_liabilities + total_equity" in normalized.warnings


def test_price_bars_are_deduplicated_ordered_and_missing_close_dropped(fetched_at):
    raw = PriceHistory(
        ticker="MOCK",
        source="mock",
        fetched_at=fetched_at,
        bars=[
            PriceBar(
                date=date(2025, 1, 3),
                open=12,
                high=13,
                low=11,
                close=12.5,
                adj_close=12.4,
                volume=300,
            ),
            PriceBar(
                date=date(2025, 1, 2),
                open=10,
                high=11,
                low=9,
                close=10.5,
                adj_close=10.4,
                volume=100,
            ),
            PriceBar(
                date=date(2025, 1, 3),
                open=13,
                high=14,
                low=12,
                close=13.5,
                adj_close=13.4,
                volume=400,
            ),
            PriceBar.model_construct(
                date=date(2025, 1, 4),
                open=14.0,
                high=15.0,
                low=13.0,
                close=None,
                adj_close=14.0,
                volume=500,
            ),
        ],
    )

    normalized = normalize_price_history(raw)

    assert [bar.date for bar in normalized.bars] == [date(2025, 1, 2), date(2025, 1, 3)]
    assert normalized.bars[-1].close == 13.5
