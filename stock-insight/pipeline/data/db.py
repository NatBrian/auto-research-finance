"""SQLite cache and quota management."""
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from pipeline.config import CACHE_DB, CACHE_TTL, API_QUOTAS


def init_db():
    """Initialize SQLite database with required tables."""
    conn = sqlite3.connect(CACHE_DB)
    cursor = conn.cursor()

    # Data cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data_cache (
            ticker TEXT NOT NULL,
            data_type TEXT NOT NULL,
            source TEXT NOT NULL,
            data_blob TEXT NOT NULL,
            fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (ticker, data_type, source)
        )
    """)

    # API usage tracking table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS api_usage (
            date DATE NOT NULL,
            service TEXT NOT NULL,
            call_count INTEGER DEFAULT 0,
            PRIMARY KEY (date, service)
        )
    """)

    conn.commit()
    conn.close()


def get_connection() -> sqlite3.Connection:
    """Get thread-safe database connection."""
    conn = sqlite3.connect(CACHE_DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def get_cached_data(
    ticker: str,
    data_type: str,
    source: str = "yfinance"
) -> Optional[Dict[str, Any]]:
    """Get cached data if not expired based on TTL."""
    ttl = CACHE_TTL.get(data_type, timedelta(hours=1))
    cutoff = datetime.utcnow() - ttl

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT data_blob, fetched_at FROM data_cache
        WHERE ticker = ? AND data_type = ? AND source = ?
        AND fetched_at > ?
    """, (ticker, data_type, source, cutoff.isoformat()))

    row = cursor.fetchone()
    conn.close()

    if row:
        return json.loads(row['data_blob'])
    return None


def set_cached_data(
    ticker: str,
    data_type: str,
    data: Dict[str, Any],
    source: str = "yfinance"
):
    """Store data in cache."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO data_cache (ticker, data_type, source, data_blob, fetched_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(ticker, data_type, source)
        DO UPDATE SET data_blob = excluded.data_blob, fetched_at = excluded.fetched_at
    """, (ticker, data_type, source, json.dumps(data), datetime.utcnow().isoformat()))

    conn.commit()
    conn.close()


def check_quota(service: str) -> Tuple[bool, int]:
    """
    Check if service has remaining quota for today.
    Returns (has_quota, current_count).
    """
    today = datetime.utcnow().date().isoformat()
    limits = API_QUOTAS.get(service, {"daily": 1000})

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT call_count FROM api_usage
        WHERE date = ? AND service = ?
    """, (today, service))

    row = cursor.fetchone()
    conn.close()

    current_count = row['call_count'] if row else 0
    has_quota = current_count < limits['daily']

    return has_quota, current_count


def increment_quota(service: str):
    """Increment API call counter for service."""
    today = datetime.utcnow().date().isoformat()

    conn = get_connection()
    cursor = conn.cursor()

    # Use IMMEDIATE transaction for thread safety
    cursor.execute("BEGIN IMMEDIATE")

    cursor.execute("""
        INSERT INTO api_usage (date, service, call_count)
        VALUES (?, ?, 1)
        ON CONFLICT(date, service)
        DO UPDATE SET call_count = call_count + 1
    """, (today, service))

    conn.commit()
    conn.close()


def get_cache_stats(ticker: str) -> Dict[str, int]:
    """Get cache statistics for a ticker."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT data_type, source FROM data_cache
        WHERE ticker = ?
    """, (ticker,))

    rows = cursor.fetchall()
    conn.close()

    stats = {"cache_hits": 0, "sources": {}}
    for row in rows:
        stats['cache_hits'] += 1
        stats['sources'][row['source']] = stats['sources'].get(row['source'], 0) + 1

    return stats


def clear_expired_cache():
    """Remove expired cache entries."""
    conn = get_connection()
    cursor = conn.cursor()

    for data_type, ttl in CACHE_TTL.items():
        cutoff = datetime.utcnow() - ttl
        cursor.execute("""
            DELETE FROM data_cache
            WHERE data_type = ? AND fetched_at < ?
        """, (data_type, cutoff.isoformat()))

    conn.commit()
    conn.close()