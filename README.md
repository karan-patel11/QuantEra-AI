# QuantEra Research Lab

Phase 0 builds the data foundation for a stock-research tool. It fetches raw
financial and daily price data, maps it into fixed Pydantic models, normalizes it,
caches it on disk, and validates source accuracy against hand-entered references.

Phase 1 adds a fundamentals lens. It computes financial ratios in Python, assigns
deterministic verdicts, preserves provenance, and optionally asks a leashed LLM to
explain the already-computed results. Phase 2 adds a technicals lens that computes
price-based indicators from Phase 0 price history with the same deterministic core
and guarded explanation pattern. Phase 4 adds a synthesis brief and a local,
grounded knowledge graph per ticker, served from a small FastAPI app.

## Install

```bash
python3 -m pip install -e ".[dev]"
```

## Public API

```python
from quantera import DataProvider, FundamentalsLens, NewsSentimentLens, TechnicalsLens

provider = DataProvider()
financials = provider.get_financials("AAPL")
prices = provider.get_price_history("AAPL")
fundamentals = FundamentalsLens(provider).analyze("AAPL")
technicals = TechnicalsLens(provider).analyze("AAPL")
news = NewsSentimentLens().analyze("AAPL")

print(financials.missing_fields())
print(len(prices.bars))
print(fundamentals.explanation)
print(technicals.explanation)
print(news.summary)
```

`DataProvider` is the entry point Phase 1+ should use. It accepts an injectable
`DataSource`, so yfinance can be replaced later without changing downstream code.

## Phase 4 Research Server

Run the local research API and graph UI:

```bash
uvicorn quantera.server.app:app
```

Open `http://127.0.0.1:8000/` for the single-page graph UI, or call the JSON API:

```bash
curl http://127.0.0.1:8000/api/research/AAPL
```

`GET /api/research/{ticker}` returns:

- `synthesis`: the fundamentals, technicals, and news results, deterministic
  disagreements, guarded narrative or deterministic fallback, source references,
  and data notes.
- `graph`: a ticker-centered hierarchy with the company, lens category clusters,
  a Research Brief synthesis node, sector, peer, verdict, news, disagreement,
  and accepted global-link nodes.
- `cached` and `generated_at`: freshness metadata.

The graph is assembled only from existing lens outputs, Finnhub peer data,
retrieved news items, accepted global links, computed verdicts, and deterministic
disagreement rules. Every node and edge includes `grounding`. Level-2 nodes carry
`parent_id` so the UI can render Fundamentals, Technicals, News & Sentiment, and
Peers & Sector as visible clusters. News nodes link to their source URL, peer
nodes recenter the UI on that ticker, and the trace panel shows each node payload
plus its grounding. Missing verdict data is shown as labeled unavailable nodes.
Accepted global-link `AFFECTS_HYPOTHESIS` edges are retargeted to the News &
Sentiment cluster, keeping the company neighborhood limited to lens categories
plus the Research Brief node.

The assembled Phase 4 response is cached under `phase4v2:{ticker}` for the news
TTL. The versioned key prevents old flat graph JSON from being served to the
hierarchical frontend. A cached response is served without rerunning lenses, peer
retrieval, graph building, or synthesis narration.

Phase 5.1 adds a lightweight technicals dashboard at
`http://127.0.0.1:8000/technicals`. It uses the same
`GET /api/research/{ticker}` payload as the graph and renders backend-computed
adjusted-close, SMA(50), SMA(200), EMA(20), and RSI(14) series with scalar
technicals verdicts. The research cache key is `phase5v1:{ticker}` so cached
payloads include chart-ready technicals series.

## Fundamentals Lens

Run the Phase 1 lens:

```python
from quantera import DataProvider, FundamentalsLens

result = FundamentalsLens(DataProvider()).analyze("AAPL")
print(result.model_dump())
```

Disable the LLM explanation and return only deterministic metrics and verdicts:

```python
result = FundamentalsLens(DataProvider()).analyze("AAPL", with_explanation=False)
```

The lens groups metrics into valuation, profitability, health, and growth. Every
metric records `inputs_used`, `source`, and `as_of`. If a required Phase 0 field is
missing, zero, or has a sign that would make the ratio misleading, the metric is
returned as `UNAVAILABLE` with a note. Missing data is never converted to zero.

The current Phase 1 growth metrics still return `UNAVAILABLE` until the
fundamentals lens consumes prior periods for growth calculations.

## Technicals Lens

Run the Phase 2 lens:

```python
from quantera import DataProvider, TechnicalsLens

result = TechnicalsLens(DataProvider()).analyze("AAPL")
print(result.model_dump())
```

