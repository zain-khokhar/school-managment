"""
School Settings, Preferences & First-Run Setup Checklist Service (Phase 2 — G22, SET-1..4).
"""

from __future__ import annotations

import json
from typing import Any

from desktop_app.database import Database
from desktop_app.exceptions import ValidationError
from desktop_app.services.audit_service import AuditService, utc_now_iso

DEFAULT_PREFERENCES: dict[str, Any] = {
    "bilingual_prints": False,
    "thermal_receipt_default": False,
    "enable_hostel": True,
    "enable_transport": True,
    "ramazan_mode": False,
    "short_bell_schedule": False,
    "checklist_dismissed": False,
    "bank_name": "",
    "bank_account_title": "",
    "bank_account_no": "",
    "print_footer_note": "Computer generated school record.",
}


class SettingsService:
    """Manages key-value school settings, school profile, and onboarding checklist."""

    def __init__(self, db: Database, audit: AuditService | None = None) -> None:
        self.db = db
        self.audit = audit or AuditService(db)

    def get_raw_map(self) -> dict[str, str]:
        rows = self.db.fetch_all("SELECT key, value FROM school_setting")
        return {r["key"]: r["value"] for r in rows}

    def set_value(self, key: str, value: Any, updated_by: str = "system") -> None:
        encoded = json.dumps(value) if not isinstance(value, str) else value
        now = utc_now_iso()
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO school_setting (key, value, updated_at, updated_by)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at,
                    updated_by = excluded.updated_by
                """,
                (key, encoded, now, updated_by),
            )

    def get_preferences(self) -> dict[str, Any]:
        raw = self.get_raw_map()
        prefs = dict(DEFAULT_PREFERENCES)
        for key, default_val in DEFAULT_PREFERENCES.items():
            if key not in raw:
                continue
            stored = raw[key]
            if isinstance(default_val, bool):
                prefs[key] = stored.lower() in ("true", "1", "yes")
            else:
                try:
                    prefs[key] = json.loads(stored)
                except Exception:
                    prefs[key] = stored
        prefs["last_backup_at"] = raw.get("last_backup_at", "")
        prefs["last_backup_file"] = raw.get("last_backup_file", "")
        return prefs

    def update_preferences(
        self,
        patch: dict[str, Any],
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        allowed_keys = set(DEFAULT_PREFERENCES.keys())
        updated_keys: list[str] = []
        uname = actor["username"] if actor else "system"

        for key, val in patch.items():
            if key not in allowed_keys:
                continue
            if isinstance(DEFAULT_PREFERENCES[key], bool):
                clean_val: Any = bool(val)
            else:
                clean_val = str(val or "").strip()[:200]
            self.set_value(key, clean_val, updated_by=uname)
            updated_keys.append(key)

        if patch.get("active_year_id"):
            year_id = int(patch["active_year_id"])
            with self.db.connection() as conn:
                exists = conn.execute(
                    "SELECT id FROM academic_year WHERE id = ?", (year_id,)
                ).fetchone()
                if not exists:
                    raise ValidationError("Selected academic year does not exist.")
                conn.execute("UPDATE academic_year SET current = 0")
                conn.execute("UPDATE academic_year SET current = 1 WHERE id = ?", (year_id,))
            updated_keys.append("active_year_id")

        if actor and updated_keys:
            self.audit.record(
                user_id=actor["id"],
                username=actor["username"],
                role=actor["role"],
                action="settings.preferences",
                entity_type="school_setting",
                summary=f"Updated preferences: {', '.join(updated_keys)}",
                ip_address=ip_address,
            )
        return self.get_preferences()

    def get_school_profile(self) -> dict[str, Any]:
        school = self.db.fetch_one("SELECT * FROM school_school ORDER BY id ASC LIMIT 1")
        if not school:
            return {
                "id": None,
                "name": "School ERP",
                "code": "SCH",
                "street": "",
                "city": "",
                "phone": "",
                "contact_phone": "",
                "contact_mobile": "",
                "currency_symbol": "Rs.",
                "required_age": 6,
            }
        out = dict(school)
        out["phone"] = out.get("contact_phone") or out.get("contact_mobile") or ""
        return out

    def update_school_profile(
        self,
        payload: dict[str, Any],
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        name = (payload.get("name") or "").strip()
        if len(name) < 2:
            raise ValidationError("School name must be at least 2 characters.")

        profile = self.get_school_profile()
        code = (payload.get("code") or profile.get("code") or "MAIN").strip().upper()[:12]
        street = (payload.get("street") or profile.get("street") or "").strip()[:200]
        city = (payload.get("city") or "").strip()[:100]
        phone = (payload.get("contact_phone") or payload.get("phone") or "").strip()[:40]
        mobile = (payload.get("contact_mobile") or profile.get("contact_mobile") or "").strip()[:40]
        req_age = max(3, min(18, int(payload.get("required_age") or profile.get("required_age") or 6)))

        with self.db.connection() as conn:
            if profile.get("id"):
                conn.execute(
                    """
                    UPDATE school_school
                    SET name = ?, code = ?, street = ?, city = ?, contact_phone = ?,
                        contact_mobile = ?, required_age = ?
                    WHERE id = ?
                    """,
                    (name, code, street, city, phone, mobile, req_age, profile["id"]),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO school_school (name, code, street, city, contact_phone, contact_mobile, required_age)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (name, code, street, city, phone, mobile, req_age),
                )

        # Update active academic year if supplied alongside school profile
        year_id = payload.get("academic_year_id") or payload.get("active_year_id")
        if year_id:
            self.update_preferences({"active_year_id": int(year_id)}, actor=None)

        # Also update optional bank header fields in school_setting
        bank_patch = {
            k: payload[k]
            for k in ("bank_name", "bank_account_title", "bank_account_no", "print_footer_note")
            if k in payload
        }
        if bank_patch:
            self.update_preferences(bank_patch, actor=None)

        if actor:
            self.audit.record(
                user_id=actor["id"],
                username=actor["username"],
                role=actor["role"],
                action="settings.school_profile",
                entity_type="school_school",
                entity_id=profile.get("id") or 1,
                summary=f"Updated school profile '{name}'",
                ip_address=ip_address,
            )
        return self.get_school_profile()

    def get_onboarding_checklist(self) -> dict[str, Any]:
        """Compute SET-1 5-step onboarding checklist status from live database state."""
        school = self.get_school_profile()
        prefs = self.get_preferences()
        cur_year = self.db.fetch_one("SELECT id, name FROM academic_year WHERE current = 1 LIMIT 1")
        classes_cnt = int(self.db.fetch_one("SELECT COUNT(*) AS c FROM school_standard")["c"])
        fees_cnt = int(self.db.fetch_one("SELECT COUNT(*) AS c FROM student_fees_structure")["c"])

        has_school = bool(
            school.get("id")
            and school.get("name")
            and (school.get("contact_phone") or school.get("contact_mobile") or school.get("street"))
        )
        has_backup = bool(prefs.get("last_backup_at"))

        steps = [
            {
                "key": "school_profile",
                "title": "School Identity & Print Header",
                "done": has_school,
                "detail": school.get("name") or "Configure school name, address, and contact",
                "target_tab": "settings",
            },
            {
                "key": "academic_year",
                "title": "Active Academic Year",
                "done": cur_year is not None,
                "detail": cur_year["name"] if cur_year else "Select current academic session",
                "target_tab": "settings",
            },
            {
                "key": "classes_seats",
                "title": "Classes & Seat Capacity",
                "done": classes_cnt > 0,
                "detail": f"{classes_cnt} classes configured" if classes_cnt else "Create classes and seat limits",
                "target_tab": "school",
            },
            {
                "key": "fee_structure",
                "title": "Fee Heads & Structure",
                "done": fees_cnt > 0,
                "detail": f"{fees_cnt} fee structures ready" if fees_cnt else "Define monthly tuition fee heads",
                "target_tab": "fees",
            },
            {
                "key": "first_backup",
                "title": "Database Safety Backup",
                "done": has_backup,
                "detail": (
                    f"Last backup: {prefs['last_backup_at'][:16].replace('T', ' ')}"
                    if has_backup
                    else "Create your first verified local backup"
                ),
                "target_tab": "settings",
            },
        ]
        for s in steps:
            s["label"] = s["title"]
            s["tab"] = s["target_tab"]
        completed = sum(1 for s in steps if s["done"])
        return {
            "completed": completed,
            "completed_count": completed,
            "total": len(steps),
            "total_count": len(steps),
            "dismissed": bool(prefs.get("checklist_dismissed")),
            "steps": steps,
        }

