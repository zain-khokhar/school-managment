"""
Phase 4 Admissions, Import/Export, ID Card & PTM Print, and Library Quick Issue Routes.

Strictly under 400 lines per anti-monolith budget (ADVANCEMENT_PLAN.md Section 10.1).
"""

from __future__ import annotations

import io
from typing import Any

from flask import Flask, Response, g, jsonify, request, send_file

from desktop_app.exceptions import ValidationError
from desktop_app.services.admission_import_service import AdmissionImportService


def _actor() -> dict[str, Any]:
    return getattr(g, "current_user", None) or {
        "id": None,
        "username": "local",
        "role": "front_desk",
    }


def register_admissions_import_routes(
    app: Flask,
    adm_import_svc: AdmissionImportService,
) -> None:
    """Register Phase 4 `/api/admissions/*`, `/api/import/*`, `/api/export/*`, and print routes."""

    @app.get("/api/admissions/check-duplicate")
    def check_admission_duplicate() -> Response:
        res = adm_import_svc.check_duplicate_and_family(
            b_form_no=request.args.get("b_form_no", "").strip(),
            student_name=request.args.get("student_name", "").strip(),
            date_of_birth=request.args.get("date_of_birth", "").strip(),
            guardian_phone=request.args.get("guardian_phone", "").strip(),
            guardian_cnic=request.args.get("guardian_cnic", "").strip(),
        )
        return jsonify({"ok": True, **res})

    @app.post("/api/admissions/enroll")
    def enroll_student_wizard() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        g.audit_recorded = True
        res = adm_import_svc.enroll_wizard(
            data,
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, **res})

    @app.get("/api/students/print/id-cards")
    def print_student_id_cards() -> Response:
        ids_raw = request.args.get("ids", "").strip()
        ids = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()] if ids_raw else None
        class_raw = request.args.get("class_id", "").strip()
        bundle = adm_import_svc.get_id_cards_bundle(
            student_ids=ids,
            class_id=int(class_raw) if class_raw else None,
        )
        return jsonify({"ok": True, **bundle})

    @app.get("/api/students/print/ptm-sheets")
    def print_student_ptm_sheets() -> Response:
        ids_raw = request.args.get("ids", "").strip()
        ids = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()] if ids_raw else None
        class_raw = request.args.get("class_id", "").strip()
        bundle = adm_import_svc.get_ptm_sheets_bundle(
            student_ids=ids,
            class_id=int(class_raw) if class_raw else None,
        )
        return jsonify({"ok": True, **bundle})

    @app.post("/api/import/students/preview")
    def preview_students_csv_import() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        res = adm_import_svc.preview_students_import(str(data.get("csv_text") or ""))
        return jsonify({"ok": True, **res})

    @app.post("/api/import/students/commit")
    def commit_students_csv_import() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        g.audit_recorded = True
        res = adm_import_svc.commit_students_import(
            str(data.get("csv_text") or ""),
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, **res})

    @app.get("/api/export/students.xlsx")
    def export_students_excel() -> Response:
        class_raw = request.args.get("class_id", "").strip()
        xlsx_bytes = adm_import_svc.export_students_xlsx(
            class_id=int(class_raw) if class_raw else None
        )
        return send_file(
            io.BytesIO(xlsx_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="students_directory.xlsx",
        )

    @app.get("/api/export/vouchers.xlsx")
    def export_vouchers_excel() -> Response:
        bmonth = request.args.get("billing_month", "").strip()
        xlsx_bytes = adm_import_svc.export_vouchers_xlsx(billing_month=bmonth)
        return send_file(
            io.BytesIO(xlsx_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="fee_vouchers_register.xlsx",
        )

    @app.post("/api/library/quick-issue")
    def library_quick_issue_by_student() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        if not data.get("student_id") or not data.get("book_id"):
            raise ValidationError("Both student_id and book_id are required.")
        g.audit_recorded = True
        res = adm_import_svc.quick_issue_book_by_student(
            student_id=int(data["student_id"]),
            book_id=int(data["book_id"]),
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, **res})
