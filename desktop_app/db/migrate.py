"""
Numbered SQLite migrations managed via ``PRAGMA user_version``.

Follows ADVANCEMENT_PLAN.md Section 10.2 & 10.3:
  - Preserves existing user data across upgrades
  - v1: ``app_user``, ``app_session``, ``audit_log``, ``school_setting``, and Phase 2 indexes
  - v2: Phase 3 integer paisa columns on ``student_payslip``, ``fee_payment``, ``fee_rule``,
        ``fee_concession``, ``school_parent.cnic``, and historical receipt backfill
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

MIGRATION_002_SQL = """
CREATE TABLE IF NOT EXISTS fee_payment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_no TEXT NOT NULL UNIQUE,
    payslip_id INTEGER NOT NULL REFERENCES student_payslip(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    amount_paisa INTEGER NOT NULL CHECK(amount_paisa > 0),
    payment_mode TEXT NOT NULL DEFAULT 'cash' CHECK(payment_mode IN ('cash', 'bank', 'cheque', 'online')),
    reference TEXT DEFAULT '',
    note TEXT DEFAULT '',
    paid_at TEXT NOT NULL,
    payment_date TEXT NOT NULL,
    received_by_id INTEGER REFERENCES app_user(id) ON DELETE SET NULL,
    received_by TEXT NOT NULL,
    reversed_at TEXT,
    reversed_by TEXT,
    reversal_reason TEXT
);

