"""Phase 4 synthesis orchestration and deterministic disagreement rules."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from quantera.lenses.fundamentals import FundamentalsLens
from quantera.lenses.news_sentiment import NewsSentimentLens
from quantera.lenses.news_sentiment import explain as guardrails
from quantera.lenses.technicals import TechnicalsLens
from quantera.llm.base import LLMClient
from quantera.models_fundamentals import (
    FundamentalsResult,
    VerdictLevel as FundamentalsVerdictLevel,
)
from quantera.models_news import NewsSentimentResult, OverallTone, SourceReference
from quantera.models_technicals import (
    TechnicalsResult,
    VerdictLevel as TechnicalVerdictLevel,
)
from quantera.provider import DataProvider
from quantera.synthesis.models_synthesis import Disagreement, SynthesisResult


logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You write a short cross-lens research brief.

Rules:
- Use only the provided deterministic verdict summaries, news tone, sources, and disagreements.
- Do not compute, infer, or introduce numbers that are not present in the input.
- Do not create, remove, or soften disagreements; name the provided disagreements explicitly.
- Cite news sources only as markdown links using the exact provided source_name and source_url.
- Keep the tone neutral and research-focused. Do not make recommendations, price forecasts, or timing claims.
- End with this exact sentence: Research/education only, not financial advice.
"""


def synthesize(
    ticker: str,
    *,
    provider: DataProvider | None = None,
    fundamentals_lens: FundamentalsLens | None = None,
    technicals_lens: TechnicalsLens | None = None,
    news_lens: NewsSentimentLens | None = None,
    llm_client: LLMClient | None = None,
    with_narrative: bool = True,
) -> SynthesisResult:
    """Run the three lenses, detect disagreements in code, and narrate safely."""

    symbol = ticker.upper()
    provider = provider or DataProvider()
    fundamentals_lens = fundamentals_lens or FundamentalsLens(provider)
    technicals_lens = technicals_lens or TechnicalsLens(provider)
    news_lens = news_lens or NewsSentimentLens(llm_client=llm_client)

    data_notes: list[str] = []
    fundamentals = _run_fundamentals(symbol, fundamentals_lens, data_notes)
    technicals = _run_technicals(symbol, technicals_lens, data_notes)
    news = _run_news(symbol, news_lens, data_notes)

    data_notes.extend(_availability_notes(fundamentals, technicals, news))
    disagreements = detect_disagreements(fundamentals, technicals, news)
    company_name = (
        fundamentals.company_name
        if fundamentals is not None and fundamentals.company_name
        else symbol
    )
    sources = _dedupe_sources(news.sources if news is not None else [])

    result = SynthesisResult(
        ticker=symbol,
        company_name=company_name,
        fundamentals=fundamentals,
        technicals=technicals,
        news=news,
        disagreements=disagreements,
        narrative=None,
        sources=sources,
        generated_at=datetime.now(timezone.utc),
        data_notes=data_notes,
    )
    if with_narrative:
        result.narrative, result.narrative_status = generate_narrative_with_status(
            result,
            llm_client=llm_client,
        )
    return result


