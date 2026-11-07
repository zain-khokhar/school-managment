"""
Numbered SQLite migrations managed via ``PRAGMA user_version``.

Follows ADVANCEMENT_PLAN.md Section 10.2 & 10.3:
  - Preserves existing user data across upgrades
  - Adds ``app_user``, ``app_session``, ``audit_log``, ``school_setting``, and Phase 2 indexes
"""

from __future__ import annotations

import sqlite3
from typing import Callable

MIGRATION_001_SQL = """
CREATE TABLE IF NOT EXISTS app_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'principal', 'teacher', 'fee_clerk', 'front_desk', 'exam_incharge')),
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    recovery_hash TEXT,
    recovery_salt TEXT,
    teacher_id INTEGER REFERENCES school_teacher(id) ON DELETE SET NULL,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    last_login_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS app_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_hash TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    ip_address TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES app_user(id) ON DELETE SET NULL,
    username TEXT NOT NULL,
    role TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    summary TEXT NOT NULL,
    ip_address TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS school_setting (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by TEXT
);

CREATE INDEX IF NOT EXISTS idx_app_session_user ON app_session(user_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON audit_log(entity_type, entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(username, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_payslip_payment_date ON student_payslip(payment_date, state);
CREATE INDEX IF NOT EXISTS idx_daily_att_date ON daily_attendance(date, state);
"""


def _execute_sql_statements(conn: sqlite3.Connection, script: str) -> None:
    """Execute multi-statement DDL using ``sqlite3.complete_statement`` without implicit COMMIT."""
    buf: list[str] = []
    for line in script.splitlines():
        stripped = line.strip()
        if not buf and (not stripped or stripped.startswith("--")):
            continue
        buf.append(line)
        candidate = "\n".join(buf)
        if sqlite3.complete_statement(candidate):
            stmt = candidate.strip()
            if stmt:
                conn.execute(stmt)
            buf.clear()
    if buf and "".join(buf).strip():
        conn.execute("\n".join(buf).strip())


def _migration_001(conn: sqlite3.Connection) -> None:
    _execute_sql_statements(conn, MIGRATION_001_SQL)


MIGRATIONS: list[tuple[int, str, Callable[[sqlite3.Connection], None]]] = [
    (1, "phase2_auth_audit_settings", _migration_001),
]

LATEST_SCHEMA_VERSION = MIGRATIONS[-1][0]


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Return current SQLite ``PRAGMA user_version`` integer."""
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row is not None else 0


def apply_migrations(conn: sqlite3.Connection) -> int:
    """Apply all pending numbered migrations atomically and return final version."""
    current = get_schema_version(conn)
    for version, _name, fn in MIGRATIONS:
        if version > current:
            fn(conn)
            conn.execute(f"PRAGMA user_version = {int(version)}")
            current = version
    return current

