"""Pydantic result contract for the Phase 2 technicals lens."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


class IndicatorStatus(str, Enum):
    OK = "OK"
    UNAVAILABLE = "UNAVAILABLE"


class Indicator(BaseModel):
    name: str
    display_name: str
    value: float | None
    status: IndicatorStatus
    window: int | None = None
    inputs_used: list[str] = Field(default_factory=list)
    as_of: date
    source: str
    note: str | None = None


class TechnicalSeriesPoint(BaseModel):
    date: date
    value: float | None
    status: IndicatorStatus
    source: str
    as_of: date
    note: str | None = None


class TechnicalSeries(BaseModel):
    name: str
    display_name: str
    window: int | None = None
    inputs_used: list[str] = Field(default_factory=list)
    points: list[TechnicalSeriesPoint] = Field(default_factory=list)


class VerdictLevel(str, Enum):
    ABOVE = "ABOVE"
    BELOW = "BELOW"
    NEUTRAL = "NEUTRAL"
    OVERBOUGHT = "OVERBOUGHT"
    OVERSOLD = "OVERSOLD"
    UNAVAILABLE = "UNAVAILABLE"


class TechnicalVerdict(BaseModel):
    indicator_name: str
    level: VerdictLevel
    rationale: str
    comparison_basis: str


class TechnicalsResult(BaseModel):
    ticker: str
    indicators: list[Indicator]
    verdicts: list[TechnicalVerdict]
    chart_series: list[TechnicalSeries] = Field(default_factory=list)
    explanation: str | None = None
    price_as_of: date
    generated_at: datetime
    bars_used: int
