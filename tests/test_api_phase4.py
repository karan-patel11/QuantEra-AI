from __future__ import annotations

from fastapi.testclient import TestClient

from quantera.cache import cache_set
from quantera.graph import build_graph
from quantera.server import app as app_module
from tests.phase4_helpers import synthesis_result


def test_research_endpoint_computes_then_serves_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module.config, "CACHE_DIR", tmp_path)
    cache_set(
        "phase4:AAPL",
        {"generated_at": "old", "synthesis": {"ticker": "OLD"}, "graph": {"nodes": []}},
        999,
    )
    calls = {"synthesize": 0, "peers": 0, "graph": 0}

    def fake_synthesize(ticker):
        calls["synthesize"] += 1
        result = synthesis_result()
        return result.model_copy(update={"ticker": ticker})

    def fake_get_peers(ticker):
        calls["peers"] += 1
        return ["MSFT"]

    def fake_build_graph(synthesis, peers):
        calls["graph"] += 1
        return build_graph(synthesis, peers)

    monkeypatch.setattr(app_module, "SYNTHESIZE_FUNC", fake_synthesize)
    monkeypatch.setattr(app_module, "GET_PEERS_FUNC", fake_get_peers)
    monkeypatch.setattr(app_module, "BUILD_GRAPH_FUNC", fake_build_graph)

    client = TestClient(app_module.app)
    first = client.get("/api/research/AAPL")
    second = client.get("/api/research/AAPL")

    assert first.status_code == 200
    assert first.json()["cached"] is False
    assert first.json()["synthesis"]["ticker"] == "AAPL"
    assert "chart_series" in first.json()["synthesis"]["technicals"]
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert "chart_series" in second.json()["synthesis"]["technicals"]
    assert calls == {"synthesize": 1, "peers": 1, "graph": 1}


def test_research_endpoint_rejects_bad_ticker():
    client = TestClient(app_module.app)
    response = client.get("/api/research/AAPL!")

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_ticker"
