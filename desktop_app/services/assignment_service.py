"""Module 4 (`assignment`): Teacher Homework Distribution, Student Submissions, and Reject History."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, ValidationError, parse_date


class AssignmentService:
    """Implements 100% of `assignment` module models, constraints, and workflows."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_file_format(self, *, name: str) -> dict[str, Any]:
        with self.db.connection() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO file_format (name) VALUES (?)",
                (name.strip().lstrip("."),),
            )
            row = conn.execute(
                "SELECT * FROM file_format WHERE name = ?",
                (name.strip().lstrip("."),),
            ).fetchone()
        return dict(row)

    def create_teacher_assignment(
        self,
        *,
        name: str,
        subject_id: int,
        standard_id: int,
        teacher_id: int,
        assign_date: str | date,
        due_date: str | date,
        type_submission: str = "hardcopy",
        file_format_id: int | None = None,
        attached_homework: str = "",
        attach_files: str = "",
        allow_past_for_seed: bool = False,
    ) -> dict[str, Any]:
        a_dt = parse_date(assign_date)
        d_dt = parse_date(due_date)
        if not a_dt or not d_dt:
            raise ValidationError("Assign date and Due date are required!")
        if not allow_past_for_seed and a_dt < date.today():
            raise ValidationError("Assign date should be Greater than or equal to current date")
        if d_dt < a_dt:
            raise ValidationError("Due date of homework should be greater than assign date")

        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO school_teacher_assignment
                (name, subject_id, standard_id, teacher_id, assign_date, due_date,
                 attached_homework, attach_files, type_submission, file_format_id, state)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')
                """,
                (
                    name.strip(),
                    subject_id,
                    standard_id,
                    teacher_id,
                    a_dt.isoformat(),
                    d_dt.isoformat(),
                    attached_homework,
                    attach_files,
                    type_submission,
                    file_format_id,
                ),
            )
            ta_id = cur.lastrowid
        return self.get_teacher_assignment(ta_id)

    def get_teacher_assignment(self, ta_id: int) -> dict[str, Any]:
        row = self.db.fetch_one(
            """
            SELECT ta.*, sub.name AS subject_name, ss.name AS class_name,
                   t.name AS teacher_name, ff.name AS file_format_name
            FROM school_teacher_assignment ta
            JOIN subject_subject sub ON sub.id = ta.subject_id
            JOIN school_standard ss ON ss.id = ta.standard_id
            JOIN school_teacher t ON t.id = ta.teacher_id
            LEFT JOIN file_format ff ON ff.id = ta.file_format_id
            WHERE ta.id = ?
            """,
            (ta_id,),
        )
        if not row:
            raise NotFoundError(f"Teacher assignment {ta_id} not found")
        row["student_assign_ids"] = self.db.fetch_all(
            """
            SELECT sa.*, st.student_name
            FROM school_student_assignment sa
            JOIN student_student st ON st.id = sa.student_id
            WHERE sa.teacher_assignment_id = ?
            ORDER BY sa.stud_roll_no ASC, sa.id ASC
            """,
            (ta_id,),
        )
        return row

    def active_teacher_assignment(self, ta_id: int) -> dict[str, Any]:
        """Activate teacher assignment and create student assignments for all `done` students."""
        ta = self.get_teacher_assignment(ta_id)
        if not ta["attached_homework"]:
            raise ValidationError("Please attach the homework!")

        students = self.db.fetch_all(
            "SELECT * FROM student_student WHERE standard_id = ? AND state = 'done'",
            (ta["standard_id"],),
        )
        fmt_name = ta.get("file_format_name") or ""
        with self.db.connection() as conn:
            for std in students:
                conn.execute(
                    """
                    INSERT INTO school_student_assignment
                    (name, subject_id, standard_id, teacher_id, assign_date, due_date,
                     student_id, stud_roll_no, teacher_assignment_id, submission_type,
                     attachfile_format, attached_homework, state, active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', 1)
                    """,
                    (
                        ta["name"],
                        ta["subject_id"],
                        ta["standard_id"],
                        ta["teacher_id"],
                        ta["assign_date"],
                        ta["due_date"],
                        std["id"],
                        std["roll_no"],
                        ta_id,
                        ta["type_submission"],
                        fmt_name,
                        ta["attached_homework"],
                    ),
                )
            conn.execute(
                "UPDATE school_teacher_assignment SET state = 'active' WHERE id = ?",
                (ta_id,),
            )
        return self.get_teacher_assignment(ta_id)

    def done_teacher_assignments(self, ta_id: int) -> dict[str, Any]:
        """Confirm teacher assignment only if ALL student assignments are `done`."""
        ta = self.get_teacher_assignment(ta_id)
        states = [s["state"] for s in ta["student_assign_ids"]]
        if not states or not all(st == "done" for st in states):
            raise ValidationError("You cannot confirm the assignment")
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE school_teacher_assignment SET state = 'done' WHERE id = ?",
                (ta_id,),
            )
        return self.get_teacher_assignment(ta_id)

    def delete_teacher_assignment(self, ta_id: int) -> None:
        ta = self.get_teacher_assignment(ta_id)
        if ta["state"] != "draft":
            raise ValidationError("Confirmed assignment can not be deleted!")
        with self.db.connection() as conn:
            conn.execute("DELETE FROM school_teacher_assignment WHERE id = ?", (ta_id,))

    # -------------------------------------------------------------------------
    # Student Assignment (`school.student.assignment`)
    # -------------------------------------------------------------------------
    def get_student_assignment(self, sa_id: int) -> dict[str, Any]:
        row = self.db.fetch_one(
            """
            SELECT sa.*, st.student_name, sub.name AS subject_name,
                   ss.name AS class_name, t.name AS teacher_name
            FROM school_student_assignment sa
            JOIN student_student st ON st.id = sa.student_id
            JOIN subject_subject sub ON sub.id = sa.subject_id
            JOIN school_standard ss ON ss.id = sa.standard_id
            JOIN school_teacher t ON t.id = sa.teacher_id
            WHERE sa.id = ?
            """,
            (sa_id,),
        )
        if not row:
            raise NotFoundError(f"Student assignment {sa_id} not found")
        row["rejection_history"] = self.db.fetch_all(
            "SELECT * FROM assignment_reject_history WHERE assignment_id = ? ORDER BY id DESC",
            (sa_id,),
        )
        return row

    def submit_and_done_student_assignment(
        self,
        sa_id: int,
        *,
        submit_assign: str = "",
        file_name: str = "",
    ) -> dict[str, Any]:
        """Validate file format (`check_file_format`) and mark student assignment `done`."""
        sa = self.get_student_assignment(sa_id)
        new_submit = submit_assign or sa.get("submit_assign") or ""
        new_fname = file_name or sa.get("file_name") or ""
        req_format = (sa.get("attachfile_format") or "").strip()

        if new_fname and req_format:
            parts = new_fname.split(".")
            if len(parts) != 2:
                raise ValidationError(f"Kindly attach file with format: {req_format}!")
            ext = parts[1]
            if not (ext in req_format or req_format in ext):
                raise ValidationError(f"Kindly attach file with format: {req_format}!")

        if sa["submission_type"] == "softcopy" and not new_submit:
            raise ValidationError(
                "You have not attached the homework! Please attach the homework!"
            )

        with self.db.connection() as conn:
            conn.execute(
                """
                UPDATE school_student_assignment
                SET submit_assign = ?, file_name = ?, state = 'done'
                WHERE id = ?
                """,
                (new_submit, new_fname, sa_id),
            )
        return self.get_student_assignment(sa_id)

    def reject_student_assignment(self, sa_id: int, *, reason: str) -> dict[str, Any]:
        """Execute `reject.reason` wizard: set state to `reject` and log history."""
        self.get_student_assignment(sa_id)
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE school_student_assignment SET state = 'reject' WHERE id = ?",
                (sa_id,),
            )
            conn.execute(
                """
                INSERT INTO assignment_reject_history (assignment_id, name, rejected_at)
                VALUES (?, ?, ?)
                """,
                (sa_id, reason.strip(), datetime.now().isoformat(timespec="seconds")),
            )
        return self.get_student_assignment(sa_id)

    def reassign_student_assignment(self, sa_id: int) -> dict[str, Any]:
        """Move rejected assignment back to `active`."""
        self.get_student_assignment(sa_id)
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE school_student_assignment SET state = 'active' WHERE id = ?",
                (sa_id,),
            )
        return self.get_student_assignment(sa_id)

    def delete_student_assignment(self, sa_id: int) -> None:
        sa = self.get_student_assignment(sa_id)
        if sa["state"] != "draft":
            raise ValidationError("Confirmed assignment can not be deleted!")
        with self.db.connection() as conn:
            conn.execute("DELETE FROM school_student_assignment WHERE id = ?", (sa_id,))

    def list_file_formats(self) -> list[dict[str, Any]]:
        return self.db.fetch_all("SELECT * FROM file_format ORDER BY name")

    def list_teacher_assignments(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT id FROM school_teacher_assignment ORDER BY id DESC")
        return [self.get_teacher_assignment(r["id"]) for r in rows]

    def list_student_assignments(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all(
            "SELECT id FROM school_student_assignment WHERE active = 1 ORDER BY id DESC"
        )
        return [self.get_student_assignment(r["id"]) for r in rows]

