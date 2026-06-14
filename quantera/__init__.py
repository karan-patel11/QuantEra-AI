"""QuantEra Research Lab data foundation and research lenses."""

from pathlib import Path

from dotenv import load_dotenv


def _load_project_dotenv(project_root: Path | None = None) -> None:
    root = project_root or Path(__file__).resolve().parents[1]
    load_dotenv(dotenv_path=root / ".env", override=False)


_load_project_dotenv()

from quantera.lenses.fundamentals import FundamentalsLens
from quantera.lenses.news_sentiment import NewsSentimentLens
from quantera.lenses.technicals import TechnicalsLens
from quantera.models import FieldValue, Financials, FinancialsByPeriod, PriceBar, PriceHistory
from quantera.models_fundamentals import (
    CategoryResult,
    FundamentalsResult,
    Metric,
    MetricStatus,
    Verdict,
    VerdictLevel,
)
from quantera.models_news import (
    GlobalConfidence,
    GlobalLink,
    ItemSentiment,
    NewsSentimentResult,
    NewsWindow,
    OverallTone,
    SentimentLabel,
    SourceReference,
)
from quantera.models_technicals import (
    Indicator,
    IndicatorStatus,
    TechnicalSeries,
    TechnicalSeriesPoint,
    TechnicalVerdict,
    TechnicalsResult,
    VerdictLevel as TechnicalVerdictLevel,
)
from quantera.provider import DataProvider

__all__ = [
    "CategoryResult",
    "DataProvider",
    "FieldValue",
    "Financials",
    "FinancialsByPeriod",
    "FundamentalsLens",
    "FundamentalsResult",
    "Indicator",
    "IndicatorStatus",
    "Metric",
    "MetricStatus",
    "GlobalConfidence",
    "GlobalLink",
    "ItemSentiment",
    "NewsSentimentLens",
    "NewsSentimentResult",
    "NewsWindow",
    "OverallTone",
    "PriceBar",
    "PriceHistory",
    "SentimentLabel",
    "SourceReference",
    "TechnicalVerdict",
    "TechnicalSeries",
    "TechnicalSeriesPoint",
    "TechnicalVerdictLevel",
    "TechnicalsLens",
    "TechnicalsResult",
    "Verdict",
    "VerdictLevel",
]
