"""Central configuration knobs for QuantEra."""

from __future__ import annotations

import os
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value is not None else default


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    return float(value) if value is not None else default


FUNDAMENTALS_TTL_SECONDS = _int_env("QUANTERA_FUNDAMENTALS_TTL_SECONDS", 86400)
PRICES_TTL_SECONDS = _int_env("QUANTERA_PRICES_TTL_SECONDS", 14400)
# LLM_PROVIDER selects the provider adapter in quantera.llm. Supported values:
# "groq" (default) and "anthropic".
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")
# Default Groq production model. Override with GROQ_MODEL when Groq changes
# model availability or when a larger/smaller instruct model is preferred.
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
# Anthropic remains available as an alternate swappable adapter.
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
NEWS_API_KEY_ENV = "NEWS_API_KEY"
NEWS_TTL_SECONDS = _int_env("QUANTERA_NEWS_TTL_SECONDS", 7200)
PEERS_TTL_SECONDS = _int_env("QUANTERA_PEERS_TTL_SECONDS", 604800)
NEWS_WINDOW_DAYS = _int_env("QUANTERA_NEWS_WINDOW_DAYS", 14)
NEWS_TOP_N = _int_env("QUANTERA_NEWS_TOP_N", 8)
PRICE_LOOKBACK_DAYS = _int_env("QUANTERA_PRICE_LOOKBACK_DAYS", 504)
VALUE_TOLERANCE = _float_env("QUANTERA_VALUE_TOLERANCE", 0.02)
FIELD_PASS_RATE = _float_env("QUANTERA_FIELD_PASS_RATE", 0.90)
CACHE_DIR = Path(os.getenv("QUANTERA_CACHE_DIR", ".cache"))

WHITELIST_SOURCE_DOMAINS = (
    "reuters.com",
    "bloomberg.com",
    "wsj.com",
    "cnbc.com",
    "marketwatch.com",
    "barrons.com",
    "ft.com",
    "apnews.com",
    "morningstar.com",
    "investors.com",
)

WHITELIST_SOURCE_NAMES = (
    "Reuters",
    "Bloomberg",
    "The Wall Street Journal",
    "Wall Street Journal",
    "CNBC",
    "MarketWatch",
    "Barron's",
    "Barrons",
    "Financial Times",
    "Associated Press",
    "AP News",
    "Morningstar",
    "Investor's Business Daily",
    "Dow Jones Newswires",
)

VALIDATION_TICKERS = [
    "AAPL",
    "MSFT",
    "JPM",
    "XOM",
    "JNJ",
    "PG",
    "CAT",
    "KO",
    "NVDA",
    "BAC",
    "CVX",
    "UNH",
    "WMT",
    "DIS",
    "GE",
]
