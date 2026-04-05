"""
TradingAgents-CC — Session State Manager

Read / write helpers for ``session/trading_session.md``.
The session file is structured Markdown with embedded JSON code blocks.
"""

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils import get_project_root, safe_json_dumps, setup_logging

logger = setup_logging()

SESSION_FILE = "session/trading_session.md"


def _session_path() -> Path:
    return get_project_root() / SESSION_FILE


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def load_session() -> dict:
    """Parse ``session/trading_session.md`` into a Python dict.

    Extracts:
      - key-value pairs from ``- **key**: value`` lines
      - JSON blocks from fenced ```json ... ``` sections, keyed by the
        nearest preceding ``##`` or ``###`` heading
      - the audit trail table rows

    Returns
    -------
    dict
        Nested dictionary representing the full session state.
    """
    path = _session_path()
    if not path.exists():
        logger.warning("Session file not found at %s", path)
        return {}

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    state: dict[str, Any] = {}

    # ---- extract top-level key-value pairs ----
    kv_pattern = re.compile(r"^-\s+\*\*(.+?)\*\*:\s*(.*)$", re.MULTILINE)
    for m in kv_pattern.finditer(text):
        key = m.group(1).strip()
        val = m.group(2).strip()
        if val.lower() == "null" or val == "":
            val = None
        elif val.replace(".", "", 1).lstrip("-").isdigit():
            val = float(val) if "." in val else int(val)
        elif val.lower() in ("true", "false"):
            val = val.lower() == "true"
        state[key] = val

    # ---- extract named JSON blocks (line-by-line scan) ----
    # Walk through line-by-line: track the last heading seen, and when we
    # encounter a ```json block, associate it with that heading.
    current_heading: str | None = None
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Track headings (## or ###)
        if stripped.startswith("## ") or stripped.startswith("### "):
            # Extract heading text (remove # prefix)
            heading_text = stripped.lstrip("#").strip()
            current_heading = heading_text

        # Detect ```json opening
        elif stripped == "```json" and current_heading is not None:
            # Collect JSON content until closing ```
            json_lines: list[str] = []
            i += 1
            while i < len(lines):
                if lines[i].strip() == "```":
                    break
                json_lines.append(lines[i])
                i += 1
            json_str = "".join(json_lines).strip()
            if current_heading not in state or not isinstance(state.get(current_heading), dict) or not state[current_heading]:
                try:
                    state[current_heading] = json.loads(json_str) if json_str and json_str != "{}" else {}
                except json.JSONDecodeError:
                    state[current_heading] = {}

        i += 1

    # ---- extract audit trail rows ----
    audit_rows: list[dict] = []
    audit_pattern = re.compile(
        r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|$",
        re.MULTILINE,
    )
    for m in audit_pattern.finditer(text):
        ts, phase, agent, action, notes = (
            m.group(1).strip(),
            m.group(2).strip(),
            m.group(3).strip(),
            m.group(4).strip(),
            m.group(5).strip(),
        )
        if ts in ("Timestamp", "---"):
            continue
        audit_rows.append(
            {
                "timestamp": ts,
                "phase": phase,
                "agent": agent,
                "action": action,
                "notes": notes,
            }
        )
    state["audit_trail"] = audit_rows

    return state


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def update_session(updates: dict[str, Any]) -> None:
    """Update specific key-value fields in the session file.

    Re-reads the file, applies updates, and writes atomically.
    Only updates ``- **key**: value`` style lines.
    """
    path = _session_path()
    if not path.exists():
        logger.error("Cannot update — session file missing: %s", path)
        return

    text = path.read_text(encoding="utf-8")

    for key, value in updates.items():
        pattern = re.compile(
            rf"^(-\s+\*\*{re.escape(key)}\*\*:\s*)(.*)$",
            re.MULTILINE,
        )
        replacement_value = "null" if value is None else str(value)
        text, count = pattern.subn(rf"\g<1>{replacement_value}", text)
        if count == 0:
            logger.debug("Key '%s' not found in session file; skipping.", key)

    _atomic_write(path, text)


def append_audit_entry(
    agent: str,
    phase: str,
    action: str,
    notes: str,
) -> None:
    """Append a new row to the Audit Trail table."""
    path = _session_path()
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    new_row = f"| {now} | {phase} | {agent} | {action} | {notes} |"

    # Append after the last line in the file (audit table is at the bottom)
    text = text.rstrip() + "\n" + new_row + "\n"
    _atomic_write(path, text)


def write_json_section(section_name: str, data: dict) -> None:
    """Replace the JSON code block under a named ``###`` or ``##`` section.

    Uses line-by-line scanning to find the section heading, then locates the
    next ``\\`\\`\\`json`` block under that heading and replaces its content.
    This approach avoids regex backtracking issues with complex markdown.

    Parameters
    ----------
    section_name : str
        The heading text, e.g. ``"Fundamentals Report"``.
    data : dict
        Data to write as formatted JSON.
    """
    path = _session_path()
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    json_str = safe_json_dumps(data)

    # Phase 1: Find the line index of the target heading
    heading_idx: int | None = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Match both ### and ## headings
        heading_text = stripped.lstrip("#").strip()
        if heading_text == section_name and (
            stripped.startswith("### ") or stripped.startswith("## ")
        ):
            heading_idx = i
            break

    if heading_idx is None:
        logger.warning("Section '%s' not found in session file.", section_name)
        _atomic_write(path, text)
        return

    # Phase 2: From heading_idx, scan forward to find ```json (stop at next ## heading)
    json_start: int | None = None
    json_end: int | None = None
    for i in range(heading_idx + 1, len(lines)):
        stripped = lines[i].strip()
        # Stop if we hit another ## heading (section boundary)
        if stripped.startswith("## ") and i > heading_idx + 1:
            break
        if stripped == "```json":
            json_start = i
            # Now find the closing ```
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == "```":
                    json_end = j
                    break
            break

    if json_start is None or json_end is None:
        logger.warning("No ```json block found under section '%s'.", section_name)
        _atomic_write(path, text)
        return

    # Phase 3: Replace the content between ```json and ```
    new_lines = lines[: json_start + 1] + [json_str + "\n"] + lines[json_end:]
    _atomic_write(path, "".join(new_lines))


def initialize_session(
    session_id: str,
    ticker: str,
    analysis_date: str,
    exchange_adapter: str,
    debate_rounds: int,
    risk_debate_rounds: int,
    max_position_size_pct: float,
    portfolio_value: float,
    initial_phase: str = "INIT",
) -> None:
    """Create the canonical ``session/trading_session.md`` from scratch.

    Parameters
    ----------
    initial_phase : str
        Phase to set on creation.  The orchestrator typically sets this to
        ``ANALYSIS`` so that the session starts in the correct state.
    """
    path = _session_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    template = _SESSION_TEMPLATE.format(
        session_id=session_id,
        ticker=ticker,
        analysis_date=analysis_date,
        phase=initial_phase,
        exchange_adapter=exchange_adapter,
        debate_rounds=debate_rounds,
        risk_debate_rounds=risk_debate_rounds,
        max_position_size_pct=max_position_size_pct,
        portfolio_value=portfolio_value,
        started_at=now,
    )
    _atomic_write(path, template)
    logger.info("Session file initialized: %s", path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _atomic_write(path: Path, content: str) -> None:
    """Write *content* to *path* atomically via a temp-file rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        # On Windows, target must not exist for os.rename
        if path.exists():
            path.unlink()
        os.rename(tmp, str(path))
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


# ---------------------------------------------------------------------------
# Session Template
# ---------------------------------------------------------------------------

_SESSION_TEMPLATE = """# Trading Session

## Session Info
- **session_id**: {session_id}
- **ticker**: {ticker}
- **analysis_date**: {analysis_date}
- **phase**: {phase}
- **status**: IN_PROGRESS
- **started_at**: {started_at}
- **completed_at**: null

## Configuration
- **exchange_adapter**: {exchange_adapter}
- **debate_rounds**: {debate_rounds}
- **risk_debate_rounds**: {risk_debate_rounds}
- **max_position_size_pct**: {max_position_size_pct}
- **portfolio_value**: {portfolio_value}

## Analyst Reports
### Fundamentals Report
```json
{{}}
```

### Sentiment Report
```json
{{}}
```

### News Report
```json
{{}}
```

### Technical Report
```json
{{}}
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
{{}}
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
```json
{{}}
```

## Portfolio Manager Decision
- **final_action**: null
- **final_quantity**: null
- **order_type**: null
- **approved**: null
- **rejection_reason**: null
```json
{{}}
```

## Order Submission
- **order_id**: null
- **submitted_at**: null
- **exchange_response**: null
```json
{{}}
```

## Audit Trail
| Timestamp | Phase | Agent | Action | Notes |
|---|---|---|---|---|
"""
