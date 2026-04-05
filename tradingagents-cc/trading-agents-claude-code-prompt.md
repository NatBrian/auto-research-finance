# PREAMBLE FOR YOUR AI CODING ASSISTANT

You are an expert **Multi-Agent Systems Architect** and **Quantitative Trading Engineer**. Your task is to generate a **complete, immediately runnable** project repository for an autonomous multi-agent trading system called the **TradingAgents-CC** (Claude Code Edition).

This system re-implements the TauricResearch TradingAgents framework (arxiv:2412.20138) natively inside **Claude Code** — replacing LangGraph's node/edge DAG with **Claude Code Skills** as agent roles, a **Markdown state file** as the shared communication bus, **MCP servers** as tool providers (market data, news, sentiment, exchange), and a **SQLite database** as the persistent memory and audit log. The system analyses a target ticker using five specialized agent teams — Analysts, Researchers (Bull/Bear debate), Trader, Risk Management, and Portfolio Manager — then submits the final approved order to a configurable stock exchange MCP.

**Read every section in full before writing a single line of code. Implementation details in later sections override earlier ones where they conflict. This system is for research and educational purposes only — it is not financial advice.**

---

## SECTION 1: ARCHITECTURE PHILOSOPHY

### Why Claude Code instead of LangGraph

The original TradingAgents uses LangGraph to wire agent nodes into a DAG with shared state. In Claude Code Edition, we replace each architectural element:

| TradingAgents (LangGraph) | TradingAgents-CC (Claude Code) |
|---|---|
| LangGraph `StateGraph` nodes | Claude Code Skill `.md` files |
| LangGraph `AgentState` TypedDict | `session/trading_session.md` (structured Markdown + embedded JSON) |
| LangGraph edges / conditional routing | Orchestrator skill reads phase field and dispatches |
| Tool-calling via LangChain tools | MCP server tools registered in `.claude.json` |
| `o1-preview` for deep thinking | Claude Code's native reasoning (no extra model needed) |
| `gpt-4o-mini` for fast data retrieval | Lightweight Python scripts called via Bash tool |
| Debate loop (N rounds) | Orchestrator calls debate skill N times, appending to state |
| In-memory state corruption over long contexts | File-persisted state, re-read at start of every skill |
| FinnHub + Alpha Vantage APIs | MCP `market_data_server` wrapping yfinance + Alpha Vantage |
| Web search tool | MCP `news_server` wrapping NewsAPI + DuckDuckGo |
| Reddit/Twitter sentiment | MCP `sentiment_server` wrapping PRAW + snscrape |
| Simulated exchange | MCP `exchange_server` (pluggable: paper / Alpaca / IBKR) |
| SQLite memory in original | `data/memory.db` — full audit trail, agent reports, debate history |

### Critical Constraint on Skill Architecture

Claude Code skills are **Markdown instruction files**, not executable scripts. Claude Code reads them and follows the instructions. They cannot call each other like functions. The orchestrator reads each sub-skill file using the `Read` tool and executes the instructions it finds there. State is persisted **exclusively** through:
1. `session/trading_session.md` — live session state and all agent reports
2. `data/memory.db` — SQLite persistent memory across sessions

---

## SECTION 2: TECHNICAL STACK

| Component | Technology | Version Constraint |
|---|---|---|
| Agent Runtime | Claude Code CLI | Latest |
| Language | Python | 3.10+ |
| Data Processing | pandas, numpy, scipy | Latest stable |
| Market Data | yfinance, alpha_vantage | Latest stable |
| Technical Indicators | pandas-ta | Latest stable |
| News | newsapi-python, duckduckgo-search | Latest stable |
| Sentiment | textblob, vaderSentiment | Latest stable |
| Exchange: Paper | Internal simulation | Built-in |
| Exchange: Live | alpaca-trade-api OR ibkr (user choice) | Latest stable |
| MCP Framework | mcp (official Anthropic lib) | Latest stable |
| Database | sqlite3 | Standard library |
| Config | PyYAML | Latest stable |
| Testing | pytest | Latest stable |
| Environment | Python venv | Standard library |

---

## SECTION 3: COMPLETE PROJECT STRUCTURE

Generate every file in this tree. No file may be omitted.

```
tradingagents-cc/
├── .claude/
│   └── skills/
│       ├── trade-now.md                  # Master orchestrator
│       ├── analyst-fundamentals.md       # Fundamental analyst agent
│       ├── analyst-sentiment.md          # Sentiment analyst agent
│       ├── analyst-news.md               # News analyst agent
│       ├── analyst-technical.md          # Technical analyst agent
│       ├── researcher-debate.md          # Bull/Bear debate orchestration
│       ├── trader-decision.md            # Trader synthesis + decision
│       ├── risk-debate.md                # Risk team debate (Risky/Neutral/Safe)
│       └── portfolio-manager.md          # Final approval + order submission
├── src/
│   ├── __init__.py
│   ├── market_data.py                    # Price/volume/fundamentals fetcher
│   ├── news_fetcher.py                   # News article retrieval
│   ├── sentiment_engine.py               # Sentiment scoring
│   ├── technical_indicators.py           # TA computation (MACD, RSI, BB, etc.)
│   ├── memory_db.py                      # SQLite read/write helpers
│   ├── state_manager.py                  # trading_session.md read/write helpers
│   ├── order_validator.py                # Pre-submission order sanity checks
│   └── utils.py                          # Shared utilities
├── mcp_servers/
│   ├── market_data_server/
│   │   ├── server.py
│   │   └── requirements.txt
│   ├── news_server/
│   │   ├── server.py
│   │   └── requirements.txt
│   ├── sentiment_server/
│   │   ├── server.py
│   │   └── requirements.txt
│   └── exchange_server/
│       ├── server.py
│       ├── adapters/
│       │   ├── __init__.py
│       │   ├── paper_adapter.py          # Built-in paper trading
│       │   ├── alpaca_adapter.py         # Alpaca brokerage
│       │   └── ibkr_adapter.py           # Interactive Brokers
│       └── requirements.txt
├── session/
│   ├── trading_session.md                # Live session state (auto-created)
│   └── .gitkeep
├── data/
│   ├── memory.db                         # SQLite persistent memory (auto-created)
│   ├── paper_portfolio.json              # Paper trading portfolio state
│   └── cache/
│       └── .gitkeep
├── outputs/
│   ├── reports/
│   │   └── .gitkeep
│   └── .gitkeep
├── config/
│   └── settings.yaml
├── tests/
│   ├── __init__.py
│   ├── test_market_data.py
│   ├── test_sentiment_engine.py
│   ├── test_technical_indicators.py
│   ├── test_memory_db.py
│   ├── test_order_validator.py
│   └── test_exchange_adapters.py
├── .claude.json
├── .env.example
├── requirements.txt
├── setup.py
└── README.md
```

---

## SECTION 4: STATE MANAGEMENT SPECIFICATION

This is the most critical section. The entire orchestration depends on a well-defined state file. All skills must read and write this file as their **first and last action**.

### `session/trading_session.md` — Canonical Schema

This file is the system's single source of truth for a live trading session. It must always conform to this exact schema. The orchestrator initializes it at the start of each `trade-now` invocation.

```markdown
# Trading Session

## Session Info
- **session_id**: null
- **ticker**: null
- **analysis_date**: null
- **phase**: INIT
- **status**: IN_PROGRESS
- **started_at**: null
- **completed_at**: null

## Configuration
- **exchange_adapter**: paper
- **debate_rounds**: 2
- **risk_debate_rounds**: 2
- **max_position_size_pct**: 10.0
- **portfolio_value**: null

## Analyst Reports
### Fundamentals Report
```json
{}
```

### Sentiment Report
```json
{}
```

### News Report
```json
{}
```

### Technical Report
```json
{}
```

## Researcher Debate
### Bull Case
```
(none)
```
### Bear Case
```
(none)
```
### Debate Transcript
```
(none)
```
### Researcher Verdict
- **recommendation**: null
- **confidence**: null
- **key_arguments**: null

## Trader Decision
- **action**: null
- **quantity**: null
- **reasoning**: null
- **conviction_score**: null
```json
{}
```

## Risk Assessment
### Risk Debate Transcript
```
(none)
```
### Risk Verdict
- **approved_action**: null
- **adjusted_quantity**: null
- **stop_loss**: null
- **take_profit**: null
- **risk_notes**: null

## Portfolio Manager Decision
- **final_action**: null
- **final_quantity**: null
- **order_type**: null
- **approved**: null
- **rejection_reason**: null

## Order Submission
- **order_id**: null
- **submitted_at**: null
- **exchange_response**: null
```json
{}
```

## Audit Trail
| Timestamp | Phase | Agent | Action | Notes |
|---|---|---|---|---|
```

### Phase Transition Rules

```
INIT → ANALYSIS → RESEARCH → TRADING → RISK_REVIEW → PM_APPROVAL → ORDER_SUBMITTED | REJECTED | FAILED
```

