"""Finnhub-backed company news adapter.

This is intentionally the only production module that makes Finnhub news HTTP
requests. Downstream code consumes the abstract NewsSource interface instead.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from quantera import config
from quantera.cache import cache_get, cache_set
from quantera.models import utc_now
from quantera.news.base import NewsError, NewsItem, NewsSource


SOURCE_NAME = "finnhub"
BASE_URL = "https://finnhub.io/api/v1/company-news"
PEERS_URL = "https://finnhub.io/api/v1/stock/peers"
TIMEOUT_SECONDS = 15


class FinnhubNewsSource(NewsSource):
    """Fetch company-tagged news from Finnhub and map it into NewsItem objects."""

    def __init__(self, api_key: str | None = None, timeout_seconds: int = TIMEOUT_SECONDS):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def get_peers(self, ticker: str) -> list[str]:
        """Return company peers from Finnhub, or an empty list if unavailable."""

        return get_peers(
            ticker,
            api_key=self.api_key,
            timeout_seconds=self.timeout_seconds,
        )

    def get_company_news(
        self,
        ticker: str,
        since: date,
        until: date,
    ) -> list[NewsItem]:
        symbol = ticker.upper()
        api_key = self.api_key or os.getenv(config.NEWS_API_KEY_ENV)
        if not api_key:
            raise NewsError(symbol, f"{config.NEWS_API_KEY_ENV} is not set")

        retrieved_at = utc_now()
        params = urlencode(
            {
                "symbol": symbol,
                "from": since.isoformat(),
                "to": until.isoformat(),
                "token": api_key,
            }
        )
        request = Request(f"{BASE_URL}?{params}", headers={"Accept": "application/json"})

        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if status >= 400:
                    raise NewsError(symbol, f"Finnhub returned HTTP {status}")
                payload = json.loads(response.read().decode("utf-8"))
        except NewsError:
            raise
        except HTTPError as exc:
            raise NewsError(symbol, f"Finnhub returned HTTP {exc.code}", exc) from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise NewsError(symbol, "Failed to fetch Finnhub company news", exc) from exc

        if isinstance(payload, dict) and payload.get("error"):
            raise NewsError(symbol, str(payload["error"]))
        if not isinstance(payload, list):
            raise NewsError(symbol, "Finnhub returned an unexpected news payload")

        items: list[NewsItem] = []
        for raw_item in payload:
            if not isinstance(raw_item, dict):
                continue
            item = self._map_item(symbol, raw_item, retrieved_at)
            if item is not None:
                items.append(item)
        return items

    def _map_item(
        self,
        symbol: str,
        raw_item: dict[str, Any],
        retrieved_at: datetime,
    ) -> NewsItem | None:
        headline = _clean_text(raw_item.get("headline"))
        source_url = _clean_text(raw_item.get("url"))
        source_name = _clean_text(raw_item.get("source"))
        published_at = _published_at(raw_item.get("datetime"))
        if not headline or not source_url or not source_name or published_at is None:
            return None

        raw_id = raw_item.get("id")
        item_id = f"finnhub:{raw_id}" if raw_id not in (None, "") else _fallback_id(
            symbol,
            headline,
            source_url,
            published_at,
        )
        return NewsItem(
            id=str(item_id),
            ticker=symbol,
            headline=headline,
            summary_text=_clean_text(raw_item.get("summary")),
            source_name=source_name,
            source_url=source_url,
            published_at=published_at,
            retrieved_at=retrieved_at,
            raw_relevance=_coerce_relevance(raw_item),
        )


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _published_at(value: Any) -> datetime | None:
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _coerce_relevance(raw_item: dict[str, Any]) -> float | None:
    for key in ("relevance", "score", "sentimentScore"):
        try:
            value = raw_item.get(key)
        except AttributeError:
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if numeric >= 0:
            return numeric
    return None


def _fallback_id(
    symbol: str,
    headline: str,
    source_url: str,
    published_at: datetime,
) -> str:
    digest = hashlib.sha256(
        f"{symbol}|{headline}|{source_url}|{published_at.isoformat()}".encode("utf-8")
    ).hexdigest()[:16]
    return f"finnhub:{digest}"


def get_peers(
    ticker: str,
    *,
    api_key: str | None = None,
    timeout_seconds: int = TIMEOUT_SECONDS,
) -> list[str]:
    """Fetch Finnhub company peers with a long TTL cache.

    Peers are external reference data. If Finnhub is unavailable, the API key is
    missing, or the payload is malformed, return an empty list instead of making
    up peer relationships.
    """

    symbol = ticker.upper()
    key = f"peers:{symbol}"
    cached = cache_get(key)
    if cached is not None:
        peers = cached.get("peers")
        if isinstance(peers, list):
            return [peer for peer in peers if isinstance(peer, str)]

    token = api_key or os.getenv(config.NEWS_API_KEY_ENV)
    if not token:
        return []

    params = urlencode({"symbol": symbol, "token": token})
    request = Request(f"{PEERS_URL}?{params}", headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", 200)
            if status >= 400:
                return []
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []

    if not isinstance(payload, list):
        return []

    peers = _clean_peers(symbol, payload)
    cache_set(key, {"peers": peers}, config.PEERS_TTL_SECONDS)
    return peers


def _clean_peers(symbol: str, payload: list[Any]) -> list[str]:
    peers: list[str] = []
    seen: set[str] = {symbol}
    for value in payload:
        peer = _clean_text(value).upper()
        if not peer or not peer.isalnum() or peer in seen:
            continue
        seen.add(peer)
        peers.append(peer)
    return peers