Disable the LLM explanation and return only deterministic indicators and verdicts:

```python
result = TechnicalsLens(DataProvider()).analyze("AAPL", with_explanation=False)
```

The lens computes 50-day and 200-day simple moving averages, 20-day EMA, 14-day
RSI using Wilder's smoothing, price versus SMA, 30-day annualized volatility,
21/63/252-trading-day trailing returns, and volume context. All return and trend
indicators use `adj_close`, not raw `close`, so splits and dividends do not
silently corrupt the calculations. Raw close is only used by the price validation
harness for raw OHLC sanity checks.

Technical verdicts are deterministic and descriptive only: above/below a moving
average band, RSI in overbought/oversold/neutral range, or neutral context. They
are not buy, sell, hold, entry, exit, or timing recommendations. If the price
history is too short for an indicator, the indicator is `UNAVAILABLE` with a note
stating the needed and available bars.

## News Sentiment Lens

Phase 3 adds the news and sentiment lens:

```python
from quantera import NewsSentimentLens

result = NewsSentimentLens().analyze("AAPL")
print(result.model_dump())
```

The default news adapter is `quantera/news/finnhub_source.py`, which calls
Finnhub's company-news endpoint and reads the API token from `NEWS_API_KEY`.
Finnhub documents the endpoint and current plan limits here:
https://finnhub.io/docs/api/company-news

The adapter only fetches and maps source data. It does not filter, score, or call
an LLM. If `NEWS_API_KEY` is missing or the provider fails, the lens returns an
empty, deterministic `NO_DATA` result instead of fabricating news.

Source reliability is code-enforced before retrieval or LLM calls. The editable
allowlist lives in `quantera/config.py` as `WHITELIST_SOURCE_DOMAINS` and
`WHITELIST_SOURCE_NAMES`, and `quantera/news/whitelist.py` is the gate. Items
that fail the gate are dropped during ingestion, and `items_considered` plus
`items_after_whitelist` show how much was filtered. Every surviving item keeps
its `source_name`, `source_url`, and `published_at` through the final result.

Retrieval is intentionally simple and local: `retrieve.py` ranks already
whitelisted items by recency, optional provider relevance, and ticker/company
keyword matches. No external vector database is used. A heavier vector store
should only be added if this simple ranking is demonstrably insufficient, and it
must embed only whitelisted text.

Per-item sentiment is leashed and source-isolated. The model sees only an item
id, headline, and summary text. It returns `POSITIVE`, `NEUTRAL`, or `NEGATIVE`
as sentiment about the text, not a prediction about the stock. Guardrails verify
the returned id, reject invented sources or URLs, reject untraceable numbers, and
keep `evidence_span` to a short snippet. On failure the item is marked
`NEUTRAL` with `rationale="unscored: guardrail"`.

`overall_tone` is computed in code from item labels and confidence weights. The
LLM never decides the aggregate. Global links are optional hypotheses only:
claims must use words like "may" or "could", cite retrieved item ids, include
`LOW`, `MEDIUM`, or `HIGH` confidence, and carry a caveat. Invalid or weak links
are dropped; an empty list is an acceptable honest result.

The summary step is narration only. It receives the item sentiments, their
rationales, the computed tone, source names/URLs/dates, and accepted hypotheses.
Every URL or markdown citation in the generated summary must trace to the
retrieved set; otherwise QuantEra falls back to a deterministic template that
lists sources, labels, confidence, and the computed tone. The lens is for
research/education only, not financial advice or a price prediction.

## Leashed LLM Explanation

`quantera/lenses/fundamentals/explain.py` and
`quantera/lenses/technicals/explain.py` plus the Phase 3
`quantera/lenses/news_sentiment/` LLM modules are the only lens modules that call an LLM.
They call the provider-neutral `LLMClient.complete(...)` interface in
`quantera/llm/base.py`; no lens constructs provider SDK clients directly.

`quantera/llm/__init__.py` selects the provider from `LLM_PROVIDER`. The default
is `groq`, which uses `quantera/llm/groq_client.py`, reads `GROQ_API_KEY`, and
defaults to `llama-3.1-8b-instant` unless `GROQ_MODEL` is set. Groq lists that
model as a production text model with JSON mode support:
https://console.groq.com/docs/model/llama-3.1-8b-instant

`LLM_PROVIDER=anthropic` switches to `quantera/llm/anthropic_client.py`, which
reads `ANTHROPIC_API_KEY` and uses `ANTHROPIC_MODEL`. Provider SDK imports stay
inside their adapter files, so Groq and Anthropic remain swappable.

