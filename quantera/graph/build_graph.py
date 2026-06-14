"""Deterministic hierarchical local knowledge graph builder.

Global-link AFFECTS_HYPOTHESIS edges are retargeted to the News & Sentiment
lens node. That keeps the company neighborhood limited to lens categories plus
the research brief, while preserving the hypothesis relationship in the news
cluster where its supporting items live.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from quantera.graph.models_graph import EdgeKind, GraphEdge, GraphNode, NodeKind, TickerGraph
from quantera.models_fundamentals import VerdictLevel as FundamentalsVerdictLevel
from quantera.models_news import OverallTone
from quantera.models_technicals import IndicatorStatus, VerdictLevel as TechnicalVerdictLevel
from quantera.synthesis.models_synthesis import SynthesisResult


PEER_LIMIT = 8
LABEL_LIMIT = 72
COMPANY_LENS_IDS = (
    "lens:fundamentals",
    "lens:technicals",
    "lens:news_sentiment",
    "lens:peers_sector",
)
SYNTHESIS_ID_PREFIX = "synthesis:"
FUNDAMENTALS_LENS_ID = "lens:fundamentals"
TECHNICALS_LENS_ID = "lens:technicals"
NEWS_LENS_ID = "lens:news_sentiment"
PEERS_SECTOR_LENS_ID = "lens:peers_sector"


@dataclass(frozen=True)
class LensCategory:
    id: str
    label: str
    lens_key: str
    grounding: str


LENS_CATEGORIES = (
    LensCategory(
        id=FUNDAMENTALS_LENS_ID,
        label="Fundamentals",
        lens_key="fundamentals",
        grounding="fundamentals lens output",
    ),
    LensCategory(
        id=TECHNICALS_LENS_ID,
        label="Technicals",
        lens_key="technicals",
        grounding="technicals lens output",
    ),
    LensCategory(
        id=NEWS_LENS_ID,
        label="News & Sentiment",
        lens_key="news",
        grounding="news sentiment lens output",
    ),
    LensCategory(
        id=PEERS_SECTOR_LENS_ID,
        label="Peers & Sector",
        lens_key="peers",
        grounding="fundamentals sector and Finnhub company peers endpoint",
    ),
)


def build_graph(synthesis: SynthesisResult, peers: list[str]) -> TickerGraph:
    """Build a grounded clustered graph from completed lens outputs and peer data."""

    symbol = synthesis.ticker.upper()
    company_id = f"company:{symbol}"
    synthesis_id = f"{SYNTHESIS_ID_PREFIX}{symbol}"
    nodes: list[GraphNode] = [
        GraphNode(
            id=company_id,
            label=synthesis.company_name or symbol,
            kind=NodeKind.COMPANY,
            payload={
                "ticker": symbol,
                "company_name": synthesis.company_name,
                "data_notes": synthesis.data_notes,
            },
            grounding="synthesis ticker and company_name",
        )
    ]
    edges: list[GraphEdge] = []

    _add_lens_categories(nodes, edges, company_id, synthesis, peers)
    _add_synthesis(nodes, edges, company_id, synthesis_id, synthesis)
    _add_fundamentals(nodes, edges, synthesis)
    _add_technicals(nodes, edges, synthesis)
    news_node_ids = _add_news(nodes, edges, synthesis)
    _add_global_links(nodes, edges, synthesis, news_node_ids)
    _add_sector(nodes, edges, synthesis)
    _add_peers(nodes, edges, symbol, peers)
    _add_disagreements(nodes, edges, synthesis_id, synthesis)

    return TickerGraph(
        ticker=symbol,
        nodes=nodes,
        edges=edges,
        generated_at=datetime.now(timezone.utc),
    )


def _add_lens_categories(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    company_id: str,
    synthesis: SynthesisResult,
    peers: list[str],
) -> None:
    usability = _lens_usability(synthesis, peers)
    for lens in LENS_CATEGORIES:
        nodes.append(
            GraphNode(
                id=lens.id,
                label=lens.label,
                kind=NodeKind.LENS_CATEGORY,
                payload={
                    "lens_key": lens.lens_key,
                    "usable_output": usability[lens.id],
                },
                grounding=lens.grounding,
            )
        )
        edges.append(
            GraphEdge(
                source_id=lens.id,
                target_id=company_id,
                kind=EdgeKind.ANALYZED_BY,
                grounding=f"{lens.label} lens category groups grounded outputs for {synthesis.ticker.upper()}",
            )
        )


def _add_synthesis(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    company_id: str,
    synthesis_id: str,
    synthesis: SynthesisResult,
) -> None:
    conclusions = _lens_conclusions(synthesis)
    nodes.append(
        GraphNode(
            id=synthesis_id,
            label="Research Brief",
            kind=NodeKind.SYNTHESIS,
            payload={
                **conclusions,
                "narrative_status": _narrative_status(synthesis),
                "disagreement_count": len(synthesis.disagreements),
            },
            grounding="deterministic synthesis result and guarded narrative status",
        )
    )
    edges.append(
        GraphEdge(
            source_id=synthesis_id,
            target_id=company_id,
            kind=EdgeKind.ANALYZED_BY,
            grounding="research brief assembled for the ticker from deterministic lens outputs",
        )
    )
    for lens_id, usable in _synthesis_contributors(synthesis).items():
        if not usable:
            continue
        edges.append(
            GraphEdge(
                source_id=lens_id,
                target_id=synthesis_id,
                kind=EdgeKind.CONTRIBUTES_TO,
                grounding=f"{lens_id.removeprefix('lens:')} produced usable deterministic output for synthesis",
            )
        )


def _add_sector(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    synthesis: SynthesisResult,
) -> None:
    sector = synthesis.fundamentals.sector if synthesis.fundamentals is not None else None
    if not sector:
        return
    sector_id = f"sector:{_slug(sector)}"
    nodes.append(
        GraphNode(
            id=sector_id,
            label=sector,
            kind=NodeKind.SECTOR,
            parent_id=PEERS_SECTOR_LENS_ID,
            payload={"sector": sector, "lens_key": "peers"},
            grounding="fundamentals data-layer sector",
        )
    )
    edges.append(
        GraphEdge(
            source_id=sector_id,
            target_id=PEERS_SECTOR_LENS_ID,
            kind=EdgeKind.GROUPED_UNDER,
            grounding="fundamentals data-layer sector grouped under Peers & Sector",
        )
    )


def _add_peers(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    symbol: str,
    peers: list[str],
) -> None:
    seen: set[str] = {symbol}
    for peer in peers:
        peer_symbol = peer.upper()
        if not peer_symbol or peer_symbol in seen:
            continue
        seen.add(peer_symbol)
        if len(seen) > PEER_LIMIT + 1:
            break
        peer_id = f"peer:{peer_symbol}"
        nodes.append(
            GraphNode(
                id=peer_id,
                label=peer_symbol,
                kind=NodeKind.PEER,
                parent_id=PEERS_SECTOR_LENS_ID,
                payload={"ticker": peer_symbol, "lens_key": "peers"},
                grounding="Finnhub company peers endpoint",
            )
        )
        edges.append(
            GraphEdge(
                source_id=peer_id,
                target_id=PEERS_SECTOR_LENS_ID,
                kind=EdgeKind.GROUPED_UNDER,
                grounding="Finnhub company peers endpoint grouped under Peers & Sector",
            )
        )


def _add_fundamentals(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    synthesis: SynthesisResult,
) -> None:
    if synthesis.fundamentals is None:
        return

    for category in synthesis.fundamentals.categories:
        metric_by_name = {metric.name: metric for metric in category.metrics}
        for verdict in category.verdicts:
            metric = metric_by_name.get(verdict.metric_name)
            display_name = metric.display_name if metric is not None else verdict.metric_name
            level = _enum_value(verdict.level)
            unavailable = level == FundamentalsVerdictLevel.UNAVAILABLE.value
            label = (
                f"{display_name}: data unavailable"
                if unavailable
                else f"{display_name}: {level}"
            )
            node_id = f"fund:{_slug(category.category)}:{_slug(verdict.metric_name)}"
            status = _enum_value(metric.status) if metric is not None else None
            nodes.append(
                GraphNode(
                    id=node_id,
                    label=label,
                    kind=NodeKind.FUND_VERDICT,
                    parent_id=FUNDAMENTALS_LENS_ID,
                    payload={
                        "lens_key": "fundamentals",
                        "category": category.category,
                        "metric_name": verdict.metric_name,
                        "display_name": display_name,
                        "level": level,
                        "value": metric.value if metric is not None else None,
                        "status": status,
                        "rationale": verdict.rationale,
                        "comparison_basis": verdict.comparison_basis,
                    },
                    grounding=f"computed fundamentals verdict for {category.category}/{verdict.metric_name}",
                )
            )
            edges.append(
                GraphEdge(
                    source_id=node_id,
                    target_id=FUNDAMENTALS_LENS_ID,
                    kind=EdgeKind.METRIC_OF,
                    grounding=f"computed fundamentals verdict for {category.category}/{verdict.metric_name}",
                )
            )


def _add_technicals(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    synthesis: SynthesisResult,
) -> None:
    if synthesis.technicals is None:
        return

    indicator_by_name = {indicator.name: indicator for indicator in synthesis.technicals.indicators}
    for verdict in synthesis.technicals.verdicts:
        indicator = indicator_by_name.get(verdict.indicator_name)
        display_name = indicator.display_name if indicator is not None else verdict.indicator_name
        level = _enum_value(verdict.level)
        status = _enum_value(indicator.status) if indicator is not None else None
        unavailable = status == IndicatorStatus.UNAVAILABLE.value
        label = (
            f"{display_name}: data unavailable"
            if unavailable
            else f"{display_name}: {level}"
        )
        node_id = f"tech:{_slug(verdict.indicator_name)}"
        nodes.append(
            GraphNode(
                id=node_id,
                label=label,
                kind=NodeKind.TECH_VERDICT,
                parent_id=TECHNICALS_LENS_ID,
                payload={
                    "lens_key": "technicals",
                    "indicator_name": verdict.indicator_name,
                    "display_name": display_name,
                    "level": level,
                    "value": indicator.value if indicator is not None else None,
                    "status": status,
                    "rationale": verdict.rationale,
                    "comparison_basis": verdict.comparison_basis,
                },
                grounding=f"computed technical verdict for {verdict.indicator_name}",
            )
        )
        edges.append(
            GraphEdge(
                source_id=node_id,
                target_id=TECHNICALS_LENS_ID,
                kind=EdgeKind.METRIC_OF,
                grounding=f"computed technical verdict for {verdict.indicator_name}",
            )
        )


def _add_news(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    synthesis: SynthesisResult,
) -> dict[str, str]:
    news_node_ids: dict[str, str] = {}
    if synthesis.news is None:
        return news_node_ids

    for sentiment in synthesis.news.item_sentiments:
        node_id = f"news:{_slug(sentiment.news_item_id)}"
        news_node_ids[sentiment.news_item_id] = node_id
        headline = sentiment.headline or sentiment.news_item_id
        nodes.append(
            GraphNode(
                id=node_id,
                label=_truncate(headline),
                kind=NodeKind.NEWS_ITEM,
                parent_id=NEWS_LENS_ID,
                payload={
                    "lens_key": "news",
                    "news_item_id": sentiment.news_item_id,
                    "headline": sentiment.headline,
                    "source_name": sentiment.source_name,
                    "url": sentiment.source_url,
                    "sentiment_label": sentiment.label.value,
                    "confidence": sentiment.confidence,
                    "rationale": sentiment.rationale,
                    "evidence_span": sentiment.evidence_span,
                },
                grounding=f"retrieved news item {sentiment.news_item_id} from {sentiment.source_name}",
            )
        )
        edges.append(
            GraphEdge(
                source_id=node_id,
                target_id=NEWS_LENS_ID,
                kind=EdgeKind.ITEM_OF,
                grounding=f"retrieved news item {sentiment.news_item_id} grouped under News & Sentiment",
            )
        )
    return news_node_ids


def _add_global_links(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    synthesis: SynthesisResult,
    news_node_ids: dict[str, str],
) -> None:
    if synthesis.news is None:
        return

    for index, link in enumerate(synthesis.news.global_links, start=1):
        node_id = f"global:{index}:{_slug(link.claim)}"
        nodes.append(
            GraphNode(
                id=node_id,
                label=_truncate(link.claim),
                kind=NodeKind.GLOBAL_LINK,
                parent_id=NEWS_LENS_ID,
                payload={
                    "lens_key": "news",
                    "hypothesis": link.claim,
                    "confidence": link.confidence.value,
                    "caveat": link.caveat,
                    "supporting_item_ids": link.supporting_item_ids,
                },
                grounding="accepted global link from news sentiment lens",
            )
        )
        edges.append(
            GraphEdge(
                source_id=node_id,
                target_id=NEWS_LENS_ID,
                kind=EdgeKind.ITEM_OF,
                grounding="accepted global link grouped under News & Sentiment",
            )
        )
        for item_id in link.supporting_item_ids:
            source_node_id = news_node_ids.get(item_id)
            if source_node_id is None:
                continue
            edges.append(
                GraphEdge(
                    source_id=source_node_id,
                    target_id=node_id,
                    kind=EdgeKind.SUPPORTS_LINK,
                    grounding=f"accepted global link cites supporting news item {item_id}",
                )
            )
        edges.append(
            GraphEdge(
                source_id=node_id,
                target_id=NEWS_LENS_ID,
                kind=EdgeKind.AFFECTS_HYPOTHESIS,
                grounding="accepted global link retargeted to News & Sentiment lens cluster",
            )
        )


def _add_disagreements(
    nodes: list[GraphNode],
    edges: list[GraphEdge],
    synthesis_id: str,
    synthesis: SynthesisResult,
) -> None:
    for index, disagreement in enumerate(synthesis.disagreements, start=1):
        node_id = f"disagreement:{index}:{_slug(disagreement.lens_a)}:{_slug(disagreement.lens_b)}"
        nodes.append(
            GraphNode(
                id=node_id,
                label=_truncate(f"Disagreement: {disagreement.lens_a} vs {disagreement.lens_b}", 58),
                kind=NodeKind.DISAGREEMENT,
                payload=disagreement.model_dump(mode="json"),
                grounding="deterministic synthesis disagreement rule",
            )
        )
        edges.append(
            GraphEdge(
                source_id=node_id,
                target_id=synthesis_id,
                kind=EdgeKind.DISAGREEMENT_OF,
                grounding="deterministic synthesis disagreement rule",
            )
        )


def _lens_usability(synthesis: SynthesisResult, peers: list[str]) -> dict[str, bool]:
    return {
        FUNDAMENTALS_LENS_ID: _fundamentals_usable(synthesis),
        TECHNICALS_LENS_ID: _technicals_usable(synthesis),
        NEWS_LENS_ID: _news_usable(synthesis),
        PEERS_SECTOR_LENS_ID: bool(peers)
        or bool(synthesis.fundamentals is not None and synthesis.fundamentals.sector),
    }


def _synthesis_contributors(synthesis: SynthesisResult) -> dict[str, bool]:
    return {
        FUNDAMENTALS_LENS_ID: _fundamentals_usable(synthesis),
        TECHNICALS_LENS_ID: _technicals_usable(synthesis),
        NEWS_LENS_ID: _news_usable(synthesis),
    }


def _fundamentals_usable(synthesis: SynthesisResult) -> bool:
    result = synthesis.fundamentals
    if result is None:
        return False
    return any(
        _enum_value(verdict.level) != FundamentalsVerdictLevel.UNAVAILABLE.value
        for category in result.categories
        for verdict in category.verdicts
    )


def _technicals_usable(synthesis: SynthesisResult) -> bool:
    result = synthesis.technicals
    if result is None:
        return False
    return any(
        _enum_value(verdict.level) != TechnicalVerdictLevel.UNAVAILABLE.value
        for verdict in result.verdicts
    )


def _news_usable(synthesis: SynthesisResult) -> bool:
    return (
        synthesis.news is not None
        and synthesis.news.overall_tone is not OverallTone.NO_DATA
        and bool(synthesis.news.item_sentiments)
    )


def _lens_conclusions(synthesis: SynthesisResult) -> dict[str, Any]:
    fundamentals_lean, fundamentals_basis = _fundamentals_lean(synthesis)
    technical_trend_state, technical_trend_basis = _technical_trend_state(synthesis)
    return {
        "fundamentals_lean": fundamentals_lean,
        "fundamentals_basis": fundamentals_basis,
        "technical_trend_state": technical_trend_state,
        "technical_trend_basis": technical_trend_basis,
        "news_overall_tone": synthesis.news.overall_tone.value if synthesis.news is not None else None,
    }


def _fundamentals_lean(synthesis: SynthesisResult) -> tuple[str | None, str]:
    result = synthesis.fundamentals
    if result is None:
        return None, "fundamentals lens unavailable"
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
    return "NEUTRAL", basis


def _technical_trend_state(synthesis: SynthesisResult) -> tuple[str | None, str]:
    if synthesis.technicals is None:
        return None, "technicals lens unavailable"
    for verdict in synthesis.technicals.verdicts:
        if verdict.indicator_name == "price_vs_sma_200":
            return _enum_value(verdict.level), verdict.rationale
    return None, "price_vs_sma_200 verdict unavailable"


def _narrative_status(synthesis: SynthesisResult) -> str:
    if synthesis.narrative_status:
        return synthesis.narrative_status
    if not synthesis.narrative:
        return "not_generated"
    if synthesis.narrative.startswith(f"{synthesis.ticker} cross-lens research brief."):
        return "template_fallback"
    return "llm_narrative"


def _slug(value: Any) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(value).strip()).strip("_").lower()
    return slug or "unknown"


def _truncate(value: str, limit: int = LABEL_LIMIT) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _enum_value(value: Any) -> str:
    return getattr(value, "value", str(value))
