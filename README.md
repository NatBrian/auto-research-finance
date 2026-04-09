# Auto-Research-Finance

A collection of autonomous, AI-driven quantitative finance systems that **implement Anthropic-aligned harnessing patterns** using **Claude Code as the customizable orchestration client**. We demonstrates how to construct reproducible, auditable agent workflows for financial research and trading by leveraging Claude Code's extension architecture: Skills for role definition, Model Context Protocol (MCP) for tool integration, and structured state files for inter-agent communication.

> **Why Claude Code as the harness layer?** Claude Code provides the most customizable client-side orchestration environment currently available for LLM-based agent systems.

---

## Projects

| Project | Description |
|---|---|
| [**paper-to-factor-pipeline**](./paper-to-factor-pipeline/) | Discovers arXiv papers, translates research into executable trading factors, backtests with survivorship-aware data, and iteratively refines until validation thresholds are met. |
| [**tradingagents-cc**](./tradingagents-cc/) | Multi-agent trading system (re-implementation of arxiv:2412.20138) with 5 specialized teams — Analysts, Researchers (Bull/Bear debate), Trader, Risk Management, and Portfolio Manager — that analyze a ticker and submit orders to paper/Alpaca/IBKR. |
| [**moomoo-dashboard**](./moomoo-dashboard/) | Visual equity research reports powered by MooMoo OpenAPI. Input a ticker → get an interactive HTML dashboard with real-time market data, technicals, fundamentals, sector comparison, and sentiment analysis. |
| [~~**stock-insight**~~](./stock-insight/) `[DEPRECATED]` | **Superseded by [moomoo-dashboard](./moomoo-dashboard/).** <br> *This project is kept for reference only and is no longer actively maintained.* |

---

## Architecture

Most projects share a common design pattern native to **Claude Code**:

```
┌──────────────────────────────────────────────────────────┐
│                     Claude Code CLI                      │
│  • Orchestrates agent reasoning, tool routing, state I/O │
│  • Implements context engineering via progressive skill  │
│    loading and session-aware compaction strategies       │
├──────────────────────────────────────────────────────────┤
│  Skills (.claude/skills/*.md)                            │
│    └─ Markdown instruction files that define agent roles │
│                                                          │
│  State Bus (session/*.md or sandbox/*.md)                │
│    └─ Structured markdown + embedded JSON                │
│    └─ All agents read/write this shared file             │
│                                                          │
│  MCP Servers (mcp_servers/*/server.py)                   │
│    └─ Tool providers registered in .claude.json          │
│    └─ Market data, news, sentiment, exchange, etc.       │
│                                                          │
│  Persistence (data/*.db, data/*.json)                    │
│    └─ SQLite audit trail, portfolio state, cache         │
└──────────────────────────────────────────────────────────┘
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10+ |
| Claude Code CLI | Latest |

Each project has its own `requirements.txt` and virtual environment. See individual project READMEs for setup instructions.

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/NatBrian/auto-research-finance.git
cd auto-research-finance

# Pick a project and follow its README
cd paper-to-factor-pipeline/   # or tradingagents-cc/ moomoo-dashboard/ stock-insight/
```

---

## Disclaimer

These systems are for **research and educational purposes only**. They are not financial advice. Past performance does not guarantee future results. Use real-money exchange adapters at your own risk.
