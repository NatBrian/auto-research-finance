# TradingAgents-CC

**Multi-Agent Trading System for Claude Code**

> ⚠️ **RESEARCH DISCLAIMER**: This system is for **research and educational purposes only**. It is NOT financial advice. Do NOT use this system with real money without understanding the risks. Past simulated performance does not guarantee future results. The authors accept no liability for financial losses incurred from the use of this software.

---

## 1. Overview

TradingAgents-CC is a native Claude Code re-implementation of the [TauricResearch TradingAgents](https://arxiv.org/abs/2412.20138) framework. Instead of LangGraph's node/edge DAG, it uses:

| Original (LangGraph) | TradingAgents-CC (Claude Code) |
|---|---|
| LangGraph `StateGraph` nodes | Claude Code Skill `.md` files |
| LangGraph `AgentState` TypedDict | `session/trading_session.md` (Markdown + JSON) |
| LangGraph edges / routing | Orchestrator skill reads phase, dispatches sequentially |
| Tool-calling via LangChain | MCP server tools registered in `.claude.json` |
| Multiple LLM providers | Claude Code's native reasoning |
| In-memory state | File-persisted state + SQLite audit trail |

**Key Design Decisions:**
- **Skills as Agents**: Each agent role (Analyst, Researcher, Trader, Risk, PM) is a Markdown instruction file that Claude Code reads and follows
- **Markdown State Bus**: `session/trading_session.md` is the single source of truth for live sessions
- **MCP Tool Providers**: Four MCP servers provide market data, news, sentiment, and exchange capabilities
- **Pluggable Exchange**: Swap between paper trading, Alpaca, and IBKR via config

---

## 2. Architecture Diagram

```
                        ┌─────────────────┐
                        │   User Input     │
                        │  (ticker, date)  │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │  trade-now.md   │
                        │  (Orchestrator) │
                        └────────┬────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
    ┌─────────▼──────┐ ┌────────▼────────┐ ┌───────▼────────┐
    │  Fundamentals  │ │   Sentiment     │ │     News       │
    │   Analyst      │ │   Analyst       │ │   Analyst      │
    └─────────┬──────┘ └────────┬────────┘ └───────┬────────┘
              │                  │                   │
              │         ┌───────▼────────┐          │
              │         │   Technical    │          │
              │         │   Analyst      │          │
              │         └───────┬────────┘          │
              └──────────────────┼──────────────────┘
                                 │
                     ┌───────────▼───────────┐
                     │  Researcher Debate    │
                     │  (Bull vs Bear)       │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │  Trader Decision      │
                     │  (Signal Aggregation) │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │  Risk Debate          │
                     │  (Risky/Neutral/Safe) │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │  Portfolio Manager    │
                     │  (Final Approval)     │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │  Exchange MCP Server  │
                     │  (Paper/Alpaca/IBKR)  │
                     └───────────────────────┘
```

---

## 3. Prerequisites

- **Python 3.10+**
- **Claude Code CLI** (latest)
- **API Keys** (optional — free fallbacks exist for all data sources):
  - NewsAPI key for premium news data
  - Reddit API credentials for sentiment analysis
  - Alpaca API keys (for live/paper trading via Alpaca)
  - IB Gateway/TWS running (for IBKR trading)

---

## 4. Installation

### 4.1 Clone and Setup Python Environment

```bash
# Clone the repository
git clone <repo-url>
cd tradingagents-cc

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (macOS/Linux)
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux

# Edit .env with your API keys (all optional for paper trading)
```

### 4.2 Install Claude Code CLI

Ensure you have Claude Code CLI installed. See [official documentation](https://docs.anthropic.com/en/docs/claude-code) for installation instructions.

```bash
# Verify Claude Code is installed
claude --version
```

### 4.3 Install TradingAgents-CC Skills

The trading agents are packaged as Claude Code skills. To install them:

**Option A: Global Installation (Recommended)**

Copy the `.claude/skills` folder to your global Claude skills directory:

```bash
# macOS/Linux
cp -r .claude/skills/* ~/.claude/skills/

# Windows (PowerShell)
Copy-Item -Recurse ".claude\skills\*" "$env:USERPROFILE\.claude\skills\"
```

**Option B: Project-Local Installation**

The skills are already in `.claude/skills/` within this project. When you run Claude Code from this directory, it will automatically detect and load these skills.

**Verify Skills Are Installed:**

```bash
claude /help
# Look for skills like: trade-now, analyst-fundamentals, analyst-sentiment, etc.
```

### 4.4 Configure MCP Servers

The MCP servers are automatically started by Claude Code when defined in `.claude.json`. No manual configuration is needed if running from this project directory.

The `.claude.json` file configures four MCP servers:

| Server | Purpose | Tools Provided |
|--------|---------|----------------|
| `market_data` | Market data, financials, technical indicators | `get_financials`, `get_valuation_metrics`, `compute_indicators_tool`, etc. |
| `news` | News, SEC filings, event calendar | `search_company_news`, `search_macro_news`, `get_recent_sec_filings`, etc. |
| `sentiment` | Social sentiment, text scoring | `get_social_sentiment`, `get_options_flow`, `get_short_interest`, etc. |
| `exchange` | Order submission, portfolio management | `submit_order`, `get_portfolio_summary`, `get_current_positions`, etc. |

**To use MCP servers globally**, add the server configurations to your global `~/.claude.json`:

```json
{
  "mcpServers": {
    "market_data": {
      "command": "python",
      "args": ["/absolute/path/to/tradingagents-cc/mcp_servers/market_data_server/server.py"]
    },
    "news": {
      "command": "python",
      "args": ["/absolute/path/to/tradingagents-cc/mcp_servers/news_server/server.py"]
    },
    "sentiment": {
      "command": "python",
      "args": ["/absolute/path/to/tradingagents-cc/mcp_servers/sentiment_server/server.py"]
    },
    "exchange": {
      "command": "python",
      "args": ["/absolute/path/to/tradingagents-cc/mcp_servers/exchange_server/server.py"]
    }
  }
}
```

> **Note**: Replace `/absolute/path/to/tradingagents-cc` with the actual absolute path to your cloned repository.

---

## 5. Choosing Your Exchange

| Feature | Paper (Default) | Alpaca | IBKR |
|---|---|---|---|
| Setup | Zero config | API key required | IB Gateway/TWS required |
| Cost | Free | Free (paper) / Commission (live) | Commission-based |
| Stocks | Simulated | US markets | Global markets |
| Real Money | No | Yes (with live URL) | Yes |
| Best For | Testing & development | US equities trading | Full brokerage |

**Paper Trading** (default — no setup needed):
```yaml
# config/settings.yaml
exchange:
  default_adapter: "paper"
```

**Alpaca**:
1. Create account at [alpaca.markets](https://alpaca.markets)
2. Generate API keys
3. Set in `.env`:
   ```
   ALPACA_API_KEY=your_key
   ALPACA_SECRET_KEY=your_secret
   ALPACA_BASE_URL=https://paper-api.alpaca.markets
   ```
4. Update `config/settings.yaml`: `default_adapter: "alpaca"`

**Interactive Brokers**:
1. Install IB Gateway or TWS
2. Enable API connections (File → Global Configuration → API → Settings)
3. Set in `.env`:
   ```
   IB_HOST=127.0.0.1
   IB_PORT=7497
   IB_CLIENT_ID=1
   ```
4. Update `config/settings.yaml`: `default_adapter: "ibkr"`

---

## 6. Starting MCP Servers

All four MCP servers must be running for the pipeline to execute. Open four terminal windows:

```bash
# Terminal 1: Market Data
python mcp_servers/market_data_server/server.py

# Terminal 2: News
python mcp_servers/news_server/server.py

# Terminal 3: Sentiment
python mcp_servers/sentiment_server/server.py

# Terminal 4: Exchange
python mcp_servers/exchange_server/server.py
```

> **Note**: When using Claude Code CLI, the MCP servers defined in `.claude.json` are started automatically. The manual startup above is only needed for standalone testing.

---

## 7. Running the Pipeline

### 7.1 Full Pipeline (Recommended)

Run the complete multi-agent trading pipeline with a single command:

```
/trade-now ticker="NVDA" date="2024-05-10" exchange="paper"
```

Or with defaults (today's date, paper exchange):
```
/trade-now ticker="AAPL"
```

This executes all phases in sequence:
1. **ANALYSIS** — All four analysts run in parallel
2. **RESEARCH** — Bull/Bear researcher debate
3. **TRADING** — Trader synthesizes and decides
4. **RISK_REVIEW** — Risk team debate
5. **PM_APPROVAL** — Portfolio Manager final approval and order submission

### 7.2 Running Individual Skills (Step-by-Step)

You can also execute each skill separately for debugging or manual control:

**Step 1: Run Individual Analysts**
```
/analyst-fundamentals
/analyst-sentiment
/analyst-news
/analyst-technical
```

Each analyst reads `session/trading_session.md` for the ticker and date, then writes their report back to the same file.

**Step 2: Run Researcher Debate**
```
/researcher-debate
```

Synthesizes all four analyst reports into a Bull vs Bear debate and produces a verdict.

**Step 3: Run Trader Decision**
```
/trader-decision
```

Aggregates all signals and produces an actionable trading decision with position sizing.

**Step 4: Run Risk Debate**
```
/risk-debate
```

Three risk personas (Risky, Neutral, Safe) debate and adjust the trader's plan.

**Step 5: Run Portfolio Manager**
```
/portfolio-manager
```

Final approval, order validation, and submission to the exchange.

### 7.3 Available Skills Summary

| Skill | Description | Phase |
|-------|-------------|-------|
| `/trade-now` | Master orchestrator — runs full pipeline | All phases |
| `/analyst-fundamentals` | Evaluates financials, valuation, DCF | ANALYSIS |
| `/analyst-sentiment` | Social media, options flow, short interest | ANALYSIS |
| `/analyst-news` | Company/macro news, SEC filings, catalysts | ANALYSIS |
| `/analyst-technical` | Technical indicators, chart patterns | ANALYSIS |
| `/researcher-debate` | Bull vs Bear structured debate | RESEARCH |
| `/trader-decision` | Signal aggregation and position sizing | TRADING |
| `/risk-debate` | Risk team (Risky/Neutral/Safe) debate | RISK_REVIEW |
| `/portfolio-manager` | Final approval and order submission | PM_APPROVAL |

---

## 8. Understanding the Output

### Session State File
`session/trading_session.md` — Contains the full state of the current session including all analyst reports, debate transcripts, decisions, and audit trail.

### Final Report
Saved to `outputs/reports/{session_id}_report.md` on completion. Contains the full pipeline results formatted for reading.

### SQLite Memory
`data/memory.db` — Persistent history of all sessions, orders, and agent reports. Query with:
```python
from src.memory_db import get_session_history, get_order_history
sessions = get_session_history("NVDA", limit=5)
orders = get_order_history("NVDA", limit=10)
```

### Paper Portfolio
`data/paper_portfolio.json` — Current paper trading portfolio state (cash, positions, trade log).

---

## 9. Configuration Reference

| Key | Default | Description |
|---|---|---|
| `exchange.default_adapter` | `"paper"` | Exchange adapter: paper, alpaca, ibkr |
| `exchange.paper.initial_cash` | `100000.0` | Starting cash for paper trading |
| `exchange.paper.slippage_bps` | `5` | Simulated slippage in basis points |
| `trading.max_position_size_pct` | `10.0` | Max % of portfolio in one position |
| `trading.max_concentration_pct` | `15.0` | Hard cap on single position % |
| `trading.min_conviction_score` | `2.0` | Min trader conviction to place order |
| `trading.block_extreme_risk` | `true` | Auto-reject EXTREME risk orders |
| `research.debate_rounds` | `2` | Bull/Bear researcher debate rounds |
| `research.risk_debate_rounds` | `2` | Risk team debate rounds |
| `research.news_lookback_days` | `14` | Days of news to fetch |
| `research.sentiment_lookback_days` | `7` | Days of sentiment data |
| `research.technical_lookback_days` | `365` | Bars of price history |
| `data.memory_db_path` | `"data/memory.db"` | SQLite database path |
| `logging.level` | `"INFO"` | Logging verbosity |

---

## 10. Agent Roles Reference

| Skill File | Agent Role | Description |
|---|---|---|
| `trade-now.md` | Orchestrator | Master pipeline controller — runs all phases in sequence |
| `analyst-fundamentals.md` | Fundamentals Analyst | Evaluates financials, valuation, DCF, insider activity |
| `analyst-sentiment.md` | Sentiment Analyst | Scores social media, options flow, short interest, analyst ratings |
| `analyst-news.md` | News Analyst | Categorizes company/macro news, SEC filings, catalysts |
| `analyst-technical.md` | Technical Analyst | Computes indicators (MACD, RSI, BB, etc.) and chart patterns |
| `researcher-debate.md` | Bull/Bear Researchers | Structured debate synthesizing analyst reports into a verdict |
| `trader-decision.md` | Trader | Aggregates signals, determines action and position size |
| `risk-debate.md` | Risk Team | Three-persona debate (Risky/Neutral/Safe) to adjust position |
| `portfolio-manager.md` | Portfolio Manager | Final approval, order validation, and exchange submission |

---

## 11. Research Disclaimer

> **THIS SOFTWARE IS PROVIDED FOR RESEARCH AND EDUCATIONAL PURPOSES ONLY.**
>
> - It does NOT constitute financial advice or a recommendation to buy or sell securities
> - Past simulated performance does NOT guarantee future results
> - The system may contain bugs that lead to incorrect analysis or unintended trades
> - Always verify any trading decisions independently before risking real capital
> - The authors and contributors accept NO LIABILITY for financial losses
> - The system uses AI-generated analysis which may be inaccurate or biased
> - Use at your own risk

---

## 12. Limitations

- **yfinance reliability**: Free data source with potential rate limits, data gaps, and latency. Not suitable for high-frequency or latency-sensitive strategies.
- **DuckDuckGo rate limits**: Fallback news/sentiment searches may be rate-limited under heavy usage.
- **Paper vs. Real**: Paper trading does not account for order book depth, partial fills, market impact, or real-time price changes during execution.
- **Single-model reasoning**: All agent roles are played by the same Claude instance — no independent model diversity.
- **No real-time streaming**: The system analyzes a single snapshot in time, not a continuous data feed.
- **Indicator accuracy**: pandas-ta computations may differ slightly from professional charting platforms.
- **Sentiment proxy**: Without Reddit/Twitter API credentials, sentiment relies on DuckDuckGo news as a proxy — less accurate than direct social data.

---

## Running Tests

```bash
python -m pytest tests/ -v
```
