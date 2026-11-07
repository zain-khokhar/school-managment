"""
desktop_app/services/outbox_service.py — Outbox, WhatsApp & Rabta Messaging Service (Phase 5).

Implements ADVANCEMENT_PLAN.md G12 + S4:
  - Offline-first Outbox queue (`outbox_message` table)
  - Pakistani mobile number validation & normalization (+92 / 03xx)
  - Safe `wa.me` Click-to-Chat URL generation (zero API cost, zero ban risk)
  - Message templating & auto-triggers (Absent alerts, Fee reminders, Exam results, Circulars)
  - Deduplication per student + template + date
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any
import urllib.parse

from desktop_app.database import Database
from desktop_app.services.audit_service import AuditService
from desktop_app.services.outbox_triggers_mixin import OutboxTriggersMixin
from desktop_app.services.settings_service import SettingsService


def clean_pakistani_phone(raw: str | None) -> str:
    """Normalize a Pakistani mobile number into international digits format (e.g., '923001234567')."""
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw).strip())
    if not digits:
        return ""
    if digits.startswith("0092"):
        digits = digits[2:]
    elif digits.startswith("03") and len(digits) == 11:
        digits = "92" + digits[1:]
    elif digits.startswith("3") and len(digits) == 10:
        digits = "92" + digits
    elif digits.startswith("92") and len(digits) >= 11:
        pass
    return digits


def build_whatsapp_link(phone: str | None, text: str) -> str:
    """Build an official WhatsApp click-to-chat URL."""
    clean = clean_pakistani_phone(phone)
    if not clean or len(clean) < 10:
        return ""
    encoded_text = urllib.parse.quote(text.strip())
    return f"https://wa.me/{clean}?text={encoded_text}"


class OutboxService(OutboxTriggersMixin):
    """Manages the offline-first Outbox messaging queue and WhatsApp click-to-chat dispatches."""

    def __init__(
        self,
        database: Database,
        audit_svc: AuditService | None = None,
        settings_svc: SettingsService | None = None,
    ) -> None:
        self.db = database
        self.audit = audit_svc
        self.settings = settings_svc

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _today(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")

    def _school_name(self) -> str:
        if self.settings:
            profile = self.settings.get_school_profile()
            if profile.get("school_name"):
                return profile["school_name"]
        return "School ERP"

    # -------------------------------------------------------------------------
    # Templates Management
    # -------------------------------------------------------------------------
    def list_templates(self) -> list[dict[str, Any]]:
        """List all message templates."""
        return self.db.fetch_all(
            "SELECT * FROM message_template WHERE active = 1 ORDER BY category, code"
        )

    def get_template(self, code: str) -> dict[str, Any] | None:
        """Fetch template by unique code."""
        rows = self.db.fetch_all(
            "SELECT * FROM message_template WHERE code = ? COLLATE NOCASE", (code,)
        )
        return rows[0] if rows else None

    def update_template(self, template_id: int, title: str, body_template: str) -> bool:
        """Update an existing template title and body."""
        with self.db.connection() as conn:
            conn.execute(
                """
                UPDATE message_template
                SET title = ?, body_template = ?, updated_at = ?
                WHERE id = ?
                """,
                (title.strip(), body_template.strip(), self._now(), template_id),
            )
        if self.audit:
            self.audit.record(
                user_id=None,
                username="system",
                role="admin",
                action="update_template",
                entity_type="message_template",
                entity_id=template_id,
                summary=f"Updated template {title}",
            )
        return True

    # -------------------------------------------------------------------------
    # Outbox Queue Management
    # -------------------------------------------------------------------------
    def enqueue_message(
        self,
        *,
        channel: str = "whatsapp",
        to_name: str,
        to_phone: str = "",
        to_email: str = "",
        template_code: str,
        category: str = "general",
        subject: str = "",
        params: dict[str, Any] | None = None,
        body_override: str | None = None,
        student_id: int | None = None,
        family_key: str = "",
        class_id: int | None = None,
        dedupe_date: str | None = None,
        created_by: str = "system",
    ) -> int:
        """Enqueue a message into the Outbox with duplicate suppression."""
        date_stamp = dedupe_date or self._today()
        phone_clean = clean_pakistani_phone(to_phone)

        # Check deduplication
        if student_id:
            dup = self.db.fetch_all(
                """
                SELECT id FROM outbox_message
                WHERE student_id = ? AND template_code = ? AND dedupe_date = ?
                  AND status != 'cancelled'
                LIMIT 1
                """,
                (student_id, template_code, date_stamp),
            )
            if dup:
                return int(dup[0]["id"])
        elif family_key:
            dup = self.db.fetch_all(
                """
                SELECT id FROM outbox_message
                WHERE family_key = ? AND template_code = ? AND dedupe_date = ?
                  AND status != 'cancelled'
                LIMIT 1
                """,
                (family_key, template_code, date_stamp),
            )
            if dup:
                return int(dup[0]["id"])

        body = body_override or ""
        payload = params or {}
        if not body:
            tpl = self.get_template(template_code)
            if tpl:
                body = self.render_template(tpl["body_template"], payload)
            else:
                body = subject or "Notification from School ERP."

        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO outbox_message (
                    channel, to_name, to_phone, to_email, template_code, category,
                    subject, payload_json, body_text, status, attempts, dedupe_date,
                    created_at, created_by, student_id, family_key, class_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ready', 0, ?, ?, ?, ?, ?, ?)
                """,
                (
                    channel,
                    to_name.strip(),
                    phone_clean,
                    (to_email or "").strip(),
                    template_code,
                    category,
                    subject.strip(),
                    json.dumps(payload),
                    body.strip(),
                    date_stamp,
                    self._now(),
                    created_by,
                    student_id,
                    family_key,
                    class_id,
                ),
            )
            msg_id = cur.lastrowid
        return int(msg_id)

    def render_template(self, template_str: str, params: dict[str, Any]) -> str:
        """Safely interpolate parameters into template string."""
        context = {
            "school_name": self._school_name(),
            "date": self._today(),
            **params,
        }
        res = template_str
        for k, v in context.items():
            res = res.replace("{" + k + "}", str(v if v is not None else ""))
        return res

    def list_messages(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        class_id: int | None = None,
        q: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> dict[str, Any]:
        """Return paginated outbox messages with WhatsApp link metadata."""
        conditions = ["1=1"]
        params: list[Any] = []

        if status and status != "all":
            conditions.append("m.status = ?")
            params.append(status)
        if category and category != "all":
            conditions.append("m.category = ?")
            params.append(category)
        if class_id:
            conditions.append("m.class_id = ?")
            params.append(class_id)
        if q:
            term = f"%{q.strip()}%"
            conditions.append("(m.to_name LIKE ? OR m.to_phone LIKE ? OR m.body_text LIKE ?)")
            params.extend([term, term, term])

        where_clause = " AND ".join(conditions)
        count_sql = f"SELECT COUNT(*) AS total FROM outbox_message m WHERE {where_clause}"
        total_row = self.db.fetch_all(count_sql, tuple(params))
        total = int(total_row[0]["total"]) if total_row else 0

        offset = max(0, (page - 1) * per_page)
        list_sql = f"""
            SELECT m.*, s.name as class_name, st.roll_no, st.pid
            FROM outbox_message m
            LEFT JOIN school_standard s ON s.id = m.class_id
            LEFT JOIN student_student st ON st.id = m.student_id
            WHERE {where_clause}
            ORDER BY m.id DESC
            LIMIT ? OFFSET ?
        """
        list_params = params + [per_page, offset]
        rows = self.db.fetch_all(list_sql, tuple(list_params))

        items = []
        for r in rows:
            item = dict(r)
            item["whatsapp_link"] = build_whatsapp_link(item.get("to_phone"), item.get("body_text", ""))
            items.append(item)

        pages = max(1, (total + per_page - 1) // per_page)
        return {
            "items": items,
            "total": total,
            "page": page,
            "pages": pages,
            "per_page": per_page,
            "stats": self.get_stats(),
        }

    def get_stats(self) -> dict[str, int]:
        """Return counts of messages across statuses and today's absent queue."""
        rows = self.db.fetch_all(
            "SELECT status, COUNT(*) as cnt FROM outbox_message GROUP BY status"
        )
        counts = {r["status"]: int(r["cnt"]) for r in rows}
        today = self._today()
        absent_today = self.db.fetch_all(
            """
            SELECT COUNT(*) as cnt FROM outbox_message
            WHERE category = 'attendance' AND dedupe_date = ? AND status = 'ready'
            """,
            (today,),
        )
        return {
            "total": sum(counts.values()),
            "ready": counts.get("ready", 0),
            "sent": counts.get("sent", 0),
            "queued": counts.get("queued", 0),
            "cancelled": counts.get("cancelled", 0),
            "failed": counts.get("failed", 0),
            "absent_today_ready": int(absent_today[0]["cnt"]) if absent_today else 0,
        }

    def mark_sent(self, msg_id: int, user: str = "clerk") -> bool:
        """Mark a message as sent by the clerk."""
        with self.db.connection() as conn:
            conn.execute(
                """
                UPDATE outbox_message
                SET status = 'sent', sent_at = ?, last_error = ''
                WHERE id = ?
                """,
                (self._now(), msg_id),
            )
        if self.audit:
            self.audit.record(
                user_id=None,
                username=user,
                role="fee_clerk",
                action="mark_outbox_sent",
                entity_type="outbox_message",
                entity_id=msg_id,
                summary="Marked outbox message sent",
            )
        return True

    def cancel_message(self, msg_id: int, user: str = "clerk") -> bool:
        """Cancel an outbox message."""
        with self.db.connection() as conn:
            conn.execute("UPDATE outbox_message SET status = 'cancelled' WHERE id = ?", (msg_id,))
        return True

    def retry_message(self, msg_id: int, user: str = "clerk") -> bool:
        """Reset an outbox message to ready."""
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE outbox_message SET status = 'ready', attempts = attempts + 1 WHERE id = ?",
                (msg_id,),
            )
        return True

    def delete_message(self, msg_id: int, user: str = "admin") -> bool:
        """Permanently delete an outbox message."""
        with self.db.connection() as conn:
            conn.execute("DELETE FROM outbox_message WHERE id = ?", (msg_id,))
        return True

    def bulk_action(self, action: str, msg_ids: list[int], user: str = "clerk") -> int:
        """Apply an action to multiple outbox messages."""
        if not msg_ids:
            return 0
        count = 0
        for mid in msg_ids:
            if action == "mark_sent":
                self.mark_sent(mid, user)
                count += 1
            elif action == "cancel":
                self.cancel_message(mid, user)
                count += 1
            elif action == "retry":
                self.retry_message(mid, user)
                count += 1
            elif action == "delete":
                self.delete_message(mid, user)
                count += 1
        return count