CREATE TABLE IF NOT EXISTS fee_rule (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    rule_type TEXT NOT NULL CHECK(rule_type IN ('sibling_discount', 'late_fee', 'vacation_discount', 'custom_discount')),
    calc_mode TEXT NOT NULL CHECK(calc_mode IN ('percent', 'fixed_paisa')),
    value INTEGER NOT NULL DEFAULT 0 CHECK(value >= 0),
    min_sibling_rank INTEGER NOT NULL DEFAULT 2,
    grace_days INTEGER NOT NULL DEFAULT 0,
    vacation_months TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fee_concession (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    concession_type TEXT NOT NULL CHECK(concession_type IN ('scholarship', 'sibling', 'staff_child', 'financial_aid', 'custom')),
    calc_mode TEXT NOT NULL CHECK(calc_mode IN ('percent', 'fixed_paisa')),
    value INTEGER NOT NULL CHECK(value >= 0),
    reason TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    approved_by TEXT DEFAULT 'admin',
    created_at TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_payslip_voucher_no
    ON student_payslip(voucher_no) WHERE voucher_no IS NOT NULL AND voucher_no != '';
CREATE INDEX IF NOT EXISTS idx_payslip_billing_month
    ON student_payslip(billing_month, standard_id, state);
CREATE INDEX IF NOT EXISTS idx_payslip_due_date
    ON student_payslip(due_date, state);
CREATE INDEX IF NOT EXISTS idx_fee_payment_date
    ON fee_payment(payment_date, reversed_at);
CREATE INDEX IF NOT EXISTS idx_fee_payment_slip
    ON fee_payment(payslip_id, reversed_at);
CREATE INDEX IF NOT EXISTS idx_fee_concession_stu
    ON fee_concession(student_id, active);
CREATE INDEX IF NOT EXISTS idx_parent_phone
    ON school_parent(phone);
CREATE INDEX IF NOT EXISTS idx_student_mobile
    ON student_student(contact_mobile);
"""

MIGRATION_003_SQL = """
CREATE TABLE IF NOT EXISTS calendar_day (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    day_type TEXT NOT NULL DEFAULT 'holiday'
        CHECK(day_type IN ('holiday', 'ramazan', 'exam_day', 'ptm', 'vacation', 'event')),
    is_off_day INTEGER NOT NULL DEFAULT 1,
    bell_profile TEXT NOT NULL DEFAULT 'regular'
        CHECK(bell_profile IN ('regular', 'ramazan', 'winter')),
    note TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS timetable_substitution (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    line_id INTEGER NOT NULL REFERENCES time_table_line(id) ON DELETE CASCADE,
    original_teacher_id INTEGER REFERENCES school_teacher(id) ON DELETE SET NULL,
    substitute_teacher_id INTEGER NOT NULL REFERENCES school_teacher(id) ON DELETE CASCADE,
    reason TEXT DEFAULT '',
    created_by TEXT DEFAULT 'admin',
    created_at TEXT NOT NULL,
    UNIQUE(date, line_id)
);

CREATE INDEX IF NOT EXISTS idx_calendar_day_date ON calendar_day(date, is_off_day);
CREATE INDEX IF NOT EXISTS idx_tt_sub_date ON timetable_substitution(date, line_id);
CREATE INDEX IF NOT EXISTS idx_exam_result_rank ON exam_result(s_exam_ids, standard_id, rank);
CREATE INDEX IF NOT EXISTS idx_student_b_form ON student_student(b_form_no);
"""

_ALLOWED_ALTER_TABLES = frozenset(
    {"student_payslip", "school_parent", "exam_result", "exam_subject", "student_student"}
)


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


def _add_column_if_missing(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    column_ddl: str,
) -> None:
    """Idempotently add a column to an allowlisted table."""
    if table not in _ALLOWED_ALTER_TABLES:
        raise ValueError(f"Table '{table}' not permitted for schema alteration")
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_ddl}")


def _migration_001(conn: sqlite3.Connection) -> None:
    _execute_sql_statements(conn, MIGRATION_001_SQL)


def _migration_002(conn: sqlite3.Connection) -> None:
    payslip_cols = [
        ("due_date", "TEXT"),
        ("voucher_no", "TEXT"),
        ("billing_month", "TEXT"),
        ("arrears_paisa", "INTEGER NOT NULL DEFAULT 0"),
        ("subtotal_paisa", "INTEGER NOT NULL DEFAULT 0"),
        ("discount_paisa", "INTEGER NOT NULL DEFAULT 0"),
        ("late_fee_paisa", "INTEGER NOT NULL DEFAULT 0"),
        ("total_paisa", "INTEGER NOT NULL DEFAULT 0"),
        ("paid_paisa", "INTEGER NOT NULL DEFAULT 0"),
        ("due_paisa", "INTEGER NOT NULL DEFAULT 0"),
    ]
    for col_name, ddl in payslip_cols:
        _add_column_if_missing(conn, "student_payslip", col_name, ddl)

    _add_column_if_missing(conn, "school_parent", "cnic", "TEXT DEFAULT ''")

    _execute_sql_statements(conn, MIGRATION_002_SQL)

    # Register voucher and receipt sequences if ir_sequence exists
    seq_exists = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ir_sequence'"
    ).fetchone()
    if seq_exists:
        conn.execute(
            "INSERT OR IGNORE INTO ir_sequence (code, prefix, padding, next_val) VALUES ('fee.voucher', 'VCH-', 5, 1)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO ir_sequence (code, prefix, padding, next_val) VALUES ('fee.receipt', 'RCP-', 5, 1)"
        )

    # Backfill integer paisa columns on pre-existing payslips
    conn.execute(
        """
        UPDATE student_payslip
        SET subtotal_paisa = CAST(ROUND(COALESCE(total, 0.0) * 100.0) AS INTEGER),
            total_paisa    = CAST(ROUND(COALESCE(total, 0.0) * 100.0) AS INTEGER),
            paid_paisa     = CAST(ROUND(COALESCE(paid_amount, 0.0) * 100.0) AS INTEGER),
            due_paisa      = CAST(ROUND(COALESCE(due_amount, 0.0) * 100.0) AS INTEGER),
            due_date       = COALESCE(due_date, date),
            billing_month  = COALESCE(billing_month, SUBSTR(date, 1, 7)),
            voucher_no     = CASE
                               WHEN voucher_no IS NULL OR voucher_no = ''
                               THEN 'VCH-LEG-' || printf('%05d', id)
                               ELSE voucher_no
                             END
        WHERE total_paisa = 0 AND (total > 0 OR paid_amount > 0 OR due_amount > 0)
        """
    )

    # Backfill 1 fee_payment receipt row for each pre-existing paid payslip without receipts
    paid_rows = conn.execute(
        """
        SELECT p.id, p.student_id, p.paid_paisa, COALESCE(p.payment_date, p.date) AS pdate
        FROM student_payslip p
        WHERE p.paid_paisa > 0
          AND NOT EXISTS (SELECT 1 FROM fee_payment fp WHERE fp.payslip_id = p.id)
        """
    ).fetchall()
    for r in paid_rows:
        pdate = r[3] or "2026-01-01"
        conn.execute(
            """
            INSERT INTO fee_payment
            (receipt_no, payslip_id, student_id, amount_paisa, payment_mode, reference, note,
             paid_at, payment_date, received_by_id, received_by)
            VALUES (?, ?, ?, ?, 'cash', '', 'Migrated historical payment', ?, ?, NULL, 'system')
            """,
            (
                f"RCP-LEG-{int(r[0]):05d}",
                int(r[0]),
                int(r[1]),
                int(r[2]),
                f"{pdate}T00:00:00Z",
                pdate,
            ),
        )


def _migration_003(conn: sqlite3.Connection) -> None:
    _add_column_if_missing(conn, "exam_result", "rank", "INTEGER")
    _add_column_if_missing(conn, "exam_result", "remarks", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "exam_subject", "is_absent", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "student_student", "b_form_no", "TEXT DEFAULT ''")
    _add_column_if_missing(conn, "student_student", "documents_json", "TEXT DEFAULT '{}'")
    _execute_sql_statements(conn, MIGRATION_003_SQL)


MIGRATIONS: list[tuple[int, str, Callable[[sqlite3.Connection], None]]] = [
    (1, "phase2_auth_audit_settings", _migration_001),
    (2, "phase3_fees_family_paisa_ledger", _migration_002),
    (3, "phase4_academics_calendar_admissions_ranks", _migration_003),
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
