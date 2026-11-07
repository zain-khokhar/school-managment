"""
Role-Aware Dashboard, Student 360° & Audit Log Routes (Phase 2 — G9, S360).
"""

from __future__ import annotations

from flask import Flask, Response, g, jsonify, request

from desktop_app.services.audit_service import AuditService
from desktop_app.services.dashboard_service import DashboardService


def register_dashboard_routes(
    app: Flask,
    dashboard_svc: DashboardService,
    audit_svc: AuditService,
) -> None:
    """Register Phase 2 role dashboards, Student 360°, and audit trail routes."""

    @app.get("/api/dashboard/home")
    def role_dashboard_home() -> Response:
        user = getattr(g, "current_user", None) or {
            "id": 0,
            "username": "principal",
            "role": "principal",
            "teacher_id": None,
        }
        payload = dashboard_svc.get_role_home(user)
        return jsonify(payload)

    @app.get("/api/students/<int:student_id>/360")
    def student_360_profile(student_id: int) -> Response:
        payload = dashboard_svc.get_student_360(student_id)
        return jsonify(payload)

    @app.get("/api/audit/logs")
    def get_audit_logs() -> Response:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 40))))
        entity_type = request.args.get("entity_type", "").strip() or None
        entity_id = request.args.get("entity_id", "").strip() or None
        username = request.args.get("username", "").strip() or None
        res = audit_svc.list_logs(
            entity_type=entity_type,
            entity_id=entity_id,
            username=username,
            page=page,
            per_page=per_page,
        )
        return jsonify({"ok": True, **res})

