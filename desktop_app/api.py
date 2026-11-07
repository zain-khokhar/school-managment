"""Local Flask API & static UI host for the 10-module School Management Desktop ERP."""

from __future__ import annotations

import io
from pathlib import Path
import sys
from typing import Any

from flask import Flask, Response, jsonify, request, send_file, send_from_directory
from werkzeug.exceptions import HTTPException

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, SchoolERPError
from desktop_app.services.assignment_service import AssignmentService
from desktop_app.services.attendance_service import AttendanceService
from desktop_app.services.event_hostel_transport_service import (
    EventService,
    HostelService,
    TransportService,
)
from desktop_app.services.exam_service import ExamService
from desktop_app.services.fees_service import FeesService
from desktop_app.services.library_service import LibraryService
from desktop_app.services.school_service import SchoolService
from desktop_app.services.seed_service import ensure_seed_data
import logging
from desktop_app.routes.auth_routes import register_auth_routes
from desktop_app.routes.dashboard_routes import register_dashboard_routes
from desktop_app.routes.phase1_routes import register_phase1_routes
from desktop_app.routes.rbac import register_rbac_and_audit
from desktop_app.routes.settings_routes import register_settings_routes
from desktop_app.services.audit_service import AuditService
from desktop_app.services.auth_service import AuthService
from desktop_app.services.backup_service import BackupService
from desktop_app.services.dashboard_service import DashboardService
from desktop_app.services.settings_service import SettingsService
from desktop_app.services.timetable_service import TimetableService


