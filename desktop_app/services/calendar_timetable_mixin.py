"""
Phase 4 Academic Calendar, Pakistani Holidays Preset & Timetable Substitution Mixin (G8, G21, S6, TT-1..4).

Extracted from `academic_engine_service.py` so every Python service file stays well under 600 lines.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from desktop_app.exceptions import NotFoundError, ValidationError, parse_date
from desktop_app.services.audit_service import utc_now_iso

PAKISTANI_HOLIDAY_PRESET = [
    ("02-05", "Kashmir Solidarity Day", "holiday"),
    ("03-23", "Pakistan Resolution Day", "holiday"),
    ("05-01", "Labour Day", "holiday"),
    ("08-14", "Independence Day of Pakistan", "holiday"),
    ("09-06", "Defence Day", "holiday"),
    ("11-09", "Iqbal Day", "holiday"),
    ("12-25", "Quaid-e-Azam Day", "holiday"),
]


class CalendarTimetableMixin:
    """Provides Academic Calendar, Holiday Presets, Weekly 2D Grid & Substitution methods."""

    db: Any
    audit: Any
    settings: Any

    # -------------------------------------------------------------------------
    # Academic Calendar & Pakistani Holiday Preset (G21, S6)
    # -------------------------------------------------------------------------
    def list_calendar_days(self, year: int | None = None, month: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if month:
            clauses.append("date LIKE ?")
            params.append(f"{month}%")
        elif year:
            clauses.append("date LIKE ?")
            params.append(f"{int(year)}-%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return self.db.fetch_all(f"SELECT * FROM calendar_day {where} ORDER BY date ASC", tuple(params))

    def get_holiday_on_date(self, target_date: str | None = None) -> dict[str, Any] | None:
        dt = (target_date or date.today().isoformat()).strip()[:10]
        return self.db.fetch_one(
            "SELECT * FROM calendar_day WHERE date = ? AND is_off_day = 1 LIMIT 1",
            (dt,),
        )

    def upsert_calendar_day(
        self,
        payload: dict[str, Any],
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        dt = parse_date(payload.get("date"), "Calendar Date").isoformat()
        title = (payload.get("title") or "").strip()
        if len(title) < 2:
            raise ValidationError("Calendar event/holiday title is required.")
        day_type = (payload.get("day_type") or "holiday").strip().lower()
        if day_type not in ("holiday", "ramazan", "exam_day", "ptm", "vacation", "event"):
            raise ValidationError(f"Unsupported day_type '{day_type}'.")
        is_off = 1 if payload.get("is_off_day", day_type in ("holiday", "vacation")) else 0
        bell_prof = (
            payload.get("bell_profile") or ("ramazan" if day_type == "ramazan" else "regular")
        ).strip().lower()
        if bell_prof not in ("regular", "ramazan", "winter"):
            bell_prof = "regular"
        note = (payload.get("note") or "").strip()[:200]
        now = utc_now_iso()

        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO calendar_day (date, title, day_type, is_off_day, bell_profile, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    title = excluded.title,
                    day_type = excluded.day_type,
                    is_off_day = excluded.is_off_day,
                    bell_profile = excluded.bell_profile,
                    note = excluded.note
                """,
                (dt, title, day_type, is_off, bell_prof, note, now),
            )
        if actor:
            self.audit.record(
                user_id=actor.get("id"),
                username=actor.get("username") or "admin",
                role=actor.get("role") or "admin",
                action="calendar.upsert",
                entity_type="calendar_day",
                entity_id=dt,
                summary=f"Configured calendar day {dt}: '{title}' ({day_type})",
                ip_address=ip_address,
            )
        return self.db.fetch_one("SELECT * FROM calendar_day WHERE date = ?", (dt,))  # type: ignore[return-value]

    def delete_calendar_day(self, day_id: int) -> None:
        with self.db.connection() as conn:
            conn.execute("DELETE FROM calendar_day WHERE id = ?", (day_id,))

    def seed_pakistani_holidays(self, year: int | None = None) -> int:
        yr = int(year or date.today().year)
        now = utc_now_iso()
        created = 0
        with self.db.connection() as conn:
            for mm_dd, title, dtype in PAKISTANI_HOLIDAY_PRESET:
                dt = f"{yr}-{mm_dd}"
                cur = conn.execute(
                    """
                    INSERT OR IGNORE INTO calendar_day
                        (date, title, day_type, is_off_day, bell_profile, note, created_at)
                    VALUES (?, ?, ?, 1, 'regular', 'National Holiday Preset', ?)
                    """,
                    (dt, title, dtype, now),
                )
                created += int(cur.rowcount or 0)
        return created

    # -------------------------------------------------------------------------
    # Timetable Weekly 2D Grid & Today's Live Strip + Substitution (G8, TT-1..4)
    # -------------------------------------------------------------------------
    def get_weekly_timetable_grid(
        self,
        *,
        class_id: int | None = None,
        teacher_id: int | None = None,
    ) -> dict[str, Any]:
        prefs = self.settings.get_preferences()
        short_mode = bool(prefs.get("short_bell_schedule") or prefs.get("ramazan_mode"))

        clauses = ["t.timetable_type = 'regular'"]
        params: list[Any] = []
        if class_id:
            clauses.append("t.standard_id = ?")
            params.append(int(class_id))
        if teacher_id:
            clauses.append("ttl.teacher_id = ?")
            params.append(int(teacher_id))

        where = " AND ".join(clauses)
        lines = self.db.fetch_all(
            f"""
            SELECT ttl.*, t.name AS timetable_name, t.standard_id,
                   ss.name AS class_name, sub.name AS subject_name, sub.code AS subject_code,
                   tch.name AS teacher_name, cr.name AS room_name
            FROM time_table_line ttl
            JOIN time_table t ON t.id = ttl.table_id
            JOIN school_standard ss ON ss.id = t.standard_id
            JOIN subject_subject sub ON sub.id = ttl.subject_id
            LEFT JOIN school_teacher tch ON tch.id = ttl.teacher_id
            LEFT JOIN class_room cr ON cr.id = COALESCE(ttl.class_room_id, t.class_room_id)
            WHERE {where}
            ORDER BY ttl.start_time ASC, ttl.id ASC
            """,
            tuple(params),
        )

        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
        grid: dict[str, list[dict[str, Any]]] = {d: [] for d in days}
        for ln in lines:
            dkey = (ln.get("week_day") or "monday").lower().strip()
            if dkey not in grid:
                grid[dkey] = []
            s_fl = float(ln["start_time"])
            e_fl = float(ln["end_time"])
            if short_mode:
                ln["time_label"] = f"{int(s_fl):02d}:00–{int(s_fl):02d}:40 (Short Bell)"
            else:
                ln["time_label"] = f"{int(s_fl):02d}:00–{int(e_fl):02d}:00"
            grid[dkey].append(ln)

        return {
            "bell_schedule": "short_seasonal" if short_mode else "regular",
            "days": days,
            "lines": lines,
            "grid": grid,
        }

    def get_today_live_periods(
        self,
        *,
        target_date: str | None = None,
        day_override: str | None = None,
        class_id: int | None = None,
    ) -> dict[str, Any]:
        dt_iso = (target_date or date.today().isoformat()).strip()[:10]
        dt_obj = parse_date(dt_iso, "Date")
        w_day = (day_override or dt_obj.strftime("%A")).lower().strip()
        holiday = self.get_holiday_on_date(dt_iso)

        clauses = ["t.timetable_type = 'regular'", "LOWER(ttl.week_day) = ?"]
        params: list[Any] = [w_day]
        if class_id:
            clauses.append("t.standard_id = ?")
            params.append(int(class_id))

        rows = self.db.fetch_all(
            f"""
            SELECT ttl.id AS line_id, ttl.table_id, ttl.start_time, ttl.end_time, ttl.week_day,
                   ttl.subject_id, ttl.teacher_id, t.standard_id,
                   ss.name AS class_name, sub.name AS subject_name,
                   tch.name AS teacher_name, cr.name AS room_name,
                   ts.id AS substitution_id, ts.substitute_teacher_id,
                   sub_tch.name AS substitute_teacher_name, ts.reason AS substitution_reason
            FROM time_table_line ttl
            JOIN time_table t ON t.id = ttl.table_id
            JOIN school_standard ss ON ss.id = t.standard_id
            JOIN subject_subject sub ON sub.id = ttl.subject_id
            LEFT JOIN school_teacher tch ON tch.id = ttl.teacher_id
            LEFT JOIN class_room cr ON cr.id = COALESCE(ttl.class_room_id, t.class_room_id)
            LEFT JOIN timetable_substitution ts
                   ON ts.line_id = ttl.id AND ts.date = ?
            LEFT JOIN school_teacher sub_tch ON sub_tch.id = ts.substitute_teacher_id
            WHERE {' AND '.join(clauses)}
            ORDER BY ttl.start_time ASC, ss.name ASC
            """,
            tuple([dt_iso] + params),
        )
        return {
            "date": dt_iso,
            "week_day": w_day,
            "holiday": holiday,
            "periods": rows,
        }

    def assign_substitution(
        self,
        *,
        target_date: str,
        line_id: int,
        substitute_teacher_id: int,
        reason: str = "",
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        dt_iso = parse_date(target_date, "Substitution Date").isoformat()
        line = self.db.fetch_one("SELECT * FROM time_table_line WHERE id = ?", (line_id,))
        if not line:
            raise NotFoundError(f"Timetable period line #{line_id} not found.")
        sub_tch = self.db.fetch_one("SELECT * FROM school_teacher WHERE id = ?", (substitute_teacher_id,))
        if not sub_tch:
            raise NotFoundError(f"Substitute teacher #{substitute_teacher_id} not found.")

        uname = (actor.get("username") if actor else None) or "admin"
        now = utc_now_iso()
        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO timetable_substitution
                    (date, line_id, original_teacher_id, substitute_teacher_id, reason, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(date, line_id) DO UPDATE SET
                    substitute_teacher_id = excluded.substitute_teacher_id,
                    reason = excluded.reason,
                    created_by = excluded.created_by,
                    created_at = excluded.created_at
                """,
                (
                    dt_iso,
                    int(line_id),
                    line.get("teacher_id"),
                    int(substitute_teacher_id),
                    (reason or "").strip()[:160],
                    uname,
                    now,
                ),
            )
        if actor:
            self.audit.record(
                user_id=actor.get("id"),
                username=uname,
                role=actor.get("role") or "admin",
                action="timetable.substitution",
                entity_type="timetable_substitution",
                entity_id=line_id,
                summary=f"Assigned substitute teacher '{sub_tch['name']}' for period #{line_id} on {dt_iso}",
                ip_address=ip_address,
            )
        return self.db.fetch_one(
            """
            SELECT ts.*, t.name AS substitute_teacher_name
            FROM timetable_substitution ts
            JOIN school_teacher t ON t.id = ts.substitute_teacher_id
            WHERE ts.date = ? AND ts.line_id = ?
            """,
            (dt_iso, int(line_id)),
        )  # type: ignore[return-value]