- `INIT`: Session created, config loaded
- `ANALYSIS`: All 4 analyst agents run (conceptually parallel — orchestrator runs them sequentially, writing each report to state before moving on)
- `RESEARCH`: Bull and Bear researchers debate using analyst reports
- `TRADING`: Trader agent synthesizes all reports and makes a decision
- `RISK_REVIEW`: Risk team debates the trader's decision
- `PM_APPROVAL`: Portfolio Manager reviews risk verdict and approves/rejects
- `ORDER_SUBMITTED`: Order successfully sent to exchange
- `REJECTED`: PM rejected the order (risk too high, criteria not met)
- `FAILED`: Unrecoverable error

---

## SECTION 5: CLAUDE CODE SKILLS

### `.claude/skills/trade-now.md`

```markdown
---
name: trade-now
description: Master orchestrator for the TradingAgents-CC multi-agent trading system
param: ticker (string) - The stock ticker to analyze, e.g. "NVDA"
param: date (string, optional) - The analysis date in YYYY-MM-DD format. Defaults to today.
param: exchange (string, optional) - Exchange adapter: "paper", "alpaca", "ibkr". Defaults to "paper".
version: 1.0
---

# TradingAgents-CC Master Orchestrator

You are executing the TradingAgents-CC pipeline. You ARE the multi-agent orchestrator. You do not delegate to external pipelines — you read each skill file and execute it in sequence, writing results to the session state file after each phase. Follow every step in order. Do not skip steps.

## Pre-flight Check

1. Read `config/settings.yaml` to load all configuration values.
2. Determine the analysis date: use the `date` parameter if provided, otherwise use today's date.
3. Determine the exchange adapter: use the `exchange` parameter if provided, else use `config.exchange.default_adapter`.
4. Check if all four MCP servers are reachable by calling `ping_market_data`, `ping_news`, `ping_sentiment`, and `ping_exchange`. If ANY fails, output:
   ```
   ⚠️  One or more MCP servers are not running. Please start all four:
       Terminal 1: python mcp_servers/market_data_server/server.py
       Terminal 2: python mcp_servers/news_server/server.py
       Terminal 3: python mcp_servers/sentiment_server/server.py
       Terminal 4: python mcp_servers/exchange_server/server.py
   Then re-run this skill.
   ```
   HALT.

5. Query the exchange for current portfolio value by calling `get_portfolio_summary`.

6. Initialize `session/trading_session.md` using the canonical schema from the project documentation (Section 4). Set:
   - `session_id`: Generate as `{ticker}_{date}_{unix_timestamp}`
   - `ticker`: the provided ticker parameter
   - `analysis_date`: the determined date
   - `phase`: ANALYSIS
   - `exchange_adapter`: the determined exchange adapter
   - `debate_rounds`: value from config
   - `risk_debate_rounds`: value from config
   - `portfolio_value`: value from exchange query
   - `started_at`: current timestamp

7. Write initial audit trail entry: `| {now} | INIT | Orchestrator | Session started | ticker={ticker}, date={date}, exchange={exchange} |`

8. Write this session to the SQLite memory database by calling `src.memory_db.save_session_start(session_id, ticker, date, exchange)`.

---

## Phase: ANALYSIS (Run all 4 analysts)

For each analyst below, read the skill file and execute it fully before moving to the next. Write the resulting report JSON into the corresponding section of `session/trading_session.md` before proceeding.

### Step A1: Fundamentals Analyst
1. Read `.claude/skills/analyst-fundamentals.md` using the Read tool.
2. Execute all instructions in that file for `ticker` and `date`.
3. Write the returned JSON report into "Fundamentals Report" in `session/trading_session.md`.
4. Append audit entry: `| {now} | ANALYSIS | FundamentalsAnalyst | Report written | sharpe={report.overall_score} |`

### Step A2: Sentiment Analyst
1. Read `.claude/skills/analyst-sentiment.md` using the Read tool.
2. Execute all instructions in that file.
3. Write the returned JSON report into "Sentiment Report" in `session/trading_session.md`.
4. Append audit entry.

### Step A3: News Analyst
1. Read `.claude/skills/analyst-news.md` using the Read tool.
2. Execute all instructions in that file.
3. Write the returned JSON report into "News Report" in `session/trading_session.md`.
4. Append audit entry.

### Step A4: Technical Analyst
1. Read `.claude/skills/analyst-technical.md` using the Read tool.
2. Execute all instructions in that file.
3. Write the returned JSON report into "Technical Report" in `session/trading_session.md`.
4. Append audit entry.

### Post-Analysis
- Update `phase` to RESEARCH in `session/trading_session.md`.
- Display a summary table of all four analyst reports to the user.

---

## Phase: RESEARCH (Bull/Bear Debate)

1. Read `.claude/skills/researcher-debate.md` using the Read tool.
2. Execute all instructions in that file, passing the full analyst reports and the `debate_rounds` config value.
3. Write the Bull Case, Bear Case, Debate Transcript, and Researcher Verdict into `session/trading_session.md`.
4. Update `phase` to TRADING.
5. Append audit entry: `| {now} | RESEARCH | ResearcherTeam | Debate complete | verdict={verdict.recommendation}, confidence={verdict.confidence} |`

---

## Phase: TRADING (Trader Decision)

1. Read `.claude/skills/trader-decision.md` using the Read tool.
2. Execute all instructions in that file.
3. Write the Trader Decision section of `session/trading_session.md` including action, quantity, reasoning, and conviction_score.
4. Update `phase` to RISK_REVIEW.
5. Append audit entry: `| {now} | TRADING | TraderAgent | Decision made | action={action}, quantity={quantity}, conviction={conviction} |`

---

## Phase: RISK_REVIEW (Risk Management Debate)

1. Read `.claude/skills/risk-debate.md` using the Read tool.
2. Execute all instructions in that file.
3. Write the Risk Debate Transcript and Risk Verdict into `session/trading_session.md`.
4. Update `phase` to PM_APPROVAL.
5. Append audit entry.

---

## Phase: PM_APPROVAL (Portfolio Manager)

1. Read `.claude/skills/portfolio-manager.md` using the Read tool.
2. Execute all instructions in that file.
3. Write the Portfolio Manager Decision into `session/trading_session.md`.

### If approved:
- Update `phase` to ORDER_SUBMITTED.
- The portfolio-manager skill handles order submission. Verify that `order_id` is populated in the state.
- Set `completed_at` to current timestamp.
- Set `status` to COMPLETE.
- Save final session to SQLite: `src.memory_db.save_session_complete(session_id, full_state_json)`.
- Save full report to `outputs/reports/{session_id}_report.md`.
- Display final summary to user (see Final Report format below).

### If rejected:
- Update `phase` to REJECTED, `status` to COMPLETE.
- Set `completed_at`.
- Log rejection reason.
- Save to SQLite.
- Display rejection summary to user.

### On any unrecoverable error:
- Update `phase` to FAILED.
- Log full error with traceback.
- Save to SQLite.

---

## Final Report Format

Display this to the user on completion:

```
╔══════════════════════════════════════════════════════════╗
║          TRADINGAGENTS-CC SESSION COMPLETE               ║
╠══════════════════════════════════════════════════════════╣
║  Ticker:        {ticker}                                 ║
║  Date:          {date}                                   ║
║  Final Action:  {final_action}                           ║
║  Quantity:      {final_quantity} shares                  ║
║  Order Type:    {order_type}                             ║
║  Order ID:      {order_id}                               ║
╠══════════════════════════════════════════════════════════╣
║  ANALYST CONSENSUS                                       ║
║  Fundamentals:  {fundamentals_summary}                   ║
║  Sentiment:     {sentiment_score} ({sentiment_label})    ║
║  News:          {news_impact}                            ║
║  Technical:     {technical_signal}                       ║
╠══════════════════════════════════════════════════════════╣
║  RESEARCH VERDICT: {researcher_recommendation}           ║
║  TRADER CONVICTION: {conviction_score}/10                ║
║  RISK RATING:   {risk_rating}                            ║
╚══════════════════════════════════════════════════════════╝
```
```

---

### `.claude/skills/analyst-fundamentals.md`

