"""
Phase 3 Family Ledger Routes — Guardian Linking, Family Search & Multi-Sibling Collection (S2, R-F1).
"""

from __future__ import annotations

from typing import Any

from flask import Flask, Response, g, jsonify, request

from desktop_app.services.family_service import FamilyService
from desktop_app.services.fee_engine_service import to_paisa


def _actor() -> dict[str, Any]:
    return getattr(g, "current_user", None) or {
        "id": None,
        "username": "local",
        "role": "fee_clerk",
    }


def register_family_routes(app: Flask, family_svc: FamilyService) -> None:
    """Register `/api/families/*` consolidated sibling ledger endpoints."""

    @app.get("/api/families")
    def search_families() -> Response:
        q = request.args.get("q", "").strip()
        only_dues = request.args.get("only_with_dues", "").lower() in ("1", "true", "yes")
        items = family_svc.list_families(q=q, only_with_dues=only_dues)
        return jsonify({"ok": True, "items": items, "total": len(items)})

    @app.get("/api/families/<string:family_key>/ledger")
    def get_family_ledger(family_key: str) -> Response:
        ledger = family_svc.get_family_ledger(family_key)
        return jsonify({"ok": True, **ledger})

    @app.post("/api/families/<string:family_key>/pay")
    def pay_family_vouchers(family_key: str) -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        raw_rupees = data.get("amount") if data.get("amount") is not None else data.get("amount_rupees")
        amount_paisa = (
            int(data["amount_paisa"])
            if data.get("amount_paisa") is not None
            else to_paisa(raw_rupees)
        )
        payslip_ids = [int(x) for x in data["payslip_ids"]] if data.get("payslip_ids") else None
        g.audit_recorded = True
        res = family_svc.collect_family_payment(
            family_key=family_key,
            amount_paisa=amount_paisa,
            payment_mode=str(data.get("payment_mode") or "cash"),
            reference=str(data.get("reference") or ""),
            note=str(data.get("note") or ""),
            payslip_ids=payslip_ids,
            payment_date=data.get("payment_date"),
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, **res})

    @app.post("/api/families/guardian")
    def link_family_guardian() -> Response:
        data: dict[str, Any] = request.get_json(force=True)
        g.audit_recorded = True
        res = family_svc.upsert_guardian(
            data,
            actor=_actor(),
            ip_address=request.remote_addr or "127.0.0.1",
        )
        return jsonify({"ok": True, **res})
