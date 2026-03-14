# QuantEra AI

**Multi-agent LLM trading platform for S&P 500 equities.**

8 specialized AI agents analyze 80+ factors across technical, fundamental, sentiment, macroeconomic, geopolitical, and predictive dimensions — then debate, aggregate, and execute through a risk-managed pipeline. Every decision comes with a full reasoning audit trail.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status: Pre-MVP](https://img.shields.io/badge/Status-Pre--MVP-orange)]()

---

## What this actually does

QuantEra runs an analysis cycle every 15 minutes during market hours. Each cycle:

1. **Collects data** from 7 free sources (yfinance, Finnhub, SEC EDGAR, Reddit, FRED, Alpaca, GPR Index)
2. **Computes 15 technical indicators** deterministically via pandas-ta
3. **Runs 8 specialized agents** in parallel — 3 rule-based, 5 LLM-powered (Groq free tier)
4. **Detects conflicts** — if agents disagree, a Bull-Bear adversarial debate resolves them
5. **Aggregates signals** with regime-adaptive weights (bull/bear/range/crisis shift automatically)
6. **Filters through risk management** — ATR position sizing, drawdown breakers, VIX gates
7. **Executes via Alpaca paper trading** and logs a complete JSON audit trail

Total cycle time: 30-90 seconds. Total monthly cost: $0.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA INGESTION LAYER                     │
│  yfinance │ Finnhub │ SEC EDGAR │ Reddit │ FRED │ Alpaca │ GPR │
└──────────────────────────┬──────────────────────────────────┘
                           │
                 SQLite Cache + Normalizer
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────┴────┐  ┌────────┴────────┐  ┌────┴─────┐
    │RULE-BASED│  │   LLM-POWERED   │  │COMPUTE   │
    │         │  │                 │  │          │
    │Technical│  │ Fundamental     │  │ Trend    │
    │Micro-   │  │ News & Events   │  │Prediction│
    │structure│  │ Social Sentiment│  │(ARIMA +  │
    │         │  │ Macro & Economic│  │ XGBoost) │
    │         │  │ Geopolitics     │  │          │
    └────┬────┘  └────────┬────────┘  └────┬─────┘
         │                │                │
         └────────────────┼────────────────┘
                          │
              Bull-Bear Adversarial Debate
                  (on agent conflict)
                          │
              Weighted Aggregation Engine
           (dynamic regime-adaptive weights)
                          │
               Risk Management Gate
        (ATR sizing, drawdown breakers, VIX)
                          │
              Alpaca Paper Trading
          BUY / SELL / HOLD + Audit Trail
```

---

## The 8 dimensions

| # | Dimension | Factors | Method | Primary source |
|---|-----------|---------|--------|----------------|
| 1 | **Technical analysis** | 15 indicators (RSI, MACD, Williams %R, VWAP, Bollinger Squeeze, OBV, ADX, ATR, etc.) | Rule-based + LLM fallback | yfinance → pandas-ta |
| 2 | **Fundamental analysis** | 14 factors (EV/EBITDA, FCF yield, earnings surprises, 10-K risk sections, analyst revisions) | LLM-powered | yfinance, Finnhub, EdgarTools |
| 3 | **News & events** | 10 signals (company news, sector impact, source credibility, temporal decay, M&A) | LLM-powered | Finnhub (60 calls/min free) |
| 4 | **Social sentiment** | 8 signals (Reddit volume spikes, sentiment polarity, put/call ratio, Fear & Greed) | LLM-powered | PRAW, Finnhub |
| 5 | **Macro & economic** | 8 factors (Fed policy, yield curve, CPI, NFP, VIX regime, sector rotation) | LLM + rule-based | FRED, yfinance |
| 6 | **Market microstructure** | 8 signals (insider buy clusters, short interest, 13F changes, gap analysis) | Rule-based | SEC EDGAR, FINRA |
| 7 | **Geopolitical risk** | ~20 signals (GPR Index, conflict monitoring, sanctions, supply chain disruption) | LLM + rule-based | GPR Index (free CSV), Finnhub |
| 8 | **Trend prediction** | ARIMA + Prophet + XGBoost ensemble (1d/5d/20d forecasts with 95% CI) | Computational (no LLM) | pmdarima, xgboost |

### Dynamic weight allocation

Weights shift automatically based on market regime detection (SPY 50/200 SMA + VIX + GPR level):

| Dimension | Bull | Bear | Range | Crisis |
|-----------|------|------|-------|--------|
| Technical | 25% | 25% | 35% | 15% |
| Fundamental | 13% | 16% | 13% | 7% |
| News & Events | 16% | 15% | 13% | 13% |
| Social Sentiment | 10% | 7% | 10% | 9% |
| Macro & Economic | 9% | 11% | 7% | 11% |
| Microstructure | 10% | 7% | 6% | 5% |
| Geopolitics | 7% | 10% | 7% | 18% |
| Trend Prediction | 10% | 9% | 9% | 22% |

---

## Technical indicators

The Technical Agent computes 15 indicators organized into 5 non-redundant categories. One indicator per market dimension — no redundancy.

**Momentum:** RSI(2) for mean-reversion entries (81% win rate backtested), RSI(14) for standard overbought/oversold, MACD(12,26,9) for trend momentum, Williams %R(5) for extreme entries (profit factor > 2.0), Rate of Change(9) for pure acceleration (2.5 reward/risk over 20 years).

**Trend:** EMA 9/21 crossover for entry timing, SMA 50/200 for secular direction and Golden/Death cross, ADX(14) as a regime filter (>25 trending, <20 ranging).

**Volatility:** Bollinger Bands(20,2σ) + Keltner Channel squeeze for breakout detection, ATR(14) for position sizing.

**Volume:** VWAP for institutional flow direction, OBV divergence for smart money detection, MFI(14) as volume-weighted RSI, custom volume anomaly ratio (>2x = significant).

**Structure:** Internal Bar Strength for mean-reversion (IBS < 0.2 = buy), support/resistance via scipy peak detection.

---

## Risk management

The risk manager has absolute veto power. No signal bypasses this gate.

| Rule | Trigger | Action |
|------|---------|--------|
| Position sizing | Every trade | Kelly-ATR: `size = (risk% × equity) / (1.5 × ATR)` |
| Max position | Per stock | 10% of portfolio hard cap |
| Stop-loss | Per trade | 2% below entry (ATR-adjusted) |
| Drawdown 5% | Portfolio level | Reduce risk 25% |
| Drawdown 10% | Portfolio level | Reduce 50%, high-conviction only |
| Drawdown 15% | Portfolio level | Halt trading 24-72 hours |
| VIX gate | VIX > 35 | Halve all position sizes |
| Earnings embargo | Within 2 days | No new trades |
| Time filter | First/last 15 min | No trades |
| Cooldown | After loss | Wait 1 hour |

---

## Data sources ($0/month)

| Source | Rate limit | Provides |
|--------|-----------|----------|
| yfinance | Unlimited* | OHLCV, fundamentals, options, sector ETFs |
| Groq API (free tier) | 30 req/min, 14.4K/day | Llama 3.1 70B inference |
| Gemini API (free tier) | 15 req/min, 1.5K/day | Fallback LLM |
| Finnhub (free tier) | 60 calls/min | News, sentiment, earnings, economic calendar |
| Alpaca (free tier) | 200 req/min | Paper trading, IEX quotes |
| PRAW | 60 req/min | Reddit r/wallstreetbets, r/stocks |
| FRED API | 120 req/min | 800K+ macro time series |
| SEC EDGAR | 10 req/sec | 10-K, 10-Q, 8-K, Form 4 filings |
| GPR Index | Monthly CSV | Caldara-Iacoviello Geopolitical Risk Index |

*yfinance can throttle under heavy use. SQLite cache minimizes redundant calls.

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.11+ |
| LLM interface | Groq SDK + Google GenAI (unified client with auto-fallback) |
| Agent framework | LangGraph |
| Technical indicators | pandas-ta (130+ indicators) |
| Trend forecasting | pmdarima + prophet + xgboost |
| SEC filings | EdgarTools |
| Reddit | PRAW |
| Portfolio analytics | pyfolio-reloaded |
| Cache | SQLite |
| Paper trading | alpaca-trade-api |
| Dashboard | Streamlit |
| Scheduling | APScheduler |

---

## Project structure

```
quantera-ai/
├── config/
│   ├── settings.py              # Tickers, intervals, thresholds, API keys
│   └── prompts/                 # Version-controlled LLM prompt templates
├── data/
│   ├── collectors/
│   │   ├── price_collector.py   # yfinance + Alpaca
│   │   ├── news_collector.py    # Finnhub news API
│   │   ├── sentiment_collector.py   # Reddit + Finnhub social
│   │   ├── fundamental_collector.py # yfinance + EdgarTools
│   │   ├── macro_collector.py   # FRED + yfinance
│   │   ├── micro_collector.py   # SEC EDGAR Form 4 + FINRA
│   │   └── geo_collector.py     # GPR Index + Finnhub geopolitical news
│   ├── cache/
│   │   └── data_cache.py        # SQLite TTL-based cache
│   └── normalizer.py            # Unified data format + timestamp alignment
├── agents/
│   ├── base_agent.py            # Abstract interface: analyze() → AgentSignal
│   ├── technical_agent.py       # 15 indicators + rule engine + LLM fallback
│   ├── fundamental_agent.py     # LLM analysis of financials + SEC filings
│   ├── news_agent.py            # LLM news sentiment with temporal decay
│   ├── sentiment_agent.py       # Reddit + social sentiment scoring
│   ├── macro_agent.py           # Fed policy + economic indicators
│   ├── micro_agent.py           # Insider trades + short interest
│   ├── geo_agent.py             # GPR Index + geopolitical event analysis
│   └── trend_agent.py           # ARIMA + XGBoost ensemble forecasting
├── core/
│   ├── llm_client.py            # Unified Groq/Gemini interface + rate limiting
│   ├── aggregator.py            # Weighted fusion + conflict detection
│   ├── debate.py                # Bull-Bear adversarial debate protocol
│   ├── regime_detector.py       # Bull/bear/range/crisis classification
│   ├── risk_manager.py          # Position sizing + drawdown gates
│   └── decision_engine.py       # Final BUY/SELL/HOLD with reasoning
├── execution/
│   ├── paper_trader.py          # Alpaca paper trading integration
│   └── order_manager.py         # Order tracking + state management
├── logging_system/
│   ├── decision_logger.py       # JSON audit trail per cycle
│   └── performance_tracker.py   # P&L, Sharpe, drawdown, win rate
├── backtest/
│   ├── backtester.py            # Walk-forward historical replay
│   └── metrics.py               # Performance computation
├── dashboard/
│   └── app.py                   # Streamlit: live status, history, analytics
├── tests/
├── main.py                      # Orchestrator + APScheduler
├── requirements.txt
├── .env.example
└── README.md
```

---

## Getting started

### Prerequisites

- Python 3.11+
- Free API keys: [Groq](https://console.groq.com), [Finnhub](https://finnhub.io), [Alpaca](https://alpaca.markets), [Reddit app](https://www.reddit.com/prefs/apps), [FRED](https://fred.stlouisfed.org/docs/api/api_key.html)

### Installation

```bash
git clone https://github.com/karan-patel11/QuantEra-AI.git
cd QuantEra-AI
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

```bash
cp .env.example .env
# Edit .env with your API keys
```

```env
GROQ_API_KEY=your_groq_key
FINNHUB_API_KEY=your_finnhub_key
ALPACA_API_KEY=your_alpaca_key
ALPACA_SECRET_KEY=your_alpaca_secret
REDDIT_CLIENT_ID=your_reddit_id
REDDIT_CLIENT_SECRET=your_reddit_secret
FRED_API_KEY=your_fred_key
```

### Run

```bash
# Start the trading system
python main.py

# Launch dashboard (separate terminal)
streamlit run dashboard/app.py
```

---

## How the LLM boundary works

This is the most important architectural decision. LLMs handle natural language interpretation. Deterministic code handles all math.

| Component | LLM? | Why |
|-----------|------|-----|
| RSI, MACD, Bollinger Bands | No | Math. pandas-ta computes exactly. |
| Position sizing, stop-loss | No | Math. ATR formula is deterministic. |
| News sentiment scoring | Yes | Interpreting "AAPL supply chain concerns ease" requires language understanding. |
| Earnings call tone analysis | Yes | Reading between the lines of management language. |
| Geopolitical impact assessment | Yes | Tracing how a tariff affects a specific company's supply chain. |
| ARIMA / XGBoost forecasting | No | Statistical models. No LLM needed. |
| Regime detection | No | SPY vs SMA + VIX threshold. Simple rules. |
| Bull-Bear debate | Yes | Argumentative reasoning about conflicting evidence. |

This split keeps Groq free-tier usage under 25 calls/day for 1 stock (limit: 14,400/day).

---

## Research foundations

This system draws from published academic work:

- **TradingAgents** (UCLA/MIT, 2024) — Multi-agent LLM framework with adversarial debate. Sharpe ratios 2.5x higher than baseline.
- **MarketSenseAI 2.0** (2024) — LLM agent stock analysis achieving 125.9% cumulative returns on S&P 100.
- **FINCON** (2024) — Dual-level risk control with conceptual verbal reinforcement.
- **QuantAgent** (2025) — Price-driven multi-agent LLMs achieving 80% directional accuracy at 1H/4H intervals.
- **Caldara & Iacoviello** (2022) — Geopolitical Risk Index measuring adverse events since 1900.
- **Kim, Muhn & Nikolaev** (2024) — GPT-4 achieves 60.35% earnings prediction accuracy, outperforming human analysts.

---

## Current status

| Milestone | Status |
|-----------|--------|
| System architecture design | Done |
| Technical specification (80+ factors) | Done |
| Data source mapping ($0 budget) | Done |
| Project structure | Done |
| Data pipeline implementation | In progress |
| Agent development | Not started |
| Aggregation engine | Not started |
| Paper trading integration | Not started |
| Streamlit dashboard | Not started |
| Backtesting engine | Not started |

---

## Roadmap

**Phase 1 (Days 1-3):** Data pipeline — collectors, cache, normalizer, LLM client.

**Phase 2 (Days 4-8):** Core agents — Technical (15 indicators), News, Sentiment, Fundamental.

**Phase 3 (Days 9-11):** Aggregation — weighted engine, risk gate, Bull-Bear debate, decision logger.

**Phase 4 (Days 12-14):** MVP — Alpaca paper trading, Streamlit dashboard, pyfolio analytics, end-to-end testing.

**Phase 5 (Month 2):** Remaining agents — Macro, Geopolitics, Microstructure, Trend Prediction. Multi-stock support.

**Phase 6 (Month 3+):** Optimization — confidence calibration, LSTM model, real-time data upgrade, backtesting.

---

## Limitations

This section exists because honesty matters more than hype.

- **Not financial advice.** This is an educational and research project. Do not trade real money without extensive paper trading validation.
- **Free data is delayed.** yfinance provides 15-minute delayed quotes. High-frequency strategies are impossible.
- **LLMs hallucinate.** Mitigated by adversarial debate + Trend Prediction anchor + strict JSON validation, but not eliminated.
- **Backtest bias.** LLMs were trained on historical market data. Backtests will be optimistically biased. Walk-forward validation only.
- **Single-stock MVP.** Starting with 1 stock means 100% concentration risk. Multi-stock in Phase 5.

---

## Contributing

This project is in active early development. If you want to contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/agent-name`)
3. Commit your changes
4. Open a pull request

Priority areas: agent implementation, backtesting engine, dashboard components.

---

## License

MIT License. See [LICENSE](LICENSE) for details.

---

<p align="center">
  <b>QuantEra AI</b> — Transparent, multi-agent intelligence for equity markets.<br>
  Built by <a href="https://github.com/karan-patel11">Karan Patel</a>
</p>