```markdown
---
name: analyst-fundamentals
description: Fundamental analyst agent — evaluates company financials and intrinsic value
---

# Fundamental Analyst Instructions

## Role
You are a Fundamental Analyst at a trading firm. Your job is to evaluate the financial health, valuation, and business quality of the target company. You are thorough, data-driven, and skeptical of hype.

## Input
Read `session/trading_session.md` to get `ticker` and `analysis_date`.

## Steps

### 1. Fetch Financial Data
Call the MCP tool `get_financials` with:
- `ticker`: from session state
- `date`: from session state

This returns: income statement (last 4 quarters), balance sheet (latest), cash flow statement (latest), and key ratios.

### 2. Fetch Insider Transactions
Call the MCP tool `get_insider_transactions` with `ticker` and a lookback of 90 days.

### 3. Fetch Earnings History
Call the MCP tool `get_earnings_history` with `ticker` (last 8 quarters).

### 4. Fetch Valuation Metrics
Call the MCP tool `get_valuation_metrics` with `ticker` and `date`.
Returns: P/E, P/B, P/S, EV/EBITDA, PEG ratio, forward P/E.

### 5. Analysis

Evaluate and score each dimension below on a scale of 1–5 (1=very negative, 3=neutral, 5=very positive):

**Profitability** (weight: 25%)
- Gross margin trend (improving/declining over 4 quarters)
- Operating margin vs industry peers
- ROE and ROA

**Growth** (weight: 25%)
- YoY revenue growth
- EPS growth trend
- Free cash flow growth

**Financial Health** (weight: 20%)
- Current ratio and quick ratio
- Debt-to-equity ratio
- Interest coverage ratio

**Valuation** (weight: 20%)
- P/E vs sector average
- PEG ratio (growth-adjusted valuation)
- Intrinsic value estimate: use a simplified DCF with 5-year FCF projection at analyst consensus growth rate, discounted at 10%

**Insider Signal** (weight: 10%)
- Net insider buying/selling in last 90 days
- Significant insider transactions (> $1M)

### 6. Earnings Surprise Pattern
- Compute average earnings surprise over last 8 quarters
- Flag if company has missed estimates 2+ times consecutively

### 7. Compose Report

Return this exact JSON structure (no markdown backticks, pure JSON):
```json
{
  "agent": "FundamentalsAnalyst",
  "ticker": "...",
  "analysis_date": "...",
  "scores": {
    "profitability": {"score": 0, "notes": "..."},
    "growth": {"score": 0, "notes": "..."},
    "financial_health": {"score": 0, "notes": "..."},
    "valuation": {"score": 0, "notes": "..."},
    "insider_signal": {"score": 0, "notes": "..."}
  },
  "overall_score": 0.0,
  "weighted_signal": "BULLISH | NEUTRAL | BEARISH",
  "intrinsic_value_estimate": 0.0,
  "current_price": 0.0,
  "upside_downside_pct": 0.0,
  "key_risks": ["..."],
  "key_strengths": ["..."],
  "earnings_surprise_avg": 0.0,
  "consecutive_misses": 0,
  "summary": "One paragraph summary of financial health and investment thesis"
}
```

Compute `overall_score` as the weighted average of all dimension scores.
Set `weighted_signal` to: BULLISH if overall_score >= 3.5, BEARISH if <= 2.5, NEUTRAL otherwise.

## Output
Write the JSON report into "Fundamentals Report" section of `session/trading_session.md`.
```

---

### `.claude/skills/analyst-sentiment.md`

```markdown
---
name: analyst-sentiment
description: Sentiment analyst agent — gauges market mood from social media and options flow
---

# Sentiment Analyst Instructions

## Role
You are a Sentiment Analyst. You quantify the collective emotional temperature of market participants using social media, options activity, and short interest data. You are data-driven and resist confirmation bias.

## Input
Read `session/trading_session.md` to get `ticker` and `analysis_date`.

## Steps

### 1. Fetch Social Media Sentiment
Call `get_social_sentiment` with `ticker`, `date`, and `lookback_days: 7`.
Returns: daily sentiment scores (positive, negative, neutral), post volume, engagement metrics from aggregated sources.

### 2. Fetch Options Flow
Call `get_options_flow` with `ticker` and `date`.
Returns: put/call ratio (PCR), unusual options activity flag, net options delta.

### 3. Fetch Short Interest
Call `get_short_interest` with `ticker`.
Returns: short_interest_pct, days_to_cover, short_interest_change_30d.

### 4. Fetch Analyst Ratings
Call `get_analyst_ratings` with `ticker`.
Returns: consensus_rating, price_target_avg, price_target_high, price_target_low, ratings_breakdown (buy/hold/sell counts), recent_rating_changes.

### 5. Compute Composite Sentiment Score

**Social Sentiment Score** (weight: 35%):
- Compute 7-day weighted average of daily sentiment (recent days weighted higher)
- Score 1–5: <-0.3 = 1, -0.3 to -0.1 = 2, -0.1 to 0.1 = 3, 0.1 to 0.3 = 4, >0.3 = 5

**Options Sentiment Score** (weight: 30%):
- PCR > 1.5: bearish (score 1), PCR 1.0–1.5: slightly bearish (2), PCR 0.7–1.0: neutral (3), PCR 0.4–0.7: slightly bullish (4), PCR < 0.4: bullish (5)
- Unusual call activity: +0.5 bonus; unusual put activity: -0.5 penalty

**Short Interest Score** (weight: 20%):
- short_interest_pct < 2%: 5 (low short pressure), 2–5%: 4, 5–10%: 3, 10–20%: 2, >20%: 1
- Note: extremely high short interest can also signal short-squeeze potential — add nuance in notes

**Analyst Consensus Score** (weight: 15%):
- Convert consensus_rating: Strong Buy=5, Buy=4, Hold=3, Underperform=2, Sell=1
- Weight by recency of rating changes

### 6. Compose Report

Return this exact JSON:
```json
{
  "agent": "SentimentAnalyst",
  "ticker": "...",
  "analysis_date": "...",
  "social_sentiment": {
    "7d_avg_score": 0.0,
    "trend": "IMPROVING | DETERIORATING | STABLE",
    "post_volume_7d": 0,
    "score": 0
  },
  "options_flow": {
    "put_call_ratio": 0.0,
    "unusual_activity": false,
    "net_delta": 0.0,
    "score": 0
  },
  "short_interest": {
    "short_interest_pct": 0.0,
    "days_to_cover": 0.0,
    "30d_change_pct": 0.0,
    "squeeze_risk": "LOW | MODERATE | HIGH",
    "score": 0
  },
  "analyst_ratings": {
    "consensus": "...",
    "price_target_avg": 0.0,
    "upside_to_target_pct": 0.0,
    "recent_upgrades": 0,
    "recent_downgrades": 0,
    "score": 0
  },
  "composite_sentiment_score": 0.0,
  "sentiment_label": "VERY_BULLISH | BULLISH | NEUTRAL | BEARISH | VERY_BEARISH",
  "key_observations": ["..."],
  "summary": "One paragraph sentiment analysis summary"
}
```

## Output
Write JSON report into "Sentiment Report" in `session/trading_session.md`.
```

---

### `.claude/skills/analyst-news.md`

```markdown
---
name: analyst-news
description: News analyst agent — evaluates macro events and company-specific news impact
---

# News Analyst Instructions

## Role
You are a News Analyst. You scan, categorize, and assess the market impact of recent news stories affecting the target company. You distinguish signal from noise and identify regime-changing events.

## Input
Read `session/trading_session.md` to get `ticker` and `analysis_date`.

## Steps

### 1. Fetch Company News
Call `search_company_news` with `ticker`, `date`, `lookback_days: 14`, `max_articles: 20`.
Returns: list of articles with title, source, published_at, url, snippet.

### 2. Fetch Macro News
Call `search_macro_news` with `date`, `lookback_days: 7`, `topics: ["federal reserve", "interest rates", "inflation", "gdp", "recession", "tariffs", "geopolitics"]`.

### 3. Fetch SEC Filings
Call `get_recent_sec_filings` with `ticker`, `lookback_days: 30`.
Returns: list of filing types (8-K, 10-Q, S-1, etc.) with dates and summaries.

### 4. Categorize and Score Each Company News Item

For each of the top 10 most relevant company articles, assess:
- **Category**: Earnings | M&A | Product | Regulatory | Legal | Management | Macro | Competitor | Other
- **Sentiment**: POSITIVE / NEGATIVE / NEUTRAL (from your analysis of content)
- **Impact Magnitude**: LOW / MEDIUM / HIGH / CRITICAL
- **Time Horizon**: IMMEDIATE (1–3 days) / SHORT (1–4 weeks) / LONG (1–6 months)

### 5. Macro Environment Assessment
Based on macro news, assess:
- Federal Reserve stance: HAWKISH / NEUTRAL / DOVISH
- Economic momentum: ACCELERATING / STABLE / DECELERATING
- Risk-on/Risk-off environment: RISK_ON / NEUTRAL / RISK_OFF
- Any sector-specific tailwinds or headwinds

### 6. Identify Catalyst Events
Upcoming events in the next 30 days (from financial calendar):
Call `get_event_calendar` with `ticker` and `lookahead_days: 30`.
Returns: earnings dates, dividend dates, product launches, analyst days, index rebalancing events.

### 7. Compose Report

```json
{
  "agent": "NewsAnalyst",
  "ticker": "...",
  "analysis_date": "...",
  "company_news_summary": [
    {
      "headline": "...",
      "category": "...",
      "sentiment": "...",
      "impact": "...",
      "time_horizon": "..."
    }
  ],
  "macro_environment": {
    "fed_stance": "...",
    "economic_momentum": "...",
    "risk_environment": "...",
    "key_macro_risks": ["..."]
  },
  "upcoming_catalysts": [
    {"event": "...", "date": "...", "expected_impact": "..."}
  ],
  "sec_filings_flag": false,
  "sec_filing_summary": "...",
  "overall_news_sentiment": "POSITIVE | NEUTRAL | NEGATIVE",
  "news_impact_score": 0.0,
  "key_stories": ["..."],
  "summary": "One paragraph news analysis summary"
}
```

`news_impact_score` ranges from -5 (very negative news) to +5 (very positive news).

## Output
Write JSON into "News Report" in `session/trading_session.md`.
```

---

### `.claude/skills/analyst-technical.md`

