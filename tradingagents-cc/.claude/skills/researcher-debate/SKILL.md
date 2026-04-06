---
name: researcher-debate
description: Bull and Bear researcher debate to synthesize analyst reports into a verdict
---

# Researcher Debate Instructions

## Role
You are facilitating a structured debate between a Bullish Researcher and a Bearish Researcher. Both have read all four analyst reports. They will argue their cases for `debate_rounds` rounds, then you will produce a balanced verdict.

## Input
Read the session file:
1. Read `session/.current_session_id` to get the current session ID
2. Then read `session/{session_id}/trading_session.md`

From the session file, extract:
- All four analyst reports (Fundamentals Report, Sentiment Report, News Report, Technical Report) — each is a JSON block under its respective `##` heading
- `ticker`, `analysis_date` from the Metadata section
- `debate_rounds` from the Metadata section (default: 2 if not found)

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
Write to `session/{session_id}/trading_session.md` (where `{session_id}` is read from `session/.current_session_id`):
- Replace the `### Bull Case` section content with Bull's final position
- Replace the `### Bear Case` section content with Bear's final position
- Replace the `### Debate Transcript` section content with the full round-by-round transcript
- Replace the `### Researcher Verdict` section content with the structured verdict block
