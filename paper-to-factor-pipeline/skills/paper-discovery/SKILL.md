---
name: paper-discovery
description: Search arXiv for relevant quantitative finance papers. Use when the user says "find papers", "search for papers", "discover papers", "look up papers on [topic]", or "search arXiv".
---

# Paper Discovery Instructions

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
   e. **Abstract Implementability Gate**: Abstract contains at least one of: a named formula, a specific lookback period (e.g., "12-month"), a named transformation (e.g., "z-score", "rank", "log return"), or an explicit signal construction description. Papers whose abstracts contain only high-level claims without implementable signal descriptions must be ranked last.

4. For each of the 5 selected papers, call `fetch_paper_details` with the arxiv_id to retrieve:
   - Full abstract
   - List of authors
   - Publication date
   - PDF URL

5. Present results to user in this exact format:
   ```
   Paper [N]: [Title]
   Authors: [Author list]
   Date: [Date]
   ArXiv ID: [ID]
   Relevance: [One sentence on why this paper is implementable]
   Key Signal Hint: [One sentence describing what kind of signal the paper proposes]
   ---
   ```

6. Ask: "Please select a paper by entering a number (1-5):"

## Output
Write the selected paper's metadata to `sandbox/research_log.md` under "Selected Paper" as the last action.
The `key_formula` field should contain the most important formula from the abstract (LaTeX notation is acceptable).