```markdown
---
name: analyst-technical
description: Technical analyst agent — computes and interprets technical indicators
---

# Technical Analyst Instructions

## Role
You are a Technical Analyst. You compute and interpret technical indicators to identify trends, momentum, support/resistance, and entry/exit timing signals. You are systematic and follow defined rules.

## Input
Read `session/trading_session.md` to get `ticker` and `analysis_date`.

## Steps

### 1. Fetch Price Data
Call `get_price_history` with:
- `ticker`: from session state
- `end_date`: analysis_date
- `lookback_days`: 365
- `interval`: "1d"

Returns: OHLCV DataFrame.

### 2. Compute Technical Indicators
Call `compute_indicators` with the price data. This tool calls `src/technical_indicators.py` internally and returns:

**Trend Indicators:**
- SMA_20, SMA_50, SMA_200 (Simple Moving Averages)
- EMA_12, EMA_26 (Exponential Moving Averages)
- MACD, MACD_signal, MACD_histogram
- ADX (Average Directional Index, 14-period)

**Momentum Indicators:**
- RSI_14 (Relative Strength Index)
- Stochastic_K, Stochastic_D (14,3,3)
- ROC_10 (Rate of Change, 10-day)

**Volatility Indicators:**
- Bollinger_Upper, Bollinger_Mid, Bollinger_Lower (20,2)
- ATR_14 (Average True Range)
- Historical_Volatility_20d

**Volume Indicators:**
- OBV (On-Balance Volume)
- VWAP (Volume-Weighted Average Price)
- Volume_SMA_20

**Support/Resistance:**
- 52-week high and low
- Recent swing highs (last 3 within 90 days)
- Recent swing lows (last 3 within 90 days)

### 3. Interpret Each Indicator

Apply these exact interpretation rules to generate signal votes:

**Trend (vote: +1 bullish, 0 neutral, -1 bearish)**
- Price > SMA_200: +1 (uptrend); Price < SMA_200: -1
- SMA_50 > SMA_200 (golden cross condition): +1; else -1
- MACD > MACD_signal AND MACD_histogram increasing: +1; MACD < MACD_signal: -1; else 0

**Momentum (vote: +1, 0, -1)**
- RSI_14 > 70: -1 (overbought); RSI_14 < 30: +1 (oversold); 40–60: +1 (healthy momentum); else 0
- Stochastic_K > Stochastic_D AND K < 80: +1; K > 80: -1; else 0
- ADX > 25 AND price uptrend: +1; ADX > 25 AND price downtrend: -1; ADX < 20: 0

**Volatility (vote: contextual)**
- Price near Bollinger_Upper (within 1%): -1 (overbought zone)
- Price near Bollinger_Lower (within 1%): +1 (oversold zone)
- Price at midband with expanding bands: 0 (transitional)
- ATR_14 / price > 3%: flag as HIGH_VOLATILITY

**Volume (vote: +1, 0, -1)**
- Volume > Volume_SMA_20 * 1.5 AND price rising: +1 (confirmed breakout)
- Volume > Volume_SMA_20 * 1.5 AND price falling: -1 (confirmed breakdown)
- OBV trend matches price trend: +1; divergence: -1

### 4. Compute Technical Score and Signal

- `trend_score`: average of trend votes
- `momentum_score`: average of momentum votes
- `volume_confirmation`: volume vote
- `total_signal_score`: weighted sum (trend: 40%, momentum: 35%, volume: 25%)
- `technical_signal`: STRONG_BUY (>0.6), BUY (0.2 to 0.6), NEUTRAL (-0.2 to 0.2), SELL (-0.2 to -0.6), STRONG_SELL (<-0.6)

### 5. Identify Chart Pattern (if any)
Scan for: Double Bottom/Top, Head & Shoulders, Cup & Handle, Bull/Bear Flag, Triangle breakout.
Flag if any pattern is identified with confidence > 70%.

### 6. Compose Report

```json
{
  "agent": "TechnicalAnalyst",
  "ticker": "...",
  "analysis_date": "...",
  "current_price": 0.0,
  "indicators": {
    "sma_20": 0.0, "sma_50": 0.0, "sma_200": 0.0,
    "rsi_14": 0.0,
    "macd": 0.0, "macd_signal": 0.0, "macd_histogram": 0.0,
    "adx": 0.0,
    "bb_upper": 0.0, "bb_lower": 0.0,
    "atr_14": 0.0,
    "52w_high": 0.0, "52w_low": 0.0
  },
  "votes": {
    "trend": 0, "momentum": 0, "volume": 0
  },
  "scores": {
    "trend_score": 0.0,
    "momentum_score": 0.0,
    "volume_confirmation": 0,
    "total_signal_score": 0.0
  },
  "technical_signal": "...",
  "chart_pattern": null,
  "key_levels": {
    "support_1": 0.0,
    "support_2": 0.0,
    "resistance_1": 0.0,
    "resistance_2": 0.0
  },
  "high_volatility_flag": false,
  "summary": "One paragraph technical analysis summary"
}
```

## Output
Write JSON into "Technical Report" in `session/trading_session.md`.
```

---

### `.claude/skills/researcher-debate.md`

```markdown
---
name: researcher-debate
description: Bull and Bear researcher debate to synthesize analyst reports into a verdict
---

# Researcher Debate Instructions

## Role
You are facilitating a structured debate between a Bullish Researcher and a Bearish Researcher. Both have read all four analyst reports. They will argue their cases for `debate_rounds` rounds, then you will produce a balanced verdict.

## Input
Read `session/trading_session.md`:
- All four analyst reports (Fundamentals, Sentiment, News, Technical)
- `ticker`, `analysis_date`, `debate_rounds`

## Pre-Debate: Individual Position Formation

### Bull Researcher (constructs opening position):
Review all analyst reports. Select the most compelling bullish evidence:
- Strongest positive signals from each analyst
- Identify the primary bull thesis (e.g., "Strong earnings growth + positive sentiment + MACD crossover")
- Estimate price target and timeframe

### Bear Researcher (constructs opening position):
Review all analyst reports. Select the most compelling bearish evidence:
- Strongest risk factors and negative signals
- Identify the primary bear thesis (e.g., "High valuation + negative news catalyst + RSI overbought")
- Estimate downside risk and stop-loss level

## Debate Rounds

Execute exactly `debate_rounds` rounds. In each round:

**Round format:**
1. **Bull argues**: Presents or refines their thesis. Must address the Bear's previous point if this is round 2+.
2. **Bear argues**: Presents or refines their counter. Must address the Bull's previous point if this is round 2+.

**Rules for the debate:**
- Arguments must cite specific data from the analyst reports (not vague claims)
- Each argument should be 3–5 sentences maximum
- Arguments may NOT repeat the same point made in a prior round without new supporting evidence
- The debate must evolve — new data points or counter-arguments must be introduced each round

Write the full debate transcript as:
```
=== ROUND {N} ===

BULL: [argument]

BEAR: [counter-argument]
```

## Post-Debate: Verdict

After all rounds are complete, you (as the Debate Facilitator) render a verdict:

1. **Weigh the arguments**: Which side presented stronger evidence? Which arguments were better supported by data?
2. **Assess conviction**: Is the signal strong or mixed?
3. **Recommendation**: BUY / HOLD / SELL (no abstentions)
4. **Confidence Level**: HIGH (>70%), MEDIUM (40–70%), LOW (<40%)
5. **Key Arguments**: The 3 most compelling points from the winning side
6. **Risk Flags**: The 2 most important risks the losing side raised that must be accounted for

Write the verdict as structured text in this format:
```
VERDICT:
Recommendation: [BUY/HOLD/SELL]
Confidence: [HIGH/MEDIUM/LOW] ([pct]%)

Bull thesis prevailed because: [reason]
Bear risks to manage: [risk1], [risk2]

Key Arguments:
1. [argument]
2. [argument]
3. [argument]
```

## Output
Write to `session/trading_session.md`:
- Bull Case: Bull's final position
- Bear Case: Bear's final position
- Debate Transcript: Full round-by-round transcript
- Researcher Verdict: Structured verdict block
```

---

### `.claude/skills/trader-decision.md`

