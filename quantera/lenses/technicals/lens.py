"""Orchestration for the technicals lens."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timezone

from quantera.lenses.technicals import explain, indicators
from quantera.lenses.technicals.verdicts import make_verdict
from quantera.llm.base import LLMClient
from quantera.models import PriceHistory
from quantera.models_technicals import Indicator, TechnicalsResult
from quantera.provider import DataProvider


IndicatorFunction = Callable[[PriceHistory], Indicator]


INDICATOR_FUNCTIONS: tuple[IndicatorFunction, ...] = (
    lambda prices: indicators.sma(prices, 50),
    lambda prices: indicators.sma(prices, 200),
    lambda prices: indicators.ema(prices, 20),
    lambda prices: indicators.rsi(prices, 14),
    lambda prices: indicators.price_vs_sma(prices, 50),
    lambda prices: indicators.price_vs_sma(prices, 200),
    lambda prices: indicators.volatility(prices, 30),
    lambda prices: indicators.return_pct(prices, 21),
    lambda prices: indicators.return_pct(prices, 63),
    lambda prices: indicators.return_pct(prices, 252),
    lambda prices: indicators.avg_volume(prices, 30),
    indicators.latest_volume,
)


class TechnicalsLens:
    """Analyze descriptive price technicals from normalized Phase 0 prices."""

    def __init__(self, provider: DataProvider, llm_client: LLMClient | None = None):
        self.provider = provider
        self.llm_client = llm_client

    def analyze(self, ticker: str, with_explanation: bool = True) -> TechnicalsResult:
        prices = self.provider.get_price_history(ticker)
        computed_indicators = [
            indicator_function(prices)
            for indicator_function in INDICATOR_FUNCTIONS
        ]
        verdicts = [make_verdict(indicator) for indicator in computed_indicators]

        result = TechnicalsResult(
            ticker=prices.ticker,
            indicators=computed_indicators,
            verdicts=verdicts,
            chart_series=indicators.chart_series(prices),
            explanation=None,
            price_as_of=_price_as_of(prices),
            generated_at=datetime.now(timezone.utc),
            bars_used=len(prices.bars),
        )

        if with_explanation:
            result.explanation = explain.generate_explanation(result, llm_client=self.llm_client)
        return result


def _price_as_of(prices: PriceHistory) -> date:
    if prices.bars:
        return prices.bars[-1].date
    return date.min
