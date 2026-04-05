"""
TradingAgents-CC — SQLite Persistent Memory

Provides create / read helpers for the four core tables:
  sessions, orders, agent_reports, price_cache.

All public functions open their own connection and close it on exit.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils import get_project_root, safe_json_dumps, setup_logging

logger = setup_logging()

# ---------------------------------------------------------------------------
# Database path
# ---------------------------------------------------------------------------

def get_db_path() -> str:
    """Return the absolute path to the SQLite database file."""
    return str(get_project_root() / "data" / "memory.db")


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
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
"""


def _connect() -> sqlite3.Connection:
    """Open (and optionally create) the database, ensuring tables exist."""
    db_path = get_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA_SQL)
    return conn


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def save_session_start(
    session_id: str,
    ticker: str,
    analysis_date: str,
    exchange: str,
) -> None:
    """Insert a new session row at the INIT phase."""
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO sessions
                (session_id, ticker, analysis_date, exchange, phase, status, started_at)
            VALUES (?, ?, ?, ?, 'INIT', 'IN_PROGRESS', ?)
            """,
            (
                session_id,
                ticker,
                analysis_date,
                exchange,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        logger.info("Session %s saved to DB (INIT).", session_id)
    finally:
        conn.close()


def save_session_complete(session_id: str, full_state_json: str) -> None:
    """Mark a session as complete and store the final state snapshot."""
    conn = _connect()
    try:
        conn.execute(
            """
            UPDATE sessions
            SET phase = 'COMPLETE',
                status = 'COMPLETE',
                completed_at = ?,
                full_state_json = ?
            WHERE session_id = ?
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                full_state_json,
                session_id,
            ),
        )
        conn.commit()
        logger.info("Session %s marked COMPLETE in DB.", session_id)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Order helpers
# ---------------------------------------------------------------------------

def save_order(
    session_id: str,
    order_dict: dict[str, Any],
    exchange_response: dict[str, Any],
) -> None:
    """Persist a submitted order and its exchange response."""
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO orders
                (order_id, session_id, ticker, action, quantity, order_type,
                 limit_price, stop_loss, take_profit, submitted_at,
                 exchange_response_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                exchange_response.get("order_id", f"ORD_{session_id}"),
                session_id,
                order_dict.get("ticker", ""),
                order_dict.get("action", ""),
                int(order_dict.get("quantity", 0)),
                order_dict.get("order_type", "MARKET"),
                order_dict.get("limit_price"),
                order_dict.get("stop_loss"),
                order_dict.get("take_profit"),
                datetime.now(timezone.utc).isoformat(),
                safe_json_dumps(exchange_response),
            ),
        )
        conn.commit()
        logger.info("Order saved for session %s.", session_id)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Agent report helpers
# ---------------------------------------------------------------------------

def save_agent_report(
    session_id: str,
    agent_name: str,
    report_dict: dict[str, Any],
) -> None:
    """Store an individual agent's JSON report."""
    conn = _connect()
    try:
        conn.execute(
            """
            INSERT INTO agent_reports (session_id, agent_name, report_json)
            VALUES (?, ?, ?)
            """,
            (session_id, agent_name, safe_json_dumps(report_dict)),
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def get_session_history(ticker: str, limit: int = 10) -> list[dict]:
    """Return the last *limit* sessions for *ticker*, newest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT * FROM sessions
            WHERE ticker = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (ticker, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_order_history(ticker: str, limit: int = 20) -> list[dict]:
    """Return the last *limit* orders for *ticker*, newest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT * FROM orders
            WHERE ticker = ?
            ORDER BY submitted_at DESC
            LIMIT ?
            """,
            (ticker, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
