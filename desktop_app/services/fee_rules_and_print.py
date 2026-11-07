"""
Phase 3 Fee Rules, Concessions, Daily Tally, Defaulters & Print Payloads.

Extracted from ``fee_engine_service.py`` so every modular service file stays strictly
under the 600-line anti-monolith budget (`scripts/check_file_sizes.py`).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
from typing import Any

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, ValidationError
from desktop_app.services.audit_service import AuditService, utc_now_iso
from desktop_app.services.settings_service import SettingsService

VALID_RULE_TYPES = frozenset({"sibling_discount", "late_fee", "vacation_discount", "custom_discount"})
VALID_CONCESSION_TYPES = frozenset({"scholarship", "sibling", "staff_child", "financial_aid", "custom"})
VALID_CALC_MODES = frozenset({"percent", "fixed_paisa"})


MAX_MONETARY_RUPEES = Decimal("100000000")


def to_paisa(value: Any) -> int:
    """Convert a rupee value (`int`, `float`, `str`, `Decimal`) into exact integer paisa."""
    if value is None or value == "":
        raise ValidationError("Amount is required.")
    try:
        dec = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(f"Invalid monetary amount: {value!r}") from exc
    if not dec.is_finite() or dec < 0:
        raise ValidationError("Amount must be a non-negative finite number.")
    if dec > MAX_MONETARY_RUPEES:
        raise ValidationError("Amount exceeds the maximum single-transaction ceiling (Rs. 100,000,000).")
    return int((dec * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_paisa(paisa: int) -> float:
    """Convert integer paisa to 2-decimal float for JSON / legacy column sync."""
    return round(int(paisa) / 100.0, 2)


def paisa_decimal_str(paisa: int) -> str:
    """Exact string representation (`'1234.55'`) without IEEE-754 float intermediate."""
    sign = "-" if paisa < 0 else ""
    abs_p = abs(int(paisa))
    return f"{sign}{abs_p // 100}.{abs_p % 100:02d}"


class FeeRulesAndPrintMixin:
    """Fee Rules, Student Concessions, Daily Cash Tally, Defaulters & Print Bundle methods."""

    db: Database
    audit: AuditService
    settings: SettingsService

    def get_voucher(self, payslip_id: int) -> dict[str, Any]:  # pragma: no cover - implemented on subclass
        raise NotImplementedError

    @staticmethod
    def _hydrate_voucher_dict(row: dict[str, Any]) -> dict[str, Any]:
        out = dict(row)
        if int(out.get("total_paisa") or 0) == 0 and float(out.get("total") or 0.0) > 0:
            out["total_paisa"] = to_paisa(out["total"])
            out["paid_paisa"] = to_paisa(out.get("paid_amount") or 0)
            out["due_paisa"] = to_paisa(out.get("due_amount") or 0)
        out["total"] = from_paisa(out["total_paisa"])
        out["paid_amount"] = from_paisa(out["paid_paisa"])
        out["due_amount"] = from_paisa(out["due_paisa"])
        out["voucher_display"] = out.get("voucher_no") or out.get("number") or f"VCH-{out['id']}"
        return out

    # -------------------------------------------------------------------------
    # Fee Rules & Student Concessions (G5)
    # -------------------------------------------------------------------------
    def list_rules(self, active_only: bool = False) -> list[dict[str, Any]]:
        clause = "WHERE active = 1" if active_only else ""
        rows = self.db.fetch_all(f"SELECT * FROM fee_rule {clause} ORDER BY id ASC")
        for r in rows:
            r["value_rupees"] = from_paisa(r["value"]) if r["calc_mode"] == "fixed_paisa" else r["value"]
        return rows

    def upsert_rule(
        self,
        payload: dict[str, Any],
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        name = (payload.get("name") or "").strip()
        code = (payload.get("code") or "").strip().upper()
        rule_type = (payload.get("rule_type") or "").strip()
        calc_mode = (payload.get("calc_mode") or "percent").strip()
        if len(name) < 2 or not code:
            raise ValidationError("Rule name and code are required.")
        if rule_type not in VALID_RULE_TYPES:
            raise ValidationError(f"Invalid rule_type '{rule_type}'.")
        if calc_mode not in VALID_CALC_MODES:
            raise ValidationError(f"Invalid calc_mode '{calc_mode}'.")

        if calc_mode == "percent":
            value = int(payload.get("value", 0))
            if value < 0 or value > 100:
                raise ValidationError("Percentage rule value must be between 0 and 100.")
        else:
            value = (
                to_paisa(payload["value_rupees"])
                if payload.get("value_rupees") is not None
                else int(payload.get("value", 0))
            )
            if value < 0:
                raise ValidationError("Fixed rule amount cannot be negative.")

        min_sib = max(2, int(payload.get("min_sibling_rank") or 2))
        grace = max(0, int(payload.get("grace_days") or 0))
        vac_months = ",".join(
            s.strip() for s in str(payload.get("vacation_months") or "").split(",") if s.strip()
        )
        active = 1 if payload.get("active", True) else 0
        now = utc_now_iso()

        with self.db.connection() as conn:
            conn.execute(
                """
                INSERT INTO fee_rule
                (name, code, rule_type, calc_mode, value, min_sibling_rank, grace_days, vacation_months, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    rule_type = excluded.rule_type,
                    calc_mode = excluded.calc_mode,
                    value = excluded.value,
                    min_sibling_rank = excluded.min_sibling_rank,
                    grace_days = excluded.grace_days,
                    vacation_months = excluded.vacation_months,
                    active = excluded.active
                """,
                (name, code, rule_type, calc_mode, value, min_sib, grace, vac_months, active, now),
            )
            row = conn.execute("SELECT * FROM fee_rule WHERE code = ?", (code,)).fetchone()

        if actor:
            self.audit.record(
                user_id=actor.get("id"),
                username=actor.get("username") or "admin",
                role=actor.get("role") or "admin",
                action="fees.rule_upsert",
                entity_type="fee_rule",
                entity_id=row["id"],
                summary=f"Saved fee rule '{name}' ({code})",
                ip_address=ip_address,
            )
        out = dict(row)
        out["value_rupees"] = from_paisa(out["value"]) if out["calc_mode"] == "fixed_paisa" else out["value"]
        return out

    def list_concessions(self, student_id: int | None = None, active_only: bool = True) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if student_id is not None:
            clauses.append("fc.student_id = ?")
            params.append(int(student_id))
        if active_only:
            clauses.append("fc.active = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.db.fetch_all(
            f"""
            SELECT fc.*, st.student_name, st.last, st.pid, ss.name AS class_name
            FROM fee_concession fc
            JOIN student_student st ON st.id = fc.student_id
            LEFT JOIN school_standard ss ON ss.id = st.standard_id
            {where}
            ORDER BY fc.id DESC
            """,
            params,
        )
        for r in rows:
            r["value_rupees"] = from_paisa(r["value"]) if r["calc_mode"] == "fixed_paisa" else r["value"]
        return rows

    def create_concession(
        self,
        payload: dict[str, Any],
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        student_id = int(payload.get("student_id") or 0)
        stu = self.db.fetch_one("SELECT id, student_name, pid FROM student_student WHERE id = ?", (student_id,))
        if not stu:
            raise NotFoundError(f"Student #{student_id} not found.")

        ctype = (payload.get("concession_type") or "scholarship").strip()
        cmode = (payload.get("calc_mode") or "percent").strip()
        if ctype not in VALID_CONCESSION_TYPES:
            raise ValidationError(f"Invalid concession_type '{ctype}'.")
        if cmode not in VALID_CALC_MODES:
            raise ValidationError(f"Invalid calc_mode '{cmode}'.")

        if cmode == "percent":
            val = int(payload.get("value", 0))
            if val <= 0 or val > 100:
                raise ValidationError("Scholarship/concession percentage must be between 1 and 100.")
        else:
            val = (
                to_paisa(payload["value_rupees"])
                if payload.get("value_rupees") is not None
                else int(payload.get("value", 0))
            )
            if val <= 0:
                raise ValidationError("Concession amount must be greater than zero.")

        reason = (payload.get("reason") or "").strip()[:200]
        approved_by = (actor.get("username") if actor else None) or "admin"
        now = utc_now_iso()

        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO fee_concession
                (student_id, concession_type, calc_mode, value, reason, active, approved_by, created_at)
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (student_id, ctype, cmode, val, reason, approved_by, now),
            )
            cid = int(cur.lastrowid)

        if actor:
            self.audit.record(
                user_id=actor.get("id"),
                username=approved_by,
                role=actor.get("role") or "admin",
                action="fees.concession_create",
                entity_type="fee_concession",
                entity_id=cid,
                summary=f"Granted {ctype} concession to {stu['student_name']} ({stu['pid']})",
                ip_address=ip_address,
            )
        return self.list_concessions(student_id=student_id, active_only=False)[0]

    def delete_concession(
        self,
        concession_id: int,
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> None:
        with self.db.connection() as conn:
            row = conn.execute("SELECT id, active FROM fee_concession WHERE id = ?", (concession_id,)).fetchone()
            if not row:
                raise NotFoundError(f"Concession #{concession_id} not found.")
            cur = conn.execute("UPDATE fee_concession SET active = 0 WHERE id = ? AND active = 1", (concession_id,))
            deactivated = cur.rowcount > 0
        if deactivated and actor:
            self.audit.record(
                user_id=actor.get("id"),
                username=actor.get("username") or "admin",
                role=actor.get("role") or "admin",
                action="fees.concession_deactivate",
                entity_type="fee_concession",
                entity_id=concession_id,
                summary=f"Deactivated fee concession #{concession_id}",
                ip_address=ip_address,
            )

    # -------------------------------------------------------------------------
    # Daily Cash Tally, Defaulters Aging & Print Bundles (R-F4, S1)
    # -------------------------------------------------------------------------
    def get_daily_tally(self, target_date: str | None = None) -> dict[str, Any]:
        dt = (target_date or date.today().isoformat()).strip()
        rows = self.db.fetch_all(
            """
            SELECT fp.*, p.voucher_no, p.number AS slip_number,
                   st.student_name, st.last, st.pid, ss.name AS class_name
            FROM fee_payment fp
            JOIN student_payslip p ON p.id = fp.payslip_id
            JOIN student_student st ON st.id = fp.student_id
            LEFT JOIN school_standard ss ON ss.id = st.standard_id
            WHERE fp.payment_date = ?
            ORDER BY fp.id DESC
            """,
            (dt,),
        )

        by_mode_paisa = {m: 0 for m in ("cash", "bank", "cheque", "online")}
        reversed_paisa = 0
        reversed_count = 0
        active_count = 0

        for r in rows:
            amt_p = int(r["amount_paisa"])
            r["amount"] = from_paisa(amt_p)
            r["amount_exact"] = paisa_decimal_str(amt_p)
            if r["reversed_at"]:
                reversed_paisa += amt_p
                reversed_count += 1
            else:
                mode = r["payment_mode"] if r["payment_mode"] in by_mode_paisa else "cash"
                by_mode_paisa[mode] += amt_p
                active_count += 1

        net_paisa = sum(by_mode_paisa.values())
        return {
            "date": dt,
            "net_collected_paisa": net_paisa,
            "net_collected": paisa_decimal_str(net_paisa),
            "net_collected_float": from_paisa(net_paisa),
            "active_receipts_count": active_count,
            "reversed_count": reversed_count,
            "reversed_paisa": reversed_paisa,
            "reversed_amount": from_paisa(reversed_paisa),
            "by_mode_paisa": by_mode_paisa,
            "by_mode": {k: from_paisa(v) for k, v in by_mode_paisa.items()},
            "receipts": rows,
        }

    def list_defaulters(self, class_id: int | None = None, min_days_overdue: int = 0) -> list[dict[str, Any]]:
        today = date.today()
        clause = "WHERE p.state IN ('confirm', 'pending') AND (p.due_paisa > 0 OR p.due_amount > 0)"
        params: list[Any] = []
        if class_id:
            clause += " AND p.standard_id = ?"
            params.append(int(class_id))

        rows = self.db.fetch_all(
            f"""
            SELECT p.*, st.student_name, st.last, st.pid, st.contact_mobile,
                   ss.name AS class_name
            FROM student_payslip p
            JOIN student_student st ON st.id = p.student_id
            LEFT JOIN school_standard ss ON ss.id = p.standard_id
            {clause}
            ORDER BY COALESCE(p.due_date, p.date) ASC, p.due_paisa DESC
            """,
            params,
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            item = self._hydrate_voucher_dict(r)
            ref_dt_str = (item.get("due_date") or item.get("date") or today.isoformat())[:10]
            try:
                days_over = (today - date.fromisoformat(ref_dt_str)).days
            except ValueError:
                days_over = 0
            item["days_overdue"] = max(0, days_over)
            if item["days_overdue"] >= min_days_overdue:
                out.append(item)
        return out

    def _late_surcharge_for_due(self, due_paisa: int, rule: dict[str, Any] | None) -> int:
        if due_paisa <= 0 or not rule:
            return 0
        if rule["calc_mode"] == "percent":
            return (int(due_paisa) * int(rule["value"])) // 100
        return int(rule["value"])

    def get_print_vouchers(
        self,
        *,
        payslip_ids: list[int] | None = None,
        billing_month: str = "",
        class_id: int | None = None,
    ) -> dict[str, Any]:
        school = self.settings.get_school_profile()
        prefs = self.settings.get_preferences()
        late_rule = self.db.fetch_one(
            "SELECT calc_mode, value FROM fee_rule WHERE rule_type = 'late_fee' AND active = 1 ORDER BY id DESC LIMIT 1"
        )

        if payslip_ids:
            ids = [int(x) for x in payslip_ids]
        else:
            clauses = ["state != 'cancel'"]
            params: list[Any] = []
            if billing_month:
                clauses.append("billing_month = ?")
                params.append(billing_month)
            if class_id:
                clauses.append("standard_id = ?")
                params.append(int(class_id))
            rows = self.db.fetch_all(
                f"SELECT id FROM student_payslip WHERE {' AND '.join(clauses)} ORDER BY standard_id ASC, id ASC LIMIT 200",
                params,
            )
            ids = [int(r["id"]) for r in rows]

        vouchers: list[dict[str, Any]] = []
        for sid in ids:
            v = self.get_voucher(sid)
            surcharge_p = self._late_surcharge_for_due(int(v["due_paisa"]), late_rule)
            after_due_p = int(v["due_paisa"]) + surcharge_p
            digest = hashlib.sha256(
                f"{v['voucher_display']}:{v['pid']}:{v['total_paisa']}".encode("utf-8")
            ).hexdigest()[:10].upper()
            v["copies"] = ["Bank Copy", "School Copy", "Parent Copy"]
            v["late_surcharge_paisa"] = surcharge_p
            v["after_due_paisa"] = after_due_p
            v["after_due_amount"] = from_paisa(after_due_p)
            v["qr_payload"] = f"ERP|{v['voucher_display']}|{v['pid']}|{paisa_decimal_str(v['due_paisa'])}|{digest}"
            v["verification_code"] = digest
            vouchers.append(v)

        return {"school": school, "preferences": prefs, "vouchers": vouchers}

    def get_print_receipt(self, payment_id: int) -> dict[str, Any]:
        pmt = self.db.fetch_one("SELECT * FROM fee_payment WHERE id = ?", (payment_id,))
        if not pmt:
            raise NotFoundError(f"Payment receipt #{payment_id} not found.")
        voucher = self.get_voucher(int(pmt["payslip_id"]))
        pmt_out = dict(pmt)
        pmt_out["amount"] = from_paisa(pmt_out["amount_paisa"])
        pmt_out["amount_exact"] = paisa_decimal_str(pmt_out["amount_paisa"])
        return {
            "school": self.settings.get_school_profile(),
            "preferences": self.settings.get_preferences(),
            "receipt": pmt_out,
            "voucher": voucher,
        }