def detect_disagreements(
    fundamentals: FundamentalsResult | None,
    technicals: TechnicalsResult | None,
    news: NewsSentimentResult | None,
) -> list[Disagreement]:
    """Apply documented, deterministic cross-lens disagreement rules.

    Rule 1: fundamentals lean versus news tone. The fundamentals lean is the
    count of STRONG verdicts versus WEAK verdicts across available fundamental
    verdicts. A STRONG lean conflicts with NEGATIVE news tone; a WEAK lean
    conflicts with POSITIVE news tone.

    Rule 2: 200-day price trend versus news tone. The price_vs_sma_200 verdict
    is treated as the long-term technical trend state. ABOVE conflicts with
    NEGATIVE news tone; BELOW conflicts with POSITIVE news tone.

    Rule 3: valuation versus growth tension. Available valuation and growth
    category verdicts are separately leaned by STRONG versus WEAK counts. A
    STRONG lean in one category and WEAK lean in the other is surfaced as an
    internal fundamentals tension.
    """

    disagreements: list[Disagreement] = []
    news_tone = news.overall_tone if news is not None else None

    if fundamentals is not None and news_tone is not None:
        lean, basis = _fundamentals_lean(fundamentals)
        if lean == FundamentalsVerdictLevel.STRONG.value and news_tone is OverallTone.NEGATIVE:
            disagreements.append(
                Disagreement(
                    description="Fundamentals lean strong while recent news tone is negative.",
                    lens_a="fundamentals",
                    lens_b="news",
                    basis=f"{basis}; news overall_tone={news_tone.value}",
                )
            )
        if lean == FundamentalsVerdictLevel.WEAK.value and news_tone is OverallTone.POSITIVE:
            disagreements.append(
                Disagreement(
                    description="Fundamentals lean weak while recent news tone is positive.",
                    lens_a="fundamentals",
                    lens_b="news",
                    basis=f"{basis}; news overall_tone={news_tone.value}",
                )
            )

    if technicals is not None and news_tone is not None:
        trend_verdict = _technical_verdict(technicals, "price_vs_sma_200")
        if trend_verdict is not None:
            level = _enum_value(trend_verdict.level)
            if level == TechnicalVerdictLevel.ABOVE.value and news_tone is OverallTone.NEGATIVE:
                disagreements.append(
                    Disagreement(
                        description="The long-term price trend is above its 200-day SMA while recent news tone is negative.",
                        lens_a="technicals",
                        lens_b="news",
                        basis=(
                            f"price_vs_sma_200={level}: {trend_verdict.rationale}; "
                            f"news overall_tone={news_tone.value}"
                        ),
                    )
                )
            if level == TechnicalVerdictLevel.BELOW.value and news_tone is OverallTone.POSITIVE:
                disagreements.append(
                    Disagreement(
                        description="The long-term price trend is below its 200-day SMA while recent news tone is positive.",
                        lens_a="technicals",
                        lens_b="news",
                        basis=(
                            f"price_vs_sma_200={level}: {trend_verdict.rationale}; "
                            f"news overall_tone={news_tone.value}"
                        ),
                    )
                )

    if fundamentals is not None:
        valuation_lean, valuation_basis = _category_lean(fundamentals, "valuation")
        growth_lean, growth_basis = _category_lean(fundamentals, "growth")
        if (
            valuation_lean is not None
            and growth_lean is not None
            and {valuation_lean, growth_lean}
            == {FundamentalsVerdictLevel.STRONG.value, FundamentalsVerdictLevel.WEAK.value}
        ):
            disagreements.append(
                Disagreement(
                    description="Valuation and growth verdicts point in opposite directions.",
                    lens_a="fundamentals.valuation",
                    lens_b="fundamentals.growth",
                    basis=f"{valuation_basis}; {growth_basis}",
                )
            )

    return disagreements


def generate_narrative(
    result: SynthesisResult,
    *,
    llm_client: LLMClient | None = None,
) -> str:
    narrative, _ = generate_narrative_with_status(result, llm_client=llm_client)
    return narrative


def generate_narrative_with_status(
    result: SynthesisResult,
    *,
    llm_client: LLMClient | None = None,
) -> tuple[str, str]:
    payload = _narrative_payload(result)
    try:
        text = guardrails.call_llm(
            payload,
            SYSTEM_PROMPT,
            max_tokens=700,
            llm_client=llm_client,
        ).strip()
    except Exception as exc:
        logger.info("Falling back to deterministic synthesis narrative: %s", exc)
        return render_template_narrative(result), "template_fallback"

    if not _narrative_passes_guardrails(text, payload):
        logger.warning("Discarded synthesis narrative because it failed guardrails")
        return render_template_narrative(result), "template_fallback"
    return text, "llm_narrative"


