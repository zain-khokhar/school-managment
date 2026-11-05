"""Module 2 (`school_fees`): Fee Structures, Fee Registers, Payslips, Invoices, and Payments."""

from __future__ import annotations

from datetime import date
from typing import Any

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, UserError, ValidationError, parse_date


class FeesService:
    """Implements 100% of `school_fees` models, constraints, and payment workflows."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_fees_structure(
        self,
        *,
        name: str,
        code: str,
        lines: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        with self.db.connection() as conn:
            dup = conn.execute(
                "SELECT id FROM student_fees_structure WHERE code = ?",
                (code.strip(),),
            ).fetchone()
            if dup:
                raise ValidationError("The code of the Fees Structure must be unique !")
            cur = conn.execute(
                "INSERT INTO student_fees_structure (name, code) VALUES (?, ?)",
                (name.strip(), code.strip()),
            )
            struct_id = cur.lastrowid

        if lines:
            for ln in lines:
                self.create_fees_structure_line(
                    structure_id=struct_id,
                    name=ln["name"],
                    code=ln["code"],
                    duration_type=ln.get("type", "month"),
                    amount=float(ln["amount"]),
                )
        return self.get_fees_structure(struct_id)

    def create_fees_structure_line(
        self,
        *,
        structure_id: int,
        name: str,
        code: str,
        duration_type: str = "month",
        amount: float = 0.0,
    ) -> dict[str, Any]:
        with self.db.connection() as conn:
            seq = self.db.next_by_code("student.fees.structure.line", conn=conn)
            cur = conn.execute(
                """
                INSERT INTO student_fees_structure_line
                (structure_id, name, code, type, amount, sequence)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (structure_id, name.strip(), code.strip(), duration_type, float(amount), seq),
            )
            line_id = cur.lastrowid
        return self.db.fetch_one(
            "SELECT * FROM student_fees_structure_line WHERE id = ?",
            (line_id,),
        )  # type: ignore[return-value]

    def add_structure_line_month_range(
        self,
        *,
        slipline1_id: int,
        academic_year_id: int,
        from_month_id: int,
        to_month_id: int,
        sequence: int = 1,
    ) -> dict[str, Any]:
        """Validate non-overlapping month ranges on fee structure line (`check_month`)."""
        from_m = self.db.fetch_one("SELECT * FROM academic_month WHERE id = ?", (from_month_id,))
        to_m = self.db.fetch_one("SELECT * FROM academic_month WHERE id = ?", (to_month_id,))
        if not from_m or not to_m:
            raise ValidationError("From Month and To Month are required!")

        f_start = parse_date(from_m["date_start"])
        t_stop = parse_date(to_m["date_stop"])
        if f_start and t_stop and t_stop < f_start:
            raise ValidationError("To Month should be greater than From Month!")

        with self.db.connection() as conn:
            existing = conn.execute(
                """
                SELECT spl.*, fm.date_start AS f_start, tm.date_stop AS t_stop
                FROM student_payslip_line_line spl
                JOIN academic_month fm ON fm.id = spl.from_month_id
                JOIN academic_month tm ON tm.id = spl.to_month_id
                WHERE spl.slipline1_id = ? AND spl.academic_year_id = ?
                """,
                (slipline1_id, academic_year_id),
            ).fetchall()
            for old in existing:
                old_s = parse_date(old["f_start"])
                old_e = parse_date(old["t_stop"])
                if old_s and old_e and f_start and t_stop and (
                    old_s <= f_start <= old_e or old_s <= t_stop <= old_e
                ):
                    raise ValidationError("Error! You cannot define overlapping months!")
            cur = conn.execute(
                """
                INSERT INTO student_payslip_line_line
                (slipline1_id, sequence, academic_year_id, from_month_id, to_month_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (slipline1_id, sequence, academic_year_id, from_month_id, to_month_id),
            )
            rid = cur.lastrowid
        return self.db.fetch_one(
            "SELECT * FROM student_payslip_line_line WHERE id = ?",
            (rid,),
        )  # type: ignore[return-value]

    def get_fees_structure(self, structure_id: int) -> dict[str, Any]:
        row = self.db.fetch_one(
            "SELECT * FROM student_fees_structure WHERE id = ?",
            (structure_id,),
        )
        if not row:
            raise NotFoundError(f"Fees structure {structure_id} not found")
        lines = self.db.fetch_all(
            "SELECT * FROM student_fees_structure_line WHERE structure_id = ? ORDER BY id",
            (structure_id,),
        )
        row["line_ids"] = lines
        row["total_amount"] = sum(float(l["amount"]) for l in lines)
        return row

    # -------------------------------------------------------------------------
    # Fee Register (Batch Payslips)
    # -------------------------------------------------------------------------
    def create_fees_register(
        self,
        *,
        name: str,
        standard_id: int,
        fees_structure_id: int | None = None,
        register_date: str | date | None = None,
        journal_name: str = "Tuition Fees Journal",
    ) -> dict[str, Any]:
        dt = parse_date(register_date) or date.today()
        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO student_fees_register
                (name, date, number, total_amount, state, journal_name, fees_structure_id, standard_id)
                VALUES (?, ?, 'New', 0.0, 'draft', ?, ?, ?)
                """,
                (name.strip(), dt.isoformat(), journal_name, fees_structure_id, standard_id),
            )
            reg_id = cur.lastrowid
        return self.get_fees_register(reg_id)

    def get_fees_register(self, register_id: int) -> dict[str, Any]:
        reg = self.db.fetch_one(
            """
            SELECT r.*, fs.name AS structure_name, s.name AS standard_name
            FROM student_fees_register r
            LEFT JOIN student_fees_structure fs ON fs.id = r.fees_structure_id
            LEFT JOIN standard_standard s ON s.id = r.standard_id
            WHERE r.id = ?
            """,
            (register_id,),
        )
        if not reg:
            raise NotFoundError(f"Fees register {register_id} not found")
        slips = self.db.fetch_all(
            """
            SELECT p.*, st.student_name
            FROM student_payslip p
            JOIN student_student st ON st.id = p.student_id
            WHERE p.register_id = ?
            ORDER BY p.id
            """,
            (register_id,),
        )
        reg["line_ids"] = slips
        reg["total_amount"] = sum(float(s["total"]) for s in slips)
        return reg

    def fees_register_confirm(self, register_id: int) -> dict[str, Any]:
        """Confirm fee register and generate student payslips for all `done` students in standard."""
        reg = self.get_fees_register(register_id)
        if not reg["journal_name"]:
            raise ValidationError("Kindly, Select Account Journal!")
        if not reg["fees_structure_id"]:
            raise ValidationError("Kindly, Select Fees Structure!")

        school_stds = self.db.fetch_all(
            "SELECT id FROM school_standard WHERE standard_id = ?",
            (reg["standard_id"],),
        )
        ss_ids = [s["id"] for s in school_stds]
        if not ss_ids:
            students = []
        else:
            placeholders = ",".join("?" for _ in ss_ids)
            students = self.db.fetch_all(
                f"SELECT * FROM student_student WHERE standard_id IN ({placeholders}) AND state = 'done'",
                tuple(ss_ids),
            )

        for stu in students:
            existing = self.db.fetch_one(
                "SELECT id FROM student_payslip WHERE student_id = ? AND date = ?",
                (stu["id"], reg["date"]),
            )
            if existing:
                raise ValidationError(
                    f"There exists a Fees record for: {stu['student_name']} for same date.!"
                )
            self.create_payslip(
                student_id=stu["id"],
                name=reg["name"],
                fees_structure_id=reg["fees_structure_id"],
                register_id=register_id,
                slip_date=reg["date"],
                journal_name=reg["journal_name"],
            )

        with self.db.connection() as conn:
            num = self.db.next_by_code("student.fees.register", conn=conn)
            total = conn.execute(
                "SELECT COALESCE(SUM(total), 0.0) AS t FROM student_payslip WHERE register_id = ?",
                (register_id,),
            ).fetchone()["t"]
            conn.execute(
                "UPDATE student_fees_register SET number = ?, total_amount = ?, state = 'confirm' WHERE id = ?",
                (num, float(total), register_id),
            )
        return self.get_fees_register(register_id)

    # -------------------------------------------------------------------------
    # Student Payslip & Payment Lifecycle
    # -------------------------------------------------------------------------
    def create_payslip(
        self,
        *,
        student_id: int,
        name: str = "Tuition Fee Slip",
        fees_structure_id: int | None = None,
        register_id: int | None = None,
        slip_date: str | date | None = None,
        journal_name: str = "Tuition Fees Journal",
    ) -> dict[str, Any]:
        stu = self.db.fetch_one("SELECT * FROM student_student WHERE id = ?", (student_id,))
        if not stu:
            raise NotFoundError(f"Student {student_id} not found")
        dt = parse_date(slip_date) or date.today()

        with self.db.connection() as conn:
            dup = conn.execute(
                "SELECT id FROM student_payslip WHERE student_id = ? AND date = ? AND state = 'draft'",
                (student_id, dt.isoformat()),
            ).fetchone()
            if dup:
                raise ValidationError("The code of the Fees Structure must be unique !")

            cur = conn.execute(
                """
                INSERT INTO student_payslip
                (fees_structure_id, standard_id, division_id, medium_id, register_id,
                 name, number, student_id, date, total, paid_amount, due_amount, journal_name, state)
                VALUES (?, ?, ?, ?, ?, ?, '/', ?, ?, 0.0, 0.0, 0.0, ?, 'draft')
                """,
                (
                    fees_structure_id,
                    stu["standard_id"],
                    stu["division_id"],
                    stu["medium_id"],
                    register_id,
                    name.strip(),
                    student_id,
                    dt.isoformat(),
                    journal_name,
                ),
            )
            slip_id = cur.lastrowid
        return self.get_payslip(slip_id)

    def get_payslip(self, slip_id: int) -> dict[str, Any]:
        row = self.db.fetch_one(
            """
            SELECT p.*, st.student_name, st.pid, ss.name AS class_name,
                   fs.name AS structure_name
            FROM student_payslip p
            JOIN student_student st ON st.id = p.student_id
            LEFT JOIN school_standard ss ON ss.id = p.standard_id
            LEFT JOIN student_fees_structure fs ON fs.id = p.fees_structure_id
            WHERE p.id = ?
            """,
            (slip_id,),
        )
        if not row:
            raise NotFoundError(f"Payslip {slip_id} not found")
        row["line_ids"] = self.db.fetch_all(
            "SELECT * FROM student_payslip_line WHERE slip_id = ? ORDER BY id",
            (slip_id,),
        )
        return row

    def payslip_confirm(self, slip_id: int) -> dict[str, Any]:
        """Confirm payslip: clone lines from fee structure and compute total and due_amount."""
        slip = self.get_payslip(slip_id)
        if not slip["journal_name"]:
            raise ValidationError("Kindly, Select Account Journal!")
        if not slip["fees_structure_id"]:
            raise ValidationError("Kindly, Select Fees Structure!")

        struct = self.get_fees_structure(slip["fees_structure_id"])
        with self.db.connection() as conn:
            conn.execute("DELETE FROM student_payslip_line WHERE slip_id = ?", (slip_id,))
            total = 0.0
            for ln in struct["line_ids"]:
                amt = float(ln["amount"])
                total += amt
                conn.execute(
                    """
                    INSERT INTO student_payslip_line (slip_id, name, code, type, amount)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (slip_id, ln["name"], ln["code"], ln["type"], amt),
                )
            conn.execute(
                """
                UPDATE student_payslip
                SET total = ?, due_amount = ?, state = 'confirm'
                WHERE id = ?
                """,
                (total, total, slip_id),
            )
            if slip["register_id"]:
                reg_tot = conn.execute(
                    "SELECT COALESCE(SUM(total), 0.0) AS t FROM student_payslip WHERE register_id = ?",
                    (slip["register_id"],),
                ).fetchone()["t"]
                conn.execute(
                    "UPDATE student_fees_register SET total_amount = ? WHERE id = ?",
                    (float(reg_tot), slip["register_id"]),
                )
        return self.get_payslip(slip_id)

    def student_pay_fees(self, slip_id: int, payment_amount: float | None = None) -> dict[str, Any]:
        """Generate invoice / process payment on student payslip (`pending` or `paid`)."""
        slip = self.get_payslip(slip_id)
        if slip["state"] == "draft":
            slip = self.payslip_confirm(slip_id)

        with self.db.connection() as conn:
            num = slip["number"]
            if not num or num == "/":
                num = self.db.next_by_code("student.payslip", conn=conn)

            if payment_amount is None:
                # Just generates invoice -> moves state to 'pending'
                conn.execute(
                    "UPDATE student_payslip SET number = ?, state = 'pending' WHERE id = ?",
                    (num, slip_id),
                )
            else:
                amt = float(payment_amount)
                if amt <= 0:
                    raise ValidationError("Payment amount must be greater than zero!")
                new_paid = float(slip["paid_amount"]) + amt
                total = float(slip["total"])
                new_due = max(0.0, total - new_paid)
                new_state = "paid" if new_due == 0.0 else "pending"
                conn.execute(
                    """
                    UPDATE student_payslip
                    SET number = ?, paid_amount = ?, due_amount = ?, state = ?, payment_date = ?
                    WHERE id = ?
                    """,
                    (num, new_paid, new_due, new_state, date.today().isoformat(), slip_id),
                )
        return self.get_payslip(slip_id)

    def mark_student_fees_received(self, student_id: int) -> dict[str, Any]:
        """Mirrors `StudentFees.fees_received()` in `school_fees`."""
        paid_slip = self.db.fetch_one(
            "SELECT id FROM student_payslip WHERE student_id = ? AND state = 'paid' LIMIT 1",
            (student_id,),
        )
        if not paid_slip:
            raise UserError("Fees Payment are due")
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE student_student SET state = 'fees_received' WHERE id = ?",
                (student_id,),
            )
        return self.db.fetch_one("SELECT * FROM student_student WHERE id = ?", (student_id,))  # type: ignore[return-value]

    def delete_payslip(self, slip_id: int) -> None:
        slip = self.get_payslip(slip_id)
        if slip["state"] != "draft":
            raise ValidationError("You can delete record in unconfirm state only!")
        with self.db.connection() as conn:
            conn.execute("DELETE FROM student_payslip WHERE id = ?", (slip_id,))

    def list_fee_structures(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT id FROM student_fees_structure ORDER BY id")
        return [self.get_fees_structure(r["id"]) for r in rows]

    def list_fees_registers(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT id FROM student_fees_register ORDER BY id DESC")
        return [self.get_fees_register(r["id"]) for r in rows]

    def list_payslips(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT id FROM student_payslip ORDER BY id DESC")
        return [self.get_payslip(r["id"]) for r in rows]

