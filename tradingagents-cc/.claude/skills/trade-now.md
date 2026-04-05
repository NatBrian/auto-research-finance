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

6. Initialize `session/trading_session.md` by running the Bash tool:
   ```bash
   python -c "
   from src.state_manager import initialize_session
   initialize_session(
       session_id='{session_id}',
       ticker='{ticker}',
       analysis_date='{date}',
       exchange_adapter='{exchange}',
       debate_rounds={debate_rounds},
       risk_debate_rounds={risk_debate_rounds},
       max_position_size_pct={max_position_size_pct},
       portfolio_value={portfolio_value},
       initial_phase='ANALYSIS',
   )
   "
   ```
   Where:
   - `session_id`: Generate as `{ticker}_{date}_{unix_timestamp}`
   - `ticker`: the provided ticker parameter
   - `date`: the determined analysis date
   - `exchange`: the determined exchange adapter
   - `debate_rounds` and `risk_debate_rounds`: from config
   - `max_position_size_pct`: from config
   - `portfolio_value`: from exchange portfolio summary
   - `initial_phase`: set to ANALYSIS since we're about to run analysts

7. Write initial audit trail entry: `| {now} | INIT | Orchestrator | Session started | ticker={ticker}, date={date}, exchange={exchange} |`

8. Write this session to the SQLite memory database by running:
   ```bash
   python -c "from src.memory_db import save_session_start; save_session_start('{session_id}', '{ticker}', '{date}', '{exchange}')"
   ```

---

## Phase: ANALYSIS (Run all 4 analysts)

For each analyst below, read the skill file and execute it fully before moving to the next. Write the resulting report JSON into the corresponding section of `session/trading_session.md` before proceeding.

### Step A1: Fundamentals Analyst
1. Read `.claude/skills/analyst-fundamentals.md` using the Read tool.
2. Execute all instructions in that file for `ticker` and `date`.
3. Write the returned JSON report into "Fundamentals Report" in `session/trading_session.md`.
4. Append audit entry: `| {now} | ANALYSIS | FundamentalsAnalyst | Report written | overall_score={report.overall_score} |`

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
- Save final session to SQLite:
  ```bash
  python -c "
from src.memory_db import save_session_complete
from pathlib import Path
state_content = Path('session/trading_session.md').read_text(encoding='utf-8')
save_session_complete('{session_id}', state_content)
"
  ```
- Copy `session/trading_session.md` to `outputs/reports/{session_id}_report.md`.
- Display final summary to user (see Final Report format below).

### If rejected:
- Update `phase` to REJECTED, `status` to COMPLETE.
- Set `completed_at`.
- Log rejection reason.
- Save to SQLite:
  ```bash
  python -c "
from src.memory_db import save_session_complete
from pathlib import Path
state_content = Path('session/trading_session.md').read_text(encoding='utf-8')
save_session_complete('{session_id}', state_content)
"
  ```
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