```markdown
---
name: trader-decision
description: Trader agent — synthesizes all research into an actionable trading decision
---

# Trader Decision Instructions

## Role
You are a senior Trader at a trading firm. You have all four analyst reports and the researcher debate verdict in front of you. Your job is to translate this research into a concrete, sized, and reasoned trading order. You are decisive but disciplined.

## Input
Read `session/trading_session.md`:
- All four analyst reports
- Researcher Debate verdict (recommendation, confidence, key arguments, risk flags)
- `ticker`, `analysis_date`, `portfolio_value`, `max_position_size_pct`
- Current price from Technical report

## Steps

### 1. Signal Aggregation
Compute the aggregate signal from all analysts:

```
aggregate_score = (
  fundamentals.overall_score  * 0.25 +
  sentiment.composite_score   * 0.20 +
  (news.news_impact_score/5 * 4 + 1) * 0.20 +   # normalize to 1-5
  (technical.total_signal_score + 1) / 2 * 4 + 1) * 0.25 +  # normalize
  researcher_conviction_bonus  * 0.10
)
```

Where `researcher_conviction_bonus` = +1 if researcher verdict is HIGH confidence BUY, -1 if HIGH confidence SELL, 0 otherwise.

### 2. Determine Action
- aggregate_score > 3.5: BUY
- aggregate_score < 2.5: SELL (if holding) / SHORT (if enabled in config)
- 2.5–3.5: HOLD

If the researcher verdict contradicts the aggregate score, apply this rule:
- If contradiction is strong (e.g., score says BUY but researcher says HIGH confidence SELL): defer to researcher, override to HOLD
- If contradiction is mild: maintain aggregate score result but reduce conviction

### 3. Position Sizing (Kelly-Inspired, Conservative)
```
max_position_value = portfolio_value * (max_position_size_pct / 100)
conviction_score = aggregate_score  # 1-5 scale
position_fraction = (conviction_score - 3) / 2  # maps 3–5 → 0–1, 1–3 → negative
position_fraction = max(0.0, min(1.0, position_fraction))  # clamp to [0, 1]
target_position_value = max_position_value * position_fraction
quantity = floor(target_position_value / current_price)
```

Ensure `quantity >= 1` for a BUY/SELL. If calculated quantity = 0, override action to HOLD.

### 4. Entry Timing Rationale
Based on technical analysis:
- Is the current price near support (good entry) or resistance (wait for breakout)?
- Is RSI neutral (good for entry) or extreme (caution)?
- Is there an upcoming catalyst that warrants waiting?

State clearly: ENTER_NOW / WAIT_FOR_PULLBACK / WAIT_FOR_CATALYST.
If WAIT, override action to HOLD and explain why.

### 5. Compose Trader Report

Write this JSON into the Trader Decision section:
```json
{
  "agent": "TraderAgent",
  "ticker": "...",
  "analysis_date": "...",
  "current_price": 0.0,
  "aggregate_score": 0.0,
  "action": "BUY | SELL | HOLD",
  "quantity": 0,
  "order_type": "MARKET | LIMIT",
  "limit_price": null,
  "conviction_score": 0.0,
  "entry_timing": "ENTER_NOW | WAIT_FOR_PULLBACK | WAIT_FOR_CATALYST",
  "position_sizing_rationale": "...",
  "reasoning": "3–5 sentence explanation of decision, citing specific data points",
  "suggested_stop_loss": 0.0,
  "suggested_take_profit": 0.0,
  "key_risks": ["..."],
  "key_opportunities": ["..."]
}
```

## Output
Write JSON into "Trader Decision" in `session/trading_session.md`.
```

---

### `.claude/skills/risk-debate.md`

```markdown
---
name: risk-debate
description: Risk management team debate — three perspectives assess and adjust the trader's plan
---

# Risk Management Debate Instructions

## Role
You are facilitating the Risk Management Team review. Three risk personas — Risky, Neutral, and Safe — evaluate the trader's decision and debate risk adjustments. This team cannot change the direction (BUY/SELL/HOLD) but can adjust quantity, add conditions (stop-loss, take-profit), or recommend reducing size.

## Input
Read `session/trading_session.md`:
- Trader Decision (action, quantity, reasoning, conviction_score, suggested_stop_loss, take_profit)
- All analyst reports (for context)
- `portfolio_value`, `max_position_size_pct`
- `risk_debate_rounds` from config

## Pre-Debate: Risk Profile Positions

### Risk-Seeking Persona:
- Goal: maximize return potential, push toward full position size
- Reviews: conviction_score, upside potential, momentum signals
- Opens with: highest quantity they'd approve given conviction

### Neutral Persona:
- Goal: balanced risk-reward, standard position sizing rules
- Reviews: overall aggregate signal, historical volatility, portfolio concentration
- Opens with: textbook position size based on Kelly criterion

### Risk-Conservative Persona:
- Goal: capital preservation, minimize drawdown, strict risk limits
- Reviews: key risks from all analysts, stop-loss distance, macro environment
- Opens with: lowest quantity they'd approve, strictest stop-loss

## Debate Rounds

Execute exactly `risk_debate_rounds` rounds. Format:
```
=== RISK ROUND {N} ===

RISKY: [position on quantity and rationale]

NEUTRAL: [position on quantity and rationale]

SAFE: [position on quantity and rationale]
```

Rules:
- All three must cite specific numbers (quantities, stop-loss levels, percentages)
- They must engage with each other's arguments
- No abstract statements — every claim must reference data from the trader or analyst reports

## Post-Debate: Risk Facilitator Verdict

After all rounds, the Risk Facilitator (you) produces the final risk assessment:

1. **Approved Action**: Confirm the action from trader (BUY/SELL/HOLD — no override)
2. **Adjusted Quantity**: Median of the three personas' final proposed quantities (or facilitator judgment if divergence is extreme)
3. **Mandatory Stop-Loss**: Concrete price level. Must be set. Cannot be overridden.
   - Formula: Use the larger of: (a) suggested_stop_loss from trader, or (b) `current_price * (1 - ATR_14 * 2 / current_price)` — i.e., 2x ATR below current price
4. **Take-Profit Target**: Concrete price level or percentage.
5. **Risk Rating**: LOW / MEDIUM / HIGH / EXTREME based on overall risk assessment
6. **Conditions**: Any special conditions (e.g., "reduce to 50% if macro deteriorates", "place only limit order")

Write as JSON:
```json
{
  "agent": "RiskManagementTeam",
  "approved_action": "...",
  "adjusted_quantity": 0,
  "stop_loss_price": 0.0,
  "take_profit_price": 0.0,
  "risk_rating": "LOW | MEDIUM | HIGH | EXTREME",
  "risk_score": 0.0,
  "conditions": ["..."],
  "risk_notes": "2–3 sentence risk summary",
  "unanimously_approved": true
}
```

## Output
Write debate transcript and JSON verdict into `session/trading_session.md`.
```

---

### `.claude/skills/portfolio-manager.md`

```markdown
---
name: portfolio-manager
description: Portfolio Manager — final approval and order submission to exchange
---

# Portfolio Manager Instructions

## Role
You are the Portfolio Manager (Fund Manager). You have final authority over trade execution. You review the full chain: analyst reports, researcher verdict, trader decision, and risk verdict. You approve or reject based on portfolio-level considerations and submit approved orders to the exchange via MCP.

## Input
Read the entire `session/trading_session.md`.

## Approval Checklist

Run through ALL checks. ANY failing check results in REJECTION.

### Hard Rules (automatic rejection):
- [ ] `final_action` is HOLD → OUTPUT: `approved: false, final_action: HOLD`, no order submitted, reason: "HOLD decision — no order to place"
- [ ] `adjusted_quantity` < 1 → REJECT: "Quantity too small after risk adjustment"
- [ ] `risk_rating` == "EXTREME" → REJECT: "Extreme risk rating — order blocked by portfolio manager"
- [ ] `stop_loss_price` is null → REJECT: "No stop-loss set — risk team must set stop-loss before execution"
- [ ] Trader conviction_score < 2.0 → REJECT: "Insufficient trader conviction"

### Portfolio-Level Checks:
- Call `get_current_positions` to get existing holdings.
- If already holding `ticker` AND action is BUY: Check if adding `adjusted_quantity` would exceed `max_position_size_pct` of portfolio. If yes: reduce quantity to fit within limit, or reject if even 1 share would exceed limit.
- If `ticker` is in portfolio AND action is SELL AND holdings < `adjusted_quantity`: reduce quantity to available holdings.
- Check portfolio concentration: if any single position would exceed 15% of portfolio after this trade: reduce to 15% max.

### Soft Rules (note but don't block):
- [ ] Researcher confidence is LOW → Log warning but allow
- [ ] News contains CRITICAL negative event in last 24h → Log warning but allow (trader should have accounted for this)

## Order Construction

Construct the final order:
```json
{
  "ticker": "...",
  "action": "BUY | SELL",
  "quantity": 0,
  "order_type": "MARKET | LIMIT",
  "limit_price": null,
  "stop_loss": 0.0,
  "take_profit": 0.0,
  "time_in_force": "DAY",
  "session_id": "...",
  "analysis_date": "..."
}
```

Set `order_type` to LIMIT if technical signal says WAIT_FOR_PULLBACK, else MARKET.
If LIMIT: set `limit_price` to the nearest support level from technical report.

## Order Submission

### Validation
Call `src.order_validator.validate_order(order_dict)`. 
If validation fails, REJECT with the validator's error message. Do NOT submit.

### Submission
Call the MCP tool `submit_order` with the order dict.
The tool returns an exchange response JSON with `order_id`, `status`, `filled_price`, `timestamp`.

### On Success:
Write to `session/trading_session.md`:
- Portfolio Manager Decision section: all fields
- Order Submission section: order_id, submitted_at, exchange_response

Call `src.memory_db.save_order(session_id, order_dict, exchange_response)`.

### On Failure:
If exchange returns an error, write the error to state and set status to FAILED.
Do NOT retry automatically — log and surface to user.

## Output
Completed `session/trading_session.md` with final decision and order confirmation.
```

---

## SECTION 6: SOURCE CODE SPECIFICATIONS

