"""SQLite connection helpers for ARGUS v2.5."""

from __future__ import annotations

import sqlite3


PRAGMA_STATEMENTS: tuple[str, ...] = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000",
)


def open_v25_connection(db_path: str) -> sqlite3.Connection:
    """Open SQLite connection and apply required pragmas in strict order."""

    conn = sqlite3.connect(db_path, check_same_thread=True)
    cursor = conn.cursor()
    for statement in PRAGMA_STATEMENTS:
        cursor.execute(statement)
    return conn

