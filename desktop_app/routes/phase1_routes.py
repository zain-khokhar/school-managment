"""
Phase 1 Routes — Paginated Students, Today Attendance, Bulk Haziri Mark & Global Search.

Extracted from api.py to enforce the anti-monolith rule (<= 400 lines per Python module).
Includes structured request timing logs for performance analysis (D4 requirement).
"""

from __future__ import annotations

from datetime import date as _date
import logging
import time
from typing import Any

from flask import Flask, Response, jsonify, request

from desktop_app.database import Database
from desktop_app.exceptions import SchoolERPError
from desktop_app.services.attendance_service import AttendanceService

logger = logging.getLogger("school_erp.perf")


def register_phase1_routes(
    app: Flask,
    database: Database,
    att_svc: AttendanceService,
) -> None:
    """Register Phase 1 enterprise routes on the Flask application."""

    @app.get("/api/students/list")
    def list_students_paginated() -> Response:
        """Paginated student directory — avoids returning 1000+ rows in one shot."""
        t0 = time.perf_counter()
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 50))))
        q = request.args.get("q", "").strip()
        class_id = request.args.get("class_id", "").strip()
        year_id = request.args.get("year_id", "").strip()
        state_f = request.args.get("state", "").strip()

        clauses: list[str] = []
        params: list[Any] = []

        if q:
            clauses.append(
                "(s.student_name LIKE ? OR s.last LIKE ? OR s.pid LIKE ? "
                "OR CAST(s.roll_no AS TEXT) LIKE ? OR s.contact_mobile LIKE ?)"
            )
            like = f"%{q}%"
            params.extend([like, like, like, like, like])
        if class_id:
            clauses.append("s.standard_id = ?")
            params.append(int(class_id))
        if year_id:
            clauses.append("s.year_id = ?")
            params.append(int(year_id))
        if state_f:
            clauses.append("s.state = ?")
            params.append(state_f)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

        with database.connection() as conn:
            total_row = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM student_student s "
                f"LEFT JOIN school_standard ss ON ss.id = s.standard_id "
                f"LEFT JOIN academic_year ay ON ay.id = s.year_id {where}",
                params,
            ).fetchone()
            total = int(total_row["cnt"]) if total_row else 0
            offset = (page - 1) * per_page
            rows = conn.execute(
                f"""
                SELECT s.id, s.pid, s.student_name, s.middle, s.last,
                       s.roll_no, s.state, s.gender, s.date_of_birth,
                       s.contact_mobile, s.standard_id, s.year_id,
                       ss.name AS class_name,
                       ay.name AS year_name
                FROM student_student s
                LEFT JOIN school_standard ss ON ss.id = s.standard_id
                LEFT JOIN academic_year ay   ON ay.id = s.year_id
                {where}
                ORDER BY ss.name ASC, s.roll_no ASC, s.student_name ASC
                LIMIT ? OFFSET ?
                """,
                params + [per_page, offset],
            ).fetchall()

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            "students_list page=%d per_page=%d total=%d q=%r elapsed_ms=%.2f",
            page, per_page, total, q, elapsed_ms,
        )

        return jsonify({
            "ok": True,
            "items": [dict(r) for r in rows],
            "total": total,
            "page": page,
            "pages": max(1, -(-total // per_page)),
            "elapsed_ms": elapsed_ms,
        })

    @app.get("/api/attendance/today/<int:class_id>")
    def get_today_attendance(class_id: int) -> Response:
        """Get today's attendance sheet for a class if it already exists."""
        today = _date.today().isoformat()
        with database.connection() as conn:
            row = conn.execute(
                """
                SELECT da.*, ss.name AS class_name
                FROM daily_attendance da
                JOIN school_standard ss ON ss.id = da.standard_id
                WHERE da.standard_id = ? AND da.date = ?
                ORDER BY da.id DESC
                LIMIT 1
                """,
                (class_id, today),
            ).fetchone()
        if not row:
            return jsonify({"ok": True, "attendance": None})

        att = dict(row)
        att["student_ids"] = database.fetch_all(
            """
            SELECT dal.*, st.student_name, st.pid, st.middle, st.last, st.roll_no
            FROM daily_attendance_line dal
            JOIN student_student st ON st.id = dal.stud_id
            WHERE dal.standard_id = ?
            ORDER BY dal.roll_no ASC, dal.id ASC
            """,
            (att["id"],),
        )
        return jsonify({"ok": True, "attendance": att})

    @app.post("/api/attendance/daily/<int:att_id>/bulk-mark")
    def bulk_mark_attendance(att_id: int) -> Response:
        """
        G1 FIX: Bulk mark absent/present in a single SQLite transaction.
        Body: { "lines": [{"line_id": 5, "is_absent": true}, ...] }
        """
        t0 = time.perf_counter()
        data: dict[str, Any] = request.get_json(force=True)
        lines: list[dict[str, Any]] = data.get("lines", [])
        if not lines:
            raise SchoolERPError("'lines' list required")

        att = att_svc.get_daily_attendance(att_id)
        if att["state"] == "validate":
            raise SchoolERPError(
                "Yeh haziri already validate ho chuki hai. "
                "Draft mein wapis laane ke liye 'Reset to Draft' use karein."
            )

        with database.connection() as conn:
            for line_item in lines:
                line_id = int(line_item["line_id"])
                is_abs = bool(line_item.get("is_absent", False))
                conn.execute(
                    """
                    UPDATE daily_attendance_line
                    SET is_present = ?, is_absent = ?, present_absentcheck = 1
                    WHERE id = ? AND standard_id = ?
                    """,
                    (0 if is_abs else 1, 1 if is_abs else 0, line_id, att_id),
                )
            AttendanceService._recompute_daily_counts_conn(conn, att_id)

        updated = att_svc.get_daily_attendance(att_id)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            "bulk_mark att_id=%d lines=%d absent=%d elapsed_ms=%.2f",
            att_id, len(lines), updated["total_absent"], elapsed_ms,
        )

        return jsonify({
            "ok": True,
            "total_student": updated["total_student"],
            "total_presence": updated["total_presence"],
            "total_absent": updated["total_absent"],
            "elapsed_ms": elapsed_ms,
        })

    @app.get("/api/search")
    def global_search() -> Response:
        """Global search across students, teachers, and fee vouchers (min 2 chars)."""
        q = request.args.get("q", "").strip()
        if len(q) < 2:
            return jsonify({"ok": True, "results": [], "query": q})

        like = f"%{q}%"
        results: list[dict[str, Any]] = []
        with database.connection() as conn:
            students = conn.execute(
                """
                SELECT 'student' AS type, s.id,
                       TRIM(s.student_name || ' ' || COALESCE(s.last, '')) AS label,
                       COALESCE(ss.name, 'Unassigned') AS sub,
                       s.pid AS meta, s.state
                FROM student_student s
                LEFT JOIN school_standard ss ON ss.id = s.standard_id
                WHERE s.student_name LIKE ? OR s.last LIKE ?
                   OR s.pid LIKE ? OR s.contact_mobile LIKE ?
                LIMIT 10
                """,
                (like, like, like, like),
            ).fetchall()
            results.extend(dict(r) for r in students)

            teachers = conn.execute(
                """
                SELECT 'teacher' AS type, id,
                       name AS label, COALESCE(department, 'Faculty') AS sub,
                       work_email AS meta, 'active' AS state
                FROM school_teacher
                WHERE name LIKE ? OR work_email LIKE ? OR phone_numbers LIKE ?
                LIMIT 5
                """,
                (like, like, like),
            ).fetchall()
            results.extend(dict(r) for r in teachers)

            vouchers = conn.execute(
                """
                SELECT 'voucher' AS type, p.id,
                       p.number || ' — ' || s.student_name AS label,
                       p.name AS sub,
                       'Rs. ' || CAST(ROUND(p.total, 0) AS INTEGER) AS meta,
                       p.state
                FROM student_payslip p
                JOIN student_student s ON s.id = p.student_id
                WHERE p.number LIKE ? OR p.name LIKE ? OR s.student_name LIKE ?
                LIMIT 5
                """,
                (like, like, like),
            ).fetchall()
            results.extend(dict(r) for r in vouchers)

        return jsonify({"ok": True, "results": results, "query": q})