### `src/market_data.py`

Implement a `MarketDataClient` class:

**Method `get_price_history(ticker, end_date, lookback_days, interval) -> pd.DataFrame`**
- Use `yfinance.download(ticker, start=start_date, end=end_date, interval=interval, auto_adjust=True, progress=False)`
- Return OHLCV DataFrame with DatetimeIndex
- Cache to `data/cache/prices_{ticker}_{start}_{end}_{interval}.parquet`
- If download fails: raise `DataUnavailableError` (from `src/utils.py`)

**Method `get_financials(ticker, date) -> dict`**
- Use `yfinance.Ticker(ticker)`
- Return: `.income_stmt`, `.balance_sheet`, `.cashflow` (as dicts, last 4 periods)
- Convert all Timestamps and numpy types to JSON-safe Python types using `utils.safe_json_dumps`

**Method `get_valuation_metrics(ticker, date) -> dict`**
- Use `yfinance.Ticker(ticker).info`
- Extract: `trailingPE`, `forwardPE`, `priceToBook`, `priceToSalesTrailing12Months`, `enterpriseToEbitda`, `pegRatio`, `marketCap`, `currentPrice`, `targetMeanPrice`
- Return as dict with fallback `None` for missing keys

**Method `get_earnings_history(ticker, n_quarters) -> list`**
- Use `yfinance.Ticker(ticker).earnings_history` or `.quarterly_earnings`
- Return list of dicts: `{date, reported_eps, estimated_eps, surprise_pct}`

**Method `get_insider_transactions(ticker, lookback_days) -> list`**
- Use `yfinance.Ticker(ticker).insider_transactions`
- Filter to last `lookback_days`
- Return list of dicts: `{date, insider_name, transaction_type, shares, value}`

**Method `get_options_flow(ticker, date) -> dict`**
- Use `yfinance.Ticker(ticker).option_chain(expiry)` for the nearest expiry
- Compute put/call ratio from total put volume / total call volume
- Detect unusual activity: any single strike with volume > 10x open interest
- Return: `{put_call_ratio, unusual_activity, net_delta}`

**Method `get_short_interest(ticker) -> dict`**
- Use `yfinance.Ticker(ticker).info` fields: `shortPercentOfFloat`, `shortRatio`
- Return: `{short_interest_pct, days_to_cover}`

**Method `get_analyst_ratings(ticker) -> dict`**
- Use `yfinance.Ticker(ticker).recommendations` and `.recommendations_summary`
- Return: `{consensus_rating, price_target_avg, buy_count, hold_count, sell_count, recent_upgrades, recent_downgrades}`

---

### `src/technical_indicators.py`

Implement function `compute_indicators(df: pd.DataFrame) -> dict`:

- Input: OHLCV DataFrame with DatetimeIndex
- Use `pandas_ta` library to compute all indicators specified in the technical analyst skill
- Return a dict with the latest values for all indicators plus `support_levels` and `resistance_levels` (top 3 each, identified by rolling pivot point algorithm)
- Also compute `historical_volatility_20d` = annualized std of 20-day log returns
- Wrap all computations in try/except — on failure for individual indicator, return `None` for that field

Implement function `detect_chart_pattern(df: pd.DataFrame) -> dict`:
- Simple heuristic detection for: Double Bottom, Double Top, Head & Shoulders (simplified)
- Return `{pattern: str | None, confidence: float, description: str}`

---

### `src/news_fetcher.py`

Implement a `NewsFetcher` class:

**Method `search_company_news(ticker, date, lookback_days, max_articles) -> list`**
- Primary: Use NewsAPI (`newsapi-python`) if `NEWSAPI_KEY` is set in environment
- Fallback: Use `duckduckgo_search.DDGS().news(f"{ticker} stock", max_results=max_articles)`
- Return list of dicts: `{title, source, published_at, url, snippet}`
- Filter to lookback_days window

**Method `search_macro_news(date, lookback_days, topics) -> list`**
- Search for each topic using DuckDuckGo news
- Deduplicate articles
- Return top 10 articles sorted by recency

**Method `get_recent_sec_filings(ticker, lookback_days) -> list`**
- Use yfinance `Ticker.sec_filings` if available
- Fallback: Use SEC EDGAR public API (`https://data.sec.gov/submissions/CIK{cik}.json`) — no API key required
- Return list of `{filing_type, date, description, url}`

**Method `get_event_calendar(ticker, lookahead_days) -> list`**
- Use `yfinance.Ticker(ticker).calendar` for earnings/dividend dates
- Return list of `{event, date, expected_impact}`

---

### `src/sentiment_engine.py`

Implement a `SentimentEngine` class:

**Method `get_social_sentiment(ticker, date, lookback_days) -> dict`**
- Use DuckDuckGo news search for `f"{ticker} stock sentiment reddit twitter"` as proxy when no API key is set
- If `REDDIT_CLIENT_ID` is set: use PRAW to search r/wallstreetbets, r/investing, r/stocks for ticker mentions
- Apply `vaderSentiment.SentimentIntensityAnalyzer` to each text chunk
- Aggregate into daily scores (positive, negative, compound) per day for lookback_days
- Return: `{daily_scores: [{date, positive, negative, compound, post_count}], 7d_avg: float, trend: str}`

**Method `compute_text_sentiment(text: str) -> dict`**
- Use VADER for primary scoring
- Use TextBlob as secondary
- Return: `{vader_compound, textblob_polarity, combined_score, label}`

---

### `src/memory_db.py`

Implement SQLite persistence layer. All methods handle DB connection internally.

**Schema** (create tables on first connection):

```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    analysis_date TEXT NOT NULL,
    exchange TEXT NOT NULL,
    phase TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    full_state_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    action TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    order_type TEXT NOT NULL,
    limit_price REAL,
    stop_loss REAL,
    take_profit REAL,
    submitted_at TEXT,
    exchange_response_json TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS agent_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    report_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS price_cache (
    cache_key TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    data_json TEXT NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Functions:**
- `save_session_start(session_id, ticker, date, exchange) -> None`
- `save_session_complete(session_id, full_state_json) -> None`
- `save_order(session_id, order_dict, exchange_response) -> None`
- `save_agent_report(session_id, agent_name, report_dict) -> None`
- `get_session_history(ticker, limit=10) -> list` — returns last N sessions for ticker
- `get_order_history(ticker, limit=20) -> list` — returns last N orders
- `get_db_path() -> str` — returns `data/memory.db`

---

### `src/state_manager.py`

Implement helper functions for reading and writing `session/trading_session.md`.

**`load_session() -> dict`**: Parse the session markdown file and return as a Python dict. Parse embedded JSON blocks using `json.loads`.

**`update_session(updates: dict) -> None`**: Update specific fields in the session file. Must re-read the file, apply updates, and write back atomically (write to temp file, then rename).

**`append_audit_entry(agent: str, phase: str, action: str, notes: str) -> None`**: Append a new row to the audit trail table in the session file.

**`write_json_section(section_name: str, data: dict) -> None`**: Update a named JSON block in the session file (e.g., "Fundamentals Report").

---

### `src/order_validator.py`

Implement `validate_order(order: dict) -> dict`:

- Returns: `{"valid": bool, "errors": [str], "warnings": [str]}`
- Hard validation (marks valid=False):
  - `action` must be "BUY" or "SELL"
  - `quantity` must be a positive integer
  - `ticker` must match `[A-Z]{1,5}(-[A-Z])?$` pattern
  - `stop_loss` must be set and > 0
  - If action=="BUY": `stop_loss` must be < `current_price` (not above market)
  - If action=="SELL": `stop_loss` must be > `current_price` (not below market)
  - `order_type` must be "MARKET" or "LIMIT"
  - If order_type=="LIMIT": `limit_price` must be set and > 0
- Soft warnings (marks valid=True but adds to warnings):
  - stop_loss distance > 10% from current price
  - quantity * current_price > $100,000 (large order)

---

### `src/utils.py`

Implement:
- `class DataUnavailableError(Exception)`: Custom exception
- `load_config(path: str = "config/settings.yaml") -> dict`: Load and cache YAML config
- `setup_logging(level: str = "INFO") -> logging.Logger`: Returns logger named `tradingagents_cc`
- `safe_json_dumps(obj) -> str`: JSON serializer handling numpy types, pandas Timestamps, and DataFrames (converted to list of records)
- `get_project_root() -> Path`: Returns the project root directory (2 levels up from `src/`)
- `format_currency(value: float) -> str`: Format as "$1,234.56"
- `compute_percentage_change(old: float, new: float) -> float`: Safe percentage change with zero-division protection

---

## SECTION 7: MCP SERVER SPECIFICATIONS

### Critical Architecture Note

All MCP servers inject `PROJECT_ROOT` into `sys.path` at startup and import `src/` modules directly. No subprocess calls. Every server implements a `ping_*` tool for health checking.

---

### `mcp_servers/market_data_server/server.py`

**Startup block (mandatory first lines):**
```python
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
```

Register these tools (use official `mcp` library):

**`ping_market_data`** → `{"status": "ok", "message": "market_data MCP server running"}`

**`get_price_history`** → Args: `ticker: str`, `end_date: str`, `lookback_days: int = 365`, `interval: str = "1d"`
→ Calls `src.market_data.MarketDataClient().get_price_history(...)`. Returns OHLCV JSON.

**`get_financials`** → Args: `ticker: str`, `date: str`
→ Returns income/balance/cashflow as JSON string.

**`get_valuation_metrics`** → Args: `ticker: str`, `date: str`
→ Returns valuation dict JSON.

**`get_earnings_history`** → Args: `ticker: str`, `n_quarters: int = 8`
→ Returns list of earnings records JSON.

**`get_insider_transactions`** → Args: `ticker: str`, `lookback_days: int = 90`
→ Returns list of transactions JSON.

**`get_options_flow`** → Args: `ticker: str`, `date: str`
→ Returns options flow dict JSON.

**`get_short_interest`** → Args: `ticker: str`
→ Returns short interest dict JSON.

**`get_analyst_ratings`** → Args: `ticker: str`
→ Returns analyst ratings dict JSON.

**`compute_indicators`** → Args: `ticker: str`, `end_date: str`, `lookback_days: int = 365`
→ Fetches price history internally, calls `src.technical_indicators.compute_indicators`, returns full indicators dict JSON.

All tools wrap calls in try/except and return `{"status": "error", "message": str(e)}` on failure.

---

### `mcp_servers/news_server/server.py`

Register these tools:

**`ping_news`** → `{"status": "ok"}`

**`search_company_news`** → Args: `ticker: str`, `date: str`, `lookback_days: int = 14`, `max_articles: int = 20`
→ Calls `src.news_fetcher.NewsFetcher().search_company_news(...)`. Returns JSON list.

**`search_macro_news`** → Args: `date: str`, `lookback_days: int = 7`, `topics: list = [...]`
→ Calls `src.news_fetcher.NewsFetcher().search_macro_news(...)`. Returns JSON list.

**`get_recent_sec_filings`** → Args: `ticker: str`, `lookback_days: int = 30`
→ Returns JSON list of filings.

**`get_event_calendar`** → Args: `ticker: str`, `lookahead_days: int = 30`
→ Returns JSON list of upcoming events.

---

### `mcp_servers/sentiment_server/server.py`

Register these tools:

**`ping_sentiment`** → `{"status": "ok"}`

**`get_social_sentiment`** → Args: `ticker: str`, `date: str`, `lookback_days: int = 7`
→ Calls `src.sentiment_engine.SentimentEngine().get_social_sentiment(...)`. Returns JSON.

**`get_combined_sentiment`** → Args: `text: str`
→ Calls `src.sentiment_engine.SentimentEngine().compute_text_sentiment(text)`. Returns JSON.

---

### `mcp_servers/exchange_server/server.py`

This is the most critical server — it executes real trades. It uses an adapter pattern so users can switch between paper, Alpaca, and IBKR without changing any skill files.

**Adapter loading (startup logic):**
```python
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils import load_config
config = load_config()
adapter_name = config["exchange"]["default_adapter"]