def render_template_narrative(result: SynthesisResult) -> str:
    lines = [f"{result.ticker} cross-lens research brief."]
    if result.fundamentals is None:
        lines.append("Fundamentals lens: unavailable.")
    else:
        lean, basis = _fundamentals_lean(result.fundamentals)
        lines.append(f"Fundamentals lens: {lean or 'NEUTRAL'} ({basis}).")

    if result.technicals is None:
        lines.append("Technicals lens: unavailable.")
    else:
        trend = _technical_verdict(result.technicals, "price_vs_sma_200")
        if trend is None:
            lines.append("Technicals lens: long-term trend unavailable.")
        else:
            lines.append(
                f"Technicals lens: price_vs_sma_200={_enum_value(trend.level)} ({trend.rationale})."
            )

    if result.news is None:
        lines.append("News lens: unavailable.")
    else:
        source_fragment = _source_fragment(result.sources)
        lines.append(f"News lens: overall tone is {result.news.overall_tone.value}{source_fragment}.")

    if result.disagreements:
        disagreement_text = "; ".join(
            f"{item.description} Basis: {item.basis}" for item in result.disagreements
        )
        lines.append(f"Disagreements: {disagreement_text}.")
    else:
        lines.append("Disagreements: none detected by the configured rules.")

    lines.append("Research/education only, not financial advice.")
    return "\n".join(lines)


def _run_fundamentals(
    symbol: str,
    lens: FundamentalsLens,
    data_notes: list[str],
) -> FundamentalsResult | None:
    try:
        return lens.analyze(symbol, with_explanation=False)
    except Exception as exc:
        data_notes.append(f"Fundamentals lens skipped: {exc}")
        return None


def _run_technicals(
    symbol: str,
    lens: TechnicalsLens,
    data_notes: list[str],
) -> TechnicalsResult | None:
    try:
        return lens.analyze(symbol, with_explanation=False)
    except Exception as exc:
        data_notes.append(f"Technicals lens skipped: {exc}")
        return None


def _run_news(
    symbol: str,
    lens: NewsSentimentLens,
    data_notes: list[str],
) -> NewsSentimentResult | None:
    try:
        return lens.analyze(symbol, with_summary=False)
    except Exception as exc:
        data_notes.append(f"News lens skipped: {exc}")
        return None


def _availability_notes(
    fundamentals: FundamentalsResult | None,
    technicals: TechnicalsResult | None,
    news: NewsSentimentResult | None,
) -> list[str]:
    notes: list[str] = []
    if fundamentals is not None:
        for category in fundamentals.categories:
            metric_by_name = {metric.name: metric for metric in category.metrics}
            for verdict in category.verdicts:
                if _enum_value(verdict.level) == FundamentalsVerdictLevel.UNAVAILABLE.value:
                    metric = metric_by_name.get(verdict.metric_name)
                    label = metric.display_name if metric is not None else verdict.metric_name
                    notes.append(f"Fundamentals {category.category}/{label} unavailable: {verdict.rationale}")
    if technicals is not None:
        indicator_by_name = {indicator.name: indicator for indicator in technicals.indicators}
        for verdict in technicals.verdicts:
            if _enum_value(verdict.level) == TechnicalVerdictLevel.UNAVAILABLE.value:
                indicator = indicator_by_name.get(verdict.indicator_name)
                label = indicator.display_name if indicator is not None else verdict.indicator_name
                notes.append(f"Technicals {label} unavailable: {verdict.rationale}")
    if news is None:
        notes.append("News sentiment unavailable: lens did not return a result.")
    elif news.overall_tone is OverallTone.NO_DATA:
        notes.append("News sentiment unavailable: no usable whitelisted news in the configured window.")
    elif not news.item_sentiments:
        notes.append("News sentiment has no scored retrieved items.")
    return notes


def _fundamentals_lean(result: FundamentalsResult) -> tuple[str | None, str]:
    strong = 0
    weak = 0
    unavailable = 0
    for category in result.categories:
        for verdict in category.verdicts:
            level = _enum_value(verdict.level)
            if level == FundamentalsVerdictLevel.STRONG.value:
                strong += 1
            elif level == FundamentalsVerdictLevel.WEAK.value:
                weak += 1
            elif level == FundamentalsVerdictLevel.UNAVAILABLE.value:
                unavailable += 1
    basis = f"fundamentals STRONG={strong}, WEAK={weak}, UNAVAILABLE={unavailable}"
    if strong > weak:
        return FundamentalsVerdictLevel.STRONG.value, basis
    if weak > strong:
        return FundamentalsVerdictLevel.WEAK.value, basis
    return None, basis


