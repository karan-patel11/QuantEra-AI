"""Pydantic result contract for the Phase 3 news sentiment lens."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class SentimentLabel(str, Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"


class OverallTone(str, Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"
    MIXED = "MIXED"
    NO_DATA = "NO_DATA"


class GlobalConfidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class NewsWindow(BaseModel):
    since: date
    until: date


class SourceReference(BaseModel):
    name: str
    url: str
    published_at: datetime


class ItemSentiment(BaseModel):
    news_item_id: str
    headline: str | None = None
    source_name: str
    source_url: str
    label: SentimentLabel
    confidence: float = Field(ge=0, le=1)
    rationale: str
    evidence_span: str = Field(max_length=180)


class GlobalLink(BaseModel):
    claim: str
    confidence: GlobalConfidence
    supporting_item_ids: list[str] = Field(default_factory=list)
    caveat: str


class NewsSentimentResult(BaseModel):
    ticker: str
    window: NewsWindow
    item_sentiments: list[ItemSentiment] = Field(default_factory=list)
    overall_tone: OverallTone
    global_links: list[GlobalLink] = Field(default_factory=list)
    summary: str | None = None
    sources: list[SourceReference] = Field(default_factory=list)
    generated_at: datetime
    items_considered: int
    items_after_whitelist: int
