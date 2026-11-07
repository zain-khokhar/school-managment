"""
Phase 3 Fee Engine Routes — Bulk Vouchers, Partial Collection, Undo/Reversal, Tally & Print Bundles.

Strictly under 400 lines per anti-monolith rule; sets ``g.audit_recorded = True`` when the
service records an explicit domain audit log entry.
"""

from __future__ import annotations

import time
from typing import Any

from flask import Flask, Response, g, jsonify, request

from desktop_app.exceptions import ValidationError
from desktop_app.services.fee_engine_service import FeeEngineService, to_paisa


def _actor() -> dict[str, Any]:
    return getattr(g, "current_user", None) or {
        "id": None,
        "username": "local",
        "role": "fee_clerk",
    }


def register_fees_routes(app: Flask, fee_engine: FeeEngineService) -> None:
    """Register Phase 3 `/api/fees/*` ledger, collection, rules, and print endpoints."""

    @app.get("/api/fees/vouchers")
    def list_fee_vouchers() -> Response:
        t0 = time.perf_counter()
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(200, max(1, int(request.args.get("per_page", 30))))
        q = request.args.get("q", "").strip()
        class_raw = request.args.get("class_id", "").strip()
        class_id = int(class_raw) if class_raw else None
        state = request.args.get("state", "").strip()
        billing_month = request.args.get("billing_month", "").strip()
        overdue_only = request.args.get("overdue_only", "").lower() in ("1", "true", "yes")

        res = fee_engine.list_vouchers_paginated(
            page=page,
            per_page=per_page,
            q=q,
            class_id=class_id,
            state=state,
            billing_month=billing_month,
            overdue_only=overdue_only,
        )
        res["ok"] = True
        res["elapsed_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
        return jsonify(res)

    @app.get("/api/fees/vouchers/<int:slip_id>")
    def get_fee_voucher(slip_id: int) -> Response:
        return jsonify({"ok": True, "voucher": fee_engine.get_voucher(slip_id)})

    @app.post("/api/fees/vouchers/bulk-generate")
    def bulk_generate_fee_vouchers() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        if not data.get("fees_structure_id"):
            raise ValidationError("fees_structure_id is required.")
        g.audit_recorded = True
        res = fee_engine.generate_bulk_vouchers(
            billing_month=str(data.get("billing_month") or ""),
            fees_structure_id=int(data["fees_structure_id"]),
            due_date=data.get("due_date"),
            class_id=int(data["class_id"]) if data.get("class_id") else None,
            include_arrears=bool(data.get("include_arrears", True)),
            apply_rules=bool(data.get("apply_rules", True)),
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, **res})

    @app.post("/api/fees/payments")
    def collect_fee_payment() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        if not data.get("payslip_id"):
            raise ValidationError("payslip_id is required.")
        raw_rupees = data.get("amount") if data.get("amount") is not None else data.get("amount_rupees")
        amount_paisa = (
            int(data["amount_paisa"])
            if data.get("amount_paisa") is not None
            else to_paisa(raw_rupees)
        )
        g.audit_recorded = True
        res = fee_engine.collect_payment(
            payslip_id=int(data["payslip_id"]),
            amount_paisa=amount_paisa,
            payment_mode=str(data.get("payment_mode") or "cash"),
            reference=str(data.get("reference") or ""),
            note=str(data.get("note") or ""),
            payment_date=data.get("payment_date"),
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, **res})

    @app.post("/api/fees/payments/<int:payment_id>/reverse")
    def reverse_fee_payment(payment_id: int) -> Response:
        data: dict[str, Any] = request.get_json(silent=True) or {}
        g.audit_recorded = True
        res = fee_engine.reverse_payment(
            payment_id=payment_id,
            actor=_actor(),
            reason=str(data.get("reason") or ""),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, **res})

    @app.get("/api/fees/tally")
    def get_fee_daily_tally() -> Response:
        target_date = request.args.get("date", "").strip() or None
        tally_data = fee_engine.get_daily_tally(target_date)
        return jsonify({"ok": True, "tally": tally_data, **tally_data})

    @app.get("/api/fees/defaulters")
    def list_fee_defaulters() -> Response:
        class_raw = request.args.get("class_id", "").strip()
        class_id = int(class_raw) if class_raw else None
        min_days = max(0, int(request.args.get("min_days_overdue", 0)))
        items = fee_engine.list_defaulters(class_id=class_id, min_days_overdue=min_days)
        total_due_paisa = sum(int(i["due_paisa"]) for i in items)
        return jsonify(
            {
                "ok": True,
                "items": items,
                "count": len(items),
                "total": len(items),
                "total_due_paisa": total_due_paisa,
                "total_due": round(total_due_paisa / 100.0, 2),
            }
        )

    @app.get("/api/fees/rules")
    def get_fee_rules() -> Response:
        active_only = request.args.get("active_only", "").lower() in ("1", "true", "yes")
        return jsonify({"ok": True, "items": fee_engine.list_rules(active_only=active_only)})

    @app.post("/api/fees/rules")
    def save_fee_rule() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        g.audit_recorded = True
        rule = fee_engine.upsert_rule(
            data,
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, "rule": rule})

    @app.get("/api/fees/concessions")
    def get_fee_concessions() -> Response:
        stu_raw = request.args.get("student_id", "").strip()
        stu_id = int(stu_raw) if stu_raw else None
        active_only = request.args.get("active_only", "1").lower() not in ("0", "false", "no")
        return jsonify(
            {
                "ok": True,
                "items": fee_engine.list_concessions(student_id=stu_id, active_only=active_only),
            }
        )

    @app.post("/api/fees/concessions")
    def create_fee_concession() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        g.audit_recorded = True
        conc = fee_engine.create_concession(
            data,
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, "concession": conc})

    @app.post("/api/fees/concessions/<int:conc_id>/delete")
    def deactivate_fee_concession(conc_id: int) -> Response:
        g.audit_recorded = True
        fee_engine.delete_concession(
            conc_id,
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True})

    @app.get("/api/fees/print/vouchers")
    def print_fee_vouchers_bundle() -> Response:
        ids_raw = request.args.get("ids", "").strip()
        ids = [int(x) for x in ids_raw.split(",") if x.strip().isdigit()] if ids_raw else None
        billing_month = request.args.get("billing_month", "").strip()
        class_raw = request.args.get("class_id", "").strip()
        class_id = int(class_raw) if class_raw else None
        bundle = fee_engine.get_print_vouchers(
            payslip_ids=ids,
            billing_month=billing_month,
            class_id=class_id,
        )
        return jsonify({"ok": True, **bundle})

    @app.get("/api/fees/print/receipt/<int:payment_id>")
    def print_fee_receipt_bundle(payment_id: int) -> Response:
        bundle = fee_engine.get_print_receipt(payment_id)
        return jsonify({"ok": True, **bundle})
