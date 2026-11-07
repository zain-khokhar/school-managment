"""
Phase 4 Academic Routes — Quick Exam Setup, Spreadsheet Marks Grid, Rank Computation,
Report Cards, Result Gazette, Weekly Timetable Grid, Today's Substitutions & Academic Calendar.

Strictly under 400 lines per anti-monolith budget (ADVANCEMENT_PLAN.md Section 10.1).
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, g, jsonify, request

from desktop_app.exceptions import ValidationError
from desktop_app.services.academic_engine_service import AcademicEngineService
from desktop_app.services.timetable_service import TimetableService


def _actor() -> dict[str, Any]:
    return getattr(g, "current_user", None) or {
        "id": None,
        "username": "local",
        "role": "admin",
    }


def register_academics_routes(
    app: Flask,
    academic_svc: AcademicEngineService,
    tt_svc: TimetableService,
) -> None:
    """Register Phase 4 `/api/exams/*`, `/api/timetable/*`, and `/api/calendar/*` endpoints."""

    # -------------------------------------------------------------------------
    # Exams, Marks Grid, Ranks, Report Cards & Gazette (G7, S5, R-E1, R-T3)
    # -------------------------------------------------------------------------
    @app.post("/api/exams/quick-create")
    def quick_create_exam() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        g.audit_recorded = True
        res = academic_svc.quick_create_exam(
            data,
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, **res})

    @app.get("/api/exams/<int:exam_id>/marks-grid")
    def get_exam_marks_grid(exam_id: int) -> Response:
        class_raw = request.args.get("class_id", "").strip()
        sub_raw = request.args.get("subject_id", "").strip()
        if not class_raw or not sub_raw:
            raise ValidationError("Both class_id and subject_id query parameters are required.")
        grid = academic_svc.get_marks_grid(exam_id, int(class_raw), int(sub_raw))
        return jsonify({"ok": True, **grid})

    @app.post("/api/exams/<int:exam_id>/marks-grid")
    def save_exam_marks_grid(exam_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        if not data.get("class_id") or not data.get("subject_id"):
            raise ValidationError("Both class_id and subject_id are required.")
        g.audit_recorded = True
        grid = academic_svc.save_marks_grid(
            exam_id=exam_id,
            class_id=int(data["class_id"]),
            subject_id=int(data["subject_id"]),
            entries=list(data.get("entries") or []),
            finalize=bool(data.get("finalize", False)),
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, **grid})

    @app.post("/api/exams/<int:exam_id>/compute-ranks")
    def compute_exam_ranks(exam_id: int) -> Response:
        data: dict[str, Any] = request.get_json(silent=True) or {}
        class_id = int(data["class_id"]) if data.get("class_id") else None
        g.audit_recorded = True
        ranked = academic_svc.compute_ranks(
            exam_id=exam_id,
            class_id=class_id,
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, "results": ranked, "count": len(ranked)})

    @app.get("/api/exams/<int:exam_id>/gazette")
    def get_exam_gazette(exam_id: int) -> Response:
        class_raw = request.args.get("class_id", "").strip()
        class_id = int(class_raw) if class_raw else None
        gazette = academic_svc.get_exam_gazette(exam_id, class_id=class_id)
        return jsonify({"ok": True, **gazette})

    @app.get("/api/exams/print/report-cards")
    def print_exam_report_cards() -> Response:
        exam_raw = request.args.get("exam_id", "").strip()
        if not exam_raw:
            raise ValidationError("exam_id query parameter is required.")
        class_raw = request.args.get("class_id", "").strip()
        stu_raw = request.args.get("student_id", "").strip()
        bundle = academic_svc.get_report_cards_bundle(
            exam_id=int(exam_raw),
            class_id=int(class_raw) if class_raw else None,
            student_id=int(stu_raw) if stu_raw else None,
        )
        return jsonify({"ok": True, **bundle})

    # -------------------------------------------------------------------------
    # Timetable Weekly Grid, Slot Addition & Today's Live Strip (G8, TT-1..4)
    # -------------------------------------------------------------------------
    @app.get("/api/timetable/weekly-grid")
    def get_weekly_timetable_grid() -> Response:
        class_raw = request.args.get("class_id", "").strip()
        tch_raw = request.args.get("teacher_id", "").strip()
        grid = academic_svc.get_weekly_timetable_grid(
            class_id=int(class_raw) if class_raw else None,
            teacher_id=int(tch_raw) if tch_raw else None,
        )
        return jsonify({"ok": True, **grid})

    @app.post("/api/timetable/slot")
    def add_timetable_slot() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        class_id = int(data["standard_id"])
        year_id = int(data.get("year_id") or 1)
        existing = academic_svc.db.fetch_one(
            """
            SELECT id FROM time_table
            WHERE standard_id = ? AND year_id = ? AND timetable_type = 'regular'
            ORDER BY id DESC LIMIT 1
            """,
            (class_id, year_id),
        )
        if existing:
            table_id = int(existing["id"])
        else:
            tt = tt_svc.create_timetable(
                name=data.get("name") or f"Regular Timetable #{class_id}",
                standard_id=class_id,
                year_id=year_id,
                timetable_type="regular",
                class_room_id=int(data["class_room_id"]) if data.get("class_room_id") else None,
            )
            table_id = int(tt["id"])

        line = tt_svc.add_timetable_line(
            table_id=table_id,
            subject_id=int(data["subject_id"]),
            teacher_id=int(data["teacher_id"]),
            start_time=float(data["start_time"]),
            end_time=float(data["end_time"]),
            week_day=str(data.get("week_day") or "monday"),
            class_room_id=int(data["class_room_id"]) if data.get("class_room_id") else None,
        )
        return jsonify({"ok": True, "line": line, "table_id": table_id})

    @app.get("/api/timetable/today")
    def get_today_timetable_strip() -> Response:
        target_date = request.args.get("date", "").strip() or None
        day_override = request.args.get("day", "").strip() or None
        class_raw = request.args.get("class_id", "").strip()
        data = academic_svc.get_today_live_periods(
            target_date=target_date,
            day_override=day_override,
            class_id=int(class_raw) if class_raw else None,
        )
        return jsonify({"ok": True, **data})

    @app.post("/api/timetable/substitutions")
    def assign_timetable_substitution() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        if not data.get("line_id") or not data.get("substitute_teacher_id"):
            raise ValidationError("line_id and substitute_teacher_id are required.")
        g.audit_recorded = True
        sub = academic_svc.assign_substitution(
            target_date=str(data.get("date") or ""),
            line_id=int(data["line_id"]),
            substitute_teacher_id=int(data["substitute_teacher_id"]),
            reason=str(data.get("reason") or ""),
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, "substitution": sub})

    # -------------------------------------------------------------------------
    # Academic Calendar & Holidays (G21, S6)
    # -------------------------------------------------------------------------
    @app.get("/api/calendar/days")
    def list_calendar_days() -> Response:
        year_raw = request.args.get("year", "").strip()
        month_raw = request.args.get("month", "").strip() or None
        items = academic_svc.list_calendar_days(
            year=int(year_raw) if year_raw.isdigit() else None,
            month=month_raw,
        )
        return jsonify({"ok": True, "items": items, "total": len(items)})

    @app.post("/api/calendar/days")
    def save_calendar_day() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        g.audit_recorded = True
        day = academic_svc.upsert_calendar_day(
            data,
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, "day": day})

    @app.post("/api/calendar/days/<int:day_id>/delete")
    def remove_calendar_day(day_id: int) -> Response:
        academic_svc.delete_calendar_day(day_id)
        return jsonify({"ok": True})

    @app.post("/api/calendar/preset-pakistani")
    def load_pakistani_holiday_preset() -> Response:
        data: dict[str, Any] = request.get_json(silent=True) or {}
        yr = int(data["year"]) if data.get("year") else None
        cnt = academic_svc.seed_pakistani_holidays(year=yr)
        return jsonify({"ok": True, "created_count": cnt})
