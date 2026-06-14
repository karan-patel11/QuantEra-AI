"""Editable allowlist for news sources that may enter the news sentiment lens.

The source gate is enforced before retrieval and before any LLM call. Edit the
domain and source-name defaults in quantera.config to adjust the allowlist.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from quantera import config
from quantera.news.base import NewsItem


def is_whitelisted(item: NewsItem) -> bool:
    """Return True only when the item's source name or URL is explicitly allowed."""

    domain = _registrable_domain(item.source_url)
    if any(_domain_matches(domain, allowed) for allowed in config.WHITELIST_SOURCE_DOMAINS):
        return True
    source_name = _normalize_name(item.source_name)
    return source_name in {_normalize_name(name) for name in config.WHITELIST_SOURCE_NAMES}


def _registrable_domain(url: str) -> str:
    parsed = urlparse(url)
    netloc = parsed.netloc or parsed.path.split("/", maxsplit=1)[0]
    netloc = netloc.lower().split("@")[-1].split(":")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _domain_matches(domain: str, allowed: str) -> bool:
    allowed_domain = allowed.lower().removeprefix("www.")
    return domain == allowed_domain or domain.endswith(f".{allowed_domain}")


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
