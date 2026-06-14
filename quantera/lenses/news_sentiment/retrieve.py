"""Simple local retrieval over already-whitelisted company news items."""

from __future__ import annotations

import re
from datetime import timezone

from quantera import config
from quantera.news.base import NewsItem


def retrieve_relevant_news(
    items: list[NewsItem],
    ticker: str,
    *,
    company_name: str | None = None,
    top_n: int = config.NEWS_TOP_N,
) -> list[NewsItem]:
    """Rank by recency, optional source relevance, and ticker/company keyword match."""

    symbol = ticker.upper()
    scored = [
        (_score_item(item, symbol, company_name), item.published_at, item)
        for item in items
    ]
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return [item for _, _, item in scored[:top_n]]


def _score_item(item: NewsItem, ticker: str, company_name: str | None) -> float:
    text = f"{item.headline} {item.summary_text}".lower()
    score = _recency_score(item)
    score += _source_relevance(item)
    score += _keyword_score(text, ticker, company_name)
    return score


def _recency_score(item: NewsItem) -> float:
    published_at = item.published_at
    retrieved_at = item.retrieved_at
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    if retrieved_at.tzinfo is None:
        retrieved_at = retrieved_at.replace(tzinfo=timezone.utc)
    age_days = max((retrieved_at - published_at).total_seconds() / 86400, 0)
    return max(0.0, 1.0 - min(age_days, 30) / 30)


def _source_relevance(item: NewsItem) -> float:
    if item.raw_relevance is None:
        return 0.0
    return min(float(item.raw_relevance), 1.0)


def _keyword_score(text: str, ticker: str, company_name: str | None) -> float:
    score = 0.0
    if re.search(rf"\b{re.escape(ticker.lower())}\b", text):
        score += 1.0
    if company_name:
        company_words = [
            word
            for word in re.findall(r"[a-z0-9]+", company_name.lower())
            if len(word) > 2
        ]
        if company_words:
            matches = sum(1 for word in company_words if re.search(rf"\b{re.escape(word)}\b", text))
            score += min(matches / len(company_words), 1.0)
    return score