def _category_lean(
    result: FundamentalsResult,
    category_name: str,
) -> tuple[str | None, str]:
    category = next(
        (item for item in result.categories if item.category == category_name),
        None,
    )
    if category is None:
        return None, f"{category_name}=UNAVAILABLE: category missing"

    strong = 0
    weak = 0
    levels: list[str] = []
    for verdict in category.verdicts:
        level = _enum_value(verdict.level)
        levels.append(f"{verdict.metric_name}={level}")
        if level == FundamentalsVerdictLevel.STRONG.value:
            strong += 1
        if level == FundamentalsVerdictLevel.WEAK.value:
            weak += 1

    basis = f"{category_name} verdicts: {', '.join(levels)}"
    if strong > weak:
        return FundamentalsVerdictLevel.STRONG.value, basis
    if weak > strong:
        return FundamentalsVerdictLevel.WEAK.value, basis
    return None, basis


def _technical_verdict(technicals: TechnicalsResult, indicator_name: str):
    return next(
        (verdict for verdict in technicals.verdicts if verdict.indicator_name == indicator_name),
        None,
    )


def _narrative_payload(result: SynthesisResult) -> dict[str, Any]:
    return {
        "ticker": result.ticker,
        "company_name": result.company_name,
        "fundamentals": _fundamentals_payload(result.fundamentals),
        "technicals": _technicals_payload(result.technicals),
        "news": _news_payload(result.news),
        "disagreements": [item.model_dump(mode="json") for item in result.disagreements],
        "sources": [source.model_dump(mode="json") for source in result.sources],
        "data_notes": result.data_notes,
    }


def _fundamentals_payload(result: FundamentalsResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    lean, basis = _fundamentals_lean(result)
    categories: list[dict[str, Any]] = []
    for category in result.categories:
        categories.append(
            {
                "category": category.category,
                "verdicts": [
                    {
                        "metric_name": verdict.metric_name,
                        "level": _enum_value(verdict.level),
                        "rationale": verdict.rationale,
                        "comparison_basis": verdict.comparison_basis,
                    }
                    for verdict in category.verdicts
                ],
            }
        )
    return {"overall_lean": lean, "overall_basis": basis, "categories": categories}


def _technicals_payload(result: TechnicalsResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "verdicts": [
            {
                "indicator_name": verdict.indicator_name,
                "level": _enum_value(verdict.level),
                "rationale": verdict.rationale,
                "comparison_basis": verdict.comparison_basis,
            }
            for verdict in result.verdicts
        ]
    }


def _news_payload(result: NewsSentimentResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "overall_tone": result.overall_tone.value,
        "item_sentiments": [
            {
                "news_item_id": sentiment.news_item_id,
                "source_name": sentiment.source_name,
                "source_url": sentiment.source_url,
                "label": sentiment.label.value,
                "confidence": round(sentiment.confidence, 4),
                "rationale": sentiment.rationale,
            }
            for sentiment in result.item_sentiments
        ],
        "global_links": [link.model_dump(mode="json") for link in result.global_links],
    }


def _narrative_passes_guardrails(text: str, payload: dict[str, Any]) -> bool:
    allowed_urls = {
        source["url"]
        for source in payload["sources"]
        if isinstance(source, dict) and source.get("url")
    }
    allowed_source_names = {
        source["name"]
        for source in payload["sources"]
        if isinstance(source, dict) and source.get("name")
    }
    if guardrails.has_disallowed_url(text, allowed_urls):
        return False
    if guardrails.has_bad_markdown_citation(text, allowed_source_names, allowed_urls):
        return False
    if guardrails.has_untraceable_number(text, payload):
        return False
    if guardrails.contains_advice_language(text):
        return False
    lower_text = text.lower()
    if "research" not in lower_text or "financial advice" not in lower_text:
        return False
    return True


def _dedupe_sources(sources: list[SourceReference]) -> list[SourceReference]:
    deduped: list[SourceReference] = []
    seen_urls: set[str] = set()
    for source in sources:
        if source.url in seen_urls:
            continue
        seen_urls.add(source.url)
        deduped.append(source)
    return deduped


def _source_fragment(sources: list[SourceReference]) -> str:
    if not sources:
        return ""
    rendered = ", ".join(f"{source.name} ({source.url})" for source in sources[:3])
    return f", with sources {rendered}"


def _enum_value(value: Any) -> str:
    return getattr(value, "value", str(value))
