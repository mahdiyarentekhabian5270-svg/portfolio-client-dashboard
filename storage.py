"""Local persistence: assets in JSON, last-good quotes and history in SQLite."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
ASSETS_FILE = BASE_DIR / "assets.json"
DB_FILE = BASE_DIR / "portfolio_history.sqlite3"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_storage() -> None:
    if not ASSETS_FILE.exists():
        ASSETS_FILE.write_text("[]\n", encoding="utf-8")
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS last_quotes (
                quote_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                saved_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                captured_at TEXT NOT NULL,
                total_value_irr REAL NOT NULL,
                asset_count INTEGER NOT NULL,
                usd_irr REAL
            )
        """)


def load_assets() -> list[dict[str, Any]]:
    init_storage()
    try:
        data = json.loads(ASSETS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_assets(assets: list[dict[str, Any]]) -> None:
    temp = ASSETS_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(ASSETS_FILE)


def new_asset_id() -> str:
    return uuid.uuid4().hex[:12]


def save_last_quote(quote_key: str, payload: dict[str, Any]) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO last_quotes(quote_key, payload, saved_at) VALUES(?,?,?) "
            "ON CONFLICT(quote_key) DO UPDATE SET payload=excluded.payload, saved_at=excluded.saved_at",
            (quote_key, json.dumps(payload, ensure_ascii=False), datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def get_last_quote(quote_key: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("SELECT payload FROM last_quotes WHERE quote_key=?", (quote_key,)).fetchone()
    if not row:
        return None
    try:
        payload = json.loads(row["payload"])
        payload["stale"] = True
        payload["fallback_from_cache"] = True
        return payload
    except (json.JSONDecodeError, TypeError):
        return None


def save_snapshot(total_value_irr: float, asset_count: int, usd_irr: float | None) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _connect() as conn:
        latest = conn.execute("SELECT captured_at FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
        if latest:
            try:
                previous = datetime.fromisoformat(latest["captured_at"])
                if (datetime.now(timezone.utc) - previous).total_seconds() < 240:
                    return
            except ValueError:
                pass
        conn.execute(
            "INSERT INTO snapshots(captured_at,total_value_irr,asset_count,usd_irr) VALUES(?,?,?,?)",
            (now, float(total_value_irr), int(asset_count), usd_irr),
        )


def load_snapshots(limit: int = 500) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT captured_at,total_value_irr,asset_count,usd_irr FROM snapshots ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]
