"""Module 5 (`timetable`): Regular & Exam Timetables, Overlap & Collision Detection."""

from __future__ import annotations

from datetime import date
from typing import Any

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, ValidationError, parse_date


class TimetableService:
    """Implements 100% of `timetable` and `exam` timetable extensions and collision rules."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_timetable(
        self,
        *,
        name: str,
        standard_id: int,
        year_id: int,
        timetable_type: str = "regular",
        class_room_id: int | None = None,
        lines: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        with self.db.connection() as conn:
            dup = conn.execute(
                """
                SELECT id FROM time_table
                WHERE year_id = ? AND standard_id = ? AND timetable_type = ?
                LIMIT 1
                """,
                (year_id, standard_id, timetable_type),
            ).fetchone()
            if dup:
                raise ValidationError(
                    "A record with the same Year and Standard already exists."
                )

            if timetable_type == "exam" and lines is not None and len(lines) == 0:
                raise ValidationError("Please Enter Exam Timetable!")

            cur = conn.execute(
                """
                INSERT INTO time_table (name, standard_id, year_id, timetable_type, class_room_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name.strip(), standard_id, year_id, timetable_type, class_room_id),
            )
            tt_id = cur.lastrowid

        if lines:
            for ln in lines:
                self.add_timetable_line(
                    table_id=tt_id,
                    subject_id=ln["subject_id"],
                    teacher_id=ln.get("teacher_id"),
                    start_time=float(ln["start_time"]),
                    end_time=float(ln["end_time"]),
                    week_day=ln.get("week_day"),
                    exm_date=ln.get("exm_date"),
                    class_room_id=ln.get("class_room_id", class_room_id),
                )
        return self.get_timetable(tt_id)

    def add_timetable_line(
        self,
        *,
        table_id: int,
        subject_id: int,
        start_time: float,
        end_time: float,
        teacher_id: int | None = None,
        week_day: str | None = None,
        exm_date: str | date | None = None,
        class_room_id: int | None = None,
        allow_past_for_seed: bool = False,
    ) -> dict[str, Any]:
        tt = self.db.fetch_one("SELECT * FROM time_table WHERE id = ?", (table_id,))
        if not tt:
            raise NotFoundError(f"Timetable {table_id} not found")

        s_time = float(start_time)
        e_time = float(end_time)
        if s_time > 24 or e_time > 24:
            raise ValidationError("Start and End Time should be less than 24 hours!")
        if s_time >= e_time:
            raise ValidationError("Start time should be less than end time!")

        sub = self.db.fetch_one("SELECT * FROM subject_subject WHERE id = ?", (subject_id,))
        if not sub:
            raise ValidationError("Subject not found!")

        tt_type = tt["timetable_type"]
        day_of_week = None
        exm_dt_iso = None

        if tt_type == "regular":
            if not teacher_id:
                raise ValidationError("Teacher is required for regular timetable!")
            teacher = self.db.fetch_one("SELECT * FROM school_teacher WHERE id = ?", (teacher_id,))
            if not teacher:
                raise ValidationError("Teacher not found!")
            # Check teacher subject assignment (`check_teacher`)
            assigned = self.db.fetch_one(
                "SELECT 1 FROM subject_teacher_rel WHERE subject_id = ? AND teacher_id = ?",
                (subject_id, teacher_id),
            )
            if not assigned:
                raise ValidationError(
                    f"The subject {sub['name']} is not assigned to teacher {teacher['name']}."
                )

            w_day = (week_day or "monday").lower().strip()
            with self.db.connection() as conn:
                # 1. Intra-table 4-way time overlap check (`check_time_overlap`)
                overlaps = conn.execute(
                    """
                    SELECT id FROM time_table_line
                    WHERE table_id = ? AND week_day = ?
                      AND (
                        (start_time <= ? AND end_time > ?)
                        OR (start_time < ? AND end_time >= ?)
                        OR (start_time <= ? AND end_time >= ?)
                        OR (start_time >= ? AND end_time <= ?)
                      )
                    """,
                    (
                        table_id,
                        w_day,
                        s_time,
                        s_time,
                        e_time,
                        e_time,
                        s_time,
                        e_time,
                        s_time,
                        e_time,
                    ),
                ).fetchone()
                if overlaps:
                    raise ValidationError("Time should not overlap!")

                # 2. Inter-table teacher & classroom collision (`check_teacher_room`)
                other_teacher_clash = conn.execute(
                    """
                    SELECT ttl.id FROM time_table_line ttl
                    JOIN time_table t ON t.id = ttl.table_id
                    WHERE t.id != ? AND t.timetable_type = 'regular'
                      AND ttl.teacher_id = ? AND ttl.week_day = ? AND ttl.start_time = ?
                    LIMIT 1
                    """,
                    (table_id, teacher_id, w_day, s_time),
                ).fetchone()
                if other_teacher_clash:
                    raise ValidationError("There is a lecture of Lecturer at same time!")

                if class_room_id:
                    other_room_clash = conn.execute(
                        """
                        SELECT ttl.id FROM time_table_line ttl
                        JOIN time_table t ON t.id = ttl.table_id
                        WHERE t.id != ? AND t.timetable_type = 'regular'
                          AND ttl.class_room_id = ? AND ttl.start_time = ?
                        LIMIT 1
                        """,
                        (table_id, class_room_id, s_time),
                    ).fetchone()
                    if other_room_clash:
                        raise ValidationError("The room is occupied.")

                cur = conn.execute(
                    """
                    INSERT INTO time_table_line
                    (table_id, teacher_id, subject_id, start_time, end_time, week_day, class_room_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (table_id, teacher_id, subject_id, s_time, e_time, w_day, class_room_id),
                )
                line_id = cur.lastrowid

        else:
            # Exam timetable rules (`ExtendedTimeTable` & `ExtendedTimeTableLine`)
            if not teacher_id:
                raise ValidationError("PLease Enter Supervisior!")
            ex_dt = parse_date(exm_date)
            if not ex_dt:
                raise ValidationError("Exam Date is required!")
            if not allow_past_for_seed and ex_dt < date.today():
                raise ValidationError(
                    "Invalid Date Error! Exam Date should be greater than today!"
                )
            day_of_week = ex_dt.strftime("%A")
            exm_dt_iso = ex_dt.isoformat()
            w_day = day_of_week.lower()

            with self.db.connection() as conn:
                # Duplicate subject in same exam timetable
                dup_sub = conn.execute(
                    "SELECT id FROM time_table_line WHERE table_id = ? AND subject_id = ?",
                    (table_id, subject_id),
                ).fetchone()
                if dup_sub:
                    raise ValidationError(f"{sub['name']} Subject Exam Already Taken")

                # Same date and start_time in same exam timetable
                same_slot = conn.execute(
                    "SELECT id FROM time_table_line WHERE table_id = ? AND exm_date = ? AND start_time = ?",
                    (table_id, exm_dt_iso, s_time),
                ).fetchone()
                if same_slot:
                    raise ValidationError("There is already Exam at same Date and Time!")

                # Room clash across other exam timetables
                if class_room_id:
                    other_exam_room = conn.execute(
                        """
                        SELECT ttl.id FROM time_table_line ttl
                        JOIN time_table t ON t.id = ttl.table_id
                        WHERE t.id != ? AND t.timetable_type = 'exam'
                          AND ttl.class_room_id = ? AND ttl.exm_date = ? AND ttl.start_time = ?
                        LIMIT 1
                        """,
                        (table_id, class_room_id, exm_dt_iso, s_time),
                    ).fetchone()
                    if other_exam_room:
                        raise ValidationError("The room is occupied!")

                cur = conn.execute(
                    """
                    INSERT INTO time_table_line
                    (table_id, teacher_id, subject_id, start_time, end_time, week_day, exm_date, day_of_week, class_room_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        table_id,
                        teacher_id,
                        subject_id,
                        s_time,
                        e_time,
                        w_day,
                        exm_dt_iso,
                        day_of_week,
                        class_room_id,
                    ),
                )
                line_id = cur.lastrowid

        return self.db.fetch_one("SELECT * FROM time_table_line WHERE id = ?", (line_id,))  # type: ignore[return-value]

    def get_timetable(self, table_id: int) -> dict[str, Any]:
        tt = self.db.fetch_one(
            """
            SELECT tt.*, ss.name AS class_name, ay.name AS year_name, cr.name AS room_name
            FROM time_table tt
            JOIN school_standard ss ON ss.id = tt.standard_id
            JOIN academic_year ay ON ay.id = tt.year_id
            LEFT JOIN class_room cr ON cr.id = tt.class_room_id
            WHERE tt.id = ?
            """,
            (table_id,),
        )
        if not tt:
            raise NotFoundError(f"Timetable {table_id} not found")
        lines = self.db.fetch_all(
            """
            SELECT ttl.*, sub.name AS subject_name, t.name AS teacher_name, cr.name AS room_name
            FROM time_table_line ttl
            JOIN subject_subject sub ON sub.id = ttl.subject_id
            LEFT JOIN school_teacher t ON t.id = ttl.teacher_id
            LEFT JOIN class_room cr ON cr.id = ttl.class_room_id
            WHERE ttl.table_id = ?
            ORDER BY COALESCE(ttl.exm_date, ''), ttl.start_time ASC
            """,
            (table_id,),
        )
        tt["timetable_ids"] = lines
        return tt

    def delete_timetable(self, table_id: int) -> None:
        """Prevent deleting exam schedule if linked to a running exam (`ExtendedTimeTable.unlink`)."""
        with self.db.connection() as conn:
            running = conn.execute(
                """
                SELECT e.id FROM exam_schedule_line esl
                JOIN exam_exam e ON e.id = esl.exam_id
                WHERE esl.timetable_id = ? AND e.state = 'running'
                LIMIT 1
                """,
                (table_id,),
            ).fetchone()
            if running:
                raise ValidationError(
                    "You cannot delete schedule of exam which is in running!"
                )
            conn.execute("DELETE FROM time_table WHERE id = ?", (table_id,))

    def list_timetables(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT id FROM time_table ORDER BY id DESC")
        return [self.get_timetable(r["id"]) for r in rows]

