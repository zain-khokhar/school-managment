"""
Audit trail service for School Management ERP (Phase 2 — G3).

Every mutating action and security event is recorded with actor identity,
timestamp, entity metadata, and secret-redacted summaries.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from desktop_app.database import Database

REDACTED_FIELDS = frozenset(
    {
        "password",
        "secret",
        "new_secret",
        "current_secret",
        "pin",
        "token",
        "session_token",
        "recovery_code",
        "new_recovery_code",
        "password_hash",
        "password_salt",
        "recovery_hash",
        "recovery_salt",
    }
)


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format (seconds precision)."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def redact_dict(payload: Any) -> dict[str, Any]:
    """Return a new dictionary with any credential/secret keys replaced."""
    if not isinstance(payload, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, val in payload.items():
        key_lower = str(key).lower()
        if key_lower in REDACTED_FIELDS or "secret" in key_lower or "password" in key_lower or "token" in key_lower:
            cleaned[str(key)] = "[REDACTED]"
        elif isinstance(val, dict):
            cleaned[str(key)] = redact_dict(val)
        else:
            text = str(val)
            cleaned[str(key)] = text[:160] if len(text) > 160 else val
    return cleaned


class AuditService:
    """Append-only audit log reader and writer."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self,
        *,
        user_id: int | None,
        username: str,
        role: str,
        action: str,
        entity_type: str,
        entity_id: str | int | None = None,
        summary: str = "",
        ip_address: str = "127.0.0.1",
    ) -> int:
        """Insert a single immutable audit_log row and return its ID."""
        safe_summary = summary.strip()[:400] if summary else action
        ent_id_str = str(entity_id) if entity_id is not None else None
        now = utc_now_iso()
        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO audit_log (
                    user_id, username, role, action, entity_type,
                    entity_id, summary, ip_address, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    username or "anonymous",
                    role or "unauthenticated",
                    action,
                    entity_type,
                    ent_id_str,
                    safe_summary,
                    ip_address or "127.0.0.1",
                    now,
                ),
            )
            return int(cur.lastrowid)

    def list_logs(
        self,
        *,
        entity_type: str | None = None,
        entity_id: str | int | None = None,
        username: str | None = None,
        page: int = 1,
        per_page: int = 50,
    ) -> dict[str, Any]:
        """Return paginated audit trail entries ordered newest-first."""
        safe_page = max(1, int(page))
        safe_limit = min(100, max(1, int(per_page)))
        clauses: list[str] = []
        params: list[Any] = []

        if entity_type:
            clauses.append("entity_type = ?")
            params.append(entity_type)
        if entity_id is not None and str(entity_id) != "":
            clauses.append("entity_id = ?")
            params.append(str(entity_id))
        if username:
            clauses.append("username = ?")
            params.append(username)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        offset = (safe_page - 1) * safe_limit

        with self.db.connection() as conn:
            cnt_row = conn.execute(
                f"SELECT COUNT(*) AS c FROM audit_log {where}",
                tuple(params),
            ).fetchone()
            total = int(cnt_row["c"]) if cnt_row else 0
            rows = conn.execute(
                f"""
                SELECT id, user_id, username, role, action, entity_type,
                       entity_id, summary, ip_address, created_at
                FROM audit_log
                {where}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                tuple(params + [safe_limit, offset]),
            ).fetchall()

        return {
            "items": [dict(r) for r in rows],
            "total": total,
            "page": safe_page,
            "pages": max(1, -(-total // safe_limit)),
        }

