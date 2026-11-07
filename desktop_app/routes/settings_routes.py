"""
Settings, First-Run Checklist, Database Health, Backup & Restore Routes (Phase 2 — G13, G22).
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, g, jsonify, request

from desktop_app.services.auth_service import AuthService
from desktop_app.services.backup_service import BackupService
from desktop_app.services.settings_service import SettingsService


def register_settings_routes(
    app: Flask,
    settings_svc: SettingsService,
    backup_svc: BackupService,
    auth_svc: AuthService,
) -> None:
    """Register school settings, database health, backup, and restore routes."""

    @app.get("/api/settings")
    def get_settings_bundle() -> Response:
        years = settings_svc.db.fetch_all("SELECT id, name, current FROM academic_year ORDER BY id ASC")
        return jsonify(
            {
                "ok": True,
                "school": settings_svc.get_school_profile(),
                "years": years,
                "preferences": settings_svc.get_preferences(),
                "checklist": settings_svc.get_onboarding_checklist(),
                "health": backup_svc.check_health(),
                "backups": backup_svc.list_backups(),
            }
        )

    @app.get("/api/settings/health")
    def get_database_health() -> Response:
        return jsonify({"ok": True, "health": backup_svc.check_health()})

    @app.post("/api/settings/profile")
    def update_school_profile() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        actor = getattr(g, "current_user", None)
        profile = settings_svc.update_school_profile(
            data,
            actor=actor,
            ip_address=request.remote_addr or "127.0.0.1",
        )
        g.audit_recorded = True
        return jsonify(
            {
                "ok": True,
                "school": profile,
                "checklist": settings_svc.get_onboarding_checklist(),
            }
        )

    @app.post("/api/settings/preferences")
    def update_preferences() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        actor = getattr(g, "current_user", None)
        prefs = settings_svc.update_preferences(
            data,
            actor=actor,
            ip_address=request.remote_addr or "127.0.0.1",
        )
        g.audit_recorded = True
        return jsonify(
            {
                "ok": True,
                "preferences": prefs,
                "checklist": settings_svc.get_onboarding_checklist(),
            }
        )

    @app.post("/api/settings/backup")
    def trigger_backup() -> Response:
        data: dict[str, Any] = request.get_json(silent=True) or {}
        actor = getattr(g, "current_user", None)
        bk = backup_svc.create_backup(
            suffix=data.get("note", "manual"),
            actor=actor,
            ip_address=request.remote_addr or "127.0.0.1",
        )
        g.audit_recorded = True
        return jsonify(
            {
                "ok": True,
                "backup": bk,
                "health": backup_svc.check_health(),
                "backups": backup_svc.list_backups(),
                "checklist": settings_svc.get_onboarding_checklist(),
            }
        )

    @app.post("/api/settings/restore")
    def trigger_restore() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        actor = getattr(g, "current_user", None)
        res = backup_svc.restore_backup(
            filename=data.get("filename", ""),
            actor=actor,
            ip_address=request.remote_addr or "127.0.0.1",
        )
        g.audit_recorded = True
        return jsonify(
            {
                "ok": True,
                **res,
                "health": backup_svc.check_health(),
            }
        )

    @app.post("/api/settings/recovery-code")
    def rotate_recovery_code() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        actor = getattr(g, "current_user", None)
        code = auth_svc.regenerate_recovery_code(
            user_id=int(actor["id"]),
            current_secret=data.get("current_secret", ""),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        g.audit_recorded = True
        return jsonify({"ok": True, "recovery_code": code})

