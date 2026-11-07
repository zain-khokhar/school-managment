"""
desktop_app/routes/outbox_routes.py — Flask REST API endpoints for Outbox & Messaging (Phase 5).

Provides endpoints for message listing, bulk dispatches, WhatsApp links,
auto-triggers (absent alerts, fee reminders, result alerts, circulars),
and message template customizations.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, g, jsonify, request

from desktop_app.exceptions import SchoolERPError
from desktop_app.services.outbox_service import OutboxService


def register_outbox_routes(app: Flask, outbox_svc: OutboxService) -> None:
    """Register all Phase 5 Outbox and Rabta communication routes."""

    def _current_user() -> str:
        user = getattr(g, "current_user", None)
        return str(user.get("username", "system")) if user else "system"

    @app.get("/api/outbox/messages")
    def list_outbox_messages() -> Response:
        status = request.args.get("status")
        category = request.args.get("category")
        class_id = int(request.args["class_id"]) if request.args.get("class_id") else None
        q = request.args.get("q")
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 25))

        res = outbox_svc.list_messages(
            status=status,
            category=category,
            class_id=class_id,
            q=q,
            page=page,
            per_page=per_page,
        )
        return jsonify({"ok": True, **res})

    @app.get("/api/outbox/stats")
    def get_outbox_stats() -> Response:
        stats = outbox_svc.get_stats()
        return jsonify({"ok": True, "stats": stats})

    @app.post("/api/outbox/messages/<int:msg_id>/action")
    def outbox_message_action(msg_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True) or {}
        action = data.get("action")
        user = _current_user()

        if action == "mark_sent":
            outbox_svc.mark_sent(msg_id, user=user)
        elif action == "cancel":
            outbox_svc.cancel_message(msg_id, user=user)
        elif action == "retry":
            outbox_svc.retry_message(msg_id, user=user)
        elif action == "delete":
            outbox_svc.delete_message(msg_id, user=user)
        else:
            raise SchoolERPError(f"Unknown outbox action: {action}")

        return jsonify({"ok": True, "id": msg_id, "action": action})

    @app.post("/api/outbox/bulk-action")
    def outbox_bulk_action() -> Response:
        data: dict[str, Any] = request.get_json(force=True) or {}
        action = data.get("action", "")
        msg_ids = [int(i) for i in data.get("msg_ids", []) if str(i).isdigit()]
        user = _current_user()

        affected = outbox_svc.bulk_action(action, msg_ids, user=user)
        return jsonify({"ok": True, "action": action, "affected": affected})

    @app.get("/api/outbox/templates")
    def list_message_templates() -> Response:
        templates = outbox_svc.list_templates()
        return jsonify({"ok": True, "templates": templates})

    @app.post("/api/outbox/templates/<int:template_id>")
    def update_message_template(template_id: int) -> Response:
        data: dict[str, Any] = request.get_json(force=True) or {}
        title = data.get("title", "").strip()
        body_template = data.get("body_template", "").strip()
        if not title or not body_template:
            raise SchoolERPError("Template title and body cannot be empty.")

        outbox_svc.update_template(template_id, title, body_template)
        return jsonify({"ok": True, "id": template_id})

    @app.post("/api/outbox/generate/absent")
    def generate_absent_alerts() -> Response:
        data: dict[str, Any] = request.get_json(silent=True) or {}
        target_date = data.get("date")
        user = _current_user()
        res = outbox_svc.generate_absent_alerts(target_date, user=user)
        return jsonify({"ok": True, **res})

    @app.post("/api/outbox/generate/fee-reminders")
    def generate_fee_reminders() -> Response:
        data: dict[str, Any] = request.get_json(silent=True) or {}
        min_balance = float(data.get("min_balance", 1.0))
        class_id = int(data["class_id"]) if data.get("class_id") else None
        user = _current_user()
        res = outbox_svc.generate_fee_reminders(min_balance, class_id=class_id, user=user)
        return jsonify({"ok": True, **res})

    @app.post("/api/outbox/generate/exam-results")
    def generate_exam_results() -> Response:
        data: dict[str, Any] = request.get_json(force=True) or {}
        if not data.get("exam_id"):
            raise SchoolERPError("exam_id is required to generate result alerts.")
        exam_id = int(data["exam_id"])
        class_id = int(data["class_id"]) if data.get("class_id") else None
        user = _current_user()
        res = outbox_svc.generate_exam_alerts(exam_id, standard_id=class_id, user=user)
        return jsonify({"ok": True, **res})

    @app.post("/api/outbox/generate/circular")
    def generate_circular() -> Response:
        data: dict[str, Any] = request.get_json(force=True) or {}
        title = data.get("title", "").strip()
        body = data.get("body", "").strip()
        if not title or not body:
            raise SchoolERPError("Notice title and body are required.")
        target_type = data.get("target_type", "all")
        class_id = int(data["class_id"]) if data.get("class_id") else None
        user = _current_user()
        res = outbox_svc.generate_circular(
            title=title,
            body_text=body,
            target_type=target_type,
            standard_id=class_id,
            user=user,
        )
        return jsonify({"ok": True, **res})

