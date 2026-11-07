"""
desktop_app/services/outbox_triggers_mixin.py — Outbox Auto-Triggers & Batch Generators (Phase 5).

Provides mixin methods for generating absent notices, fee balance reminders,
examination result cards, and general circular broadcasts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


class OutboxTriggersMixin:
    """Batch generator mixin for OutboxService."""

    def generate_absent_alerts(self, date_str: str | None = None, user: str = "system") -> dict[str, int]:
        """Generate outbox alerts for all students marked absent on a specific date."""
        target_date = date_str or self._today()
        records = self.db.fetch_all(
            """
            SELECT dal.stud_id AS student_id, dal.is_present, dal.is_absent,
                   s.student_name, s.roll_no, s.pid, s.contact_mobile, s.standard_id,
                   st.name AS standard_name,
                   p.name AS parent_name, p.phone AS parent_phone
            FROM daily_attendance_line dal
            JOIN daily_attendance da ON da.id = dal.standard_id
            JOIN student_student s ON s.id = dal.stud_id
            LEFT JOIN school_standard st ON st.id = da.standard_id
            LEFT JOIN students_parents_rel rel ON rel.student_id = s.id
            LEFT JOIN school_parent p ON p.id = rel.parent_id
            WHERE da.date = ? AND dal.is_absent = 1
            """,
            (target_date,),
        )

        enqueued = 0
        skipped = 0
        for r in records:
            sid = int(r["student_id"])
            phone = r["parent_phone"] or r["contact_mobile"]
            guardian = r["parent_name"] or "Parent / Guardian"
            gr = r["roll_no"] or r["pid"] or str(sid)
            params = {
                "guardian_name": guardian,
                "student_name": r["student_name"],
                "class_name": r["standard_name"] or "Class",
                "gr_no": gr,
                "date": target_date,
            }
            res = self.enqueue_message(
                channel="whatsapp",
                to_name=guardian,
                to_phone=phone,
                template_code="ABSENT_ALERT",
                category="attendance",
                params=params,
                student_id=sid,
                class_id=r["standard_id"],
                dedupe_date=target_date,
                created_by=user,
            )
            if res > 0:
                enqueued += 1
            else:
                skipped += 1

        return {"enqueued": enqueued, "skipped": skipped, "date": target_date}

    def generate_fee_reminders(
        self,
        min_balance: float = 1.0,
        class_id: int | None = None,
        user: str = "system",
    ) -> dict[str, int]:
        """Generate fee balance reminder messages for students with pending vouchers."""
        conditions = ["p.state = 'confirm'", "p.total_amount > 0"]
        params: list[Any] = []
        if class_id:
            conditions.append("s.standard_id = ?")
            params.append(class_id)

        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT p.id as payslip_id, p.number as voucher_no, p.total_amount, p.due_date,
                   p.balance_paisa, p.total_paisa,
                   s.id as student_id, s.student_name, s.roll_no, s.pid, s.contact_mobile, s.standard_id,
                   st.name as standard_name,
                   par.name as parent_name, par.phone as parent_phone
            FROM student_payslip p
            JOIN student_student s ON s.id = p.student_id
            LEFT JOIN school_standard st ON st.id = s.standard_id
            LEFT JOIN students_parents_rel rel ON rel.student_id = s.id
            LEFT JOIN school_parent par ON par.id = rel.parent_id
            WHERE {where_clause}
            ORDER BY p.id DESC
        """
        records = self.db.fetch_all(sql, tuple(params))
        dedupe_key = datetime.now().strftime("%Y-%m")

        enqueued = 0
        skipped = 0
        for r in records:
            balance_paisa = r["balance_paisa"] if r.get("balance_paisa") is not None else int(r["total_amount"] * 100)
            balance_rs = balance_paisa / 100.0
            if balance_rs < min_balance:
                continue

            sid = int(r["student_id"])
            phone = r["parent_phone"] or r["contact_mobile"]
            guardian = r["parent_name"] or "Parent / Guardian"
            params_dict = {
                "guardian_name": guardian,
                "student_name": r["student_name"],
                "class_name": r["standard_name"] or "Class",
                "amount": f"Rs. {balance_rs:,.2f}",
                "voucher_no": r["voucher_no"] or f"VCH-{r['payslip_id']}",
                "due_date": r["due_date"] or "Due on presentation",
            }
            res = self.enqueue_message(
                channel="whatsapp",
                to_name=guardian,
                to_phone=phone,
                template_code="FEE_REMINDER",
                category="fee_due",
                params=params_dict,
                student_id=sid,
                class_id=r["standard_id"],
                dedupe_date=f"{dedupe_key}-VCH{r['payslip_id']}",
                created_by=user,
            )
            if res > 0:
                enqueued += 1
            else:
                skipped += 1

        return {"enqueued": enqueued, "skipped": skipped}

    def generate_exam_alerts(
        self,
        exam_id: int,
        standard_id: int | None = None,
        user: str = "system",
    ) -> dict[str, int]:
        """Generate examination result notices for finalized exam results."""
        conditions = ["r.s_exam_ids = ?"]
        params: list[Any] = [exam_id]
        if standard_id:
            conditions.append("r.standard_id = ?")
            params.append(standard_id)

        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT r.student_id, r.percentage, r.result, r.rank,
                   e.name as exam_name,
                   s.student_name, s.contact_mobile, s.standard_id,
                   st.name as standard_name,
                   par.name as parent_name, par.phone as parent_phone
            FROM exam_result r
            JOIN exam_exam e ON e.id = r.s_exam_ids
            JOIN student_student s ON s.id = r.student_id
            LEFT JOIN school_standard st ON st.id = s.standard_id
            LEFT JOIN students_parents_rel rel ON rel.student_id = s.id
            LEFT JOIN school_parent par ON par.id = rel.parent_id
            WHERE {where_clause}
        """
        records = self.db.fetch_all(sql, tuple(params))
        dedupe_key = f"EXAM-{exam_id}"

        enqueued = 0
        skipped = 0
        for r in records:
            sid = int(r["student_id"])
            phone = r["parent_phone"] or r["contact_mobile"]
            guardian = r["parent_name"] or "Parent / Guardian"
            params_dict = {
                "guardian_name": guardian,
                "student_name": r["student_name"],
                "exam_name": r["exam_name"] or "Term Exam",
                "percentage": f"{float(r['percentage'] or 0):.1f}",
                "grade": r["result"] or "Pass",
                "rank": f"Rank #{r['rank']}" if r.get("rank") else "",
            }
            res = self.enqueue_message(
                channel="whatsapp",
                to_name=guardian,
                to_phone=phone,
                template_code="RESULT_READY",
                category="result",
                params=params_dict,
                student_id=sid,
                class_id=r["standard_id"],
                dedupe_date=dedupe_key,
                created_by=user,
            )
            if res > 0:
                enqueued += 1
            else:
                skipped += 1

        return {"enqueued": enqueued, "skipped": skipped}

    def generate_circular(
        self,
        *,
        title: str,
        body_text: str,
        target_type: str = "all",
        standard_id: int | None = None,
        user: str = "system",
    ) -> dict[str, int]:
        """Broadcast a general circular or PTM announcement to active students."""
        conditions = ["s.active = 1"]
        params: list[Any] = []
        if target_type == "class" and standard_id:
            conditions.append("s.standard_id = ?")
            params.append(standard_id)

        where_clause = " AND ".join(conditions)
        sql = f"""
            SELECT s.id as student_id, s.student_name, s.contact_mobile, s.standard_id,
                   st.name as standard_name,
                   par.name as parent_name, par.phone as parent_phone
            FROM student_student s
            LEFT JOIN school_standard st ON st.id = s.standard_id
            LEFT JOIN students_parents_rel rel ON rel.student_id = s.id
            LEFT JOIN school_parent par ON par.id = rel.parent_id
            WHERE {where_clause}
        """
        students = self.db.fetch_all(sql, tuple(params))
        dedupe_key = f"CIRCULAR-{self._today()}-{abs(hash(title)) % 10000}"

        enqueued = 0
        for r in students:
            sid = int(r["student_id"])
            phone = r["parent_phone"] or r["contact_mobile"]
            guardian = r["parent_name"] or "Parent / Guardian"
            params_dict = {
                "guardian_name": guardian,
                "student_name": r["student_name"],
                "class_name": r["standard_name"] or "School",
                "notice_title": title.strip(),
                "notice_body": body_text.strip(),
            }
            self.enqueue_message(
                channel="whatsapp",
                to_name=guardian,
                to_phone=phone,
                template_code="PTM_CIRCULAR",
                category="circular",
                subject=title.strip(),
                params=params_dict,
                student_id=sid,
                class_id=r["standard_id"],
                dedupe_date=dedupe_key,
                created_by=user,
            )
            enqueued += 1

        return {"enqueued": enqueued, "target": target_type}

