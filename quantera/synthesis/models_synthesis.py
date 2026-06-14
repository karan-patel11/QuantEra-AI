"""Pydantic result contract for the Phase 4 synthesis layer."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from quantera.models_fundamentals import FundamentalsResult
from quantera.models_news import NewsSentimentResult, SourceReference
from quantera.models_technicals import TechnicalsResult


class Disagreement(BaseModel):
    description: str
    lens_a: str
    lens_b: str
    basis: str


class SynthesisResult(BaseModel):
    ticker: str
    company_name: str
    fundamentals: FundamentalsResult | None = None
    technicals: TechnicalsResult | None = None
    news: NewsSentimentResult | None = None
    disagreements: list[Disagreement] = Field(default_factory=list)
    narrative: str | None = None
    narrative_status: str | None = None
    sources: list[SourceReference] = Field(default_factory=list)
    generated_at: datetime
    data_notes: list[str] = Field(default_factory=list)
