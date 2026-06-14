from __future__ import annotations

from datetime import date, datetime, timezone

from quantera.models_fundamentals import (
    CategoryResult,
    FundamentalsResult,
    Metric,
    MetricStatus,
    Verdict,
    VerdictLevel,
)
from quantera.models_news import (
    GlobalConfidence,
    GlobalLink,
    ItemSentiment,
    NewsSentimentResult,
    NewsWindow,
    OverallTone,
    SentimentLabel,
    SourceReference,
)
from quantera.models_technicals import (
    Indicator,
    IndicatorStatus,
    TechnicalVerdict,
    TechnicalsResult,
    VerdictLevel as TechnicalVerdictLevel,
)
from quantera.synthesis.models_synthesis import SynthesisResult


NOW = datetime(2026, 1, 5, tzinfo=timezone.utc)


def metric(
    name: str,
    display_name: str,
    value: float | None,
    status: MetricStatus = MetricStatus.OK,
) -> Metric:
    return Metric(
        name=name,
        display_name=display_name,
        value=value,
        status=status,
        inputs_used=["mock"],
        source="mock",
        as_of=NOW,
        note="missing mock input" if status is MetricStatus.UNAVAILABLE else None,
    )


def fund_verdict(
    metric_name: str,
    level: VerdictLevel,
    rationale: str | None = None,
) -> Verdict:
    return Verdict(
        metric_name=metric_name,
        level=level,
        rationale=rationale or f"{metric_name} is {level.value}",
        comparison_basis="mock_basis",
    )


def fundamentals_result(
    *,
    valuation_level: VerdictLevel = VerdictLevel.STRONG,
    growth_level: VerdictLevel = VerdictLevel.NEUTRAL,
    sector: str | None = "Technology",
) -> FundamentalsResult:
    growth_status = (
        MetricStatus.UNAVAILABLE
        if growth_level is VerdictLevel.UNAVAILABLE
        else MetricStatus.OK
    )
    return FundamentalsResult(
        ticker="AAPL",
        company_name="Apple Inc.",
        sector=sector,
        categories=[
            CategoryResult(
                category="valuation",
                metrics=[metric("pe_ratio", "P/E Ratio", 18.0)],
                verdicts=[fund_verdict("pe_ratio", valuation_level)],
            ),
            CategoryResult(
                category="growth",
                metrics=[
                    metric(
                        "revenue_growth_yoy",
                        "Revenue Growth YoY",
                        None if growth_status is MetricStatus.UNAVAILABLE else 0.12,
                        growth_status,
                    )
                ],
                verdicts=[
                    fund_verdict(
                        "revenue_growth_yoy",
                        growth_level,
                        "Revenue growth data unavailable"
                        if growth_level is VerdictLevel.UNAVAILABLE
                        else None,
                    )
                ],
            ),
        ],
        generated_at=NOW,
        data_as_of=NOW,
    )


def technicals_result(
    *,
    trend_level: TechnicalVerdictLevel = TechnicalVerdictLevel.ABOVE,
) -> TechnicalsResult:
    return TechnicalsResult(
        ticker="AAPL",
        indicators=[
            Indicator(
                name="price_vs_sma_200",
                display_name="Price vs 200-day SMA",
                value=0.05 if trend_level is not TechnicalVerdictLevel.UNAVAILABLE else None,
                status=IndicatorStatus.OK
                if trend_level is not TechnicalVerdictLevel.UNAVAILABLE
                else IndicatorStatus.UNAVAILABLE,
                window=200,
                inputs_used=["adj_close"],
                as_of=date(2026, 1, 5),
                source="mock",
            )
        ],
        verdicts=[
            TechnicalVerdict(
                indicator_name="price_vs_sma_200",
                level=trend_level,
                rationale=f"price_vs_sma_200 is {trend_level.value}",
                comparison_basis="mock_basis",
            )
        ],
        price_as_of=date(2026, 1, 5),
        generated_at=NOW,
        bars_used=220,
    )


def news_result(
    *,
    tone: OverallTone = OverallTone.NEGATIVE,
    include_item: bool = True,
    include_global_link: bool = True,
) -> NewsSentimentResult:
    sentiments = []
    sources = []
    links = []
    if include_item:
        sentiments = [
            ItemSentiment(
                news_item_id="news-1",
                headline="Apple profit outlook improved",
                source_name="Reuters",
                source_url="https://www.reuters.com/markets/apple-profit-outlook",
                label=SentimentLabel.POSITIVE,
                confidence=0.81,
                rationale="The text highlights an improved outlook.",
                evidence_span="profit outlook improved",
            )
        ]
        sources = [
            SourceReference(
                name="Reuters",
                url="https://www.reuters.com/markets/apple-profit-outlook",
                published_at=NOW,
            )
        ]
    if include_global_link:
        links = [
            GlobalLink(
                claim="Improved services demand may affect the company context.",
                confidence=GlobalConfidence.MEDIUM,
                supporting_item_ids=["news-1"],
                caveat="Based on a limited item set.",
            )
        ]
    return NewsSentimentResult(
        ticker="AAPL",
        window=NewsWindow(since=date(2026, 1, 1), until=date(2026, 1, 5)),
        item_sentiments=sentiments,
        overall_tone=tone,
        global_links=links,
        sources=sources,
        generated_at=NOW,
        items_considered=len(sentiments),
        items_after_whitelist=len(sentiments),
    )


def synthesis_result(
    *,
    fundamentals: FundamentalsResult | None = None,
    technicals: TechnicalsResult | None = None,
    news: NewsSentimentResult | None = None,
    narrative: str | None = None,
    narrative_status: str | None = None,
) -> SynthesisResult:
    news = news if news is not None else news_result()
    return SynthesisResult(
        ticker="AAPL",
        company_name="Apple Inc.",
        fundamentals=fundamentals if fundamentals is not None else fundamentals_result(),
        technicals=technicals if technicals is not None else technicals_result(),
        news=news,
        disagreements=[],
        narrative=narrative,
        narrative_status=narrative_status,
        sources=news.sources,
        generated_at=NOW,
        data_notes=[],
    )
