"""
Phase 3 Fee Engine Service — Exact Paisa Ledger, Bulk Vouchers, Partial Payments & Reversals.

Implements ADVANCEMENT_PLAN.md G4, G5, G11, S1, Section 10.3 & Section 12.3 (R-F2..R-F4):
  - All monetary arithmetic runs in integer paisa (`1 PKR = 100 paisa`) — zero float drift.
  - Idempotent class-wise / school-wide monthly voucher generation with automatic arrears carry-forward.
  - Partial & full fee collection (`cash`, `bank`, `cheque`, `online`) with sequential receipts.
  - 30-second clerk Undo window vs post-30s Admin/Principal-only reversal with mandatory reason & audit.
  - Rules, concessions, daily tally, defaulters & print bundles live in ``fee_rules_and_print.py``.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import re
from typing import Any

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, ValidationError
from desktop_app.services.audit_service import AuditService, utc_now_iso
from desktop_app.services.auth_service import AuthError
from desktop_app.services.fee_rules_and_print import (
    FeeRulesAndPrintMixin,
    from_paisa,
    paisa_decimal_str,
    to_paisa,
)
from desktop_app.services.settings_service import SettingsService

_BILLING_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_VALID_MODES = frozenset({"cash", "bank", "cheque", "online"})
CLERK_UNDO_WINDOW_SECONDS = 35.0  # 30s UI countdown + 5s local request tolerance

__all__ = ["FeeEngineService", "to_paisa", "from_paisa", "paisa_decimal_str", "CLERK_UNDO_WINDOW_SECONDS"]


def _parse_utc(iso_str: str) -> datetime:
    clean = iso_str.strip().replace(" ", "T")
    if clean.endswith("Z"):
        clean = clean[:-1] + "+00:00"
    dt = datetime.fromisoformat(clean)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class FeeEngineService(FeeRulesAndPrintMixin):
    """Enterprise School Fee Engine with integer-paisa accounting."""

    def __init__(
        self,
        db: Database,
        audit: AuditService | None = None,
        settings: SettingsService | None = None,
    ) -> None:
        self.db = db
        self.audit = audit or AuditService(db)
        self.settings = settings or SettingsService(db, self.audit)

    # -------------------------------------------------------------------------
    # Bulk Monthly Voucher Generation (G4, S1, R-F3)
    # -------------------------------------------------------------------------
    @staticmethod
    def _sibling_rank_conn(conn: Any, stu: dict[str, Any]) -> int:
        sid = int(stu["id"])
        sib_ids: set[int] = {sid}
        p_rows = conn.execute(
            "SELECT parent_id FROM students_parents_rel WHERE student_id = ?", (sid,)
        ).fetchall()
        if p_rows:
            pids = [int(r["parent_id"]) for r in p_rows]
            ph = ",".join("?" for _ in pids)
            linked = conn.execute(
                f"""
                SELECT DISTINCT s.id
                FROM student_student s
                JOIN students_parents_rel r ON r.student_id = s.id
                WHERE r.parent_id IN ({ph}) AND s.active = 1 AND s.state IN ('done', 'fees_received')
                """,
                pids,
            ).fetchall()
            sib_ids.update(int(r["id"]) for r in linked)

        mobile = (stu.get("contact_mobile") or "").strip()
        if mobile:
            m_rows = conn.execute(
                """
                SELECT id FROM student_student
                WHERE contact_mobile = ? AND active = 1 AND state IN ('done', 'fees_received')
                """,
                (mobile,),
            ).fetchall()
            sib_ids.update(int(r["id"]) for r in m_rows)

        if len(sib_ids) <= 1:
            return 1
        ph_all = ",".join("?" for _ in sib_ids)
        dob_rows = conn.execute(
            f"SELECT id FROM student_student WHERE id IN ({ph_all}) ORDER BY COALESCE(NULLIF(date_of_birth, ''), '9999-12-31') ASC, id ASC",
            list(sib_ids),
        ).fetchall()
        ordered = [int(r["id"]) for r in dob_rows]
        return ordered.index(sid) + 1

    def generate_bulk_vouchers(
        self,
        *,
        billing_month: str,
        fees_structure_id: int,
        due_date: str | None = None,
        class_id: int | None = None,
        include_arrears: bool = True,
        apply_rules: bool = True,
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        bm = (billing_month or "").strip()
        if not _BILLING_MONTH_RE.match(bm):
            raise ValidationError("billing_month must be in YYYY-MM format (e.g. 2026-09).")
        due_dt = (due_date or f"{bm}-10").strip()
        month_num = str(int(bm.split("-")[1]))

        struct = self.db.fetch_one(
            "SELECT * FROM student_fees_structure WHERE id = ?", (int(fees_structure_id),)
        )
        if not struct:
            raise NotFoundError(f"Fee structure #{fees_structure_id} not found.")
        struct_lines = self.db.fetch_all(
            "SELECT * FROM student_fees_structure_line WHERE structure_id = ? ORDER BY sequence, id",
            (int(fees_structure_id),),
        )
        if not struct_lines:
            raise ValidationError("Selected fee structure has no fee head lines.")

        stu_clause = "WHERE state IN ('done', 'fees_received') AND active = 1"
        stu_params: list[Any] = []
        if class_id:
            stu_clause += " AND standard_id = ?"
            stu_params.append(int(class_id))

        students = self.db.fetch_all(f"SELECT * FROM student_student {stu_clause} ORDER BY id ASC", stu_params)
        rules = self.list_rules(active_only=True) if apply_rules else []

        created_ids: list[int] = []
        skipped_count = 0
        total_billed_paisa = 0

        with self.db.connection() as conn:
            for stu in students:
                sid = int(stu["id"])
                existing = conn.execute(
                    """
                    SELECT id FROM student_payslip
                    WHERE student_id = ? AND billing_month = ? AND state != 'cancel'
                    LIMIT 1
                    """,
                    (sid, bm),
                ).fetchone()
                if existing:
                    skipped_count += 1
                    continue

                slip_date = f"{bm}-01"
                for day_try in range(1, 28):
                    cand = f"{bm}-{day_try:02d}"
                    clash = conn.execute(
                        "SELECT 1 FROM student_payslip WHERE student_id = ? AND date = ? LIMIT 1",
                        (sid, cand),
                    ).fetchone()
                    if not clash:
                        slip_date = cand
                        break

                subtotal_paisa = 0
                voucher_lines: list[tuple[str, str, str, int]] = []
                for sl in struct_lines:
                    ln_paisa = to_paisa(sl["amount"])
                    subtotal_paisa += ln_paisa
                    voucher_lines.append((sl["name"], sl["code"], sl["type"], ln_paisa))

                discount_paisa = 0
                if apply_rules and subtotal_paisa > 0:
                    stu_concs = conn.execute(
                        "SELECT * FROM fee_concession WHERE student_id = ? AND active = 1 ORDER BY id ASC",
                        (sid,),
                    ).fetchall()
                    for sc in stu_concs:
                        c_amt = (
                            (subtotal_paisa * int(sc["value"])) // 100
                            if sc["calc_mode"] == "percent"
                            else int(sc["value"])
                        )
                        c_amt = min(c_amt, max(0, subtotal_paisa - discount_paisa))
                        if c_amt > 0:
                            discount_paisa += c_amt
                            voucher_lines.append(
                                (f"Concession ({sc['concession_type'].title()})", "DISC-STU", "discount", -c_amt)
                            )

                    sib_rank = self._sibling_rank_conn(conn, stu)
                    sib_matches = [r for r in rules if r["rule_type"] == "sibling_discount" and sib_rank >= int(r["min_sibling_rank"])]
                    best_sib = max(sib_matches, key=lambda r: (int(r["min_sibling_rank"]), (subtotal_paisa * int(r["value"])) // 100 if r["calc_mode"] == "percent" else int(r["value"])), default=None)
                    active_rules = ([best_sib] if best_sib else []) + [r for r in rules if r["rule_type"] != "sibling_discount"]
                    for rl in active_rules:
                        rtype = rl["rule_type"]
                        if rtype == "sibling_discount":
                            r_amt = (subtotal_paisa * int(rl["value"])) // 100 if rl["calc_mode"] == "percent" else int(rl["value"])
                        elif rtype == "vacation_discount":
                            v_set = {m.strip().lstrip("0") for m in (rl["vacation_months"] or "").split(",") if m.strip()}
                            r_amt = (
                                ((subtotal_paisa * int(rl["value"])) // 100 if rl["calc_mode"] == "percent" else int(rl["value"]))
                                if month_num in v_set
                                else 0
                            )
                        elif rtype == "custom_discount":
                            r_amt = (
                                (subtotal_paisa * int(rl["value"])) // 100
                                if rl["calc_mode"] == "percent"
                                else int(rl["value"])
                            )
                        else:
                            r_amt = 0

                        r_amt = min(r_amt, max(0, subtotal_paisa - discount_paisa))
                        if r_amt > 0:
                            discount_paisa += r_amt
                            voucher_lines.append((rl["name"], rl["code"], "discount", -r_amt))

                arrears_paisa = 0
                if include_arrears:
                    prior_open = conn.execute(
                        """
                        SELECT id, due_paisa, due_amount
                        FROM student_payslip
                        WHERE student_id = ?
                          AND state IN ('confirm', 'pending')
                          AND (due_paisa > 0 OR due_amount > 0)
                          AND (COALESCE(billing_month, SUBSTR(date, 1, 7)) < ?)
                        ORDER BY date ASC, id ASC
                        """,
                        (sid, bm),
                    ).fetchall()
                    for pr in prior_open:
                        pr_due = int(pr["due_paisa"]) if int(pr["due_paisa"] or 0) > 0 else to_paisa(pr["due_amount"])
                        if pr_due > 0:
                            arrears_paisa += pr_due
                            conn.execute(
                                "UPDATE student_payslip SET due_paisa = 0, due_amount = 0.0, state = 'rolled_over' WHERE id = ?",
                                (int(pr["id"]),),
                            )
                    if arrears_paisa > 0:
                        voucher_lines.append(("Previous Arrears Carried Forward", "ARR", "arrears", arrears_paisa))

                total_paisa = max(0, subtotal_paisa - discount_paisa + arrears_paisa)
                slip_num = self.db.next_by_code("student.payslip", conn=conn)
                vch_seq = self.db.next_by_code("fee.voucher", conn=conn)
                voucher_no = f"{vch_seq[:4]}{bm.replace('-', '')}-{vch_seq[4:]}"

                cur = conn.execute(
                    """
                    INSERT INTO student_payslip
                    (fees_structure_id, standard_id, division_id, medium_id, register_id,
                     name, number, voucher_no, billing_month, student_id, date, due_date,
                     arrears_paisa, subtotal_paisa, discount_paisa, late_fee_paisa,
                     total_paisa, paid_paisa, due_paisa,
                     total, paid_amount, due_amount, journal_name, state)
                    VALUES (?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 0, ?, ?, 0.0, ?, 'Tuition Fees Journal', 'confirm')
                    """,
                    (
                        int(fees_structure_id), stu["standard_id"], stu["division_id"], stu["medium_id"],
                        f"Fee Voucher — {bm}", slip_num, voucher_no, bm, sid, slip_date, due_dt,
                        arrears_paisa, subtotal_paisa, discount_paisa, total_paisa, total_paisa,
                        from_paisa(total_paisa), from_paisa(total_paisa),
                    ),
                )
                slip_id = int(cur.lastrowid)
                for ln_name, ln_code, ln_type, ln_paisa in voucher_lines:
                    conn.execute(
                        "INSERT INTO student_payslip_line (slip_id, name, code, type, amount) VALUES (?, ?, ?, ?, ?)",
                        (slip_id, ln_name, ln_code, ln_type, from_paisa(ln_paisa)),
                    )
                created_ids.append(slip_id)
                total_billed_paisa += total_paisa

        if actor:
            self.audit.record(
                user_id=actor.get("id"),
                username=actor.get("username") or "admin",
                role=actor.get("role") or "admin",
                action="fees.bulk_generate",
                entity_type="student_payslip",
                entity_id=bm,
                summary=f"Generated {len(created_ids)} vouchers for {bm} (skipped {skipped_count})",
                ip_address=ip_address,
            )

        return {
            "billing_month": bm,
            "due_date": due_dt,
            "created_count": len(created_ids),
            "skipped_count": skipped_count,
            "total_billed_paisa": total_billed_paisa,
            "total_billed": from_paisa(total_billed_paisa),
            "voucher_ids": created_ids,
        }

    # -------------------------------------------------------------------------
    # Voucher Queries, Partial Collection & Reversal (G4, R-F2, R-F4)
    # -------------------------------------------------------------------------
    def get_voucher(self, payslip_id: int) -> dict[str, Any]:
        row = self.db.fetch_one(
            """
            SELECT p.*, st.student_name, st.middle, st.last, st.pid, st.roll_no,
                   st.contact_mobile, ss.name AS class_name, fs.name AS structure_name
            FROM student_payslip p
            JOIN student_student st ON st.id = p.student_id
            LEFT JOIN school_standard ss ON ss.id = p.standard_id
            LEFT JOIN student_fees_structure fs ON fs.id = p.fees_structure_id
            WHERE p.id = ?
            """,
            (payslip_id,),
        )
        if not row:
            raise NotFoundError(f"Fee voucher #{payslip_id} not found.")
        out = self._hydrate_voucher_dict(row)
        out["lines"] = self.db.fetch_all(
            "SELECT * FROM student_payslip_line WHERE slip_id = ? ORDER BY id ASC",
            (payslip_id,),
        )
        out["payments"] = self.db.fetch_all(
            "SELECT * FROM fee_payment WHERE payslip_id = ? ORDER BY id DESC",
            (payslip_id,),
        )
        for pmt in out["payments"]:
            pmt["amount"] = from_paisa(pmt["amount_paisa"])
        return out

    def list_vouchers_paginated(
        self,
        *,
        page: int = 1,
        per_page: int = 30,
        q: str = "",
        class_id: int | None = None,
        state: str = "",
        billing_month: str = "",
        overdue_only: bool = False,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if q.strip():
            like = f"%{q.strip()}%"
            clauses.append(
                "(p.voucher_no LIKE ? OR p.number LIKE ? OR st.student_name LIKE ? "
                "OR st.last LIKE ? OR st.pid LIKE ? OR st.contact_mobile LIKE ?)"
            )
            params.extend([like, like, like, like, like, like])
        if class_id:
            clauses.append("p.standard_id = ?")
            params.append(int(class_id))
        if state:
            clauses.append("p.state = ?")
            params.append(state)
        if billing_month:
            clauses.append("p.billing_month = ?")
            params.append(billing_month)
        if overdue_only:
            clauses.append(
                "p.state IN ('confirm', 'pending') AND p.due_paisa > 0 "
                "AND COALESCE(p.due_date, p.date) < ?"
            )
            params.append(date.today().isoformat())

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        offset = (max(1, page) - 1) * per_page

        with self.db.connection() as conn:
            total = int(
                conn.execute(
                    f"""
                    SELECT COUNT(*) AS c
                    FROM student_payslip p
                    JOIN student_student st ON st.id = p.student_id
                    {where}
                    """,
                    params,
                ).fetchone()["c"]
            )
            rows = conn.execute(
                f"""
                SELECT p.*, st.student_name, st.last, st.pid, st.contact_mobile,
                       ss.name AS class_name
                FROM student_payslip p
                JOIN student_student st ON st.id = p.student_id
                LEFT JOIN school_standard ss ON ss.id = p.standard_id
                {where}
                ORDER BY p.id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, per_page, offset],
            ).fetchall()

        return {
            "items": [self._hydrate_voucher_dict(dict(r)) for r in rows],
            "total": total,
            "page": max(1, page),
            "pages": max(1, -(-total // per_page)),
        }

    def collect_payment(
        self,
        *,
        payslip_id: int,
        amount_paisa: int,
        payment_mode: str = "cash",
        reference: str = "",
        note: str = "",
        payment_date: str | None = None,
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        if amount_paisa <= 0:
            raise ValidationError("Payment amount must be greater than zero.")
        mode = (payment_mode or "cash").strip().lower()
        if mode not in _VALID_MODES:
            raise ValidationError(f"Invalid payment_mode '{mode}'. Choose cash, bank, cheque, or online.")

        pdate = (payment_date or date.today().isoformat()).strip()
        paid_at = utc_now_iso()
        uname = (actor.get("username") if actor else None) or "system"
        uid = actor.get("id") if actor else None

        with self.db.connection() as conn:
            slip = conn.execute("SELECT * FROM student_payslip WHERE id = ?", (payslip_id,)).fetchone()
            if not slip:
                raise NotFoundError(f"Fee voucher #{payslip_id} not found.")
            if slip["state"] in ("cancel", "rolled_over"):
                raise ValidationError(f"Cannot collect payment on voucher in '{slip['state']}' state.")

            total_p = int(slip["total_paisa"]) if int(slip["total_paisa"] or 0) > 0 else to_paisa(slip["total"])
            paid_p = int(slip["paid_paisa"]) if int(slip["paid_paisa"] or 0) > 0 else to_paisa(slip["paid_amount"] or 0)
            due_p = max(0, total_p - paid_p)
            if due_p <= 0 or slip["state"] == "paid":
                raise ValidationError("This fee voucher is already settled in full.")
            if amount_paisa > due_p:
                raise ValidationError(
                    f"Payment (Rs. {paisa_decimal_str(amount_paisa)}) exceeds remaining balance "
                    f"(Rs. {paisa_decimal_str(due_p)})."
                )

            rcp_no = self.db.next_by_code("fee.receipt", conn=conn)
            slip_num = slip["number"]
            if not slip_num or slip_num == "/":
                slip_num = self.db.next_by_code("student.payslip", conn=conn)

            cur = conn.execute(
                """
                INSERT INTO fee_payment
                (receipt_no, payslip_id, student_id, amount_paisa, payment_mode, reference, note,
                 paid_at, payment_date, received_by_id, received_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rcp_no,
                    payslip_id,
                    int(slip["student_id"]),
                    amount_paisa,
                    mode,
                    (reference or "").strip()[:80],
                    (note or "").strip()[:200],
                    paid_at,
                    pdate,
                    uid,
                    uname,
                ),
            )
            payment_id = int(cur.lastrowid)

            new_paid_p = paid_p + amount_paisa
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
                    payslip_id,
                ),
            )
            pmt_row = dict(conn.execute("SELECT * FROM fee_payment WHERE id = ?", (payment_id,)).fetchone())

        pmt_row["amount"] = from_paisa(pmt_row["amount_paisa"])
        if actor:
            self.audit.record(
                user_id=uid,
                username=uname,
                role=actor.get("role") or "fee_clerk",
                action="fees.payment_collect",
                entity_type="fee_payment",
                entity_id=payment_id,
                summary=f"Collected Rs. {paisa_decimal_str(amount_paisa)} ({mode}) — {rcp_no}",
                ip_address=ip_address,
            )

        return {"payment": pmt_row, "payslip": self.get_voucher(payslip_id)}

    def reverse_payment(
        self,
        *,
        payment_id: int,
        actor: dict[str, Any],
        reason: str = "",
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        role = actor.get("role") or "fee_clerk"
        uname = actor.get("username") or "unknown"
        clean_reason = (reason or "").strip()

        with self.db.connection() as conn:
            pmt = conn.execute("SELECT * FROM fee_payment WHERE id = ?", (payment_id,)).fetchone()
            if not pmt:
                raise NotFoundError(f"Payment receipt #{payment_id} not found.")
            if pmt["reversed_at"]:
                raise ValidationError("This payment receipt has already been reversed.")

            elapsed_s = (datetime.now(timezone.utc) - _parse_utc(pmt["paid_at"])).total_seconds()
            is_admin = role in ("admin", "principal")
            actor_uid = actor.get("id")
            if not is_admin and pmt["received_by_id"] and actor_uid and int(pmt["received_by_id"]) != int(actor_uid):
                raise AuthError("Fee clerks can only undo their own receipts within the 30-second window.", status_code=403)
            if elapsed_s > CLERK_UNDO_WINDOW_SECONDS and not is_admin:
                raise AuthError("The 30-second undo window has expired. Administrator or Principal required.", status_code=403)
            if elapsed_s > CLERK_UNDO_WINDOW_SECONDS and len(clean_reason) < 3:
                raise ValidationError("A reversal reason (min 3 characters) is required after the 30-second window.")
            if not clean_reason:
                clean_reason = "Quick undo within 30s window"

            payslip_id = int(pmt["payslip_id"])
            slip = conn.execute("SELECT * FROM student_payslip WHERE id = ?", (payslip_id,)).fetchone()
            if slip and slip["state"] == "rolled_over":
                raise ValidationError("Cannot reverse a payment on a voucher whose balance has already been carried forward.")

            cur = conn.execute(
                "UPDATE fee_payment SET reversed_at = ?, reversed_by = ?, reversal_reason = ? WHERE id = ? AND reversed_at IS NULL",
                (utc_now_iso(), uname, clean_reason[:200], payment_id),
            )
            if cur.rowcount == 0:
                raise ValidationError("This payment receipt has already been reversed.")
            active_sum = int(
                conn.execute(
                    "SELECT COALESCE(SUM(amount_paisa), 0) AS s FROM fee_payment WHERE payslip_id = ? AND reversed_at IS NULL",
                    (payslip_id,),
                ).fetchone()["s"]
            )
            total_p = int(slip["total_paisa"]) if int(slip["total_paisa"] or 0) > 0 else to_paisa(slip["total"])
            due_p = max(0, total_p - active_sum)
            new_state = "paid" if due_p == 0 and total_p > 0 else ("pending" if active_sum > 0 else "confirm")

            conn.execute(
                """
                UPDATE student_payslip
                SET paid_paisa = ?, due_paisa = ?, paid_amount = ?, due_amount = ?, state = ?
                WHERE id = ?
                """,
                (active_sum, due_p, from_paisa(active_sum), from_paisa(due_p), new_state, payslip_id),
            )
            updated_pmt = dict(conn.execute("SELECT * FROM fee_payment WHERE id = ?", (payment_id,)).fetchone())

        updated_pmt["amount"] = from_paisa(updated_pmt["amount_paisa"])
        self.audit.record(
            user_id=actor.get("id"),
            username=uname,
            role=role,
            action="fees.payment_reverse",
            entity_type="fee_payment",
            entity_id=payment_id,
            summary=f"Reversed {updated_pmt['receipt_no']} (Rs. {paisa_decimal_str(updated_pmt['amount_paisa'])}): {clean_reason}",
            ip_address=ip_address,
        )
        return {"payment": updated_pmt, "payslip": self.get_voucher(payslip_id)}
