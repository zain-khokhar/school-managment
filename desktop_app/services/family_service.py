"""
Phase 3 Family Ledger Service — Sibling Consolidation & Single-Receipt Family Fee Collection (S2, R-F1).

Reuses ``school_parent`` and ``students_parents_rel`` (with fallback to shared ``contact_mobile``)
so families with multiple enrolled children can be searched by guardian name, mobile, CNIC, or GR No,
and paid in one atomic transaction producing itemized receipts plus a combined family receipt.
"""

from __future__ import annotations

from datetime import date
import re
from typing import Any

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, ValidationError
from desktop_app.services.audit_service import AuditService, utc_now_iso
from desktop_app.services.fee_engine_service import (
    FeeEngineService,
    from_paisa,
    paisa_decimal_str,
    to_paisa,
)
from desktop_app.services.settings_service import SettingsService


def _digits_only(val: str | None) -> str:
    return re.sub(r"\D+", "", val or "")


class FamilyService:
    """Consolidated Family Account & Sibling Fee Allocation Engine."""

    def __init__(
        self,
        db: Database,
        fee_engine: FeeEngineService | None = None,
        audit: AuditService | None = None,
        settings: SettingsService | None = None,
    ) -> None:
        self.db = db
        self.audit = audit or AuditService(db)
        self.settings = settings or SettingsService(db, self.audit)
        self.fee_engine = fee_engine or FeeEngineService(db, self.audit, self.settings)

    # -------------------------------------------------------------------------
    # Guardian Linking
    # -------------------------------------------------------------------------
    def upsert_guardian(
        self,
        payload: dict[str, Any],
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        name = (payload.get("name") or "").strip()
        phone = (payload.get("phone") or payload.get("mobile") or "").strip()[:40]
        cnic = (payload.get("cnic") or "").strip()[:25]
        relation = (payload.get("relation") or "Guardian").strip()[:40]
        email = (payload.get("email") or "").strip()[:100]

        raw_sids = payload.get("student_ids") or (
            [payload["student_id"]] if payload.get("student_id") else []
        )
        student_ids = [int(x) for x in raw_sids if x]
        if len(name) < 2:
            raise ValidationError("Guardian full name is required (min 2 characters).")
        if not student_ids:
            raise ValidationError("At least one student must be linked to the guardian.")

        with self.db.connection() as conn:
            existing_parent = None
            if cnic:
                existing_parent = conn.execute(
                    "SELECT id FROM school_parent WHERE cnic = ? AND cnic != '' LIMIT 1", (cnic,)
                ).fetchone()
            if not existing_parent and phone:
                existing_parent = conn.execute(
                    "SELECT id FROM school_parent WHERE phone = ? LIMIT 1",
                    (phone,),
                ).fetchone()

            if existing_parent:
                parent_id = int(existing_parent["id"])
                conn.execute(
                    """
                    UPDATE school_parent
                    SET name = ?, relation_name = ?, phone = COALESCE(NULLIF(?, ''), phone),
                        cnic = COALESCE(NULLIF(?, ''), cnic),
                        email = COALESCE(NULLIF(?, ''), email)
                    WHERE id = ?
                    """,
                    (name, relation, phone, cnic, email, parent_id),
                )
            else:
                cur = conn.execute(
                    """
                    INSERT INTO school_parent (name, relation_name, phone, cnic, email, active)
                    VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (name, relation, phone, cnic, email),
                )
                parent_id = int(cur.lastrowid)

            for sid in student_ids:
                stu = conn.execute("SELECT id, contact_mobile FROM student_student WHERE id = ?", (sid,)).fetchone()
                if not stu:
                    raise NotFoundError(f"Student #{sid} not found.")
                conn.execute(
                    "INSERT OR IGNORE INTO students_parents_rel (student_id, parent_id) VALUES (?, ?)",
                    (sid, parent_id),
                )
                if phone and not (stu["contact_mobile"] or "").strip():
                    conn.execute(
                        "UPDATE student_student SET contact_mobile = ? WHERE id = ?",
                        (phone, sid),
                    )

        family_key = f"P-{parent_id}"
        if actor:
            self.audit.record(
                user_id=actor.get("id"),
                username=actor.get("username") or "admin",
                role=actor.get("role") or "admin",
                action="families.guardian_upsert",
                entity_type="school_parent",
                entity_id=parent_id,
                summary=f"Linked guardian '{name}' ({family_key}) to {len(student_ids)} student(s)",
                ip_address=ip_address,
            )
        return {"family_key": family_key, "parent_id": parent_id, "student_ids": student_ids}

    # -------------------------------------------------------------------------
    # Family Resolution & Search
    # -------------------------------------------------------------------------
    def _build_all_family_groups(self) -> dict[str, dict[str, Any]]:
        with self.db.connection() as conn:
            parents = {
                int(r["id"]): dict(r)
                for r in conn.execute("SELECT * FROM school_parent WHERE active = 1").fetchall()
            }
            rels = conn.execute("SELECT student_id, parent_id FROM students_parents_rel ORDER BY parent_id ASC").fetchall()
            stu_to_parent: dict[int, int] = {}
            for r in rels:
                sid, pid = int(r["student_id"]), int(r["parent_id"])
                if pid in parents and sid not in stu_to_parent:
                    stu_to_parent[sid] = pid

            students = conn.execute(
                """
                SELECT s.*, ss.name AS class_name
                FROM student_student s
                LEFT JOIN school_standard ss ON ss.id = s.standard_id
                WHERE s.active = 1
                ORDER BY s.id ASC
                """
            ).fetchall()

            dues_by_stu: dict[int, tuple[int, int]] = {}
            for dr in conn.execute(
                """
                SELECT student_id,
                       COUNT(*) AS open_cnt,
                       COALESCE(SUM(CASE WHEN due_paisa > 0 THEN due_paisa ELSE CAST(ROUND(due_amount * 100) AS INTEGER) END), 0) AS due_p
                FROM student_payslip
                WHERE state IN ('confirm', 'pending') AND (due_paisa > 0 OR due_amount > 0)
                GROUP BY student_id
                """
            ).fetchall():
                dues_by_stu[int(dr["student_id"])] = (int(dr["open_cnt"]), int(dr["due_p"]))

        groups: dict[str, dict[str, Any]] = {}
        for s_row in students:
            s = dict(s_row)
            sid = int(s["id"])
            open_cnt, due_p = dues_by_stu.get(sid, (0, 0))
            s["open_vouchers_count"] = open_cnt
            s["due_paisa"] = due_p
            s["due_amount"] = from_paisa(due_p)

            if sid in stu_to_parent:
                p = parents[stu_to_parent[sid]]
                fkey = f"P-{p['id']}"
                if fkey not in groups:
                    groups[fkey] = {
                        "family_key": fkey,
                        "guardian_name": p["name"],
                        "relation": p.get("relation_name") or "Guardian",
                        "phone": p.get("phone") or p.get("mobile") or s.get("contact_mobile") or "",
                        "cnic": p.get("cnic") or "",
                        "children": [],
                    }
                groups[fkey]["children"].append(s)
            else:
                mob_digits = _digits_only(s.get("contact_mobile"))
                if len(mob_digits) >= 7:
                    fkey = f"M-{mob_digits}"
                    fam_label = f"{(s.get('last') or s['student_name']).strip()} Family"
                else:
                    fkey = f"S-{sid}"
                    fam_label = f"Guardian of {s['student_name']} {(s.get('last') or '').strip()}".strip()

                if fkey not in groups:
                    groups[fkey] = {
                        "family_key": fkey,
                        "guardian_name": fam_label,
                        "relation": "Guardian",
                        "phone": s.get("contact_mobile") or "",
                        "cnic": "",
                        "children": [],
                    }
                groups[fkey]["children"].append(s)

        for g in groups.values():
            kids = g["children"]
            g["children_count"] = len(kids)
            g["children_names"] = ", ".join(
                f"{c['student_name']} {(c.get('last') or '').strip()}".strip() for c in kids
            )
            g["open_vouchers_count"] = sum(int(c["open_vouchers_count"]) for c in kids)
            g["total_due_paisa"] = sum(int(c["due_paisa"]) for c in kids)
            g["total_due"] = from_paisa(g["total_due_paisa"])

        return groups

    def list_families(self, q: str = "", only_with_dues: bool = False) -> list[dict[str, Any]]:
        groups = self._build_all_family_groups()
        needle = (q or "").strip().lower()
        needle_digits = _digits_only(needle)

        results: list[dict[str, Any]] = []
        for g in groups.values():
            if only_with_dues and g["total_due_paisa"] <= 0:
                continue
            if needle:
                hay = " ".join(
                    [
                        g["family_key"],
                        g["guardian_name"],
                        g["phone"],
                        g["cnic"],
                        g["children_names"],
                        " ".join(c.get("pid") or "" for c in g["children"]),
                    ]
                ).lower()
                digit_hay = _digits_only(g["phone"] + g["cnic"])
                matched = needle in hay or (len(needle_digits) >= 4 and needle_digits in digit_hay)
                if not matched:
                    continue

            summary = {k: v for k, v in g.items() if k != "children"}
            summary["student_ids"] = [int(c["id"]) for c in g["children"]]
            results.append(summary)

        results.sort(key=lambda item: (-item["total_due_paisa"], -item["children_count"], item["guardian_name"]))
        return results

    def _resolve_family_group(self, family_key: str) -> dict[str, Any]:
        groups = self._build_all_family_groups()
        key = (family_key or "").strip()
        if key in groups:
            return groups[key]
        if key.isdigit():
            for prefix in ("P-", "S-"):
                if f"{prefix}{key}" in groups:
                    return groups[f"{prefix}{key}"]
            sid = int(key)
            for g in groups.values():
                if any(int(c["id"]) == sid for c in g["children"]):
                    return g
        raise NotFoundError(f"Family account '{family_key}' not found.")

    def get_family_ledger(self, family_key: str) -> dict[str, Any]:
        grp = self._resolve_family_group(family_key)
        sids = [int(c["id"]) for c in grp["children"]]
        ph = ",".join("?" for _ in sids)

        raw_vouchers = self.db.fetch_all(
            f"""
            SELECT p.*, st.student_name, st.last, st.pid, ss.name AS class_name
            FROM student_payslip p
            JOIN student_student st ON st.id = p.student_id
            LEFT JOIN school_standard ss ON ss.id = p.standard_id
            WHERE p.student_id IN ({ph}) AND p.state != 'cancel'
            ORDER BY COALESCE(p.due_date, p.date) ASC, p.id ASC
            """,
            sids,
        )
        vouchers = [FeeEngineService._hydrate_voucher_dict(r) for r in raw_vouchers]
        open_vouchers = [v for v in vouchers if v["state"] in ("confirm", "pending") and v["due_paisa"] > 0]

        payments = self.db.fetch_all(
            f"""
            SELECT fp.*, p.voucher_no, p.number AS slip_number, st.student_name, st.last, st.pid
            FROM fee_payment fp
            JOIN student_payslip p ON p.id = fp.payslip_id
            JOIN student_student st ON st.id = fp.student_id
            WHERE fp.student_id IN ({ph})
            ORDER BY fp.id DESC LIMIT 50
            """,
            sids,
        )
        for pmt in payments:
            pmt["amount"] = from_paisa(pmt["amount_paisa"])

        active_billed = sum(v["total_paisa"] for v in vouchers if v["state"] != "rolled_over")
        active_paid = sum(int(p["amount_paisa"]) for p in payments if not p["reversed_at"])
        total_due_p = sum(v["due_paisa"] for v in open_vouchers)

        return {
            "family_key": grp["family_key"],
            "guardian": {
                "name": grp["guardian_name"],
                "relation": grp["relation"],
                "phone": grp["phone"],
                "cnic": grp["cnic"],
            },
            "children": grp["children"],
            "open_vouchers": open_vouchers,
            "vouchers": list(reversed(vouchers)),
            "payments": payments,
            "summary": {
                "children_count": len(grp["children"]),
                "open_vouchers_count": len(open_vouchers),
                "total_billed_paisa": active_billed,
                "total_paid_paisa": active_paid,
                "total_due_paisa": total_due_p,
                "total_due": from_paisa(total_due_p),
            },
        }

    # -------------------------------------------------------------------------
    # Atomic Multi-Sibling Payment Allocation (R-F1)
    # -------------------------------------------------------------------------
    def collect_family_payment(
        self,
        *,
        family_key: str,
        amount_paisa: int,
        payment_mode: str = "cash",
        reference: str = "",
        note: str = "",
        payslip_ids: list[int] | None = None,
        payment_date: str | None = None,
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        if amount_paisa <= 0:
            raise ValidationError("Family payment amount must be greater than zero.")
        mode = (payment_mode or "cash").strip().lower()
        if mode not in ("cash", "bank", "cheque", "online"):
            raise ValidationError(f"Invalid payment_mode '{mode}'.")

        ledger = self.get_family_ledger(family_key)
        candidates = ledger["open_vouchers"]
        if payslip_ids:
            wanted = {int(x) for x in payslip_ids}
            candidates = [v for v in candidates if int(v["id"]) in wanted]
        if not candidates:
            raise ValidationError("No open fee vouchers found for this family.")

        max_payable = sum(int(v["due_paisa"]) for v in candidates)
        if amount_paisa > max_payable:
            raise ValidationError(
                f"Payment (Rs. {paisa_decimal_str(amount_paisa)}) exceeds total family due "
                f"(Rs. {paisa_decimal_str(max_payable)})."
            )

        pdate = (payment_date or date.today().isoformat()).strip()
        paid_at = utc_now_iso()
        uname = (actor.get("username") if actor else None) or "system"
        uid = actor.get("id") if actor else None

        receipts: list[dict[str, Any]] = []
        remaining = amount_paisa

        with self.db.connection() as conn:
            for v in candidates:
                if remaining <= 0:
                    break
                vid = int(v["id"])
                row = conn.execute("SELECT * FROM student_payslip WHERE id = ?", (vid,)).fetchone()
                total_p = int(row["total_paisa"]) if int(row["total_paisa"] or 0) > 0 else to_paisa(row["total"])
                paid_p = int(row["paid_paisa"]) if int(row["paid_paisa"] or 0) > 0 else to_paisa(row["paid_amount"] or 0)
                due_p = max(0, total_p - paid_p)
                if due_p <= 0:
                    continue

                alloc = min(remaining, due_p)
                remaining -= alloc
                rcp_no = self.db.next_by_code("fee.receipt", conn=conn)
                slip_num = row["number"] if row["number"] and row["number"] != "/" else self.db.next_by_code("student.payslip", conn=conn)

                cur = conn.execute(
                    """
                    INSERT INTO fee_payment
                    (receipt_no, payslip_id, student_id, amount_paisa, payment_mode, reference, note,
                     paid_at, payment_date, received_by_id, received_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rcp_no,
                        vid,
                        int(row["student_id"]),
                        alloc,
                        mode,
                        (reference or "").strip()[:80],
                        (note or f"Family payment ({ledger['family_key']})")[:200],
                        paid_at,
                        pdate,
                        uid,
                        uname,
                    ),
                )
                pmt_id = int(cur.lastrowid)
                new_paid_p = paid_p + alloc
                new_due_p = max(0, total_p - new_paid_p)
                new_state = "paid" if new_due_p == 0 else "pending"

                conn.execute(
                    """
                    UPDATE student_payslip
                    SET number = ?, total_paisa = ?, paid_paisa = ?, due_paisa = ?,
                        total = ?, paid_amount = ?, due_amount = ?, payment_date = ?, state = ?
                    WHERE id = ?
                    """,
                    (
                        slip_num,
                        total_p,
                        new_paid_p,
                        new_due_p,
                        from_paisa(total_p),
                        from_paisa(new_paid_p),
                        from_paisa(new_due_p),
                        pdate,
                        new_state,
                        vid,
                    ),
                )
                receipts.append(
                    {
                        "id": pmt_id,
                        "receipt_no": rcp_no,
                        "payslip_id": vid,
                        "voucher_no": v["voucher_display"],
                        "voucher_display": v["voucher_display"],
                        "student_id": int(row["student_id"]),
                        "student_name": f"{v['student_name']} {(v.get('last') or '').strip()}".strip(),
                        "pid": v.get("pid") or "",
                        "class_name": v.get("class_name") or "",
                        "amount_paisa": alloc,
                        "allocated_paisa": alloc,
                        "amount": from_paisa(alloc),
                        "remaining_due_paisa": new_due_p,
                        "remaining_due": from_paisa(new_due_p),
                    }
                )
            if remaining > 0:
                raise ValidationError(
                    f"Voucher balance changed concurrently; Rs. {paisa_decimal_str(remaining)} could not be allocated."
                )

        allocated_paisa = amount_paisa - remaining
        if actor:
            self.audit.record(
                user_id=uid,
                username=uname,
                role=actor.get("role") or "fee_clerk",
                action="families.payment_collect",
                entity_type="family_ledger",
                entity_id=ledger["family_key"],
                summary=f"Collected Rs. {paisa_decimal_str(allocated_paisa)} across {len(receipts)} voucher(s) for {ledger['guardian']['name']}",
                ip_address=ip_address,
            )

        updated_ledger = self.get_family_ledger(ledger["family_key"])
        combined_no = (
            receipts[0]["receipt_no"]
            if len(receipts) == 1
            else f"FAM-{receipts[0]['receipt_no']}"
        )
        combined_receipt = {
            "combined_receipt_no": combined_no,
            "receipt_count": len(receipts),
            "school": self.settings.get_school_profile(),
            "preferences": self.settings.get_preferences(),
            "family_key": ledger["family_key"],
            "guardian": ledger["guardian"],
            "payment_mode": mode,
            "reference": reference,
            "payment_date": pdate,
            "paid_at": paid_at,
            "received_by": uname,
            "total_paid_paisa": allocated_paisa,
            "total_paid": from_paisa(allocated_paisa),
            "remaining_family_due_paisa": updated_ledger["summary"]["total_due_paisa"],
            "remaining_family_due": updated_ledger["summary"]["total_due"],
            "items": receipts,
            "student_receipts": receipts,
        }
        return {
            "family_key": ledger["family_key"],
            "allocated_paisa": allocated_paisa,
            "allocated_amount": from_paisa(allocated_paisa),
            "receipts": receipts,
            "ledger": updated_ledger,
            "combined_receipt": combined_receipt,
            "family_receipt": combined_receipt,
        }
