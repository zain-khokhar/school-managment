"""
Authentication, Recovery & Staff Role Management Routes (Phase 2 — G3, SET-6).
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, g, jsonify, request

from desktop_app.routes.rbac import SESSION_COOKIE, extract_session_token
from desktop_app.services.auth_service import AuthService


def _attach_session_cookie(resp: Response, token: str) -> Response:
    resp.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="Strict",
        max_age=86400,
        path="/",
    )
    return resp


def register_auth_routes(
    app: Flask,
    auth_svc: AuthService,
    enforce_auth: bool | None = None,
) -> None:
    """Register authentication and user management endpoints."""

    @app.get("/api/auth/status")
    def auth_status() -> Response:
        has_users = auth_svc.has_any_users()
        strict = True if enforce_auth is True else (False if enforce_auth is False else has_users)
        user = getattr(g, "current_user", None) or auth_svc.resolve_session(extract_session_token())
        return jsonify(
            {
                "ok": True,
                "setup_required": not has_users,
                "auth_enforced": strict,
                "authenticated": user is not None,
                "user": user,
            }
        )

    @app.post("/api/auth/setup")
    def auth_setup() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        res = auth_svc.setup_initial_admin(
            full_name=data.get("full_name", ""),
            username=data.get("username", "admin"),
            secret=data.get("secret", ""),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        g.audit_recorded = True
        resp = jsonify(
            {
                "ok": True,
                "user": res["user"],
                "token": res["token"],
                "recovery_code": res["recovery_code"],
            }
        )
        return _attach_session_cookie(resp, res["token"])

    @app.post("/api/auth/login")
    def auth_login() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        res = auth_svc.login(
            username=data.get("username", ""),
            secret=data.get("secret", ""),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        g.audit_recorded = True
        resp = jsonify({"ok": True, "user": res["user"], "token": res["token"]})
        return _attach_session_cookie(resp, res["token"])

    @app.post("/api/auth/logout")
    def auth_logout() -> Response:
        auth_svc.logout(extract_session_token(), ip_address=request.remote_addr or "127.0.0.1")
        g.audit_recorded = True
        resp = jsonify({"ok": True})
        resp.delete_cookie(SESSION_COOKIE, path="/")
        return resp

    @app.post("/api/auth/recover")
    def auth_recover() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        res = auth_svc.recover_account(
            username=data.get("username", ""),
            recovery_code=data.get("recovery_code", ""),
            new_secret=data.get("new_secret", ""),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        g.audit_recorded = True
        return jsonify({"ok": True, "new_recovery_code": res["new_recovery_code"]})

    @app.get("/api/auth/users")
    def list_staff_users() -> Response:
        return jsonify({"ok": True, "users": auth_svc.list_users()})

    @app.post("/api/auth/users")
    def create_staff_user() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        actor = getattr(g, "current_user", None)
        user = auth_svc.create_user(
            full_name=data.get("full_name", ""),
            username=data.get("username", ""),
            role=data.get("role", "teacher"),
            secret=data.get("secret", ""),
            teacher_id=int(data["teacher_id"]) if data.get("teacher_id") else None,
            actor=actor,
            ip_address=request.remote_addr or "127.0.0.1",
        )
        g.audit_recorded = True
        return jsonify({"ok": True, "user": user})

    @app.post("/api/auth/users/<int:user_id>/action")
    def manage_staff_user(user_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        actor = getattr(g, "current_user", None)
        updated = auth_svc.manage_user(
            user_id=user_id,
            action=data.get("action", ""),
            payload=data,
            actor=actor,
            ip_address=request.remote_addr or "127.0.0.1",
        )
        g.audit_recorded = True
        return jsonify({"ok": True, "user": updated})

