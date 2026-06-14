"""FastAPI server for the Phase 4 research brief and local graph."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from quantera import config
from quantera.cache import cache_get, cache_set
from quantera.graph import build_graph
from quantera.news.finnhub_source import get_peers
from quantera.synthesis import synthesize


app = FastAPI(title="QuantEra Research Lab")

STATIC_DIR = Path(__file__).resolve().parent / "static"
TICKER_PATTERN = re.compile(r"^[A-Za-z0-9]{1,10}$")
SYNTHESIZE_FUNC = synthesize
GET_PEERS_FUNC = get_peers
BUILD_GRAPH_FUNC = build_graph
RESEARCH_CACHE_PREFIX = "phase5v1"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/technicals")
def technicals_dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "technicals.html")


@app.get("/api/research/{ticker}")
def research(ticker: str) -> dict[str, Any]:
    symbol = _validate_ticker(ticker)
    key = f"{RESEARCH_CACHE_PREFIX}:{symbol}"
    cached = cache_get(key)
    if _is_cached_payload(cached):
        return {
            "cached": True,
            "generated_at": cached["generated_at"],
            "synthesis": cached["synthesis"],
            "graph": cached["graph"],
        }

    try:
        synthesis_result = SYNTHESIZE_FUNC(symbol)
        peers = GET_PEERS_FUNC(symbol)
        graph = BUILD_GRAPH_FUNC(synthesis_result, peers)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "error": "research_failed",
                "ticker": symbol,
                "message": str(exc),
            },
        ) from exc

    payload = {
        "generated_at": synthesis_result.generated_at.isoformat(),
        "synthesis": synthesis_result.model_dump(mode="json"),
        "graph": graph.model_dump(mode="json"),
    }
    cache_set(key, payload, config.NEWS_TTL_SECONDS)
    return {"cached": False, **payload}


def _validate_ticker(ticker: str) -> str:
    if not TICKER_PATTERN.fullmatch(ticker):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_ticker",
                "message": "Ticker must be alphanumeric and at most 10 characters.",
            },
        )
    return ticker.upper()


def _is_cached_payload(value: dict[str, Any] | None) -> bool:
    return (
        isinstance(value, dict)
        and isinstance(value.get("generated_at"), str)
        and isinstance(value.get("synthesis"), dict)
        and isinstance(value.get("graph"), dict)
    )
