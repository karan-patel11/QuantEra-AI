"""Pydantic result contract for the Phase 1 fundamentals lens."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class MetricStatus(str, Enum):
    OK = "OK"
    UNAVAILABLE = "UNAVAILABLE"


class Metric(BaseModel):
    name: str
    display_name: str
    value: float | None
    status: MetricStatus
    inputs_used: list[str] = Field(default_factory=list)
    source: str
    as_of: datetime
    note: str | None = None


class VerdictLevel(str, Enum):
    STRONG = "STRONG"
    NEUTRAL = "NEUTRAL"
    WEAK = "WEAK"
    UNAVAILABLE = "UNAVAILABLE"


class Verdict(BaseModel):
    metric_name: str
    level: VerdictLevel
    rationale: str
    comparison_basis: str


class CategoryResult(BaseModel):
    category: str
    metrics: list[Metric]
    verdicts: list[Verdict]


class FundamentalsResult(BaseModel):
    ticker: str
    company_name: str | None
    sector: str | None
    categories: list[CategoryResult]
    explanation: str | None = None
    generated_at: datetime
    data_as_of: datetime
