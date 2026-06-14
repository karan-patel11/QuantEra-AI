"""Human-fillable adjusted-close spot checks for price validation.

Keep this file intentionally small. Full price-series ground truth is too large
to maintain by hand, so Phase 2 validates sampled adjusted closes plus structural
sanity checks in the harness.
"""

from __future__ import annotations


PRICE_REFERENCE_DATA = {
    "AAPL": {
        "verified_by_human": False,
        "source_url": "",
        "adj_close_checks": [
            {
                "date": "2025-01-02",
                "expected_adj_close": None,
                "tolerance": 0.01,
            }
        ],
        "trading_day_count_checks": [
            {
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
                "expected_count": None,
            }
        ],
    },
    "MSFT": {
        "verified_by_human": False,
        "source_url": "",
        "adj_close_checks": [
            {
                "date": "2025-01-02",
                "expected_adj_close": None,
                "tolerance": 0.01,
            }
        ],
        "trading_day_count_checks": [
            {
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
                "expected_count": None,
            }
        ],
    },
}
