"""Tests for src/memory_db.py"""

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import memory_db


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path, monkeypatch):
    """Point the database to a temp directory for each test."""
    db_file = str(tmp_path / "test_memory.db")
    monkeypatch.setattr(memory_db, "get_db_path", lambda: db_file)
    yield db_file


class TestSessionPersistence:
    def test_save_and_retrieve_session(self):
        """save_session_start + get_session_history should round-trip."""
        memory_db.save_session_start("TEST_001", "AAPL", "2024-01-10", "paper")
        history = memory_db.get_session_history("AAPL", limit=10)
        assert len(history) >= 1
        assert history[0]["session_id"] == "TEST_001"
        assert history[0]["ticker"] == "AAPL"
        assert history[0]["status"] == "IN_PROGRESS"

    def test_save_session_complete(self):
        """save_session_complete should update phase and status."""
        memory_db.save_session_start("TEST_002", "NVDA", "2024-01-10", "paper")
        memory_db.save_session_complete("TEST_002", '{"test": true}')
        history = memory_db.get_session_history("NVDA")
        assert history[0]["status"] == "COMPLETE"
        assert history[0]["full_state_json"] == '{"test": true}'


class TestOrderPersistence:
    def test_save_order(self):
        """save_order + get_order_history should round-trip."""
        memory_db.save_session_start("TEST_003", "MSFT", "2024-01-10", "paper")
        order = {
            "ticker": "MSFT",
            "action": "BUY",
            "quantity": 10,
            "order_type": "MARKET",
            "stop_loss": 300.0,
        }
        response = {"order_id": "ORD_001", "status": "FILLED", "filled_price": 350.0}
        memory_db.save_order("TEST_003", order, response)
        orders = memory_db.get_order_history("MSFT")
        assert len(orders) >= 1
        assert orders[0]["order_id"] == "ORD_001"


class TestSchemaCreation:
    def test_db_creates_tables_on_first_run(self, use_temp_db):
        """All four tables should exist after first connection."""
        import sqlite3
        # Force a fresh connection
        db_path = use_temp_db
        if os.path.exists(db_path):
            os.unlink(db_path)
        # Trigger table creation
        memory_db.save_session_start("TEST_SCHEMA", "X", "2024-01-01", "paper")
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "sessions" in tables
        assert "orders" in tables
        assert "agent_reports" in tables
        assert "price_cache" in tables