def get_ui_dir() -> Path:
    """Resolve `desktop_app/ui` folder in both normal Python and PyInstaller frozen `.exe`."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")) / "desktop_app" / "ui"
    return Path(__file__).resolve().parent / "ui"


def create_app(
    db: Database | None = None,
    seed: bool = True,
    enforce_auth: bool | None = None,
) -> Flask:
    """Create and configure the local Flask application for the School Management Desktop App."""
    database = db or Database()
    if seed:
        ensure_seed_data(database)

    ui_dir = get_ui_dir()
    app = Flask(__name__, static_folder=str(ui_dir), static_url_path="/static")
    app.config["DATABASE"] = database

    school_svc = SchoolService(database)
    fees_svc = FeesService(database)
    att_svc = AttendanceService(database)
    assign_svc = AssignmentService(database)
    tt_svc = TimetableService(database)
    exam_svc = ExamService(database)
    lib_svc = LibraryService(database)
    event_svc = EventService(database)
    hostel_svc = HostelService(database)
    trans_svc = TransportService(database)

    audit_svc = AuditService(database)
    auth_svc = AuthService(database, audit_svc)
    settings_svc = SettingsService(database, audit_svc)
    backup_svc = BackupService(database, settings_svc, audit_svc)
    dashboard_svc = DashboardService(database, settings_svc, backup_svc, audit_svc)

    @app.before_request
    def check_local_host() -> tuple[Response, int] | None:
        host = (request.host or "").split(":")[0].lower()
        if host not in ("127.0.0.1", "localhost", ""):
            return jsonify({"ok": False, "error": "Localhost access only"}), 403
        return None

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:;",
        )
        return response

    @app.errorhandler(NotFoundError)
    def handle_not_found(exc: NotFoundError) -> tuple[Response, int]:
        return jsonify({"ok": False, "error": str(exc)}), 404

    @app.errorhandler(SchoolERPError)
    def handle_erp_error(exc: SchoolERPError) -> tuple[Response, int]:
        return jsonify({"ok": False, "error": str(exc)}), 400

    @app.get("/favicon.ico")
    def favicon() -> tuple[str, int]:
        return "", 204

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception) -> Any:
        if isinstance(exc, HTTPException):
            return exc
        logging.getLogger("school_erp.api").exception("Unhandled API error: %s", exc)
        return jsonify({"ok": False, "error": "Internal server error occurred."}), 500

    # -------------------------------------------------------------------------
    # UI Entrypoint & Bootstrap Snapshot
    # -------------------------------------------------------------------------
    @app.get("/")
    def serve_index() -> Response:
        return send_from_directory(str(ui_dir), "index.html")

    @app.get("/api/health")
    def health() -> Response:
        return jsonify({"ok": True, "status": "healthy", "db_name": Path(database.db_path).name})

    @app.get("/api/bootstrap")
    def bootstrap() -> Response:
        """Return full ERP state across all 10 modules in one fast SQLite WAL read."""
        return jsonify(
            {
                "ok": True,
                "kpis": school_svc.get_dashboard_kpis(),
                "preferences": settings_svc.get_preferences(),
                "backup_health": backup_svc.check_health(),
                "school": {
                    "schools": school_svc.list_schools(),
                    "years": school_svc.list_academic_years(),
                    "months": school_svc.list_academic_months(),
                    "standards": school_svc.list_school_standards(),
                    "base_standards": database.fetch_all("SELECT * FROM standard_standard ORDER BY sequence"),
                    "divisions": database.fetch_all("SELECT * FROM standard_division ORDER BY sequence"),
                    "mediums": database.fetch_all("SELECT * FROM standard_medium ORDER BY sequence"),
                    "classrooms": database.fetch_all("SELECT * FROM class_room ORDER BY number"),
                    "subjects": school_svc.list_subjects(),
                    "teachers": school_svc.list_teachers(),
                    "students": school_svc.list_students(include_inactive=True),
                    "grades": database.fetch_all("SELECT * FROM grade_master ORDER BY id"),
                },
                "fees": {
                    "structures": fees_svc.list_fee_structures(),
                    "registers": fees_svc.list_fees_registers(),
                    "payslips": fees_svc.list_payslips(),
                },
                "attendance": {
                    "daily": att_svc.list_daily_attendance(),
                    "sheets": att_svc.list_attendance_sheets(),
                    "leaves": att_svc.list_leave_requests(),
                },
                "assignment": {
                    "formats": assign_svc.list_file_formats(),
                    "teacher_assignments": assign_svc.list_teacher_assignments(),
                    "student_assignments": assign_svc.list_student_assignments(),
                },
                "timetable": {
                    "timetables": tt_svc.list_timetables(),
                },
                "exam": {
                    "exams": exam_svc.list_exams(),
                    "results": exam_svc.list_exam_results(),
                },
                "library": {
                    "books": lib_svc.list_books(),
                    "cards": lib_svc.list_cards(),
                    "issues": lib_svc.list_book_issues(),
                    "authors": database.fetch_all("SELECT * FROM library_author ORDER BY name"),
                    "racks": database.fetch_all("SELECT * FROM library_rack ORDER BY name"),
                },
                "event": {
                    "events": event_svc.list_events(),
                    "registrations": event_svc.list_registrations(),
                },
                "hostel": {
                    "hostels": hostel_svc.list_hostels(),
                    "rooms": hostel_svc.list_rooms(),
                    "residents": hostel_svc.list_hostel_students(),
                },
                "transport": {
                    "vehicles": trans_svc.list_vehicles(),
                    "routes": trans_svc.list_routes(),
                    "registrations": trans_svc.list_registrations(),
                    "participants": trans_svc.list_participants(),
                },
            }
        )

    # -------------------------------------------------------------------------
    # Module 1: School, Academic, Teachers, Students
    # -------------------------------------------------------------------------
    @app.post("/api/students")
    def create_student() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        stu = school_svc.create_student(
            student_name=data["student_name"],
            middle=data.get("middle", ""),
            last=data.get("last", ""),
            year_id=int(data["year_id"]),
            school_id=int(data["school_id"]),
            standard_id=int(data["standard_id"]),
            date_of_birth=data["date_of_birth"],
            admission_date=data.get("admission_date"),
            gender=data.get("gender", "male"),
            email=data.get("email", ""),
            contact_mobile=data.get("contact_mobile", ""),
        )
        stu_id = stu["id"]
        if data.get("auto_admit", True):
            school_svc.admission_done(stu_id)
        return jsonify({"ok": True, "id": stu_id})

    @app.post("/api/students/<int:student_id>/action")
    def student_action(student_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        action = data.get("action")
        if action == "admission_done":
            school_svc.admission_done(student_id)
        elif action == "set_alumni":
            school_svc.set_alumni(student_id)
        elif action == "terminate":
            school_svc.terminate_student(
                student_id,
                reason=data.get("reason", "Administrative Termination"),
            )
        elif action == "cancel":
            school_svc.cancel_admission(student_id)
        else:
            raise SchoolERPError(f"Unknown student action: {action}")
        return jsonify({"ok": True})

    @app.post("/api/school/assign-roll-no")
    def assign_roll_no() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        updated = school_svc.assign_roll_no(
            standard_id=int(data["standard_id"]),
            medium_id=int(data["medium_id"]),
        )
        return jsonify({"ok": True, "updated": len(updated)})

    @app.post("/api/school/move-standards")
    def move_standards() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        moved = school_svc.move_standards(academic_year_id=int(data["academic_year_id"]))
        return jsonify({"ok": True, "moved": len(moved)})

    @app.post("/api/teachers")
    def create_teacher() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        tch = school_svc.create_teacher(
            name=data["name"],
            work_email=data.get("work_email", ""),
            phone_numbers=data.get("phone_numbers", ""),
            department=data.get("department", ""),
            school_id=int(data["school_id"]) if data.get("school_id") else None,
        )
        return jsonify({"ok": True, "id": tch["id"]})

    # -------------------------------------------------------------------------
    # Module 2: School Fees
    # -------------------------------------------------------------------------
    @app.post("/api/fees/payslips")
    def create_payslip() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        slip = fees_svc.create_payslip(
            student_id=int(data["student_id"]),
            name=data.get("name", "Tuition Fee Slip"),
            slip_date=data.get("date"),
            fees_structure_id=int(data["fees_structure_id"]) if data.get("fees_structure_id") else None,
        )
        if data.get("auto_confirm", True) and data.get("fees_structure_id"):
            fees_svc.payslip_confirm(slip["id"])
        return jsonify({"ok": True, "id": slip["id"]})

    @app.post("/api/fees/payslips/<int:slip_id>/action")
    def payslip_action(slip_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        action = data.get("action")
        if action == "confirm":
            fees_svc.payslip_confirm(slip_id)
        elif action == "pay":
            slip = fees_svc.get_payslip(slip_id)
            amt = (
                float(data["amount"])
                if data.get("amount") is not None
                else max(1.0, float(slip["due_amount"]) or float(slip["total"]))
            )
            fees_svc.student_pay_fees(slip_id, payment_amount=amt)
        else:
            raise SchoolERPError(f"Unknown payslip action: {action}")
        return jsonify({"ok": True})

    # -------------------------------------------------------------------------
    # Module 3: School Attendance
    # -------------------------------------------------------------------------
    @app.post("/api/attendance/daily")
    def create_daily_attendance() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        att = att_svc.create_daily_attendance(
            standard_id=int(data["standard_id"]),
            user_id=int(data["user_id"]) if data.get("user_id") else None,
            att_date=data.get("date"),
        )
        return jsonify({"ok": True, "id": att["id"]})

    @app.post("/api/attendance/daily/<int:att_id>/action")
    def daily_attendance_action(att_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        action = data.get("action")
        if action == "validate":
            att_svc.attendance_validate(att_id)
        elif action == "draft":
            att_svc.attendance_draft(att_id)
        else:
            raise SchoolERPError(f"Unknown attendance action: {action}")
        return jsonify({"ok": True})

    @app.post("/api/attendance/leaves")
    def create_leave() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        lv = att_svc.create_leave_request(
            name=data["name"],
            student_id=int(data["student_id"]),
            start_date=data["start_date"],
            end_date=data["end_date"],
            reason=data.get("reason", ""),
        )
        return jsonify({"ok": True, "id": lv["id"]})

    @app.post("/api/attendance/leaves/<int:leave_id>/action")
    def leave_action(leave_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        action = data.get("action")
        if action == "toapprove":
            att_svc.leave_toapprove(leave_id)
        elif action == "approve":
            att_svc.leave_approve(leave_id)
        elif action == "reject":
            att_svc.leave_reject(leave_id)
        else:
            raise SchoolERPError(f"Unknown leave action: {action}")
        return jsonify({"ok": True})

    @app.get("/api/attendance/export-xlsx")
    def export_attendance_xlsx() -> Response:
        sheet_id = int(request.args["sheet_id"]) if request.args.get("sheet_id") else None
        xlsx_bytes = att_svc.export_attendance_xlsx(sheet_id=sheet_id)
        return send_file(
            io.BytesIO(xlsx_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="school_attendance_sheets.xlsx",
        )

    # -------------------------------------------------------------------------
    # Module 4: Assignment
    # -------------------------------------------------------------------------
    @app.post("/api/assignments/teacher")
    def create_teacher_assignment() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        ta = assign_svc.create_teacher_assignment(
            name=data["name"],
            subject_id=int(data["subject_id"]),
            standard_id=int(data["standard_id"]),
            teacher_id=int(data["teacher_id"]),
            assign_date=data["assign_date"],
            due_date=data["due_date"],
            type_submission=data.get("type_submission", "hardcopy"),
            file_format_id=int(data["file_format_id"]) if data.get("file_format_id") else None,
            attached_homework=data.get("attached_homework", "Homework Assignment Instructions"),
        )
        if data.get("auto_activate", True):
            assign_svc.active_teacher_assignment(ta["id"])
        return jsonify({"ok": True, "id": ta["id"]})

    @app.post("/api/assignments/student/<int:assign_id>/action")
    def student_assignment_action(assign_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        action = data.get("action")
        if action == "active":
            assign_svc.reassign_student_assignment(assign_id)
        elif action == "done":
            assign_svc.submit_and_done_student_assignment(
                assign_id,
                submit_assign=data.get("submit_assign", "homework.pdf"),
                file_name=data.get("file_name", "homework.pdf"),
            )
        elif action == "reject":
            assign_svc.reject_student_assignment(
                assign_id,
                reason=data.get("reason", "Incomplete work"),
            )
        else:
            raise SchoolERPError(f"Unknown assignment action: {action}")
        return jsonify({"ok": True})

    # -------------------------------------------------------------------------
    # Module 5: Timetable
    # -------------------------------------------------------------------------
    @app.post("/api/timetables")
    def create_timetable() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        tt = tt_svc.create_timetable(
            name=data["name"],
            standard_id=int(data["standard_id"]),
            year_id=int(data["year_id"]),
            timetable_type=data.get("timetable_type", "regular"),
            class_room_id=int(data["class_room_id"]) if data.get("class_room_id") else None,
            lines=data.get("lines", []),
        )
        return jsonify({"ok": True, "id": tt["id"]})

    # -------------------------------------------------------------------------
    # Module 6: Exam
    # -------------------------------------------------------------------------
    @app.post("/api/exams")
    def create_exam() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        eid = exam_svc.create_exam(
            name=data["name"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            grade_system_id=int(data["grade_system_id"]) if data.get("grade_system_id") else None,
            academic_year_id=int(data["academic_year_id"]) if data.get("academic_year_id") else None,
            standard_ids=[int(x) for x in data.get("standard_ids", [])],
            schedule_lines=data.get("schedule_lines", []),
            allow_past_dates=bool(data.get("allow_past_dates", False)),
        )
        return jsonify({"ok": True, "id": eid})

    @app.post("/api/exams/<int:exam_id>/action")
    def exam_action(exam_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        action = data.get("action")
        if action == "running":
            exam_svc.set_exam_running(exam_id)
        elif action == "generate_result":
            exam_svc.generate_result(exam_id)
        elif action == "finished":
            exam_svc.set_exam_finished(exam_id)
        elif action == "cancelled":
            exam_svc.set_exam_cancelled(exam_id)
        else:
            raise SchoolERPError(f"Unknown exam action: {action}")
        return jsonify({"ok": True})

    @app.post("/api/exam-results/<int:result_id>/action")
    def exam_result_action(result_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        action = data.get("action")
        if action == "confirm":
            exam_svc.confirm_exam_result(result_id)
        elif action == "re_evaluate":
            exam_svc.result_re_evaluation(result_id)
        elif action == "re_eval_confirm":
            exam_svc.re_evaluation_confirm(result_id)
        elif action == "done":
            exam_svc.set_result_done(result_id)
        else:
            raise SchoolERPError(f"Unknown exam result action: {action}")
        return jsonify({"ok": True})

    @app.post("/api/exam-subjects/<int:subject_line_id>")
    def update_exam_subject(subject_line_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        updated = exam_svc.update_exam_subject_marks(
            subject_line_id,
            obtain_marks=float(data["obtain_marks"]) if "obtain_marks" in data else None,
            marks_reeval=float(data["marks_reeval"]) if "marks_reeval" in data else None,
        )
        return jsonify({"ok": True, "result": updated})

    # -------------------------------------------------------------------------
    # Module 7: Library
    # -------------------------------------------------------------------------
    @app.post("/api/library/books")
    def create_book() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        bid = lib_svc.create_book(
            name=data["name"],
            isbn=data.get("isbn"),
            code=data.get("code"),
            barcode=data.get("barcode"),
            author_id=int(data["author_id"]) if data.get("author_id") else None,
            rack_id=int(data["rack_id"]) if data.get("rack_id") else None,
            qty_available=int(data.get("qty_available", 1)),
            day_to_return_book=int(data.get("day_to_return_book", 14)),
            fine_late_return=float(data.get("fine_late_return", 10.0)),
            fine_lost=float(data.get("fine_lost", 500.0)),
        )
        return jsonify({"ok": True, "id": bid})

    @app.post("/api/library/cards")
    def create_card() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        cid = lib_svc.create_library_card(
            user=data.get("user", "student"),
            student_id=int(data["student_id"]) if data.get("student_id") else None,
            teacher_id=int(data["teacher_id"]) if data.get("teacher_id") else None,
            book_limit=int(data.get("book_limit", 3)),
            start_date=data.get("start_date"),
            duration=int(data.get("duration", 12)),
        )
        if data.get("auto_run", True):
            lib_svc.running_state_card(cid)
        return jsonify({"ok": True, "id": cid})

    @app.post("/api/library/issues")
    def create_book_issue() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        iid = lib_svc.create_book_issue(
            book_id=int(data["book_id"]),
            card_id=int(data["card_id"]),
            date_issue=data.get("date_issue"),
        )
        if data.get("auto_issue", True):
            lib_svc.issue_book(iid)
        return jsonify({"ok": True, "id": iid})

    @app.post("/api/library/issues/<int:issue_id>/action")
    def book_issue_action(issue_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        action = data.get("action")
        if action == "issue":
            lib_svc.issue_book(issue_id)
        elif action == "reissue":
            lib_svc.reissue_book(issue_id)
        elif action == "return":
            lib_svc.return_book(issue_id, actual_return_date=data.get("actual_return_date"))
        elif action == "lost":
            lib_svc.lost_book(issue_id)
        elif action == "pay_fine":
            lib_svc.pay_fine(issue_id)
        else:
            raise SchoolERPError(f"Unknown library issue action: {action}")
        return jsonify({"ok": True})

    # -------------------------------------------------------------------------
    # Module 8: School Event
    # -------------------------------------------------------------------------
    @app.post("/api/events")
    def create_event() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        eid = event_svc.create_event(
            name=data["name"],
            start_date=data["start_date"],
            end_date=data["end_date"],
            event_type=data.get("event_type", "intra"),
            contact_teacher_id=int(data["contact_teacher_id"]) if data.get("contact_teacher_id") else None,
        )
        return jsonify({"ok": True, "id": eid})

    @app.post("/api/events/registrations")
    def create_event_registration() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        rid = event_svc.create_registration(int(data["event_id"]), int(data["part_name_id"]))
        if data.get("auto_confirm", True):
            event_svc.confirm_registration(rid)
        return jsonify({"ok": True, "id": rid})

    @app.post("/api/events/registrations/<int:reg_id>/action")
    def event_reg_action(reg_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        action = data.get("action")
        if action == "confirm":
            event_svc.confirm_registration(reg_id)
        elif action == "cancel":
            event_svc.cancel_registration(reg_id)
        elif action == "draft":
            event_svc.set_registration_draft(reg_id)
        else:
            raise SchoolERPError(f"Unknown event registration action: {action}")
        return jsonify({"ok": True})

    # -------------------------------------------------------------------------
    # Module 9: School Hostel
    # -------------------------------------------------------------------------
    @app.post("/api/hostel/residents")
    def create_hostel_resident() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        hsid = hostel_svc.create_hostel_student(
            student_id=int(data["student_id"]),
            hostel_info_id=int(data["hostel_info_id"]),
            room_id=int(data["room_id"]),
            duration=int(data["duration"]),
            admission_date=data.get("admission_date"),
        )
        if data.get("auto_reserve", True):
            hostel_svc.reservation_state(hsid)
        return jsonify({"ok": True, "id": hsid})

    @app.post("/api/hostel/residents/<int:hs_id>/action")
    def hostel_resident_action(hs_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        action = data.get("action")
        if action == "reserve":
            hostel_svc.reservation_state(hs_id)
        elif action == "pay":
            amt = float(data["amount"]) if data.get("amount") is not None else None
            hostel_svc.pay_hostel_fees(hs_id, payment_amount=amt)
        elif action == "discharge":
            hostel_svc.discharge_student(hs_id)
        elif action == "cancel":
            hostel_svc.cancel_hostel_student(hs_id)
        else:
            raise SchoolERPError(f"Unknown hostel action: {action}")
        return jsonify({"ok": True})

    # -------------------------------------------------------------------------
    # Module 10: School Transport
    # -------------------------------------------------------------------------
    @app.post("/api/transport/registrations")
    def create_transport_reg() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        tr_id = trans_svc.create_transport_registration(
            route_id=int(data["route_id"]),
            student_id=int(data["student_id"]),
            vehicle_id=int(data["vehicle_id"]),
            registration_month=int(data["registration_month"]),
            reg_date=data.get("reg_date"),
        )
        if data.get("auto_confirm", True):
            trans_svc.trans_regi_confirm(tr_id)
        return jsonify({"ok": True, "id": tr_id})

    @app.post("/api/transport/registrations/<int:reg_id>/action")
    def transport_reg_action(reg_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        action = data.get("action")
        if action == "confirm":
            trans_svc.trans_regi_confirm(reg_id)
        elif action == "pay":
            amt = float(data["amount"]) if data.get("amount") is not None else None
            trans_svc.pay_transport_fees(reg_id, payment_amount=amt)
        else:
            raise SchoolERPError(f"Unknown transport action: {action}")
        return jsonify({"ok": True})

    @app.post("/api/transport/transfer-vehicle")
    def transfer_vehicle() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        updated = trans_svc.transfer_vehicle(
            int(data["participant_id"]),
            int(data["new_vehicle_id"]),
        )
        return jsonify({"ok": True, "participant": updated})


    # -------------------------------------------------------------------------
    # Phase 1 & Phase 2 Modular Routes + Deny-by-Default RBAC & Audit Middleware
    # -------------------------------------------------------------------------
    register_phase1_routes(app, database, att_svc)
    register_auth_routes(app, auth_svc, enforce_auth=enforce_auth)
    register_dashboard_routes(app, dashboard_svc, audit_svc)
    register_settings_routes(app, settings_svc, backup_svc, auth_svc)
    register_rbac_and_audit(app, auth_svc, audit_svc, dashboard_svc, enforce_auth=enforce_auth)

    return app
