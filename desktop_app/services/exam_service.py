"""Exam module service preserving all Odoo constraints, grade calculations, re-evaluation, and wizards."""

from __future__ import annotations

from datetime import date
import sqlite3
from typing import Any

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, ValidationError, parse_date


class ExamService:
    """Service layer for the `exam` module."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # -------------------------------------------------------------------------
    # Main Exams (exam.exam)
    # -------------------------------------------------------------------------
    def create_exam(
        self,
        name: str,
        start_date: str,
        end_date: str,
        grade_system_id: int | None = None,
        academic_year_id: int | None = None,
        standard_ids: list[int] | None = None,
        schedule_lines: list[dict[str, Any]] | None = None,
        exam_code: str | None = None,
        allow_past_dates: bool = False,
    ) -> int:
        """Create an exam with date and schedule line validations."""
        if not name or not name.strip():
            raise ValidationError("Exam Name is required!")

        d_start = parse_date(start_date, "Start Date")
        d_end = parse_date(end_date, "End Date")

        if not allow_past_dates and d_start < date.today():
            raise ValidationError("Start Date Must be Greater Than Today's Date!")
        if d_end < d_start:
            raise ValidationError("End date Must be Greater Than Start Date!")

        with self.db.connection() as conn:
            self._validate_schedule_dates(conn, d_start, d_end, schedule_lines or [])
            code = exam_code.strip() if exam_code else self.db.next_by_code("exam.exam", conn)
            cur = conn.execute(
                """
                INSERT INTO exam_exam
                    (name, exam_code, start_date, end_date, state, grade_system_id, academic_year_id, active)
                VALUES (?, ?, ?, ?, 'draft', ?, ?, 1)
                """,
                (
                    name.strip(),
                    code,
                    d_start.isoformat(),
                    d_end.isoformat(),
                    grade_system_id,
                    academic_year_id,
                ),
            )
            exam_id = int(cur.lastrowid)

            for std_id in standard_ids or []:
                conn.execute(
                    "INSERT OR IGNORE INTO exam_standard_rel (exam_id, standard_id) VALUES (?, ?)",
                    (exam_id, std_id),
                )

            for line in schedule_lines or []:
                conn.execute(
                    """
                    INSERT INTO exam_schedule_line (exam_id, standard_id, timetable_id)
                    VALUES (?, ?, ?)
                    """,
                    (exam_id, line["standard_id"], line["timetable_id"]),
                )
            return exam_id

    def _validate_schedule_dates(
        self,
        conn: sqlite3.Connection,
        d_start: date,
        d_end: date,
        schedule_lines: list[dict[str, Any]],
    ) -> None:
        """Verify all exam timetable line dates lie within [start_date, end_date]."""
        for line in schedule_lines:
            tt_id = line["timetable_id"]
            tt_lines = conn.execute(
                "SELECT exm_date FROM time_table_line WHERE table_id = ? AND exm_date IS NOT NULL",
                (tt_id,),
            ).fetchall()
            for tl in tt_lines:
                exm_dt = parse_date(tl["exm_date"], "Exam Timetable Date")
                if exm_dt < d_start or exm_dt > d_end:
                    raise ValidationError(
                        "Error! Examitanion Date Must be in between Start date and End date !"
                    )

    def add_exam_schedule(self, exam_id: int, standard_id: int, timetable_id: int) -> int:
        """Add a schedule line to an existing exam and validate timetable dates."""
        with self.db.connection() as conn:
            exam = conn.execute(
                "SELECT start_date, end_date FROM exam_exam WHERE id = ?",
                (exam_id,),
            ).fetchone()
            if not exam:
                raise NotFoundError(f"Exam {exam_id} not found.")
            d_start = parse_date(exam["start_date"], "Start Date")
            d_end = parse_date(exam["end_date"], "End Date")
            self._validate_schedule_dates(
                conn,
                d_start,
                d_end,
                [{"standard_id": standard_id, "timetable_id": timetable_id}],
            )
            cur = conn.execute(
                """
                INSERT INTO exam_schedule_line (exam_id, standard_id, timetable_id)
                VALUES (?, ?, ?)
                """,
                (exam_id, standard_id, timetable_id),
            )
            std = conn.execute(
                "SELECT standard_id FROM school_standard WHERE id = ?",
                (standard_id,),
            ).fetchone()
            if std:
                conn.execute(
                    "INSERT OR IGNORE INTO exam_standard_rel (exam_id, standard_id) VALUES (?, ?)",
                    (exam_id, std["standard_id"]),
                )
            return int(cur.lastrowid)

    def set_exam_draft(self, exam_id: int) -> None:
        with self.db.connection() as conn:
            conn.execute("UPDATE exam_exam SET state = 'draft' WHERE id = ?", (exam_id,))

    def set_exam_running(self, exam_id: int) -> None:
        """Set exam state to running after checking standards and schedules exist."""
        with self.db.connection() as conn:
            exam = conn.execute("SELECT id FROM exam_exam WHERE id = ?", (exam_id,)).fetchone()
            if not exam:
                raise NotFoundError(f"Exam {exam_id} not found.")
            std_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM exam_standard_rel WHERE exam_id = ?",
                (exam_id,),
            ).fetchone()["cnt"]
            sched_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM exam_schedule_line WHERE exam_id = ?",
                (exam_id,),
            ).fetchone()["cnt"]
            if std_count == 0 and sched_count == 0:
                raise ValidationError("Please Select Standard!")
            if sched_count == 0:
                raise ValidationError("Please Add Exam Schedule!")
            conn.execute("UPDATE exam_exam SET state = 'running' WHERE id = ?", (exam_id,))

    def set_exam_finished(self, exam_id: int) -> None:
        with self.db.connection() as conn:
            conn.execute("UPDATE exam_exam SET state = 'finished' WHERE id = ?", (exam_id,))

    def set_exam_cancelled(self, exam_id: int) -> None:
        with self.db.connection() as conn:
            conn.execute("UPDATE exam_exam SET state = 'cancelled' WHERE id = ?", (exam_id,))

    def set_exam_active(self, exam_id: int, active: bool) -> None:
        """Check `_check_result` constraint: only Marksheet Done Exam can be deactivated."""
        with self.db.connection() as conn:
            if not active:
                not_done = conn.execute(
                    """
                    SELECT COUNT(*) AS cnt
                    FROM exam_result
                    WHERE s_exam_ids = ? AND state != 'done'
                    """,
                    (exam_id,),
                ).fetchone()["cnt"]
                if not_done > 0:
                    raise ValidationError("Only Marksheet Done Exam Should be Unactive!")
            conn.execute(
                "UPDATE exam_exam SET active = ? WHERE id = ?",
                (1 if active else 0, exam_id),
            )

    def generate_result(self, exam_id: int) -> list[int]:
        """Generate `exam.result` and `exam.subject` lines for all scheduled classes & students."""
        created_ids: list[int] = []
        with self.db.connection() as conn:
            exam = conn.execute(
                "SELECT * FROM exam_exam WHERE id = ?",
                (exam_id,),
            ).fetchone()
            if not exam:
                raise NotFoundError(f"Exam {exam_id} not found.")

            schedules = conn.execute(
                """
                SELECT esl.*, ss.school_id
                FROM exam_schedule_line esl
                JOIN school_standard ss ON ss.id = esl.standard_id
                WHERE esl.exam_id = ?
                """,
                (exam_id,),
            ).fetchall()

            for sched in schedules:
                query = """
                    SELECT id, roll_no, standard_id
                    FROM student_student
                    WHERE standard_id = ?
                      AND state = 'done'
                      AND school_id = ?
                """
                params: list[Any] = [sched["standard_id"], sched["school_id"]]
                if exam["academic_year_id"]:
                    query += " AND year_id = ?"
                    params.append(exam["academic_year_id"])

                students = conn.execute(query, tuple(params)).fetchall()

                tt_subjects = conn.execute(
                    """
                    SELECT DISTINCT ttl.subject_id, sub.minimum_marks, sub.maximum_marks
                    FROM time_table_line ttl
                    JOIN subject_subject sub ON sub.id = ttl.subject_id
                    WHERE ttl.table_id = ?
                    """,
                    (sched["timetable_id"],),
                ).fetchall()

                for stu in students:
                    existing = conn.execute(
                        """
                        SELECT id FROM exam_result
                        WHERE s_exam_ids = ? AND student_id = ? AND standard_id = ?
                        """,
                        (exam_id, stu["id"], stu["standard_id"]),
                    ).fetchone()
                    if existing:
                        created_ids.append(int(existing["id"]))
                        continue

                    cur = conn.execute(
                        """
                        INSERT INTO exam_result
                            (s_exam_ids, student_id, roll_no, standard_id, grade_system_id,
                             total, percentage, result, grade, state, active)
                        VALUES (?, ?, ?, ?, ?, 0.0, 0.0, 'Pass', '', 'draft', 1)
                        """,
                        (
                            exam_id,
                            stu["id"],
                            stu["roll_no"],
                            stu["standard_id"],
                            exam["grade_system_id"],
                        ),
                    )
                    res_id = int(cur.lastrowid)
                    for sub in tt_subjects:
                        conn.execute(
                            """
                            INSERT INTO exam_subject
                                (exam_id, subject_id, obtain_marks, minimum_marks, maximum_marks, marks_reeval)
                            VALUES (?, ?, 0.0, ?, ?, 0.0)
                            """,
                            (
                                res_id,
                                sub["subject_id"],
                                float(sub["minimum_marks"] or 35.0),
                                float(sub["maximum_marks"] or 100.0),
                            ),
                        )
                    self._recompute_result_conn(conn, res_id)
                    created_ids.append(res_id)
        return created_ids

    # -------------------------------------------------------------------------
    # Exam Results & Subject Marks (exam.result & exam.subject)
    # -------------------------------------------------------------------------
    def create_exam_result(
        self,
        s_exam_ids: int,
        student_id: int,
        grade_system_id: int | None = None,
        subject_lines: list[dict[str, Any]] | None = None,
    ) -> int:
        """Create an exam result record and its subject lines."""
        with self.db.connection() as conn:
            stu = conn.execute(
                "SELECT id, roll_no, standard_id FROM student_student WHERE id = ?",
                (student_id,),
            ).fetchone()
            if not stu:
                raise NotFoundError(f"Student {student_id} not found.")
            exam = conn.execute(
                "SELECT id, grade_system_id FROM exam_exam WHERE id = ?",
                (s_exam_ids,),
            ).fetchone()
            if not exam:
                raise NotFoundError(f"Exam {s_exam_ids} not found.")

            eff_grade_sys = grade_system_id or exam["grade_system_id"]
            cur = conn.execute(
                """
                INSERT INTO exam_result
                    (s_exam_ids, student_id, roll_no, standard_id, grade_system_id,
                     total, percentage, result, grade, state, active)
                VALUES (?, ?, ?, ?, ?, 0.0, 0.0, 'Pass', '', 'draft', 1)
                """,
                (s_exam_ids, student_id, stu["roll_no"], stu["standard_id"], eff_grade_sys),
            )
            res_id = int(cur.lastrowid)

            for line in subject_lines or []:
                self._insert_or_update_subject_conn(
                    conn,
                    exam_result_id=res_id,
                    subject_id=line["subject_id"],
                    obtain_marks=float(line.get("obtain_marks", 0.0)),
                    minimum_marks=float(line.get("minimum_marks", 35.0)),
                    maximum_marks=float(line.get("maximum_marks", 100.0)),
                    marks_reeval=float(line.get("marks_reeval", 0.0)),
                )
            self._recompute_result_conn(conn, res_id)
            return res_id

    def _insert_or_update_subject_conn(
        self,
        conn: sqlite3.Connection,
        exam_result_id: int,
        subject_id: int,
        obtain_marks: float,
        minimum_marks: float,
        maximum_marks: float,
        marks_reeval: float = 0.0,
        subject_line_id: int | None = None,
    ) -> int:
        """Validate `_validate_marks` and insert/update `exam_subject`."""
        if obtain_marks > maximum_marks:
            raise ValidationError("The obtained marks should not extend maximum marks!")
        if minimum_marks > maximum_marks:
            raise ValidationError("The minimum marks should not extend maximum marks!")
        if marks_reeval > maximum_marks:
            raise ValidationError("The revaluation marks should not extend maximum marks!")

        if subject_line_id is not None:
            conn.execute(
                """
                UPDATE exam_subject
                SET subject_id = ?, obtain_marks = ?, minimum_marks = ?,
                    maximum_marks = ?, marks_reeval = ?
                WHERE id = ?
                """,
                (
                    subject_id,
                    obtain_marks,
                    minimum_marks,
                    maximum_marks,
                    marks_reeval,
                    subject_line_id,
                ),
            )
            return subject_line_id

        cur = conn.execute(
            """
            INSERT INTO exam_subject
                (exam_id, subject_id, obtain_marks, minimum_marks, maximum_marks, marks_reeval)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (exam_result_id, subject_id, obtain_marks, minimum_marks, maximum_marks, marks_reeval),
        )
        return int(cur.lastrowid)

    def update_exam_subject_marks(
        self,
        exam_subject_id: int,
        obtain_marks: float | None = None,
        marks_reeval: float | None = None,
        minimum_marks: float | None = None,
        maximum_marks: float | None = None,
    ) -> dict[str, Any]:
        """Update subject marks, validate constraints, and recompute result."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM exam_subject WHERE id = ?",
                (exam_subject_id,),
            ).fetchone()
            if not row:
                raise NotFoundError(f"Exam subject line {exam_subject_id} not found.")

            new_obtain = float(obtain_marks if obtain_marks is not None else row["obtain_marks"])
            new_reeval = float(marks_reeval if marks_reeval is not None else row["marks_reeval"])
            new_min = float(minimum_marks if minimum_marks is not None else row["minimum_marks"])
            new_max = float(maximum_marks if maximum_marks is not None else row["maximum_marks"])

            self._insert_or_update_subject_conn(
                conn,
                exam_result_id=row["exam_id"],
                subject_id=row["subject_id"],
                obtain_marks=new_obtain,
                minimum_marks=new_min,
                maximum_marks=new_max,
                marks_reeval=new_reeval,
                subject_line_id=exam_subject_id,
            )
            self._recompute_result_conn(conn, row["exam_id"])
            res = conn.execute(
                "SELECT * FROM exam_result WHERE id = ?",
                (row["exam_id"],),
            ).fetchone()
            return dict(res)

    def _recompute_result_conn(self, conn: sqlite3.Connection, result_id: int) -> None:
        """Mirror `_compute_total`, `_compute_per`, `_compute_result`, and `_compute_grade`."""
        res = conn.execute("SELECT * FROM exam_result WHERE id = ?", (result_id,)).fetchone()
        if not res:
            return

        grade_lines: list[sqlite3.Row] = []
        if res["grade_system_id"]:
            grade_lines = conn.execute(
                "SELECT * FROM grade_line WHERE grade_id = ? ORDER BY from_mark DESC",
                (res["grade_system_id"],),
            ).fetchall()

        subjects = conn.execute(
            "SELECT * FROM exam_subject WHERE exam_id = ?",
            (result_id,),
        ).fetchall()

        use_reeval = res["state"] in ("re-evaluation", "re-evaluation_confirm")
        total_obtained = 0.0
        total_max = 0.0
        any_fail = False

        for sub in subjects:
            mark = float(sub["marks_reeval"] if use_reeval and sub["marks_reeval"] > 0 else sub["obtain_marks"])
            max_m = float(sub["maximum_marks"] or 0.0)
            min_m = float(sub["minimum_marks"] or 0.0)
            total_obtained += mark
            total_max += max_m

            matched_grade_id = None
            matched_fail = False
            if max_m > 0:
                sub_pct = (mark / max_m) * 100.0 if max_m != 100.0 else mark
            else:
                sub_pct = mark

            for gl in grade_lines:
                if float(gl["from_mark"]) <= sub_pct <= float(gl["to_mark"]):
                    matched_grade_id = gl["id"]
                    if gl["fail"]:
                        matched_fail = True
                    break

            conn.execute(
                "UPDATE exam_subject SET grade_line_id = ? WHERE id = ?",
                (matched_grade_id, sub["id"]),
            )
            if matched_fail or mark < min_m:
                any_fail = True

        percentage = round((total_obtained / total_max) * 100.0, 2) if total_max > 1.0 else 0.0
        overall_grade = ""
        for gl in grade_lines:
            if float(gl["from_mark"]) <= percentage <= float(gl["to_mark"]):
                overall_grade = gl["grade"]
                if gl["fail"]:
                    any_fail = True
                break

        result_str = "Fail" if (any_fail or not subjects) else "Pass"
        conn.execute(
            """
            UPDATE exam_result
            SET total = ?, percentage = ?, grade = ?, result = ?
            WHERE id = ?
            """,
            (round(total_obtained, 2), percentage, overall_grade, result_str, result_id),
        )

    def confirm_exam_result(self, result_id: int) -> None:
        """Confirm result (`result_confirm`) ensuring no zero max/min marks."""
        with self.db.connection() as conn:
            subjects = conn.execute(
                "SELECT minimum_marks, maximum_marks FROM exam_subject WHERE exam_id = ?",
                (result_id,),
            ).fetchall()
            for sub in subjects:
                if float(sub["maximum_marks"]) == 0 or float(sub["minimum_marks"]) == 0:
                    raise ValidationError(
                        "Subject Maximum Marks or Minimum Marks Cannot be Zero!"
                    )
            conn.execute("UPDATE exam_result SET state = 'confirm' WHERE id = ?", (result_id,))
            self._recompute_result_conn(conn, result_id)

    def result_re_evaluation(self, result_id: int) -> None:
        """Trigger re-evaluation (`result_re_evaluation`), copying `obtain_marks` to `marks_reeval`."""
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE exam_subject SET marks_reeval = obtain_marks WHERE exam_id = ?",
                (result_id,),
            )
            conn.execute(
                "UPDATE exam_result SET state = 're-evaluation' WHERE id = ?",
                (result_id,),
            )
            self._recompute_result_conn(conn, result_id)

    def re_evaluation_confirm(self, result_id: int) -> None:
        """Confirm re-evaluated marks (`re_evaluation_confirm`)."""
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE exam_result SET state = 're-evaluation_confirm' WHERE id = ?",
                (result_id,),
            )
            self._recompute_result_conn(conn, result_id)

    def set_result_done(self, result_id: int) -> None:
        """Mark exam result as `done`."""
        with self.db.connection() as conn:
            conn.execute("UPDATE exam_result SET state = 'done' WHERE id = ?", (result_id,))

    def delete_exam_result(self, result_id: int) -> None:
        """Only allow deleting `exam.result` in `draft` state."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT state FROM exam_result WHERE id = ?",
                (result_id,),
            ).fetchone()
            if not row:
                raise NotFoundError(f"Exam result {result_id} not found.")
            if row["state"] != "draft":
                raise ValidationError("You can delete record in unconfirm state only!")
            conn.execute("DELETE FROM exam_result WHERE id = ?", (result_id,))

    # -------------------------------------------------------------------------
    # Additional Exam & Results (additional.exam & additional.exam.result)
    # -------------------------------------------------------------------------
    def create_additional_exam(
        self,
        name: str,
        standard_id: int,
        subject_id: int,
        maximum_marks: int,
        minimum_marks: int,
        exam_date: str | None = None,
        weightage: str = "",
        addtional_exam_code: str | None = None,
    ) -> int:
        """Create additional exam with `_check_max_marks` constraint."""
        if minimum_marks >= maximum_marks:
            raise ValidationError("Minimum Marks Must Be Less Than Maximum Marks")

        with self.db.connection() as conn:
            code = (
                addtional_exam_code.strip()
                if addtional_exam_code
                else self.db.next_by_code("additional.exam", conn)
            )
            cur = conn.execute(
                """
                INSERT INTO additional_exam
                    (name, addtional_exam_code, standard_id, subject_id, exam_date,
                     maximum_marks, minimum_marks, weightage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    code,
                    standard_id,
                    subject_id,
                    exam_date or date.today().isoformat(),
                    maximum_marks,
                    minimum_marks,
                    weightage,
                ),
            )
            return int(cur.lastrowid)

    def create_additional_exam_result(
        self,
        a_exam_id: int,
        student_id: int,
        obtain_marks: float,
    ) -> int:
        """Create additional exam result with duplicate and mark checks."""
        with self.db.connection() as conn:
            a_exam = conn.execute(
                "SELECT * FROM additional_exam WHERE id = ?",
                (a_exam_id,),
            ).fetchone()
            if not a_exam:
                raise NotFoundError(f"Additional Exam {a_exam_id} not found.")
            stu = conn.execute(
                "SELECT id, roll_no, standard_id FROM student_student WHERE id = ?",
                (student_id,),
            ).fetchone()
            if not stu:
                raise NotFoundError(f"Student {student_id} not found.")

            dup = conn.execute(
                "SELECT id FROM additional_exam_result WHERE a_exam_id = ? AND student_id = ?",
                (a_exam_id, student_id),
            ).fetchone()
            if dup:
                raise ValidationError(
                    "You cannot create duplicate result for same student and exam!"
                )

            if obtain_marks > float(a_exam["maximum_marks"]):
                raise ValidationError("The obtained marks should not extend maximum marks!")

            result_str = "Pass" if obtain_marks >= float(a_exam["minimum_marks"]) else "Fail"
            cur = conn.execute(
                """
                INSERT INTO additional_exam_result
                    (a_exam_id, student_id, roll_no, standard_id, obtain_marks, result, active)
                VALUES (?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    a_exam_id,
                    student_id,
                    stu["roll_no"],
                    stu["standard_id"],
                    obtain_marks,
                    result_str,
                ),
            )
            return int(cur.lastrowid)

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------
    def list_exams(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT e.*, ay.name AS academic_year_name, gm.name AS grade_system_name,
                   (SELECT COUNT(*) FROM exam_result er WHERE er.s_exam_ids = e.id) AS result_count
            FROM exam_exam e
            LEFT JOIN academic_year ay ON ay.id = e.academic_year_id
            LEFT JOIN grade_master gm ON gm.id = e.grade_system_id
            WHERE e.active = 1
            ORDER BY e.start_date DESC, e.id DESC
            """
        )

    def list_exam_results(self, exam_id: int | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT er.*, e.name AS exam_name, e.exam_code,
                   s.student_name, s.pid, ss.name AS standard_name,
                   gm.name AS grade_system_name
            FROM exam_result er
            JOIN exam_exam e ON e.id = er.s_exam_ids
            JOIN student_student s ON s.id = er.student_id
            LEFT JOIN school_standard ss ON ss.id = er.standard_id
            LEFT JOIN grade_master gm ON gm.id = er.grade_system_id
            WHERE er.active = 1
        """
        params: list[Any] = []
        if exam_id is not None:
            query += " AND er.s_exam_ids = ?"
            params.append(exam_id)
        query += " ORDER BY er.id DESC"
        results = self.db.fetch_all(query, tuple(params))
        for res in results:
            res["subjects"] = self.db.fetch_all(
                """
                SELECT es.*, sub.name AS subject_name, sub.code AS subject_code,
                       gl.grade AS subject_grade
                FROM exam_subject es
                JOIN subject_subject sub ON sub.id = es.subject_id
                LEFT JOIN grade_line gl ON gl.id = es.grade_line_id
                WHERE es.exam_id = ?
                ORDER BY es.id
                """,
                (res["id"],),
            )
        return results

