# Autonomous Claude Code Finance Workflows

This repository contains algorithmic trading research and development. The system runs natively within **Claude Code** (Anthropic's agentic CLI), utilizing Skill files for orchestration and Model Context Protocol (MCP) servers for tool integration.

---

## 📂 Repository Structure

The repository is organized into four top-level folders, each representing a self-contained research workflow:

```text
/
├── 01_paper_to_factor_pipeline/   # Academic Research Translation
├── 02_market_regime_detector/     # (Example: Regime Classification)
├── 03_portfolio_optimizer/        # (Example: Allocation Optimization)
├── 04_risk_monitor/               # (Example: Real-time Risk Analytics)
└── README.md
```

---

## 🔄 Workflow Descriptions

### 1. Paper-to-Factor Pipeline
*Location: `01_paper_to_factor_pipeline/`*

This workflow automates the translation of academic theory into production code.
*   **Input**: A research topic.
*   **Process**:
    1.  Autonomously finds relevant academic papers on arXiv.
    2.  Translates mathematical logic into executable Python trading signals.
    3.  Backtests against historical data with rigorous data integrity handling.
    4.  Compares performance against Market Benchmark (SPY) and ML Baselines (XGBoost, Logistic Regression).
    5.  Iteratively refines the approach.
*   **Output**: A validated, production-ready Python file.

### 2. [Workflow Name]
*Location: `02_market_regime_detector/`*
*(Description to be added based on folder contents)*

### 3. [Workflow Name]
*Location: `03_portfolio_optimizer/`*
*(Description to be added based on folder contents)*

### 4. [Workflow Name]
*Location: `04_risk_monitor/`*
*(Description to be added based on folder contents)*

---

## ⚠️ Critical Implementation Guidelines

1.  **Context**: Ensure you are operating within the correct folder for the specific workflow you intend to run.
2.  **Dependencies**: Each workflow may require specific MCP server connections or data sources. Check the `skills/` directory inside each folder for specific requirements.
