"""
Role-Aware Daily Overview Dashboards & Student 360° Service (Phase 2 — G9, S8, S360-1..8).

Implements 5 focused operational home views:
  1. Principal / Admin (P1..P7 + onboarding checklist)
  2. Teacher (T1..T5)
  3. Fee Clerk (F1..F5 tally & defaulters)
  4. Front Desk (FD-1..FD-3 seat meter & incomplete admissions)
  5. Exam In-Charge (EX-1..EX-3 marks progress matrix)

Includes a 60-second TTL cache automatically invalidated after mutating requests.
"""

from __future__ import annotations

from datetime import date, timedelta
import threading
import time
from typing import Any

from desktop_app.database import Database
from desktop_app.services.audit_service import AuditService
from desktop_app.services.backup_service import BackupService
from desktop_app.services.settings_service import SettingsService
from desktop_app.services.student360_service import Student360Service


class DashboardService:
    """Fast SQL aggregation engine for role homes and Student 360° profile."""

    CACHE_TTL_SECONDS = 60.0

    def __init__(
        self,
        db: Database,
        settings: SettingsService | None = None,
        backup: BackupService | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.db = db
        self.audit = audit or AuditService(db)
        self.settings = settings or SettingsService(db, self.audit)
        self.backup = backup or BackupService(db, self.settings, self.audit)
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def invalidate_cache(self) -> None:
        """Clear cached dashboard payloads immediately after a write operation."""
        with self._lock:
            self._cache.clear()

    def get_role_home(self, user: dict[str, Any]) -> dict[str, Any]:
        """Return role-specific daily overview payload within the <500ms budget."""
        t0 = time.perf_counter()
        raw_role = user.get("role", "principal")
        eff_role = "principal" if raw_role in ("admin", "principal") else raw_role
        cache_key = f"{eff_role}:{user.get('id', 0)}:{user.get('teacher_id') or 0}"

        now_mono = time.monotonic()
        with self._lock:
            hit = self._cache.get(cache_key)
            if hit and (now_mono - hit[0]) < self.CACHE_TTL_SECONDS:
                cached = dict(hit[1])
                cached["elapsed_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
                cached["cached"] = True
                return cached

        if eff_role == "teacher":
            payload = self._build_teacher_home(user)
        elif eff_role == "fee_clerk":
            payload = self._build_fee_clerk_home()
        elif eff_role == "front_desk":
            payload = self._build_front_desk_home()
        elif eff_role == "exam_incharge":
            payload = self._build_exam_incharge_home()
        else:
            payload = self._build_principal_home()

        payload["ok"] = True
        payload["role"] = eff_role
        payload["effective_role"] = eff_role
        payload["cached"] = False
        payload["elapsed_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)

        with self._lock:
            self._cache[cache_key] = (now_mono, dict(payload))
        return payload

    def _build_principal_home(self) -> dict[str, Any]:
        today = date.today()
        today_iso = today.isoformat()
        yesterday_iso = (today - timedelta(days=1)).isoformat()
        overdue_cutoff = (today - timedelta(days=30)).isoformat()
        next7_iso = (today + timedelta(days=7)).isoformat()

        with self.db.connection() as conn:
            # P1: Today's fee collection vs yesterday (from net active fee_payment receipts)
            p1_today = conn.execute(
                """
                SELECT COALESCE(SUM(amount_paisa), 0) / 100.0 AS amt, COUNT(*) AS cnt
                FROM fee_payment
                WHERE payment_date = ? AND reversed_at IS NULL
                """,
                (today_iso,),
            ).fetchone()
            p1_yest = conn.execute(
                """
                SELECT COALESCE(SUM(amount_paisa), 0) / 100.0 AS amt
                FROM fee_payment
                WHERE payment_date = ? AND reversed_at IS NULL
                """,
                (yesterday_iso,),
            ).fetchone()
            total_collected = conn.execute(
                "SELECT COALESCE(SUM(amount_paisa), 0) / 100.0 AS amt FROM fee_payment WHERE reversed_at IS NULL"
            ).fetchone()["amt"]

            # P2 & P5: Classes + Today's Attendance
            class_rows = conn.execute(
                """
                SELECT ss.id, ss.name, ss.capacity, ss.total_students, ss.remaining_seats,
                       t.name AS teacher_name,
                       da.id AS att_id, da.state AS att_state,
                       da.total_student AS att_total, da.total_presence AS att_present,
                       da.total_absent AS att_absent
                FROM school_standard ss
                LEFT JOIN school_teacher t ON t.id = ss.user_id
                LEFT JOIN daily_attendance da ON da.standard_id = ss.id AND da.date = ?
                ORDER BY ss.id ASC
                """,
                (today_iso,),
            ).fetchall()

            # P3: Fee dues & 30+ days overdue
            dues_row = conn.execute(
                """
                SELECT COALESCE(SUM(due_amount), 0.0) AS total_due,
                       COUNT(DISTINCT student_id) AS stu_cnt,
                       SUM(CASE WHEN date <= ? THEN 1 ELSE 0 END) AS overdue_30d
                FROM student_payslip
                WHERE state IN ('confirm', 'pending') AND due_amount > 0
                """,
                (overdue_cutoff,),
            ).fetchone()

            # Counts
            stu_counts = conn.execute(
                """
                SELECT SUM(CASE WHEN state IN ('done', 'fees_received') AND active = 1 THEN 1 ELSE 0 END) AS enrolled,
                       SUM(CASE WHEN state = 'draft' AND active = 1 THEN 1 ELSE 0 END) AS drafts
                FROM student_student
                """
            ).fetchone()
            teachers_cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM school_teacher WHERE active = 1"
            ).fetchone()["c"]

            # Pending leaves for P4
            pending_leaves = conn.execute(
                """
                SELECT lr.id, lr.name, lr.days, lr.reason, lr.state, lr.start_date, lr.end_date,
                       st.student_name, st.last, ss.name AS class_name
                FROM studentleave_request lr
                JOIN student_student st ON st.id = lr.student_id
                JOIN school_standard ss ON ss.id = lr.standard_id
                WHERE lr.state IN ('draft', 'toapprove')
                ORDER BY lr.id DESC LIMIT 10
                """
            ).fetchall()

            # Pending exam results for P4
            pending_exams = conn.execute(
                """
                SELECT e.id, e.name, COUNT(er.id) AS pending_cnt
                FROM exam_exam e
                JOIN exam_result er ON er.s_exam_ids = e.id AND er.state != 'done'
                WHERE e.active = 1
                GROUP BY e.id, e.name
                LIMIT 5
                """
            ).fetchall()

            # P6: Next 7 days events & exams
            upcoming_events = conn.execute(
                """
                SELECT 'event' AS kind, id, name AS title, start_date, end_date
                FROM school_event
                WHERE end_date >= ? AND start_date <= ?
                UNION ALL
                SELECT 'exam' AS kind, id, name AS title, start_date, end_date
                FROM exam_exam
                WHERE end_date >= ? AND start_date <= ? AND active = 1
                ORDER BY start_date ASC LIMIT 8
                """,
                (today_iso, next7_iso, today_iso, next7_iso),
            ).fetchall()

            # P7: Recent admissions
            recent_adm = conn.execute(
                """
                SELECT s.id, s.pid, s.student_name, s.last, s.admission_date, s.state,
                       ss.name AS class_name
                FROM student_student s
                LEFT JOIN school_standard ss ON ss.id = s.standard_id
                WHERE s.active = 1
                ORDER BY s.id DESC LIMIT 6
                """
            ).fetchall()

        class_strip = [dict(r) for r in class_rows]
        marked = [c for c in class_strip if c["att_id"] is not None]
        pres_sum = sum(int(c["att_present"] or 0) for c in marked)
        stud_sum = sum(int(c["att_total"] or 0) for c in marked)
        att_pct = round((pres_sum / stud_sum) * 100) if stud_sum > 0 else None
        unmarked = [c for c in class_strip if c["att_id"] is None and int(c["total_students"] or 0) > 0]

        health = self.backup.check_health()
        attention: list[dict[str, Any]] = []
        for c in unmarked:
            sub_txt = f"{c['total_students']} students • Teacher: {c.get('teacher_name') or 'Unassigned'}"
            attention.append(
                {
                    "type": "unmarked_attendance",
                    "severity": "warn",
                    "title": f"Attendance pending — {c['name']}",
                    "sub": sub_txt,
                    "detail": sub_txt,
                    "class_id": c["id"],
                    "action_tab": "attendance",
                    "action_label": "Open Roll Call",
                }
            )
        for ex in pending_exams:
            sub_txt = f"{ex['pending_cnt']} student result sheets not finalized"
            attention.append(
                {
                    "type": "pending_marks",
                    "severity": "warn",
                    "title": f"Marks confirmation pending — {ex['name']}",
                    "sub": sub_txt,
                    "detail": sub_txt,
                    "action_tab": "exam",
                    "action_label": "Open Exams",
                }
            )
        if health["backup_overdue"]:
            sub_txt = (
                f"Last backup: {health['last_backup_at'][:16].replace('T', ' ')}"
                if health["last_backup_at"]
                else "No backup has been created yet"
            )
            attention.append(
                {
                    "type": "backup_stale",
                    "severity": "warn",
                    "title": "Database backup overdue",
                    "sub": sub_txt,
                    "detail": sub_txt,
                    "action_tab": "settings",
                }
            )

        return {
            "cards": {
                "today_collection": {
                    "amount": float(p1_today["amt"] or 0.0),
                    "receipts": int(p1_today["cnt"] or 0),
                    "yesterday_amount": float(p1_yest["amt"] or 0.0),
                    "all_time_collected": float(total_collected or 0.0),
                },
                "today_attendance": {
                    "pct": att_pct,
                    "marked_classes": len(marked),
                    "total_classes": len(class_strip),
                    "unmarked_classes": len(unmarked),
                    "present": pres_sum,
                    "total": stud_sum,
                },
                "fee_dues": {
                    "total_due": float(dues_row["total_due"] or 0.0),
                    "students_count": int(dues_row["stu_cnt"] or 0),
                    "overdue_30d_count": int(dues_row["overdue_30d"] or 0),
                },
                "enrollment": {
                    "enrolled": int(stu_counts["enrolled"] or 0),
                    "drafts": int(stu_counts["drafts"] or 0),
                    "teachers": int(teachers_cnt),
                },
            },
            "attention_items": attention,
            "pending_leaves": [dict(r) for r in pending_leaves],
            "class_strip": class_strip,
            "upcoming_7d": [dict(r) for r in upcoming_events],
            "recent_admissions": [dict(r) for r in recent_adm],
            "recent_activity": self.audit.list_logs(page=1, per_page=8)["items"],
            "checklist": self.settings.get_onboarding_checklist(),
            "backup_health": health,
        }

    def _build_teacher_home(self, user: dict[str, Any]) -> dict[str, Any]:
        today = date.today()
        today_iso = today.isoformat()
        weekday = today.strftime("%A").lower()
        teacher_id = user.get("teacher_id")

        with self.db.connection() as conn:
            cls_clause = "WHERE ss.user_id = ?" if teacher_id else ""
            cls_params: tuple[Any, ...] = (today_iso, teacher_id) if teacher_id else (today_iso,)
            classes = conn.execute(
                f"""
                SELECT ss.id, ss.name, ss.total_students,
                       da.id AS att_id, da.state AS att_state,
                       da.total_presence, da.total_absent, da.total_student
                FROM school_standard ss
                LEFT JOIN daily_attendance da ON da.standard_id = ss.id AND da.date = ?
                {cls_clause}
                ORDER BY ss.id ASC
                """,
                cls_params,
            ).fetchall()
            if not classes and teacher_id:
                classes = conn.execute(
                    """
                    SELECT ss.id, ss.name, ss.total_students,
                           da.id AS att_id, da.state AS att_state,
                           da.total_presence, da.total_absent, da.total_student
                    FROM school_standard ss
                    LEFT JOIN daily_attendance da ON da.standard_id = ss.id AND da.date = ?
                    ORDER BY ss.id ASC
                    """,
                    (today_iso,),
                ).fetchall()

            tt_clause = "AND ttl.teacher_id = ?" if teacher_id else ""
            tt_params: tuple[Any, ...] = (weekday, teacher_id) if teacher_id else (weekday,)
            periods = conn.execute(
                f"""
                SELECT ttl.id, ttl.start_time, ttl.end_time, ttl.week_day,
                       sub.name AS subject_name, ss.name AS class_name,
                       cr.name AS room_name
                FROM time_table_line ttl
                JOIN time_table tt ON tt.id = ttl.table_id AND tt.timetable_type = 'regular'
                JOIN subject_subject sub ON sub.id = ttl.subject_id
                JOIN school_standard ss ON ss.id = tt.standard_id
                LEFT JOIN class_room cr ON cr.id = COALESCE(ttl.class_room_id, tt.class_room_id)
                WHERE LOWER(COALESCE(ttl.week_day, '')) = ? {tt_clause}
                ORDER BY ttl.start_time ASC LIMIT 12
                """,
                tt_params,
            ).fetchall()

            absent_rows = conn.execute(
                """
                SELECT st.id AS student_id, st.pid, st.student_name, st.last,
                       st.roll_no, st.contact_mobile, ss.name AS class_name
                FROM daily_attendance_line dal
                JOIN daily_attendance da ON da.id = dal.standard_id AND da.date = ?
                JOIN student_student st ON st.id = dal.stud_id
                JOIN school_standard ss ON ss.id = da.standard_id
                WHERE dal.is_absent = 1
                ORDER BY ss.id ASC, dal.roll_no ASC LIMIT 20
                """,
                (today_iso,),
            ).fetchall()

            pending_marks = conn.execute(
                """
                SELECT e.id, e.name, ss.name AS class_name, COUNT(er.id) AS pending_cnt
                FROM exam_result er
                JOIN exam_exam e ON e.id = er.s_exam_ids
                LEFT JOIN school_standard ss ON ss.id = er.standard_id
                WHERE er.state != 'done' AND e.active = 1
                GROUP BY e.id, e.name, ss.name LIMIT 8
                """
            ).fetchall()

            assignments = conn.execute(
                """
                SELECT ta.id, ta.name, ta.due_date, ta.state,
                       sub.name AS subject_name, ss.name AS class_name
                FROM school_teacher_assignment ta
                JOIN subject_subject sub ON sub.id = ta.subject_id
                JOIN school_standard ss ON ss.id = ta.standard_id
                ORDER BY ta.due_date DESC LIMIT 8
                """
            ).fetchall()

        return {
            "weekday": today.strftime("%A"),
            "classes_status": [dict(r) for r in classes],
            "today_periods": [dict(r) for r in periods],
            "absent_today": [dict(r) for r in absent_rows],
            "pending_marks": [dict(r) for r in pending_marks],
            "assignments_due": [dict(r) for r in assignments],
        }

    def _build_fee_clerk_home(self) -> dict[str, Any]:
        today = date.today()
        today_iso = today.isoformat()
        yesterday_iso = (today - timedelta(days=1)).isoformat()
        overdue_cutoff = (today - timedelta(days=30)).isoformat()

        with self.db.connection() as conn:
            pmt_tally = conn.execute(
                """
                SELECT COALESCE(SUM(CASE WHEN payment_date = ? THEN amount_paisa ELSE 0 END), 0) / 100.0 AS today_amount,
                       COALESCE(SUM(CASE WHEN payment_date = ? THEN amount_paisa ELSE 0 END), 0) / 100.0 AS yesterday_amount,
                       SUM(CASE WHEN payment_date = ? THEN 1 ELSE 0 END) AS receipts_today
                FROM fee_payment
                WHERE reversed_at IS NULL
                """,
                (today_iso, yesterday_iso, today_iso),
            ).fetchone()
            dues_tally = conn.execute(
                """
                SELECT COALESCE(SUM(due_amount), 0.0) AS total_due,
                       COUNT(DISTINCT CASE WHEN due_amount > 0 THEN student_id END) AS defaulter_count,
                       COALESCE(SUM(CASE WHEN COALESCE(due_date, date) <= ? THEN due_amount ELSE 0 END), 0.0) AS overdue_30d_amount
                FROM student_payslip
                WHERE state IN ('confirm', 'pending')
                """,
                (overdue_cutoff,),
            ).fetchone()

            defaulters = conn.execute(
                """
                SELECT p.id, COALESCE(NULLIF(p.voucher_no, ''), p.number) AS number, p.name,
                       p.date, p.due_date, p.total, p.paid_amount, p.due_amount, p.state,
                       s.id AS student_id, s.pid, s.student_name, s.last, s.contact_mobile,
                       ss.name AS class_name
                FROM student_payslip p
                JOIN student_student s ON s.id = p.student_id
                LEFT JOIN school_standard ss ON ss.id = s.standard_id
                WHERE p.state IN ('confirm', 'pending') AND p.due_amount > 0
                ORDER BY COALESCE(p.due_date, p.date) ASC, p.due_amount DESC LIMIT 25
                """
            ).fetchall()

            recent_paid = conn.execute(
                """
                SELECT fp.id, fp.receipt_no AS number, (fp.amount_paisa / 100.0) AS paid_amount,
                       fp.payment_date, fp.payment_mode, 'paid' AS state,
                       s.student_name, s.last, ss.name AS class_name
                FROM fee_payment fp
                JOIN student_student s ON s.id = fp.student_id
                LEFT JOIN school_standard ss ON ss.id = s.standard_id
                WHERE fp.reversed_at IS NULL
                ORDER BY fp.id DESC LIMIT 10
                """
            ).fetchall()

        return {
            "today_tally": {
                "today_amount": float(pmt_tally["today_amount"] or 0.0),
                "yesterday_amount": float(pmt_tally["yesterday_amount"] or 0.0),
                "receipts_today": int(pmt_tally["receipts_today"] or 0),
                "total_due": float(dues_tally["total_due"] or 0.0),
                "defaulter_count": int(dues_tally["defaulter_count"] or 0),
                "overdue_30d_amount": float(dues_tally["overdue_30d_amount"] or 0.0),
            },
            "defaulters": [dict(r) for r in defaulters],
            "recent_payments": [dict(r) for r in recent_paid],
        }

    def _build_front_desk_home(self) -> dict[str, Any]:
        today_iso = date.today().isoformat()
        with self.db.connection() as conn:
            seat_rows = conn.execute(
                """
                SELECT ss.id, ss.name, ss.capacity, ss.total_students, ss.remaining_seats,
                       t.name AS teacher_name
                FROM school_standard ss
                LEFT JOIN school_teacher t ON t.id = ss.user_id
                ORDER BY ss.id ASC
                """
            ).fetchall()

            incomplete = conn.execute(
                """
                SELECT s.id, s.pid, s.student_name, s.last, s.state, s.contact_mobile,
                       s.admission_date, ss.name AS class_name
                FROM student_student s
                LEFT JOIN school_standard ss ON ss.id = s.standard_id
                WHERE s.active = 1 AND (s.state = 'draft' OR COALESCE(s.contact_mobile, '') = '')
                ORDER BY s.id DESC LIMIT 20
                """
            ).fetchall()

            today_adm = conn.execute(
                "SELECT COUNT(*) AS c FROM student_student WHERE admission_date = ? AND active = 1",
                (today_iso,),
            ).fetchone()["c"]
            active_stu = conn.execute(
                "SELECT COUNT(*) AS c FROM student_student WHERE state IN ('done', 'fees_received') AND active = 1"
            ).fetchone()["c"]

        seats_list = [dict(r) for r in seat_rows]
        free_total = sum(max(0, int(r["remaining_seats"] or 0)) for r in seats_list)
        return {
            "kpis": {
                "admissions_today": int(today_adm),
                "available_seats_total": free_total,
                "incomplete_count": len(incomplete),
                "active_students": int(active_stu),
            },
            "seat_meter": seats_list,
            "incomplete_admissions": [dict(r) for r in incomplete],
        }

    def _build_exam_incharge_home(self) -> dict[str, Any]:
        with self.db.connection() as conn:
            kpis = conn.execute(
                """
                SELECT (SELECT COUNT(*) FROM exam_exam WHERE state IN ('draft', 'running') AND active = 1) AS active_exams,
                       SUM(CASE WHEN state != 'done' THEN 1 ELSE 0 END) AS pending_results,
                       SUM(CASE WHEN state = 'done' THEN 1 ELSE 0 END) AS finalized_results,
                       SUM(CASE WHEN state IN ('re-evaluation', 're-evaluation_confirm') THEN 1 ELSE 0 END) AS reeval_requests
                FROM exam_result
                """
            ).fetchone()

            matrix = conn.execute(
                """
                SELECT e.id AS exam_id, e.name AS exam_name, e.state AS exam_state,
                       COALESCE(ss.name, 'Unassigned') AS class_name,
                       COUNT(er.id) AS total_results,
                       SUM(CASE WHEN er.state = 'done' THEN 1 ELSE 0 END) AS finalized_count,
                       SUM(CASE WHEN er.state != 'done' THEN 1 ELSE 0 END) AS pending_count,
                       ROUND(AVG(er.percentage), 1) AS avg_pct
                FROM exam_exam e
                LEFT JOIN exam_result er ON er.s_exam_ids = e.id
                LEFT JOIN school_standard ss ON ss.id = er.standard_id
                WHERE e.active = 1
                GROUP BY e.id, e.name, e.state, ss.name
                ORDER BY e.id DESC
                """
            ).fetchall()

        return {
            "exam_kpis": {
                "active_exams": int(kpis["active_exams"] or 0),
                "pending_results": int(kpis["pending_results"] or 0),
                "finalized_results": int(kpis["finalized_results"] or 0),
                "reeval_requests": int(kpis["reeval_requests"] or 0),
            },
            "marks_matrix": [dict(r) for r in matrix],
        }

    def get_student_360(self, student_id: int) -> dict[str, Any]:
        """Delegate Student 360° profile assembly to Student360Service."""
        return Student360Service(self.db).get_student_360(student_id)