The model receives only finished metric or indicator values, deterministic verdict
levels, rationales, and comparison bases. It does not receive raw financial
statements or raw price series.
After generation, QuantEra extracts every number from the model output and checks
that each number traces to the structured input. If the explanation introduces an
untraceable number, the LLM text is discarded and a deterministic template summary
is returned instead.

If the SDK is unavailable, the API key is missing, the API call fails, or the
guardrail trips, the lens still returns a trustworthy template explanation.

## Thresholds and Sector Medians

Verdicts are deterministic. Sector medians are used for `pe_ratio`, `net_margin`,
and `debt_to_equity` when the Phase 0 sector is known; otherwise the lens falls
back to absolute thresholds. Higher-is-better and lower-is-better directions are
encoded per metric.

The Phase 1 sector medians are small, hand-entered, rounded baselines for the
sectors in the validation set. They are documented as approximate scaffolding,
not live market data or investment advice. They should be refreshed and expanded
before production use. The broad reference source for these baseline-style
comparisons is NYU Stern/Aswath Damodaran's public data library:
https://pages.stern.nyu.edu/~adamodar/New_Home_Page/data.html

## Cache

Cache files are JSON entries under `.cache/` by default. Keys are namespaced:

```text
financials:{ticker}
prices:{ticker}:{lookback_days}
news:{ticker}:{since}:{until}
```

TTL defaults live in `quantera/config.py`:

```text
fundamentals: 86400 seconds
prices:       14400 seconds
news:          7200 seconds
```

The cache treats expired, corrupt, or unreadable files as misses.

## Validation

Run the reusable validation harness:

```bash
python3 -c "from quantera.validation import run_validation; run_validation()"
```

The harness compares raw line items against `quantera/validation/reference_data.py`
using `VALUE_TOLERANCE` and reports `MATCH`, `MISMATCH`, `MISSING`, and
`PERIOD_MISMATCH` rates.

Run the lightweight price validation harness:

```bash
python3 -c "from quantera.validation import run_price_validation; run_price_validation()"
```

Price validation is intentionally lighter than fundamentals validation. Full
price-series ground truth is impractical to hand-enter and maintain, so
`quantera/validation/price_reference.py` holds small human-fillable adjusted-close
spot checks and fixed-window trading-day count checks. Entries are skipped until
`verified_by_human=True`, a source URL is present, and every expected value is
filled. With no verified spot checks, the harness reports `FAIL` by design.

The price harness always runs structural sanity checks separately: bars must be
strictly chronological and de-duplicated, OHLC and adjusted-close prices must be
positive, raw close must sit within raw low/high, and large weekday gaps are
flagged. It does not require `adj_close` to sit within raw OHLC, because adjusted
close can legitimately fall outside raw high/low after split or dividend
adjustments.

Recorded validation result, run on 2026-06-09 with the yfinance source: 8
human-verified FY2024 tickers, 7 skipped unverified tickers, 24 verified fields,
24 period-aligned fields, match rate among period-aligned fields 95.8%, verdict
`PASS`.

Known discrepancy notes: XOM revenue is a definition mismatch (`349,585,000,000`
verified total revenues vs `339,247,000,000` from yfinance's sales-style line).
NVDA FY2024 is served by yfinance as `FY2024 / 2024-01-31`, which aligns by
reporting month with the verified `FY2024 / 2024-01-28` reference.

## Tests

Unit tests use mock data sources only:

```bash
python3 -m pytest
```

Run the optional live yfinance smoke test explicitly:

```bash
python3 -m pytest -m integration
```

The Groq live smoke test and the fundamentals integration test require
`GROQ_API_KEY` when run explicitly because they exercise the real default LLM
adapter. The optional Finnhub news integration test requires `NEWS_API_KEY`.

## Contract Notes

- `FieldValue.value=None` means missing, and missing values are never converted to
  zero.
- Every financial line item carries `source` and `as_of` provenance.
- `quantera/datasource/yfinance_source.py` is the only production file that imports
  `yfinance`.
- Normalization may add warnings, but it does not calculate ratios or silently fix
  failed sanity checks.
- Ratio and indicator math plus verdict assignment are code-only. The LLM only
  explains completed numbers and completed verdicts.
- `quantera/news/finnhub_source.py` is the only production file that calls the
  news API.
- `quantera/llm/groq_client.py` is the only production file that imports the
  Groq SDK or calls Groq, and `quantera/llm/anthropic_client.py` is the only
  production file that imports the Anthropic SDK or calls Anthropic.
- News sentiment is explicitly sentiment, not fact, advice, or prediction.