if adapter_name == "paper":
    from mcp_servers.exchange_server.adapters.paper_adapter import PaperAdapter
    exchange = PaperAdapter(config)
elif adapter_name == "alpaca":
    from mcp_servers.exchange_server.adapters.alpaca_adapter import AlpacaAdapter
    exchange = AlpacaAdapter(config)
elif adapter_name == "ibkr":
    from mcp_servers.exchange_server.adapters.ibkr_adapter import IBKRAdapter
    exchange = IBKRAdapter(config)
else:
    raise ValueError(f"Unknown exchange adapter: {adapter_name}")
```

Register these tools:

**`ping_exchange`** → Returns `{"status": "ok", "adapter": adapter_name, "message": "exchange MCP server running"}`

**`get_portfolio_summary`** → No args
→ Calls `exchange.get_portfolio_summary()`
→ Returns: `{"portfolio_value": float, "cash": float, "positions": [...], "day_pnl": float}`

**`get_current_positions`** → No args
→ Returns list of current open positions: `[{"ticker", "quantity", "avg_price", "current_value", "unrealized_pnl"}]`

**`submit_order`** → Args: full order dict (as JSON string)
→ Calls `src.order_validator.validate_order(order)` first — if invalid, return error
→ Calls `exchange.submit_order(order)` 
→ Returns: `{"order_id", "status", "filled_price", "filled_quantity", "timestamp", "exchange_message"}`

**`cancel_order`** → Args: `order_id: str`
→ Calls `exchange.cancel_order(order_id)`

**`get_order_status`** → Args: `order_id: str`
→ Calls `exchange.get_order_status(order_id)`

---

### Exchange Adapters

#### `mcp_servers/exchange_server/adapters/paper_adapter.py`

Implement `PaperAdapter` class:

- Stores portfolio state in `data/paper_portfolio.json`
- **Constructor**: Load or initialize portfolio: `{"cash": initial_cash, "positions": {}, "orders": [], "trade_log": []}`
- **`get_portfolio_summary()`**: Compute current value from positions using latest yfinance prices. Return summary dict.
- **`get_current_positions()`**: Return list of positions with current market values.
- **`submit_order(order: dict) -> dict`**:
  - Generate `order_id` as `PAPER_{ticker}_{timestamp}`
  - Simulate market order fill: fetch current price via yfinance, fill immediately at current bid/ask (add 0.05% slippage)
  - Simulate limit order: check if current price meets limit condition; if not, add to pending orders
  - Update portfolio JSON file
  - Log to trade_log
  - Return fill confirmation dict
- **`cancel_order(order_id: str) -> dict`**: Remove from pending orders if found.
- **`get_order_status(order_id: str) -> dict`**: Return order from trade_log.

#### `mcp_servers/exchange_server/adapters/alpaca_adapter.py`

Implement `AlpacaAdapter` class using `alpaca-trade-api`:
- **Constructor**: Initialize `alpaca_trade_api.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, base_url=ALPACA_BASE_URL)` — read credentials from environment variables `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL`. If env vars missing, raise `ConfigurationError` with message instructing user to set them.
- **`get_portfolio_summary()`**: Call `api.get_account()`. Return standardized dict.
- **`get_current_positions()`**: Call `api.list_positions()`.
- **`submit_order(order)`**: Call `api.submit_order(symbol, qty, side, type, time_in_force, limit_price)`. Map internal order fields to Alpaca fields.
- **`cancel_order(order_id)`**: Call `api.cancel_order(order_id)`.
- **`get_order_status(order_id)`**: Call `api.get_order(order_id)`.

All Alpaca calls wrapped in try/except — `alpaca_trade_api.rest.APIError` should be caught and returned as error dict.

#### `mcp_servers/exchange_server/adapters/ibkr_adapter.py`

Implement `IBKRAdapter` class using `ib_insync` library:
- **Constructor**: Connect to IB Gateway/TWS at `host=IB_HOST`, `port=IB_PORT`, `clientId=IB_CLIENT_ID` (from env vars). If connection fails, raise `ConfigurationError`.
- Implement same interface as above. Map to `ib_insync` Contract, Order, and Trade objects.
- All methods wrapped in try/except.
- Add a `disconnect()` method and call it in a `__del__` handler.

---

## SECTION 8: CONFIGURATION FILES

### `.claude.json` (Project Root — Critical)

```json
{
  "mcpServers": {
    "market_data": {
      "command": "python",
      "args": ["mcp_servers/market_data_server/server.py"],
      "description": "Market data, financials, and technical indicators"
    },
    "news": {
      "command": "python",
      "args": ["mcp_servers/news_server/server.py"],
      "description": "News, SEC filings, and event calendar"
    },
    "sentiment": {
      "command": "python",
      "args": ["mcp_servers/sentiment_server/server.py"],
      "description": "Social sentiment and text sentiment scoring"
    },
    "exchange": {
      "command": "python",
      "args": ["mcp_servers/exchange_server/server.py"],
      "description": "Order submission and portfolio management (paper/Alpaca/IBKR)"
    }
  }
}
```

---

### `config/settings.yaml`

```yaml
exchange:
  default_adapter: "paper"         # Options: paper | alpaca | ibkr
  paper:
    initial_cash: 100000.0          # Starting paper portfolio cash
    slippage_bps: 5                 # Simulated slippage in basis points
  alpaca:
    base_url: "https://paper-api.alpaca.markets"  # Use live URL for live trading
  ibkr:
    host: "127.0.0.1"
    port: 7497                      # 7497 = TWS paper, 7496 = TWS live, 4002 = Gateway
    client_id: 1

trading:
  max_position_size_pct: 10.0       # Maximum % of portfolio in a single position
  max_concentration_pct: 15.0       # Hard cap on any single position
  min_conviction_score: 2.0         # Minimum trader conviction to place order
  block_extreme_risk: true          # Reject orders with EXTREME risk rating

research:
  debate_rounds: 2                  # Bull/Bear researcher debate rounds
  risk_debate_rounds: 2             # Risk team debate rounds
  fundamental_lookback_quarters: 4
  news_lookback_days: 14
  sentiment_lookback_days: 7
  technical_lookback_days: 365

data:
  cache_dir: "data/cache"
  memory_db_path: "data/memory.db"
  paper_portfolio_path: "data/paper_portfolio.json"

