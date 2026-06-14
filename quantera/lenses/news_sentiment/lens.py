"""Orchestration for the Phase 3 news sentiment lens."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from quantera import config
from quantera.lenses.news_sentiment import global_links, retrieve, sentiment, summarize
from quantera.llm.base import LLMClient
from quantera.models_news import NewsSentimentResult, NewsWindow, OverallTone, SourceReference
from quantera.news.base import NewsError, NewsSource
from quantera.news.finnhub_source import FinnhubNewsSource
from quantera.news.ingest import ingest_news


class NewsSentimentLens:
    """Analyze whitelisted company-news tone with strict provenance guardrails."""

    def __init__(
        self,
        source: NewsSource | None = None,
        *,
        use_cache: bool = True,
        llm_client: LLMClient | None = None,
    ):
        self.source = source or FinnhubNewsSource()
        self.use_cache = use_cache
        self.llm_client = llm_client

    def analyze(
        self,
        ticker: str,
        window_days: int = config.NEWS_WINDOW_DAYS,
        with_summary: bool = True,
    ) -> NewsSentimentResult:
        symbol = ticker.upper()
        try:
            ingested = ingest_news(
                symbol,
                window_days,
                source=self.source,
                use_cache=self.use_cache,
            )
        except NewsError:
            return self._empty_result(symbol, window_days, with_summary)

        retrieved_items = retrieve.retrieve_relevant_news(
            ingested.items,
            symbol,
            top_n=config.NEWS_TOP_N,
        )
        item_sentiments = sentiment.score_item_sentiments(
            retrieved_items,
            llm_client=self.llm_client,
        )
        proposed_global_links = global_links.propose_global_links(
            retrieved_items,
            llm_client=self.llm_client,
        )
        overall_tone = summarize.compute_overall_tone(item_sentiments)
        window = NewsWindow(since=ingested.since, until=ingested.until)
        summary_text = None
        if with_summary:
            summary_text = summarize.generate_summary(
                symbol,
                window,
                retrieved_items,
                item_sentiments,
                overall_tone,
                proposed_global_links,
                llm_client=self.llm_client,
            )

        return NewsSentimentResult(
            ticker=symbol,
            window=window,
            item_sentiments=item_sentiments,
            overall_tone=overall_tone,
            global_links=proposed_global_links,
            summary=summary_text,
            sources=_source_references(retrieved_items),
            generated_at=datetime.now(timezone.utc),
            items_considered=ingested.items_considered,
            items_after_whitelist=ingested.items_after_whitelist,
        )

    def _empty_result(
        self,
        symbol: str,
        window_days: int,
        with_summary: bool,
    ) -> NewsSentimentResult:
        until = datetime.now(timezone.utc).date()
        window = NewsWindow(since=until - timedelta(days=window_days), until=until)
        summary_text = None
        if with_summary:
            summary_text = summarize.render_template_summary(
                symbol,
                window,
                [],
                [],
                OverallTone.NO_DATA,
                [],
            )
        return NewsSentimentResult(
            ticker=symbol,
            window=window,
            item_sentiments=[],
            overall_tone=OverallTone.NO_DATA,
            global_links=[],
            summary=summary_text,
            sources=[],
            generated_at=datetime.now(timezone.utc),
            items_considered=0,
            items_after_whitelist=0,
        )


def _source_references(items: list) -> list[SourceReference]:
    references: list[SourceReference] = []
    seen_urls: set[str] = set()
    for item in items:
        if item.source_url in seen_urls:
            continue
        seen_urls.add(item.source_url)
        references.append(
            SourceReference(
                name=item.source_name,
                url=item.source_url,
                published_at=item.published_at,
            )
        )
    return references
