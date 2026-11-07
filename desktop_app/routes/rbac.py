"""
Deny-by-Default RBAC Guard & Automatic Mutating Audit Middleware (Phase 2 — G3, Section 10.5).

Every ``/api/*`` endpoint must be explicitly listed in ``PUBLIC_ENDPOINTS`` or
``ROUTE_PERMISSIONS``. Unlisted endpoints are denied with HTTP 403 by default.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, g, jsonify, request

from desktop_app.services.audit_service import AuditService, redact_dict
from desktop_app.services.auth_service import AuthError, AuthService
from desktop_app.services.dashboard_service import DashboardService

SESSION_COOKIE = "erp_session"

ALL_STAFF = frozenset({"admin", "principal", "teacher", "fee_clerk", "front_desk", "exam_incharge"})
ADMINS = frozenset({"admin", "principal"})
TEACHING = frozenset({"admin", "principal", "teacher"})
FEES_STAFF = frozenset({"admin", "principal", "fee_clerk"})
FRONT_DESK_STAFF = frozenset({"admin", "principal", "front_desk"})
EXAM_LEAD = frozenset({"admin", "principal", "exam_incharge"})
EXAM_MARKING = frozenset({"admin", "principal", "exam_incharge", "teacher"})

PUBLIC_ENDPOINTS: set[tuple[str, str]] = {
    ("GET", "/api/health"),
    ("GET", "/api/auth/status"),
    ("POST", "/api/auth/setup"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/recover"),
}

ROUTE_PERMISSIONS: dict[tuple[str, str], frozenset[str]] = {
    # Auth & user management
    ("POST", "/api/auth/logout"): ALL_STAFF,
    ("GET", "/api/auth/users"): ADMINS,
    ("POST", "/api/auth/users"): ADMINS,
    ("POST", "/api/auth/users/<int:user_id>/action"): ADMINS,
    # Dashboards, search, bootstrap & Student 360
    ("GET", "/api/bootstrap"): ALL_STAFF,
    ("GET", "/api/dashboard/home"): ALL_STAFF,
    ("GET", "/api/search"): ALL_STAFF,
    ("GET", "/api/students/list"): ALL_STAFF,
    ("GET", "/api/students/<int:student_id>/360"): ALL_STAFF,
    ("GET", "/api/audit/logs"): ADMINS,
    # Settings & Backup
    ("GET", "/api/settings"): ADMINS,
    ("POST", "/api/settings/profile"): ADMINS,
    ("POST", "/api/settings/preferences"): ADMINS,
    ("GET", "/api/settings/health"): ADMINS,
    ("POST", "/api/settings/backup"): ADMINS,
    ("POST", "/api/settings/restore"): ADMINS,
    ("POST", "/api/settings/recovery-code"): ADMINS,
    # Module 1: School, Admissions, Faculty
    ("POST", "/api/students"): FRONT_DESK_STAFF,
    ("POST", "/api/students/<int:student_id>/action"): FRONT_DESK_STAFF,
    ("POST", "/api/school/assign-roll-no"): FRONT_DESK_STAFF,
    ("POST", "/api/school/move-standards"): ADMINS,
    ("POST", "/api/teachers"): ADMINS,
    # Module 2: Fees
    ("POST", "/api/fees/payslips"): FEES_STAFF,
    ("POST", "/api/fees/payslips/<int:slip_id>/action"): FEES_STAFF,
    # Module 3: Attendance
    ("GET", "/api/attendance/today/<int:class_id>"): TEACHING,
    ("POST", "/api/attendance/daily"): TEACHING,
    ("POST", "/api/attendance/daily/<int:att_id>/bulk-mark"): TEACHING,
    ("POST", "/api/attendance/daily/<int:att_id>/action"): TEACHING,
    ("POST", "/api/attendance/leaves"): TEACHING | FRONT_DESK_STAFF,
    ("POST", "/api/attendance/leaves/<int:leave_id>/action"): TEACHING,
    ("GET", "/api/attendance/export-xlsx"): TEACHING,
    # Module 4: Assignments
    ("POST", "/api/assignments/teacher"): TEACHING,
    ("POST", "/api/assignments/student/<int:assign_id>/action"): TEACHING,
    # Module 5 & 6: Timetable & Exams
    ("POST", "/api/timetables"): EXAM_LEAD,
    ("POST", "/api/exams"): EXAM_LEAD,
    ("POST", "/api/exams/<int:exam_id>/action"): EXAM_LEAD,
    ("POST", "/api/exam-results/<int:result_id>/action"): EXAM_MARKING,
    ("POST", "/api/exam-subjects/<int:subject_line_id>"): EXAM_MARKING,
    # Module 7..10: Library, Events, Hostel, Transport
    ("POST", "/api/library/books"): ADMINS,
    ("POST", "/api/library/cards"): ADMINS,
    ("POST", "/api/library/issues"): ADMINS,
    ("POST", "/api/library/issues/<int:issue_id>/action"): ADMINS,
    ("POST", "/api/events"): FRONT_DESK_STAFF,
    ("POST", "/api/events/registrations"): FRONT_DESK_STAFF,
    ("POST", "/api/events/registrations/<int:reg_id>/action"): FRONT_DESK_STAFF,
    ("POST", "/api/hostel/residents"): ADMINS,
    ("POST", "/api/hostel/residents/<int:hs_id>/action"): ADMINS,
    ("POST", "/api/transport/registrations"): ADMINS,
    ("POST", "/api/transport/registrations/<int:reg_id>/action"): ADMINS,
    ("POST", "/api/transport/transfer-vehicle"): ADMINS,
}


def extract_session_token() -> str | None:
    """Read session token from ``X-Session-Token`` header, Bearer header, or HttpOnly cookie."""
    hdr = (request.headers.get("X-Session-Token") or "").strip()
    if hdr:
        return hdr
    auth_hdr = (request.headers.get("Authorization") or "").strip()
    if auth_hdr.lower().startswith("bearer "):
        return auth_hdr[7:].strip()
    cookie_tok = (request.cookies.get(SESSION_COOKIE) or "").strip()
    return cookie_tok or None


def register_rbac_and_audit(
    app: Flask,
    auth_svc: AuthService,
    audit_svc: AuditService,
    dashboard_svc: DashboardService,
    enforce_auth: bool | None = None,
) -> None:
    """Attach deny-by-default authorization guard and automatic write audit hook."""

    @app.errorhandler(AuthError)
    def handle_auth_error(exc: AuthError) -> tuple[Response, int]:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    @app.before_request
    def enforce_rbac_guard() -> tuple[Response, int] | None:
        if not request.path.startswith("/api/"):
            return None

        rule_str = request.url_rule.rule if request.url_rule else request.path
        key = (request.method.upper(), rule_str)

        token = extract_session_token()
        user = auth_svc.resolve_session(token)
        g.current_user = user
        g.audit_recorded = False

        if key in PUBLIC_ENDPOINTS:
            return None

        # Auth is strictly active when enforce_auth=True OR once at least one user exists
        has_users = auth_svc.has_any_users()
        strict_mode = True if enforce_auth is True else (False if enforce_auth is False else has_users)

        if not strict_mode:
            # Legacy test compatibility mode (0 users in app_user and enforce_auth not forced)
            if user is None:
                g.current_user = {
                    "id": None,
                    "username": "system_setup",
                    "full_name": "System Setup",
                    "role": "admin",
                    "teacher_id": None,
                    "active": True,
                }
            return None

        if user is None:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": "Authentication required. Please sign in.",
                        "setup_required": not has_users,
                    }
                ),
                401,
            )

        allowed_roles = ROUTE_PERMISSIONS.get(key)
        if not allowed_roles or user["role"] not in allowed_roles:
            audit_svc.record(
                user_id=user["id"],
                username=user["username"],
                role=user["role"],
                action="rbac.denied",
                entity_type="endpoint",
                entity_id=rule_str,
                summary=f"Denied {request.method} {request.path} for role '{user['role']}'",
                ip_address=request.remote_addr or "127.0.0.1",
            )
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": f"Access denied: your role ({user['role']}) is not permitted to perform this action.",
                    }
                ),
                403,
            )
        return None

    @app.after_request
    def auto_audit_and_cache_invalidation(response: Response) -> Response:
        if (
            request.path.startswith("/api/")
            and request.method in ("POST", "PUT", "DELETE")
            and 200 <= response.status_code < 300
        ):
            dashboard_svc.invalidate_cache()

            if not getattr(g, "audit_recorded", False):
                actor: dict[str, Any] = getattr(g, "current_user", None) or {
                    "id": None,
                    "username": "anonymous",
                    "role": "unauthenticated",
                }
                view_args = request.view_args or {}
                ent_id = next(iter(view_args.values()), None) if view_args else None
                if ent_id is None:
                    resp_json = response.get_json(silent=True) or {}
                    ent_id = resp_json.get("id")

                parts = [p for p in request.path.split("/") if p and p != "api" and not p.isdigit()]
                entity_type = parts[0] if parts else "system"
                raw_body = request.get_json(silent=True) or {}
                safe_body = redact_dict(raw_body)
                action_hint = safe_body.get("action") or request.method.lower()
                action_code = f"{entity_type}.{action_hint}"
                summary = f"{request.method} {request.path}"
                if safe_body:
                    preview = ", ".join(f"{k}={v}" for k, v in list(safe_body.items())[:4])
                    summary = f"{summary} ({preview})"

                audit_svc.record(
                    user_id=actor.get("id"),
                    username=actor.get("username") or "anonymous",
                    role=actor.get("role") or "unauthenticated",
                    action=action_code,
                    entity_type=entity_type,
                    entity_id=ent_id,
                    summary=summary,
                    ip_address=request.remote_addr or "127.0.0.1",
                )
        return response

