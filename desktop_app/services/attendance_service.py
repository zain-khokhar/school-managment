"""Module 3 (`school_attendance`): Leave Requests, Daily Roll Call, 31-Day Sheets, and XLSX Export."""

from __future__ import annotations

from datetime import date
import io
from typing import Any

from num2words import num2words
import xlsxwriter

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, ValidationError, parse_date

DAY_COLUMNS: list[str] = [num2words(d).replace("-", "") for d in range(1, 32)]


class AttendanceService:
    """Implements 100% of `school_attendance` models, validations, `num2words` matrix, and XLSX report."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # -------------------------------------------------------------------------
    # Student Leave Request (`studentleave.request`)
    # -------------------------------------------------------------------------
    def create_leave_request(
        self,
        *,
        name: str,
        student_id: int,
        start_date: str | date,
        end_date: str | date,
        reason: str = "",
        allow_past_for_seed: bool = False,
    ) -> dict[str, Any]:
        s_dt = parse_date(start_date)
        e_dt = parse_date(end_date)
        if not s_dt or not e_dt:
            raise ValidationError("Start date and End date are required!")
        if s_dt > e_dt:
            raise ValidationError("Start date should be less than end date!")
        if not allow_past_for_seed and s_dt < date.today():
            raise ValidationError(
                "Your leave request start date should be greater than current date!"
            )

        stu = self.db.fetch_one("SELECT * FROM student_student WHERE id = ?", (student_id,))
        if not stu or not stu["standard_id"]:
            raise ValidationError("Student must be assigned to a class!")
        ss = self.db.fetch_one("SELECT * FROM school_standard WHERE id = ?", (stu["standard_id"],))
        teacher_id = ss["user_id"] if ss else None

        days = 1 if s_dt == e_dt else (e_dt - s_dt).days + 1

        with self.db.connection() as conn:
            dup = conn.execute(
                """
                SELECT id FROM studentleave_request
                WHERE student_id = ? AND start_date = ? AND end_date = ?
                LIMIT 1
                """,
                (student_id, s_dt.isoformat(), e_dt.isoformat()),
            ).fetchone()
            if dup:
                raise ValidationError(
                    "You cannot take leave on same date for the same student!"
                )
            cur = conn.execute(
                """
                INSERT INTO studentleave_request
                (name, student_id, roll_no, standard_id, teacher_id, start_date, end_date, days, reason, state)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')
                """,
                (
                    name.strip(),
                    student_id,
                    stu["roll_no"],
                    stu["standard_id"],
                    teacher_id,
                    s_dt.isoformat(),
                    e_dt.isoformat(),
                    days,
                    reason,
                ),
            )
            leave_id = cur.lastrowid
        return self.get_leave_request(leave_id)

    def get_leave_request(self, leave_id: int) -> dict[str, Any]:
        row = self.db.fetch_one(
            """
            SELECT lr.*, st.student_name, ss.name AS class_name, t.name AS teacher_name
            FROM studentleave_request lr
            JOIN student_student st ON st.id = lr.student_id
            LEFT JOIN school_standard ss ON ss.id = lr.standard_id
            LEFT JOIN school_teacher t ON t.id = lr.teacher_id
            WHERE lr.id = ?
            """,
            (leave_id,),
        )
        if not row:
            raise NotFoundError(f"Leave request {leave_id} not found")
        return row

    def leave_toapprove(self, leave_id: int) -> dict[str, Any]:
        lv = self.get_leave_request(leave_id)
        if lv["state"] == "draft":
            with self.db.connection() as conn:
                conn.execute("UPDATE studentleave_request SET state = 'toapprove' WHERE id = ?", (leave_id,))
        return self.get_leave_request(leave_id)

    def leave_approve(self, leave_id: int) -> dict[str, Any]:
        lv = self.get_leave_request(leave_id)
        if lv["state"] in ("draft", "toapprove"):
            with self.db.connection() as conn:
                conn.execute("UPDATE studentleave_request SET state = 'approve' WHERE id = ?", (leave_id,))
        return self.get_leave_request(leave_id)

    def leave_reject(self, leave_id: int) -> dict[str, Any]:
        with self.db.connection() as conn:
            conn.execute("UPDATE studentleave_request SET state = 'reject' WHERE id = ?", (leave_id,))
        return self.get_leave_request(leave_id)

    def delete_leave_request(self, leave_id: int) -> None:
        lv = self.get_leave_request(leave_id)
        if lv["state"] == "approve":
            raise ValidationError("Approve leave can not be deleted!")
        if lv["state"] == "reject":
            raise ValidationError("Reject leave can not be deleted!")
        with self.db.connection() as conn:
            conn.execute("DELETE FROM studentleave_request WHERE id = ?", (leave_id,))

    # -------------------------------------------------------------------------
    # Daily Attendance (`daily.attendance` & `daily.attendance.line`)
    # -------------------------------------------------------------------------
    def create_daily_attendance(
        self,
        *,
        standard_id: int,
        user_id: int | None = None,
        att_date: str | date | None = None,
        subject_id: int | None = None,
    ) -> dict[str, Any]:
        dt = parse_date(att_date) or date.today()
        if dt > date.today():
            raise ValidationError("Date should be less than or equal to current date!")

        with self.db.connection() as conn:
            dup = conn.execute(
                """
                SELECT id FROM daily_attendance
                WHERE standard_id = ? AND COALESCE(user_id, 0) = COALESCE(?, 0) AND date = ?
                LIMIT 1
                """,
                (standard_id, user_id, dt.isoformat()),
            ).fetchone()
            if dup:
                raise ValidationError("Attendance should be unique!")

            cur = conn.execute(
                """
                INSERT INTO daily_attendance
                (date, standard_id, user_id, state, total_student, total_presence, total_absent, is_generate, subject_id)
                VALUES (?, ?, ?, 'draft', 0, 0, 0, 0, ?)
                """,
                (dt.isoformat(), standard_id, user_id, subject_id),
            )
            att_id = cur.lastrowid

        self.get_students_for_attendance(att_id)
        return self.get_daily_attendance(att_id)

    def get_students_for_attendance(self, att_id: int) -> dict[str, Any]:
        """Populate daily attendance lines; auto-mark approved leave students as absent."""
        att = self.db.fetch_one("SELECT * FROM daily_attendance WHERE id = ?", (att_id,))
        if not att:
            raise NotFoundError(f"Daily attendance {att_id} not found")

        students = self.db.fetch_all(
            """
            SELECT * FROM student_student
            WHERE standard_id = ? AND state = 'done'
            ORDER BY roll_no ASC, id ASC
            """,
            (att["standard_id"],),
        )
        if not students:
            raise ValidationError("No Students are found for selected criteria!")

        with self.db.connection() as conn:
            conn.execute("DELETE FROM daily_attendance_line WHERE standard_id = ?", (att_id,))
            for stud in students:
                leave = conn.execute(
                    """
                    SELECT id FROM studentleave_request
                    WHERE state = 'approve'
                      AND student_id = ?
                      AND standard_id = ?
                      AND start_date <= ?
                      AND end_date >= ?
                    LIMIT 1
                    """,
                    (stud["id"], att["standard_id"], att["date"], att["date"]),
                ).fetchone()
                is_abs = 1 if leave else 0
                is_pres = 0 if leave else 1
                conn.execute(
                    """
                    INSERT INTO daily_attendance_line
                    (standard_id, stud_id, roll_no, is_present, is_absent, present_absentcheck)
                    VALUES (?, ?, ?, ?, ?, 1)
                    """,
                    (att_id, stud["id"], stud["roll_no"], is_pres, is_abs),
                )
            conn.execute("UPDATE daily_attendance SET is_generate = 1 WHERE id = ?", (att_id,))
            self._recompute_daily_counts_conn(conn, att_id)
        return self.get_daily_attendance(att_id)

    @staticmethod
    def _recompute_daily_counts_conn(conn: Any, att_id: int) -> None:
        lines = conn.execute(
            "SELECT is_present, is_absent FROM daily_attendance_line WHERE standard_id = ?",
            (att_id,),
        ).fetchall()
        total = len(lines)
        pres = sum(1 for l in lines if l["is_present"])
        absn = sum(1 for l in lines if l["is_absent"])
        conn.execute(
            """
            UPDATE daily_attendance
            SET total_student = ?, total_presence = ?, total_absent = ?
            WHERE id = ?
            """,
            (total, pres, absn, att_id),
        )

    def action_present(self, line_id: int) -> dict[str, Any]:
        line = self.db.fetch_one("SELECT * FROM daily_attendance_line WHERE id = ?", (line_id,))
        if not line:
            raise NotFoundError(f"Attendance line {line_id} not found")
        att = self.db.fetch_one("SELECT * FROM daily_attendance WHERE id = ?", (line["standard_id"],))
        if not att or att["state"] == "validate" or not att["is_generate"]:
            raise ValidationError(
                "You cannot mark as present, While attendance is in validate state!"
            )
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE daily_attendance_line SET is_present = 1, is_absent = 0, present_absentcheck = 1 WHERE id = ?",
                (line_id,),
            )
            self._recompute_daily_counts_conn(conn, att["id"])
        return self.get_daily_attendance(att["id"])

    def action_absent(self, line_id: int) -> dict[str, Any]:
        line = self.db.fetch_one("SELECT * FROM daily_attendance_line WHERE id = ?", (line_id,))
        if not line:
            raise NotFoundError(f"Attendance line {line_id} not found")
        att = self.db.fetch_one("SELECT * FROM daily_attendance WHERE id = ?", (line["standard_id"],))
        if not att or att["state"] == "validate" or not att["is_generate"]:
            raise ValidationError(
                "You cannot mark as absent, While attendance is in validate state!"
            )
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE daily_attendance_line SET is_present = 0, is_absent = 1, present_absentcheck = 1 WHERE id = ?",
                (line_id,),
            )
            self._recompute_daily_counts_conn(conn, att["id"])
        return self.get_daily_attendance(att["id"])

    def attendance_validate(self, att_id: int) -> dict[str, Any]:
        """Validate daily attendance and sync to 31-day `attendance.sheet` using `num2words`."""
        att = self.get_daily_attendance(att_id)
        dt = parse_date(att["date"])
        if not dt:
            raise ValidationError("Invalid attendance date")
        day_col = num2words(int(dt.day)).replace("-", "")
        if day_col not in DAY_COLUMNS:
            raise ValidationError("Invalid day column")
        if day_col not in DAY_COLUMNS:
            raise ValidationError("Invalid day column")

        with self.db.connection() as conn:
            yr = conn.execute(
                "SELECT * FROM academic_year WHERE date_start <= ? AND date_stop >= ? LIMIT 1",
                (dt.isoformat(), dt.isoformat()),
            ).fetchone()
            if yr:
                mo = conn.execute(
                    """
                    SELECT * FROM academic_month
                    WHERE year_id = ? AND date_start <= ? AND date_stop >= ?
                    LIMIT 1
                    """,
                    (yr["id"], dt.isoformat(), dt.isoformat()),
                ).fetchone()
                if mo:
                    sheet = conn.execute(
                        """
                        SELECT * FROM attendance_sheet
                        WHERE standard_id = ? AND month_id = ? AND year_id = ?
                        LIMIT 1
                        """,
                        (att["standard_id"], mo["id"], yr["id"]),
                    ).fetchone()
                    if not sheet:
                        sheet_name = f"{mo['name']}-{dt.year}"
                        cur = conn.execute(
                            """
                            INSERT INTO attendance_sheet
                            (name, standard_id, month_id, year_id, user_id, attendance_type)
                            VALUES (?, ?, ?, ?, ?, 'daily')
                            """,
                            (sheet_name, att["standard_id"], mo["id"], yr["id"], att["user_id"]),
                        )
                        sheet_id = cur.lastrowid
                    else:
                        sheet_id = sheet["id"]

                    for s_line in att["student_ids"]:
                        sh_line = conn.execute(
                            """
                            SELECT id FROM attendance_sheet_line
                            WHERE standard_id = ? AND roll_no = ?
                            LIMIT 1
                            """,
                            (sheet_id, s_line["roll_no"]),
                        ).fetchone()
                        val = 0 if s_line["is_absent"] else 1
                        if not sh_line:
                            conn.execute(
                                f"""
                                INSERT INTO attendance_sheet_line (standard_id, roll_no, name, {day_col})
                                VALUES (?, ?, ?, ?)
                                """,
                                (sheet_id, s_line["roll_no"], s_line["student_name"], val),
                            )
                        else:
                            conn.execute(
                                f"UPDATE attendance_sheet_line SET {day_col} = ? WHERE id = ?",
                                (val, sh_line["id"]),
                            )

            conn.execute("UPDATE daily_attendance SET state = 'validate' WHERE id = ?", (att_id,))
        return self.get_daily_attendance(att_id)

    def attendance_draft(self, att_id: int) -> dict[str, Any]:
        """Reset validated daily attendance to draft and clear day flag on monthly sheet."""
        att = self.get_daily_attendance(att_id)
        dt = parse_date(att["date"])
        if not dt:
            raise ValidationError("Please enter todays date.")
        day_col = num2words(int(dt.day)).replace("-", "")
        if day_col not in DAY_COLUMNS:
            raise ValidationError("Invalid day column")

        with self.db.connection() as conn:
            yr = conn.execute(
                "SELECT * FROM academic_year WHERE date_start <= ? AND date_stop >= ? LIMIT 1",
                (dt.isoformat(), dt.isoformat()),
            ).fetchone()
            if yr:
                mo = conn.execute(
                    """
                    SELECT * FROM academic_month
                    WHERE year_id = ? AND date_start <= ? AND date_stop >= ?
                    LIMIT 1
                    """,
                    (yr["id"], dt.isoformat(), dt.isoformat()),
                ).fetchone()
                if mo:
                    sheets = conn.execute(
                        """
                        SELECT id FROM attendance_sheet
                        WHERE standard_id = ? AND month_id = ? AND year_id = ?
                        """,
                        (att["standard_id"], mo["id"], yr["id"]),
                    ).fetchall()
                    for sh in sheets:
                        conn.execute(
                            f"UPDATE attendance_sheet_line SET {day_col} = 0 WHERE standard_id = ?",
                            (sh["id"],),
                        )
            conn.execute("UPDATE daily_attendance SET state = 'draft' WHERE id = ?", (att_id,))
        return self.get_daily_attendance(att_id)

    def get_daily_attendance(self, att_id: int) -> dict[str, Any]:
        row = self.db.fetch_one(
            """
            SELECT da.*, ss.name AS class_name, t.name AS teacher_name
            FROM daily_attendance da
            JOIN school_standard ss ON ss.id = da.standard_id
            LEFT JOIN school_teacher t ON t.id = da.user_id
            WHERE da.id = ?
            """,
            (att_id,),
        )
        if not row:
            raise NotFoundError(f"Daily attendance {att_id} not found")
        row["student_ids"] = self.db.fetch_all(
            """
            SELECT dal.*, st.student_name, st.pid
            FROM daily_attendance_line dal
            JOIN student_student st ON st.id = dal.stud_id
            WHERE dal.standard_id = ?
            ORDER BY dal.roll_no ASC, dal.id ASC
            """,
            (att_id,),
        )
        return row

    def get_attendance_sheet(self, sheet_id: int) -> dict[str, Any]:
        sheet = self.db.fetch_one(
            """
            SELECT sh.*, ss.name AS class_name, am.name AS month_name, ay.name AS year_name
            FROM attendance_sheet sh
            JOIN school_standard ss ON ss.id = sh.standard_id
            JOIN academic_month am ON am.id = sh.month_id
            JOIN academic_year ay ON ay.id = sh.year_id
            WHERE sh.id = ?
            """,
            (sheet_id,),
        )
        if not sheet:
            raise NotFoundError(f"Attendance sheet {sheet_id} not found")
        lines = self.db.fetch_all(
            "SELECT * FROM attendance_sheet_line WHERE standard_id = ? ORDER BY roll_no ASC",
            (sheet_id,),
        )
        for ln in lines:
            present_days = sum(1 for col in DAY_COLUMNS if ln.get(col) == 1)
            ln["present_days"] = present_days
            # Exact formula from school_attendance/models/school_attendance.py: (attendance_count / 31.00) * 100
            ln["percentage"] = round((float(present_days) / 31.00) * 100.0, 2)
        sheet["attendance_ids"] = lines
        return sheet

    def export_attendance_xlsx(self, sheet_id: int | None = None) -> bytes:
        """Generate Excel (.xlsx) attendance sheet report using `xlsxwriter`."""
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        header_fmt = workbook.add_format({"bold": True, "bg_color": "#1E293B", "font_color": "#FFFFFF", "border": 1, "align": "center"})
        cell_fmt = workbook.add_format({"border": 1, "align": "center"})
        name_fmt = workbook.add_format({"border": 1, "align": "left"})
        pres_fmt = workbook.add_format({"border": 1, "align": "center", "bg_color": "#DCFCE7", "font_color": "#166534", "bold": True})
        abs_fmt = workbook.add_format({"border": 1, "align": "center", "bg_color": "#FEE2E2", "font_color": "#991B1B"})

        sheets = (
            [self.get_attendance_sheet(sheet_id)]
            if sheet_id
            else [
                self.get_attendance_sheet(s["id"])
                for s in self.db.fetch_all("SELECT id FROM attendance_sheet ORDER BY id DESC")
            ]
        )
        if not sheets:
            ws = workbook.add_worksheet("Attendance")
            ws.write(0, 0, "No Attendance Sheets Found", header_fmt)
        else:
            for idx, sh in enumerate(sheets, start=1):
                title = f"{sh['class_name']}_{sh['name']}"[:31].replace("/", "-")
                ws = workbook.add_worksheet(f"{idx}_{title}"[:31])
                ws.write(0, 0, "Roll No", header_fmt)
                ws.write(0, 1, "Student Name", header_fmt)
                ws.set_column(1, 1, 24)
                for day_num in range(1, 32):
                    ws.write(0, day_num + 1, str(day_num), header_fmt)
                    ws.set_column(day_num + 1, day_num + 1, 4)
                ws.write(0, 33, "Present", header_fmt)
                ws.write(0, 34, "Attendance (%)", header_fmt)
                ws.set_column(33, 34, 14)

                for r_idx, line in enumerate(sh["attendance_ids"], start=1):
                    ws.write(r_idx, 0, line["roll_no"], cell_fmt)
                    ws.write(r_idx, 1, line["name"], name_fmt)
                    for d_idx, col_name in enumerate(DAY_COLUMNS, start=1):
                        is_p = line.get(col_name) == 1
                        ws.write(r_idx, d_idx + 1, "P" if is_p else "A", pres_fmt if is_p else abs_fmt)
                    ws.write(r_idx, 33, line["present_days"], cell_fmt)
                    ws.write(r_idx, 34, f"{line['percentage']:.2f}%", cell_fmt)

        workbook.close()
        return output.getvalue()

    def list_daily_attendance(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT id FROM daily_attendance ORDER BY date DESC, id DESC")
        return [self.get_daily_attendance(r["id"]) for r in rows]

    def list_attendance_sheets(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT id FROM attendance_sheet ORDER BY id DESC")
        return [self.get_attendance_sheet(r["id"]) for r in rows]

    def list_leave_requests(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT id FROM studentleave_request ORDER BY id DESC")
        return [self.get_leave_request(r["id"]) for r in rows]

