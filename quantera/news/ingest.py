"""Fetch, whitelist, de-duplicate, normalize, and cache company news."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from quantera import config
from quantera.cache import cache_get, cache_set
from quantera.news.base import IngestedNews, NewsItem, NewsSource
from quantera.news.finnhub_source import FinnhubNewsSource
from quantera.news.whitelist import is_whitelisted


def ingest_news(
    ticker: str,
    window_days: int = config.NEWS_WINDOW_DAYS,
    *,
    source: NewsSource | None = None,
    until: date | datetime | None = None,
    use_cache: bool = True,
) -> IngestedNews:
    """Return whitelisted, de-duplicated news plus ingestion counts."""

    symbol = ticker.upper()
    until_date = _coerce_date(until) if until is not None else datetime.now(timezone.utc).date()
    since_date = until_date - timedelta(days=window_days)
    key = f"news:{symbol}:{since_date.isoformat()}:{until_date.isoformat()}"

    if use_cache:
        cached = cache_get(key)
        if cached is not None:
            return _safe_cached_result(IngestedNews.model_validate(cached))

    news_source = source or FinnhubNewsSource()
    fetched_items = news_source.get_company_news(symbol, since_date, until_date)
    items_considered = len(fetched_items)
    whitelisted_items = [item for item in fetched_items if is_whitelisted(item)]
    deduped_items = _dedupe(whitelisted_items)
    sorted_items = sorted(deduped_items, key=lambda item: item.published_at, reverse=True)

    result = IngestedNews(
        ticker=symbol,
        since=since_date,
        until=until_date,
        items=sorted_items,
        items_considered=items_considered,
        items_after_whitelist=len(whitelisted_items),
    )
    if use_cache:
        cache_set(key, result.model_dump(mode="json"), config.NEWS_TTL_SECONDS)
    return result


def _safe_cached_result(result: IngestedNews) -> IngestedNews:
    whitelisted_items = [item for item in result.items if is_whitelisted(item)]
    deduped_items = _dedupe(whitelisted_items)
    sorted_items = sorted(deduped_items, key=lambda item: item.published_at, reverse=True)
    if len(sorted_items) == len(result.items):
        return result
    return IngestedNews(
        ticker=result.ticker,
        since=result.since,
        until=result.until,
        items=sorted_items,
        items_considered=result.items_considered,
        items_after_whitelist=len(sorted_items),
    )


def _dedupe(items: list[NewsItem]) -> list[NewsItem]:
    seen_urls: set[str] = set()
    seen_headlines: list[str] = []
    deduped: list[NewsItem] = []
    for item in sorted(items, key=lambda news_item: news_item.published_at, reverse=True):
        normalized_url = _normalize_url(item.source_url)
        normalized_headline = _normalize_headline(item.headline)
        if normalized_url and normalized_url in seen_urls:
            continue
        if _near_duplicate_headline(normalized_headline, seen_headlines):
            continue
        if normalized_url:
            seen_urls.add(normalized_url)
        if normalized_headline:
            seen_headlines.append(normalized_headline)
        deduped.append(item)
    return deduped


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    query = urlencode(
        [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=False)
            if not key.lower().startswith("utm_")
        ],
        doseq=True,
    )
    netloc = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), netloc, path, "", query, ""))


def _normalize_headline(headline: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", headline.lower()).strip()


def _near_duplicate_headline(headline: str, seen_headlines: list[str]) -> bool:
    if not headline:
        return False
    for seen in seen_headlines:
        if headline == seen:
            return True
        if SequenceMatcher(None, headline, seen).ratio() >= 0.92:
            return True
    return False


def _coerce_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value
