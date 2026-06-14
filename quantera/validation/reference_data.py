"""Human-entered reference facts for validation.

Sourcing rules for filling this template:
- Numbers must be copied from the company's actual SEC filing (10-K annual or
  10-Q quarterly) on SEC EDGAR (https://www.sec.gov/cgi-bin/browse-edgar), not
  from memory, summaries, market-data pages, or investor-relations landing pages.
- `source_url` must point to the specific filing document that was read, such as
  an EDGAR filing-index or document URL, not a generic IR homepage.
- Only use fiscal periods that have actually been filed. Do not use a period whose
  10-K or 10-Q would not yet exist as of the date of entry.
- Values are in absolute currency units. If the statement reports in millions,
  multiply by 1,000,000 before entering the value.
- Set `verified_by_human` to True only after the numbers have been entered from
  the filing and double-checked.
"""

from __future__ import annotations


REFERENCE_DATA = {
    "AAPL": {
        "fiscal_period": "FY2024",
        "report_date": "2024-09-28",
        "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/0000320193-24-000123-index.htm",
        "verified_by_human": True,
        "fields": {
            "revenue":      391_035_000_000,
            "net_income":    93_736_000_000,
            "total_assets": 364_980_000_000,
        },
    },
    "MSFT": {
        "fiscal_period": "FY2024",
        "report_date": "2024-06-30",
        "source_url": "https://www.sec.gov/Archives/edgar/data/789019/000095017024087843/0000950170-24-087843-index.htm",
        "verified_by_human": True,
        "fields": {
            "revenue":      245_122_000_000,
            "net_income":    88_136_000_000,
            "total_assets": 512_163_000_000,
        },
    },
    "JPM": {
        "fiscal_period": None,
        "report_date": None,
        "source_url": "",
        "verified_by_human": False,
        "fields": {
            "revenue": None,
            "net_income": None,
            "total_assets": None,
        },
    },
    "XOM": {
        "fiscal_period": "FY2024",
        "report_date": "2024-12-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/34088/000003408825000010/0000034088-25-000010-index.htm",
        "verified_by_human": True,
        "fields": {
            "revenue":      349_585_000_000,   # Total revenues (may mismatch if yfinance uses 339,247 M sales-only)
            "net_income":    33_680_000_000,
            "total_assets": 453_475_000_000,
        },
    },
    "JNJ": {
        "fiscal_period": "FY2024",
        "report_date": "2024-12-29",
        "source_url": "https://www.sec.gov/Archives/edgar/data/200406/000020040625000038/0000200406-25-000038-index.htm",
        "verified_by_human": True,
        "fields": {
            "revenue":       88_821_000_000,
            "net_income":    14_066_000_000,
            "total_assets": 180_104_000_000,
        },
    },
    "PG": {
        "fiscal_period": "FY2024",
        "report_date": "2024-06-30",
        "source_url": "https://www.sec.gov/Archives/edgar/data/80424/000008042424000083/0000080424-24-000083-index.htm",
        "verified_by_human": True,
        "fields": {
            "revenue":       84_039_000_000,
            "net_income":    14_879_000_000,
            "total_assets": 122_370_000_000,
        },
    },
    "CAT": {
        "fiscal_period": "FY2024",
        "report_date": "2024-12-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/18230/000001823025000008/0000018230-25-000008-index.htm",
        "verified_by_human": True,
        "fields": {
            "revenue":       64_809_000_000,
            "net_income":    10_792_000_000,
            "total_assets":  87_764_000_000,
        },
    },
    "KO": {
        "fiscal_period": "FY2024",
        "report_date": "2024-12-31",
        "source_url": "https://www.sec.gov/Archives/edgar/data/21344/000002134425000011/0000021344-25-000011-index.htm",
        "verified_by_human": True,
        "fields": {
            "revenue":       47_061_000_000,
            "net_income":    10_631_000_000,
            "total_assets": 100_549_000_000,
        },
    },
    "NVDA": {
        # NVIDIA's OWN fiscal 2024, ended 2024-01-28. yfinance's latest annual is
        # likely FY2025 (ended 2025-01-26). Expect PERIOD_MISMATCH unless the source
        # exposes this exact period.
        "fiscal_period": "FY2024",
        "report_date": "2024-01-28",
        "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/000104581024000029/0001045810-24-000029-index.htm",
        "verified_by_human": True,
        "fields": {
            "revenue":       60_922_000_000,
            "net_income":    29_760_000_000,
            "total_assets":  65_728_000_000,
        },
    },
    "BAC": {
        "fiscal_period": None,
        "report_date": None,
        "source_url": "",
        "verified_by_human": False,
        "fields": {
            "revenue": None,
            "net_income": None,
            "total_assets": None,
        },
    },
    "CVX": {
        "fiscal_period": None,
        "report_date": None,
        "source_url": "",
        "verified_by_human": False,
        "fields": {
            "revenue": None,
            "net_income": None,
            "total_assets": None,
        },
    },
    "UNH": {
        "fiscal_period": None,
        "report_date": None,
        "source_url": "",
        "verified_by_human": False,
        "fields": {
            "revenue": None,
            "net_income": None,
            "total_assets": None,
        },
    },
    "WMT": {
        "fiscal_period": None,
        "report_date": None,
        "source_url": "",
        "verified_by_human": False,
        "fields": {
            "revenue": None,
            "net_income": None,
            "total_assets": None,
        },
    },
    "DIS": {
        "fiscal_period": None,
        "report_date": None,
        "source_url": "",
        "verified_by_human": False,
        "fields": {
            "revenue": None,
            "net_income": None,
            "total_assets": None,
        },
    },
    "GE": {
        "fiscal_period": None,
        "report_date": None,
        "source_url": "",
        "verified_by_human": False,
        "fields": {
            "revenue": None,
            "net_income": None,
            "total_assets": None,
        },
    },
}