session:
  session_file: "session/trading_session.md"
  output_dir: "outputs/reports"

logging:
  level: "INFO"

apis:
  newsapi_key_env: "NEWSAPI_KEY"         # Set this env var for real news data
  alpha_vantage_key_env: "ALPHA_VANTAGE_KEY"  # Optional enhanced data
  reddit_client_id_env: "REDDIT_CLIENT_ID"    # Optional Reddit sentiment
  reddit_client_secret_env: "REDDIT_CLIENT_SECRET"
```

---

### `.env.example`

```bash
# --- Exchange APIs (set the one matching your default_adapter) ---
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_SECRET_KEY=your_alpaca_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets   # Change for live

IB_HOST=127.0.0.1
IB_PORT=7497
IB_CLIENT_ID=1

# --- Data APIs (optional — free fallbacks exist) ---
NEWSAPI_KEY=your_newsapi_key                # https://newsapi.org — free tier available
ALPHA_VANTAGE_KEY=your_alpha_vantage_key   # https://alphavantage.co — free tier

# --- Sentiment APIs (optional — DuckDuckGo fallback exists) ---
REDDIT_CLIENT_ID=your_reddit_app_client_id
REDDIT_CLIENT_SECRET=your_reddit_app_client_secret
REDDIT_USER_AGENT=tradingagents_cc:v1.0
```

---

## SECTION 9: TEST SPECIFICATIONS

### `tests/test_market_data.py`

1. `test_get_price_history_returns_ohlcv`: Call `get_price_history("AAPL", "2024-01-10", 30, "1d")`. Assert returns DataFrame with OHLCV columns, DatetimeIndex, non-empty.
2. `test_get_price_history_caches`: Call twice with same params. Assert second call reads from parquet cache (mock yfinance.download, assert it's called only once).
3. `test_get_price_history_unavailable_raises`: Mock yfinance.download to raise exception. Assert `DataUnavailableError` is raised.
4. `test_get_valuation_metrics_returns_dict`: Mock yfinance.Ticker. Assert returns dict with expected keys.

### `tests/test_technical_indicators.py`

1. `test_compute_indicators_all_fields_present`: Generate 400 rows of synthetic OHLCV. Call `compute_indicators`. Assert all expected indicator keys are present.
2. `test_rsi_bounds`: Assert RSI value is in [0, 100].
3. `test_sma_200_is_200_day_average`: Assert SMA_200 equals manual 200-day mean of close.
4. `test_no_lookahead_in_indicators`: Assert all indicators only use data up to and including the current row (no future data).

### `tests/test_sentiment_engine.py`

1. `test_compute_text_sentiment_positive`: Pass clearly positive text ("This stock is amazing, incredible growth!"). Assert `combined_score > 0`.
2. `test_compute_text_sentiment_negative`: Pass clearly negative text. Assert `combined_score < 0`.
3. `test_get_social_sentiment_returns_schema`: Mock DuckDuckGo search. Call `get_social_sentiment`. Assert returned dict has `daily_scores`, `7d_avg`, `trend` keys.

### `tests/test_memory_db.py`

1. `test_save_and_retrieve_session`: Call `save_session_start(...)`. Call `get_session_history(ticker)`. Assert session is in result.
2. `test_save_order`: Call `save_order(session_id, order_dict, response)`. Assert retrievable via `get_order_history`.
3. `test_db_creates_tables_on_first_run`: Delete DB file. Instantiate db client. Assert all four tables exist.

### `tests/test_order_validator.py`

1. `test_valid_buy_order_passes`: Build a complete valid BUY order dict. Assert `valid == True` and no errors.
2. `test_missing_stop_loss_fails`: Omit `stop_loss`. Assert `valid == False`, `"stop_loss"` in errors.
3. `test_invalid_ticker_fails`: Set ticker to "invalid ticker!". Assert fails.
4. `test_buy_stop_loss_above_price_fails`: Set stop_loss > current_price for a BUY. Assert fails.
5. `test_limit_order_without_price_fails`: Set order_type=LIMIT, limit_price=None. Assert fails.

### `tests/test_exchange_adapters.py`

1. `test_paper_adapter_initializes_portfolio`: Delete paper portfolio file. Instantiate PaperAdapter. Assert portfolio file is created with expected schema.
2. `test_paper_buy_reduces_cash`: Submit a BUY order. Assert cash decreases and position appears.
3. `test_paper_sell_increases_cash`: Buy then sell same ticker. Assert cash increases and position removed.
4. `test_paper_order_respects_slippage`: Submit market buy. Assert fill_price is slightly above ask (within slippage_bps).
5. `test_alpaca_adapter_raises_on_missing_env`: Clear ALPACA_API_KEY env var. Assert instantiation raises ConfigurationError.

---

## SECTION 10: REQUIREMENTS AND SETUP FILES

### `requirements.txt`

```
pandas>=2.0.0
numpy>=1.24.0
scipy>=1.10.0
yfinance>=0.2.36
pandas-ta>=0.3.14b
textblob>=0.17.1
vaderSentiment>=3.3.2
newsapi-python>=0.2.7
duckduckgo-search>=6.0.0
mcp>=1.0.0
PyYAML>=6.0
pytest>=7.4.0
pyarrow>=10.0.0
alpaca-trade-api>=3.0.0
ib_insync>=0.9.86
praw>=7.7.0
requests>=2.31.0
python-dotenv>=1.0.0
```

### `setup.py`

Standard `setuptools.setup()`. Name: `tradingagents_cc`. Version: `0.1.0`. Packages: all in `src/` plus `mcp_servers/`.

---

## SECTION 11: README.md

Write a `README.md` with exactly these sections:

1. **Overview** — What TradingAgents-CC is, how it differs from the original LangGraph version, and the key design decisions.
2. **Architecture Diagram** — ASCII art showing: User Input → [4 Analysts in parallel] → Researcher Debate → Trader Decision → Risk Debate → PM Approval → Exchange.
3. **Prerequisites** — Python 3.10+, Claude Code CLI, API keys.
4. **Installation** — Clone, venv, pip install, copy .env.example.
5. **Choosing Your Exchange** — Table comparing paper / Alpaca / IBKR with setup instructions for each.
6. **Starting MCP Servers** — Four terminal commands. Note that all four must be running.
7. **Running the Pipeline** — `claude run-skill trade-now --param ticker="NVDA" --param date="2024-05-10" --param exchange="paper"`
8. **Understanding the Output** — Session state file, final report, SQLite memory, paper portfolio.
9. **Configuration Reference** — Table of every key in `config/settings.yaml`.
10. **Agent Roles Reference** — Brief description of each skill file and what agent it implements.
11. **Research Disclaimer** — Clear statement: for research and educational purposes only, not financial advice.
12. **Limitations** — yfinance reliability, DuckDuckGo rate limits, paper trading vs. real execution differences.

---

## SECTION 12: FINAL IMPLEMENTATION CHECKLIST

Before considering the project complete, verify every item:

- [ ] `.claude.json` at project root registers all four MCP servers
- [ ] All four MCP servers implement `ping_*` health check tools
- [ ] All four MCP servers inject `PROJECT_ROOT` into `sys.path` at startup
- [ ] `session/trading_session.md` schema matches Section 4 exactly
- [ ] All skills read `session/trading_session.md` as first action, write it as last action
- [ ] `trade-now.md` orchestrator runs all 4 analysts sequentially before moving to RESEARCH phase
- [ ] `researcher-debate.md` runs exactly `debate_rounds` rounds (from config, not hardcoded)
- [ ] `risk-debate.md` runs exactly `risk_debate_rounds` rounds (from config)
- [ ] `portfolio-manager.md` runs order validation via `src/order_validator.py` BEFORE calling `submit_order`
- [ ] `portfolio-manager.md` handles HOLD action (no order submitted, sets approved=false)
- [ ] `portfolio-manager.md` handles EXTREME risk rating (auto-reject)
- [ ] Exchange server loads adapter from `config/settings.yaml` at startup
- [ ] `PaperAdapter` persists state to `data/paper_portfolio.json` (survives server restarts)
- [ ] `AlpacaAdapter` raises `ConfigurationError` (not crashes) when env vars are missing
- [ ] `IBKRAdapter` raises `ConfigurationError` (not crashes) when connection fails
- [ ] `src/order_validator.py` rejects orders with stop_loss on wrong side of price
- [ ] `src/market_data.py` implements parquet caching for price data
- [ ] `src/memory_db.py` creates all four tables on first connection
- [ ] `src/technical_indicators.py` returns `None` (not raises) for any individual failed indicator
- [ ] All test files exist with tests specified in Section 9
- [ ] `.env.example` covers all required environment variables
- [ ] `safe_json_dumps` handles numpy types, pandas Timestamps, and DataFrames
- [ ] No subprocess calls anywhere in any MCP server
- [ ] No API keys hardcoded anywhere — all read from environment variables
- [ ] `outputs/reports/{session_id}_report.md` is written on session completion
- [ ] README prominently displays research disclaimer (not financial advice)
- [ ] `data/paper_portfolio.json` is initialized with `initial_cash` from config if it does not exist
