"""Pydantic graph contract for Phase 4."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeKind(str, Enum):
    COMPANY = "COMPANY"
    LENS_CATEGORY = "LENS_CATEGORY"
    SYNTHESIS = "SYNTHESIS"
    DISAGREEMENT = "DISAGREEMENT"
    SECTOR = "SECTOR"
    PEER = "PEER"
    FUND_VERDICT = "FUND_VERDICT"
    TECH_VERDICT = "TECH_VERDICT"
    NEWS_ITEM = "NEWS_ITEM"
    GLOBAL_LINK = "GLOBAL_LINK"


class EdgeKind(str, Enum):
    ANALYZED_BY = "ANALYZED_BY"
    METRIC_OF = "METRIC_OF"
    ITEM_OF = "ITEM_OF"
    GROUPED_UNDER = "GROUPED_UNDER"
    CONTRIBUTES_TO = "CONTRIBUTES_TO"
    DISAGREEMENT_OF = "DISAGREEMENT_OF"
    IN_SECTOR = "IN_SECTOR"
    PEER_OF = "PEER_OF"
    HAS_VERDICT = "HAS_VERDICT"
    HAS_TECH_STATE = "HAS_TECH_STATE"
    MENTIONED_IN = "MENTIONED_IN"
    SUPPORTS_LINK = "SUPPORTS_LINK"
    AFFECTS_HYPOTHESIS = "AFFECTS_HYPOTHESIS"


class GraphNode(BaseModel):
    id: str
    label: str
    kind: NodeKind
    parent_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    grounding: str


class GraphEdge(BaseModel):
    source_id: str
    target_id: str
    kind: EdgeKind
    grounding: str


class TickerGraph(BaseModel):
    ticker: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    generated_at: datetime
