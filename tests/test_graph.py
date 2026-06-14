from __future__ import annotations

from quantera.graph import EdgeKind, NodeKind, build_graph
from quantera.models_fundamentals import VerdictLevel
from quantera.synthesis.models_synthesis import Disagreement
from tests.phase4_helpers import fundamentals_result, synthesis_result


def test_graph_builder_emits_hierarchical_grounded_structure():
    synthesis = synthesis_result(
        fundamentals=fundamentals_result(
            valuation_level=VerdictLevel.WEAK,
            growth_level=VerdictLevel.UNAVAILABLE,
        ),
        narrative="A deterministic template.",
        narrative_status="template_fallback",
    ).model_copy(
        update={
            "disagreements": [
                Disagreement(
                    description="Fundamentals and news point in different directions.",
                    lens_a="fundamentals",
                    lens_b="news",
                    basis="fundamentals WEAK; news POSITIVE",
                )
            ]
        }
    )

    graph = build_graph(synthesis, ["MSFT", "GOOG"])
    nodes_by_id = {node.id: node for node in graph.nodes}
    edge_tuples = {
        (edge.source_id, edge.target_id, edge.kind)
        for edge in graph.edges
    }

    assert nodes_by_id["company:AAPL"].kind is NodeKind.COMPANY
    assert nodes_by_id["synthesis:AAPL"].kind is NodeKind.SYNTHESIS
    assert nodes_by_id["synthesis:AAPL"].label == "Research Brief"
    assert nodes_by_id["synthesis:AAPL"].payload["narrative_status"] == "template_fallback"

    lens_ids = {
        "lens:fundamentals",
        "lens:technicals",
        "lens:news_sentiment",
        "lens:peers_sector",
    }
    assert {nodes_by_id[node_id].kind for node_id in lens_ids} == {NodeKind.LENS_CATEGORY}

    direct_company_sources = {
        edge.source_id
        for edge in graph.edges
        if edge.target_id == "company:AAPL"
    }
    assert direct_company_sources == {*lens_ids, "synthesis:AAPL"}
    assert all(
        edge.source_id in direct_company_sources
        for edge in graph.edges
        if edge.target_id == "company:AAPL"
    )

    assert ("lens:fundamentals", "company:AAPL", EdgeKind.ANALYZED_BY) in edge_tuples
    assert ("lens:technicals", "company:AAPL", EdgeKind.ANALYZED_BY) in edge_tuples
    assert ("lens:news_sentiment", "company:AAPL", EdgeKind.ANALYZED_BY) in edge_tuples
    assert ("lens:peers_sector", "company:AAPL", EdgeKind.ANALYZED_BY) in edge_tuples
    assert ("synthesis:AAPL", "company:AAPL", EdgeKind.ANALYZED_BY) in edge_tuples

    assert nodes_by_id["fund:valuation:pe_ratio"].parent_id == "lens:fundamentals"
    assert nodes_by_id["fund:valuation:pe_ratio"].payload["level"] == "WEAK"
    assert (
        nodes_by_id["fund:growth:revenue_growth_yoy"].label
        == "Revenue Growth YoY: data unavailable"
    )
    assert nodes_by_id["fund:growth:revenue_growth_yoy"].parent_id == "lens:fundamentals"
    assert (
        "fund:valuation:pe_ratio",
        "lens:fundamentals",
        EdgeKind.METRIC_OF,
    ) in edge_tuples

    assert nodes_by_id["tech:price_vs_sma_200"].parent_id == "lens:technicals"
    assert ("tech:price_vs_sma_200", "lens:technicals", EdgeKind.METRIC_OF) in edge_tuples

    assert nodes_by_id["news:news_1"].parent_id == "lens:news_sentiment"
    assert (
        nodes_by_id["news:news_1"].payload["url"]
        == "https://www.reuters.com/markets/apple-profit-outlook"
    )
    assert ("news:news_1", "lens:news_sentiment", EdgeKind.ITEM_OF) in edge_tuples

    global_nodes = [node for node in graph.nodes if node.kind is NodeKind.GLOBAL_LINK]
    assert len(global_nodes) == 1
    assert global_nodes[0].parent_id == "lens:news_sentiment"
    assert ("news:news_1", global_nodes[0].id, EdgeKind.SUPPORTS_LINK) in edge_tuples
    assert (
        global_nodes[0].id,
        "lens:news_sentiment",
        EdgeKind.AFFECTS_HYPOTHESIS,
    ) in edge_tuples

    assert nodes_by_id["sector:technology"].parent_id == "lens:peers_sector"
    assert nodes_by_id["peer:MSFT"].parent_id == "lens:peers_sector"
    assert ("sector:technology", "lens:peers_sector", EdgeKind.GROUPED_UNDER) in edge_tuples
    assert ("peer:MSFT", "lens:peers_sector", EdgeKind.GROUPED_UNDER) in edge_tuples

    disagreement_nodes = [node for node in graph.nodes if node.kind is NodeKind.DISAGREEMENT]
    assert len(disagreement_nodes) == 1
    assert disagreement_nodes[0].payload["lens_a"] == "fundamentals"
    assert (
        disagreement_nodes[0].id,
        "synthesis:AAPL",
        EdgeKind.DISAGREEMENT_OF,
    ) in edge_tuples

    level_two_nodes = [
        node
        for node in graph.nodes
        if node.kind
        in {
            NodeKind.FUND_VERDICT,
            NodeKind.TECH_VERDICT,
            NodeKind.NEWS_ITEM,
            NodeKind.GLOBAL_LINK,
            NodeKind.SECTOR,
            NodeKind.PEER,
        }
    ]
    assert all(node.parent_id in lens_ids for node in level_two_nodes)
    assert all(node.grounding for node in graph.nodes)
    assert all(edge.grounding for edge in graph.edges)
