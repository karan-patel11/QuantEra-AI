from __future__ import annotations

import pytest

from quantera.models import FieldValue
from tests.conftest import sample_financials


def test_missing_field_is_explicit(fetched_at):
    field = FieldValue.missing("mock", fetched_at)

    assert field.value is None
    assert field.is_present is False


def test_missing_fields_returns_absent_line_items(fetched_at):
    financials = sample_financials(
        fetched_at,
        overrides={"revenue": None, "market_cap": None},
    )

    assert financials.missing_fields() == ["revenue", "market_cap"]


def test_none_value_cannot_be_marked_present(fetched_at):
    with pytest.raises(ValueError):
        FieldValue(value=None, is_present=True, source="mock", as_of=fetched_at)
