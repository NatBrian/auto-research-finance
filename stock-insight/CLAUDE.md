# Financial Report Pipeline - Global Rules

## Core Principles
- Never manually write HTML/JS/CSS. Always run `python pipeline/generate_report.py --ticker <SYMBOL>`.
- Never fabricate data. If script outputs `WARNING:`, relay verbatim to user.
- If script fails: read error → fix code in failing module → re-run.

## File Locations
- Cache: `data/cache.db` (never commit)
- Output: `output/{TICKER}_{YYYY-MM-DD}.html`

## Skill Architecture
- Core skill logic lives in `.claude/skills/*/SKILL.md`
- Subdirectory CLAUDE.md files are context hints only
- Skills are invoked via `/skill-name args` or by the orchestrator

## Data Sources (Free Tiers)
- yfinance: Unlimited, rate-limited ~100 req/min
- Twelve Data: 800 calls/day free
- Finnhub: 60 calls/min free

## Error Handling
- Read error messages carefully before attempting fixes
- Check API quotas if data fetch fails
- Verify ticker symbol format (e.g., AAPL, BBCA.JK)