---
name: paper-discovery
description: Search arXiv for relevant quantitative finance papers. Use when the user says "find papers", "search for papers", "discover papers", "look up papers on [topic]", or "search arXiv".
version: 3.0
---

# Paper Discovery Instructions (Hybrid Architecture)

## Input
You will receive a `topic` string from the orchestrator (e.g., "momentum strategies").

## Steps

1. Read `sandbox/research_log.md` first.

2. Call the MCP tool `search_papers` with:
   - `query`: Combine the topic with "quantitative finance algorithmic trading". Example: "momentum strategies quantitative finance algorithmic trading"
   - `category_filter`: "q-fin"
   - `max_results`: 10

3. From the 10 results, filter down to the 5 most relevant using these criteria (in order of priority):
   a. Paper contains a clearly defined, implementable signal formula (not just theory)
   b. Paper is from q-fin.TR (Trading and Market Microstructure) or q-fin.PM (Portfolio Management) category
   c. Paper has been published or updated within the last 5 years
   d. Paper abstract explicitly mentions backtesting or empirical validation
   e. **Abstract Implementability Gate**: Abstract contains at least one of: a named formula, a specific lookback period (e.g., "12-month"), a named transformation (e.g., "z-score", "rank", "log return"), or an explicit signal construction description.

4. For each of the 5 selected papers, call `fetch_paper_details` with the arxiv_id to retrieve full details.

5. **Detect Strategy Type** for each paper by analyzing the abstract:

   | Strategy Type | Detection Keywords |
   |---------------|-------------------|
   | **rule_based** | momentum, mean-reversion, RSI, MACD, moving average, Bollinger, formula, signal, lookback, cross-sectional rank, z-score |
   | **ml_based** | machine learning, neural network, deep learning, random forest, XGBoost, LSTM, transformer, gradient boosting, feature engineering, classification, prediction model |
   | **statistical** | ARIMA, GARCH, cointegration, Kalman filter, regression, time-series model, statistical arbitrage, pairs trading, spread |

   If multiple types match, prefer: ml_based > statistical > rule_based

6. Present results to user in this format:
   ```
   Paper [N]: [Title]
   Authors: [Author list]
   Date: [Date]
   ArXiv ID: [ID]
   Type: [rule_based | ml_based | statistical]
   Relevance: [One sentence on why this paper is implementable]
   Key Signal Hint: [One sentence describing what kind of signal the paper proposes]
   ---
   ```

7. Ask: "Please select a paper by entering a number (1-5):"

## Output
Write the selected paper's metadata to `sandbox/research_log.md`:
- Under "Selected Paper": arxiv_id, title, authors, abstract_summary, key_formula
- Under "detected_type": The strategy type detected from the abstract
- This will be copied to `strategy_type` by the orchestrator

The `key_formula` field should contain the most important formula from the abstract (LaTeX notation is acceptable).