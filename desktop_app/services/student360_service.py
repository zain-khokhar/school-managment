"""
Student 360° Profile & Activity Timeline Service (Phase 2 — S360-1..S360-8).

Assembles complete student bio, linked parents & siblings, 6 smart-button KPIs,
fee vouchers, attendance & leave records, exam results, library loans, transport/hostel
allocations, awards/discipline, and audit-log activity timeline in one read transaction.
"""

from __future__ import annotations

from typing import Any

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError


class Student360Service:
    """Single-transaction aggregator for the Student 360° profile view."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def get_student_360(self, student_id: int) -> dict[str, Any]:
        """Assemble Student 360° profile (S360-1..S360-8) in one transactional read."""
        with self.db.connection() as conn:
            stu_row = conn.execute(
                """
                SELECT s.*, ss.name AS class_name, ay.name AS year_name,
                       sch.name AS school_name, sm.name AS medium_name, sd.name AS division_name
                FROM student_student s
                LEFT JOIN school_standard ss ON ss.id = s.standard_id
                LEFT JOIN academic_year ay ON ay.id = s.year_id
                LEFT JOIN school_school sch ON sch.id = s.school_id
                LEFT JOIN standard_medium sm ON sm.id = s.medium_id
                LEFT JOIN standard_division sd ON sd.id = s.division_id
                WHERE s.id = ?
                """,
                (student_id,),
            ).fetchone()
            if not stu_row:
                raise NotFoundError(f"Student #{student_id} not found.")
            stu = dict(stu_row)

            parents = conn.execute(
                """
                SELECT p.* FROM school_parent p
                JOIN students_parents_rel r ON r.parent_id = p.id
                WHERE r.student_id = ?
                """,
                (student_id,),
            ).fetchall()

            parent_ids = [int(p["id"]) for p in parents]
            sib_map: dict[int, dict[str, Any]] = {}
            if parent_ids:
                placeholders = ",".join("?" for _ in parent_ids)
                for r in conn.execute(
                    f"""
                    SELECT DISTINCT s.id, s.pid, s.student_name, s.last, s.state, ss.name AS class_name
                    FROM student_student s
                    JOIN students_parents_rel rel ON rel.student_id = s.id
                    LEFT JOIN school_standard ss ON ss.id = s.standard_id
                    WHERE rel.parent_id IN ({placeholders}) AND s.id != ? AND s.active = 1
                    """,
                    (*parent_ids, student_id),
                ).fetchall():
                    sib_map[int(r["id"])] = dict(r)

            if stu.get("contact_mobile"):
                for r in conn.execute(
                    """
                    SELECT s.id, s.pid, s.student_name, s.last, s.state, ss.name AS class_name
                    FROM student_student s
                    LEFT JOIN school_standard ss ON ss.id = s.standard_id
                    WHERE s.contact_mobile = ? AND s.id != ? AND s.active = 1
                    """,
                    (stu["contact_mobile"], student_id),
                ).fetchall():
                    sib_map[int(r["id"])] = dict(r)

            payslips = conn.execute(
                """
                SELECT id, number, name, date, total, paid_amount, due_amount, payment_date, state
                FROM student_payslip WHERE student_id = ? ORDER BY date DESC, id DESC
                """,
                (student_id,),
            ).fetchall()

            att_summary = conn.execute(
                """
                SELECT COUNT(*) AS total_days,
                       SUM(CASE WHEN dal.is_present = 1 THEN 1 ELSE 0 END) AS present_days,
                       SUM(CASE WHEN dal.is_absent = 1 THEN 1 ELSE 0 END) AS absent_days
                FROM daily_attendance_line dal
                JOIN daily_attendance da ON da.id = dal.standard_id
                WHERE dal.stud_id = ?
                """,
                (student_id,),
            ).fetchone()
            leaves = conn.execute(
                "SELECT * FROM studentleave_request WHERE student_id = ? ORDER BY id DESC LIMIT 15",
                (student_id,),
            ).fetchall()

            results = conn.execute(
                """
                SELECT er.id, er.total, er.percentage, er.result, er.grade, er.state,
                       e.name AS exam_name, e.start_date
                FROM exam_result er
                JOIN exam_exam e ON e.id = er.s_exam_ids
                WHERE er.student_id = ? ORDER BY er.id DESC
                """,
                (student_id,),
            ).fetchall()

            books = conn.execute(
                """
                SELECT bi.id, bi.issue_code, bi.date_issue, bi.date_return, bi.state, bi.penalty,
                       b.name AS book_name
                FROM library_book_issue bi
                JOIN library_book b ON b.id = bi.book_id
                WHERE bi.student_id = ? ORDER BY bi.id DESC
                """,
                (student_id,),
            ).fetchall()

            transport = conn.execute(
                """
                SELECT tp.id, tp.amount, tp.state, tp.tr_end_date,
                       st.name AS route_name, fv.license_plate
                FROM transport_participant tp
                JOIN student_transport st ON st.id = tp.transport_id
                JOIN fleet_vehicle fv ON fv.id = tp.vehicle_id
                WHERE tp.name = ? AND tp.active = 1 ORDER BY tp.id DESC LIMIT 1
                """,
                (student_id,),
            ).fetchone()

            hostel = conn.execute(
                """
                SELECT hs.id, hs.hostel_id AS code, hs.status, hs.remaining_amount,
                       ht.name AS hostel_name, hr.room_no
                FROM hostel_student hs
                JOIN hostel_type ht ON ht.id = hs.hostel_info_id
                JOIN hostel_room hr ON hr.id = hs.room_id
                WHERE hs.student_id = ? AND hs.active = 1 ORDER BY hs.id DESC LIMIT 1
                """,
                (student_id,),
            ).fetchone()

            awards = conn.execute(
                "SELECT id, name, description FROM student_award WHERE award_list_id = ? ORDER BY id DESC",
                (student_id,),
            ).fetchall()

            discipline = conn.execute(
                "SELECT id, date, note, action_taken FROM student_descipline WHERE student_id = ? ORDER BY id DESC",
                (student_id,),
            ).fetchall()

            pid_val = (stu.get("pid") or "").strip()
            if pid_val:
                audit_rows = conn.execute(
                    """
                    SELECT id, username, role, action, summary, created_at
                    FROM audit_log
                    WHERE (entity_type IN ('student', 'student_student', 'students') AND entity_id = ?)
                       OR summary LIKE ?
                    ORDER BY id DESC LIMIT 25
                    """,
                    (str(student_id), f"%{pid_val}%"),
                ).fetchall()
            else:
                audit_rows = conn.execute(
                    """
                    SELECT id, username, role, action, summary, created_at
                    FROM audit_log
                    WHERE entity_type IN ('student', 'student_student', 'students') AND entity_id = ?
                    ORDER BY id DESC LIMIT 25
                    """,
                    (str(student_id),),
                ).fetchall()

        tot_days = int(att_summary["total_days"] or 0)
        pres_days = int(att_summary["present_days"] or 0)
        att_pct = round((pres_days / tot_days) * 100) if tot_days > 0 else None
        fee_due = sum(float(p["due_amount"] or 0.0) for p in payslips if p["state"] in ("confirm", "pending"))
        last_res = dict(results[0]) if results else None
        issued_cnt = sum(1 for b in books if b["state"] == "issue")

        return {
            "ok": True,
            "student": stu,
            "parents": [dict(p) for p in parents],
            "siblings": list(sib_map.values()),
            "smart_buttons": {
                "attendance_pct": att_pct,
                "attendance_detail": f"{pres_days}/{tot_days} days" if tot_days else "No sheets yet",
                "fee_due": fee_due,
                "last_exam": f"{last_res['percentage']}% ({last_res['grade'] or last_res['result']})" if last_res else "—",
                "library_issued": issued_cnt,
                "transport_route": transport["route_name"] if transport else "None",
                "hostel_room": f"{hostel['room_no']} ({hostel['hostel_name']})" if hostel else "Day Scholar",
            },
            "payslips": [dict(p) for p in payslips],
            "attendance": {
                "total_days": tot_days,
                "present_days": pres_days,
                "absent_days": int(att_summary["absent_days"] or 0),
                "leaves": [dict(l) for l in leaves],
            },
            "exam_results": [dict(r) for r in results],
            "library_issues": [dict(b) for b in books],
            "transport": dict(transport) if transport else None,
            "hostel": dict(hostel) if hostel else None,
            "awards": [dict(a) for a in awards],
            "discipline": [dict(d) for d in discipline],
            "audit_timeline": [dict(a) for a in audit_rows],
        }

