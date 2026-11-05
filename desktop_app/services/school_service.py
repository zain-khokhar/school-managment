"""Module 1 (`school`): Core Academic, School, Class, Teacher, Parent, and Student Service."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from dateutil.relativedelta import relativedelta

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, UserError, ValidationError, parse_date, validate_email


class SchoolService:
    """Implements 100% of `school` module models, constraints, computations, and wizards."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # -------------------------------------------------------------------------
    # Academic Year & Academic Month
    # -------------------------------------------------------------------------
    def create_academic_year(
        self,
        *,
        sequence: int,
        name: str,
        code: str,
        date_start: str | date,
        date_stop: str | date,
        grade_id: int | None = None,
        current: bool = False,
        description: str = "",
    ) -> dict[str, Any]:
        start = parse_date(date_start)
        stop = parse_date(date_stop)
        if not start or not stop:
            raise ValidationError("Start date and End date are required!")
        if stop < start:
            raise ValidationError(
                "The start date of the academic year should be less than end date."
            )
        delta = stop - start
        if delta.days > 365 and not calendar.isleap(start.year):
            raise ValidationError("The duration of the academic year is invalid.")

        with self.db.connection() as conn:
            # Unique sequence check
            seq_exists = conn.execute(
                "SELECT id FROM academic_year WHERE sequence = ?",
                (sequence,),
            ).fetchone()
            if seq_exists:
                raise ValidationError("Sequence must be unique")

            # Single active current year check
            if current:
                curr_count = conn.execute(
                    "SELECT COUNT(*) AS cnt FROM academic_year WHERE current = 1"
                ).fetchone()["cnt"]
                if curr_count >= 1:
                    raise ValidationError("Error! You cannot set two current year active!")

            # Overlapping academic year check
            existing = conn.execute(
                "SELECT id, date_start, date_stop FROM academic_year"
            ).fetchall()
            for old in existing:
                old_s = parse_date(old["date_start"])
                old_e = parse_date(old["date_stop"])
                if old_s and old_e and (
                    old_s <= start <= old_e
                    or old_s <= stop <= old_e
                    or (start <= old_s and stop >= old_e)
                ):
                    raise ValidationError(
                        "Error! You cannot define overlapping academic years."
                    )

            cur = conn.execute(
                """
                INSERT INTO academic_year
                (sequence, name, code, date_start, date_stop, grade_id, current, description)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(sequence),
                    name.strip(),
                    code.strip(),
                    start.isoformat(),
                    stop.isoformat(),
                    grade_id,
                    1 if current else 0,
                    description,
                ),
            )
            year_id = cur.lastrowid
        return self.get_academic_year(year_id)

    def get_academic_year(self, year_id: int) -> dict[str, Any]:
        row = self.db.fetch_one("SELECT * FROM academic_year WHERE id = ?", (year_id,))
        if not row:
            raise NotFoundError(f"Academic Year {year_id} not found")
        row["display_name"] = f"[{row['code']}] {row['name']} "
        row["months"] = self.db.fetch_all(
            "SELECT * FROM academic_month WHERE year_id = ? ORDER BY date_start",
            (year_id,),
        )
        return row

    def list_academic_years(self) -> list[dict[str, Any]]:
        years = self.db.fetch_all("SELECT * FROM academic_year ORDER BY sequence")
        for y in years:
            y["display_name"] = f"[{y['code']}] {y['name']} "
        return years

    def next_year(self, sequence: int) -> int | None:
        row = self.db.fetch_one(
            "SELECT id FROM academic_year WHERE sequence > ? ORDER BY sequence ASC, id ASC LIMIT 1",
            (sequence,),
        )
        return row["id"] if row else None

    def generate_academic_months(self, year_id: int) -> list[dict[str, Any]]:
        """Generate academic months using relativedelta(months=1, days=-1) exactly as in Odoo."""
        year = self.get_academic_year(year_id)
        start_date = parse_date(year["date_start"])
        stop_date = parse_date(year["date_stop"])
        if not start_date or not stop_date:
            raise ValidationError("Invalid year dates")

        created: list[dict[str, Any]] = []
        curr = start_date
        while curr < stop_date:
            end_date = curr + relativedelta(months=1, days=-1)
            if end_date > stop_date:
                end_date = stop_date
            month_rec = self.create_academic_month(
                name=curr.strftime("%B"),
                code=curr.strftime("%m/%Y"),
                date_start=curr,
                date_stop=end_date,
                year_id=year_id,
            )
            created.append(month_rec)
            curr = curr + relativedelta(months=1)
        return created

    def create_academic_month(
        self,
        *,
        name: str,
        code: str,
        date_start: str | date,
        date_stop: str | date,
        year_id: int,
        description: str = "",
    ) -> dict[str, Any]:
        start = parse_date(date_start)
        stop = parse_date(date_stop)
        if not start or not stop:
            raise ValidationError("Start and stop dates are required for Academic Month!")
        if stop < start:
            raise ValidationError(
                "End of Period date should be greater than Start of Periods Date!"
            )
        year = self.get_academic_year(year_id)
        y_start = parse_date(year["date_start"])
        y_stop = parse_date(year["date_stop"])
        if (
            y_stop < stop
            or y_stop < start
            or y_start > start
            or y_start > stop
        ):
            raise ValidationError(
                "Some of the months periods overlap or is not in the academic year!"
            )

        with self.db.connection() as conn:
            existing = conn.execute(
                "SELECT id, date_start, date_stop FROM academic_month"
            ).fetchall()
            for old in existing:
                old_s = parse_date(old["date_start"])
                old_e = parse_date(old["date_stop"])
                if old_s and old_e and (
                    old_s <= start <= old_e or old_s <= stop <= old_e
                ):
                    raise ValidationError("Error! You cannot define overlapping months!")
            cur = conn.execute(
                """
                INSERT INTO academic_month (name, code, date_start, date_stop, year_id, description)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name.strip(), code.strip(), start.isoformat(), stop.isoformat(), year_id, description),
            )
            month_id = cur.lastrowid
        return self.db.fetch_one("SELECT * FROM academic_month WHERE id = ?", (month_id,))  # type: ignore[return-value]

    # -------------------------------------------------------------------------
    # Standards, Divisions, Mediums, Classrooms, Schools
    # -------------------------------------------------------------------------
    def create_medium(self, *, sequence: int, name: str, code: str, description: str = "") -> dict[str, Any]:
        with self.db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO standard_medium (sequence, name, code, description) VALUES (?, ?, ?, ?)",
                (sequence, name.strip(), code.strip(), description),
            )
            mid = cur.lastrowid
        return self.db.fetch_one("SELECT * FROM standard_medium WHERE id = ?", (mid,))  # type: ignore[return-value]

    def create_division(self, *, sequence: int, name: str, code: str, description: str = "") -> dict[str, Any]:
        with self.db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO standard_division (sequence, name, code, description) VALUES (?, ?, ?, ?)",
                (sequence, name.strip(), code.strip(), description),
            )
            did = cur.lastrowid
        return self.db.fetch_one("SELECT * FROM standard_division WHERE id = ?", (did,))  # type: ignore[return-value]

    def create_standard(self, *, sequence: int, name: str, code: str, description: str = "") -> dict[str, Any]:
        with self.db.connection() as conn:
            dup = conn.execute(
                "SELECT id FROM standard_standard WHERE name = ? OR sequence = ?",
                (name.strip(), sequence),
            ).fetchone()
            if dup:
                raise ValidationError("Name and Sequence must be unique")
            cur = conn.execute(
                "INSERT INTO standard_standard (sequence, name, code, description) VALUES (?, ?, ?, ?)",
                (sequence, name.strip(), code.strip(), description),
            )
            sid = cur.lastrowid
        return self.db.fetch_one("SELECT * FROM standard_standard WHERE id = ?", (sid,))  # type: ignore[return-value]

    def next_standard(self, sequence: int) -> dict[str, Any] | None:
        return self.db.fetch_one(
            "SELECT * FROM standard_standard WHERE sequence > ? ORDER BY sequence ASC, id ASC LIMIT 1",
            (sequence,),
        )

    def same_standard(self, sequence: int) -> dict[str, Any] | None:
        return self.db.fetch_one(
            "SELECT * FROM standard_standard WHERE sequence = ? ORDER BY id ASC LIMIT 1",
            (sequence,),
        )

    def create_classroom(self, *, name: str, number: str) -> dict[str, Any]:
        with self.db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO class_room (name, number) VALUES (?, ?)",
                (name.strip(), number.strip()),
            )
            cid = cur.lastrowid
        return self.db.fetch_one("SELECT * FROM class_room WHERE id = ?", (cid,))  # type: ignore[return-value]

    def create_school(
        self,
        *,
        name: str,
        code: str,
        required_age: int = 6,
        street: str = "",
        city: str = "Lahore",
        state_name: str = "Punjab",
        country_name: str = "Pakistan",
        contact_phone: str = "",
        contact_mobile: str = "",
        currency_symbol: str = "Rs.",
    ) -> dict[str, Any]:
        with self.db.connection() as conn:
            dup = conn.execute(
                "SELECT id FROM school_school WHERE code = ?",
                (code.strip(),),
            ).fetchone()
            if dup:
                raise ValidationError("School Code must be Unique")
            cur = conn.execute(
                """
                INSERT INTO school_school
                (name, code, required_age, street, city, state_name, country_name,
                 contact_phone, contact_mobile, currency_symbol)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    code.strip(),
                    int(required_age),
                    street,
                    city,
                    state_name,
                    country_name,
                    contact_phone,
                    contact_mobile,
                    currency_symbol,
                ),
            )
            sid = cur.lastrowid
        return self.db.fetch_one("SELECT * FROM school_school WHERE id = ?", (sid,))  # type: ignore[return-value]

    def create_school_standard(
        self,
        *,
        school_id: int,
        standard_id: int,
        division_id: int,
        medium_id: int,
        capacity: int,
        user_id: int | None = None,
        class_room_id: int | None = None,
        subject_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        if int(capacity) <= 0:
            raise ValidationError("Total seats should be greater than 0!")

        std = self.db.fetch_one("SELECT * FROM standard_standard WHERE id = ?", (standard_id,))
        div = self.db.fetch_one("SELECT * FROM standard_division WHERE id = ?", (division_id,))
        if not std or not div:
            raise ValidationError("Standard and Division are required!")
        combined_name = f"{std['name']}-{div['name']}"

        with self.db.connection() as conn:
            dup = conn.execute(
                """
                SELECT id FROM school_standard
                WHERE standard_id = ? AND division_id = ? AND school_id = ?
                """,
                (standard_id, division_id, school_id),
            ).fetchone()
            if dup:
                raise ValidationError("Division and class should be unique!")

            cur = conn.execute(
                """
                INSERT INTO school_standard
                (name, school_id, standard_id, division_id, medium_id, user_id,
                 capacity, total_students, remaining_seats, class_room_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    combined_name,
                    school_id,
                    standard_id,
                    division_id,
                    medium_id,
                    user_id,
                    int(capacity),
                    int(capacity),
                    class_room_id,
                ),
            )
            ss_id = cur.lastrowid
            if subject_ids:
                for sub_id in subject_ids:
                    conn.execute(
                        "INSERT OR IGNORE INTO subject_standards_rel (school_standard_id, subject_id) VALUES (?, ?)",
                        (ss_id, sub_id),
                    )
        self.recompute_school_standard(ss_id)
        return self.get_school_standard(ss_id)

    def recompute_school_standard(self, school_standard_id: int) -> dict[str, Any]:
        """Recompute total_students (done state) and remaining_seats = capacity - total_students."""
        with self.db.connection() as conn:
            ss = conn.execute(
                "SELECT * FROM school_standard WHERE id = ?",
                (school_standard_id,),
            ).fetchone()
            if not ss:
                raise NotFoundError(f"School standard {school_standard_id} not found")
            cnt = conn.execute(
                """
                SELECT COUNT(*) AS c FROM student_student
                WHERE standard_id = ? AND school_id = ? AND division_id = ?
                  AND medium_id = ? AND state = 'done'
                """,
                (ss["id"], ss["school_id"], ss["division_id"], ss["medium_id"]),
            ).fetchone()["c"]
            remaining = int(ss["capacity"]) - int(cnt)
            conn.execute(
                "UPDATE school_standard SET total_students = ?, remaining_seats = ? WHERE id = ?",
                (cnt, remaining, school_standard_id),
            )
        return self.get_school_standard(school_standard_id)

    def get_school_standard(self, school_standard_id: int) -> dict[str, Any]:
        row = self.db.fetch_one(
            """
            SELECT ss.*, s.name AS standard_name, d.name AS division_name,
                   m.name AS medium_name, sch.name AS school_name,
                   t.name AS teacher_name, cr.name AS room_name
            FROM school_standard ss
            JOIN standard_standard s ON s.id = ss.standard_id
            JOIN standard_division d ON d.id = ss.division_id
            JOIN standard_medium m ON m.id = ss.medium_id
            JOIN school_school sch ON sch.id = ss.school_id
            LEFT JOIN school_teacher t ON t.id = ss.user_id
            LEFT JOIN class_room cr ON cr.id = ss.class_room_id
            WHERE ss.id = ?
            """,
            (school_standard_id,),
        )
        if not row:
            raise NotFoundError(f"School standard {school_standard_id} not found")
        row["display_name"] = f"{row['standard_name']} [ {row['division_name']} ]"
        subjects = self.db.fetch_all(
            """
            SELECT sub.* FROM subject_subject sub
            JOIN subject_standards_rel rel ON rel.subject_id = sub.id
            WHERE rel.school_standard_id = ?
            """,
            (school_standard_id,),
        )
        row["subject_ids"] = [sub["id"] for sub in subjects]
        row["total_no_subjects"] = len(subjects)
        return row

    def delete_school_standard(self, school_standard_id: int) -> None:
        with self.db.connection() as conn:
            stu_cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM student_student WHERE standard_id = ?",
                (school_standard_id,),
            ).fetchone()["c"]
            sub_cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM subject_standards_rel WHERE school_standard_id = ?",
                (school_standard_id,),
            ).fetchone()["c"]
            syl_cnt = conn.execute(
                "SELECT COUNT(*) AS c FROM subject_syllabus WHERE standard_id = ?",
                (school_standard_id,),
            ).fetchone()["c"]
            if stu_cnt > 0 or sub_cnt > 0 or syl_cnt > 0:
                raise ValidationError(
                    "You cannot delete as it has reference with student, subject or syllabus!"
                )
            conn.execute("DELETE FROM school_standard WHERE id = ?", (school_standard_id,))

    # -------------------------------------------------------------------------
    # Subjects & Grading System
    # -------------------------------------------------------------------------
    def create_subject(
        self,
        *,
        name: str,
        code: str,
        maximum_marks: int = 100,
        minimum_marks: int = 35,
        weightage: int = 1,
        standard_id: int | None = None,
        is_practical: bool = False,
        is_elective_subject: bool = False,
        teacher_ids: list[int] | None = None,
        school_standard_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        if int(minimum_marks) <= 0:
            raise ValidationError("The value of minimum marks must be greater than zero")
        if int(minimum_marks) >= int(maximum_marks):
            raise ValidationError("Configure Maximum marks greater than minimum marks!")

        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO subject_subject
                (name, code, maximum_marks, minimum_marks, weightage, standard_id, is_practical, is_elective_subject)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    code.strip(),
                    int(maximum_marks),
                    int(minimum_marks),
                    int(weightage),
                    standard_id,
                    1 if is_practical else 0,
                    1 if is_elective_subject else 0,
                ),
            )
            sub_id = cur.lastrowid
            if teacher_ids:
                for tid in teacher_ids:
                    conn.execute(
                        "INSERT OR IGNORE INTO subject_teacher_rel (subject_id, teacher_id) VALUES (?, ?)",
                        (sub_id, tid),
                    )
            if school_standard_ids:
                for ssid in school_standard_ids:
                    conn.execute(
                        "INSERT OR IGNORE INTO subject_standards_rel (school_standard_id, subject_id) VALUES (?, ?)",
                        (ssid, sub_id),
                    )
        return self.get_subject(sub_id)

    def get_subject(self, subject_id: int) -> dict[str, Any]:
        sub = self.db.fetch_one("SELECT * FROM subject_subject WHERE id = ?", (subject_id,))
        if not sub:
            raise NotFoundError(f"Subject {subject_id} not found")
        teachers = self.db.fetch_all(
            "SELECT teacher_id FROM subject_teacher_rel WHERE subject_id = ?",
            (subject_id,),
        )
        sub["teacher_ids"] = [t["teacher_id"] for t in teachers]
        return sub

    def create_grade_master(
        self,
        *,
        name: str,
        lines: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        with self.db.connection() as conn:
            cur = conn.execute("INSERT INTO grade_master (name) VALUES (?)", (name.strip(),))
            gid = cur.lastrowid
        if lines:
            for ln in lines:
                self.create_grade_line(
                    grade_id=gid,
                    from_mark=ln["from_mark"],
                    to_mark=ln["to_mark"],
                    grade=ln["grade"],
                    fail=bool(ln.get("fail", False)),
                    sequence=int(ln.get("sequence", 1)),
                )
        return self.get_grade_master(gid)

    def create_grade_line(
        self,
        *,
        grade_id: int,
        from_mark: float,
        to_mark: float,
        grade: str,
        fail: bool = False,
        sequence: int = 1,
    ) -> dict[str, Any]:
        if float(to_mark) < float(from_mark):
            raise ValidationError("To Marks should be greater than From Marks!")

        with self.db.connection() as conn:
            existing = conn.execute(
                "SELECT from_mark, to_mark FROM grade_line WHERE grade_id = ?",
                (grade_id,),
            ).fetchall()
            for old in existing:
                if (
                    old["from_mark"] <= float(from_mark) <= old["to_mark"]
                    or old["from_mark"] <= float(to_mark) <= old["to_mark"]
                ):
                    raise ValidationError("Error! You cannot define overlapping Marks!")
            cur = conn.execute(
                """
                INSERT INTO grade_line (grade_id, from_mark, to_mark, grade, sequence, fail, name)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (grade_id, float(from_mark), float(to_mark), grade.strip(), sequence, 1 if fail else 0, grade.strip()),
            )
            lid = cur.lastrowid
        return self.db.fetch_one("SELECT * FROM grade_line WHERE id = ?", (lid,))  # type: ignore[return-value]

    def get_grade_master(self, grade_id: int) -> dict[str, Any]:
        gm = self.db.fetch_one("SELECT * FROM grade_master WHERE id = ?", (grade_id,))
        if not gm:
            raise NotFoundError(f"Grade master {grade_id} not found")
        gm["grade_ids"] = self.db.fetch_all(
            "SELECT * FROM grade_line WHERE grade_id = ? ORDER BY sequence, from_mark DESC",
            (grade_id,),
        )
        return gm

    # -------------------------------------------------------------------------
    # Teachers & Parents
    # -------------------------------------------------------------------------
    def create_teacher(
        self,
        *,
        name: str,
        work_email: str = "",
        phone_numbers: str = "",
        birthday: str | date | None = None,
        department: str = "Academic",
        standard_id: int | None = None,
        school_id: int | None = None,
        subject_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        bday = parse_date(birthday)
        if bday and bday > date.today():
            raise ValidationError("Birthday cannot be greater than the current date")

        if standard_id and not school_id:
            ss = self.db.fetch_one("SELECT school_id FROM school_standard WHERE id = ?", (standard_id,))
            if ss:
                school_id = ss["school_id"]

        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO school_teacher
                (name, work_email, phone_numbers, birthday, department, standard_id, school_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    work_email.strip(),
                    phone_numbers.strip(),
                    bday.isoformat() if bday else None,
                    department,
                    standard_id,
                    school_id,
                ),
            )
            tid = cur.lastrowid
            if subject_ids:
                for sid in subject_ids:
                    conn.execute(
                        "INSERT OR IGNORE INTO subject_teacher_rel (subject_id, teacher_id) VALUES (?, ?)",
                        (sid, tid),
                    )
        return self.get_teacher(tid)

    def get_teacher(self, teacher_id: int) -> dict[str, Any]:
        row = self.db.fetch_one("SELECT * FROM school_teacher WHERE id = ?", (teacher_id,))
        if not row:
            raise NotFoundError(f"Teacher {teacher_id} not found")
        subs = self.db.fetch_all(
            "SELECT subject_id FROM subject_teacher_rel WHERE teacher_id = ?",
            (teacher_id,),
        )
        row["subject_ids"] = [s["subject_id"] for s in subs]
        return row

    def create_parent(
        self,
        *,
        name: str,
        email: str = "",
        phone: str = "",
        relation_name: str = "Guardian",
    ) -> dict[str, Any]:
        validate_email(email)
        with self.db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO school_parent (name, email, phone, relation_name) VALUES (?, ?, ?, ?)",
                (name.strip(), email.strip(), phone.strip(), relation_name),
            )
            pid = cur.lastrowid
        return self.db.fetch_one("SELECT * FROM school_parent WHERE id = ?", (pid,))  # type: ignore[return-value]

    # -------------------------------------------------------------------------
    # Students & Admission / Alumni / Terminate / Promotion Workflows
    # -------------------------------------------------------------------------
    @staticmethod
    def compute_age(dob: date, today: date | None = None) -> int:
        ref = today or date.today()
        return ref.year - dob.year - ((ref.month, ref.day) < (dob.month, dob.day))

    def create_student(
        self,
        *,
        student_name: str,
        middle: str = "M",
        last: str = "L",
        date_of_birth: str | date,
        school_id: int,
        standard_id: int | None = None,
        year_id: int | None = None,
        gender: str = "male",
        email: str = "",
        contact_phone: str = "",
        contact_mobile: str = "",
        admission_date: str | date | None = None,
        leave_date: str | date | None = None,
        blood_group: str = "O+",
        parent_ids: list[int] | None = None,
        pid: str = "New",
    ) -> dict[str, Any]:
        validate_email(email)
        dob = parse_date(date_of_birth)
        if not dob:
            raise ValidationError("BirthDate is required!")

        school = self.db.fetch_one("SELECT * FROM school_school WHERE id = ?", (school_id,))
        if not school:
            raise ValidationError("School not found!")
        if not school["required_age"] or int(school["required_age"]) <= 0:
            raise ValidationError("Please set a default age for student enrollment in the school.")

        min_date = dob + relativedelta(years=int(school["required_age"]))
        if min_date > date.today():
            raise ValidationError(
                f"Age of student should be greater than {school['required_age']} years!"
            )

        adm_date = parse_date(admission_date) or date.today()
        lv_date = parse_date(leave_date)
        if lv_date and adm_date > lv_date:
            raise ValidationError("The leave date should be greater than the start date")

        with self.db.connection() as conn:
            if year_id is None:
                curr_yr = conn.execute(
                    "SELECT id FROM academic_year WHERE current = 1 LIMIT 1"
                ).fetchone()
                if not curr_yr:
                    raise ValidationError(
                        "There is no current Academic Year defined! Please contact Administator!"
                    )
                year_id = curr_yr["id"]

            division_id = None
            medium_id = None
            if standard_id:
                ss = conn.execute(
                    "SELECT division_id, medium_id FROM school_standard WHERE id = ?",
                    (standard_id,),
                ).fetchone()
                if ss:
                    division_id = ss["division_id"]
                    medium_id = ss["medium_id"]

            actual_pid = pid
            if not actual_pid or actual_pid == "New":
                actual_pid = self.db.next_by_code("student.student", conn=conn)

            age = self.compute_age(dob)
            cur = conn.execute(
                """
                INSERT INTO student_student
                (pid, student_name, middle, last, email, contact_phone, contact_mobile,
                 year_id, school_id, standard_id, division_id, medium_id, admission_date,
                 leave_date, gender, date_of_birth, age, blood_group, state, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', 1)
                """,
                (
                    actual_pid,
                    student_name.strip(),
                    middle.strip(),
                    last.strip(),
                    email.strip(),
                    contact_phone.strip(),
                    contact_mobile.strip(),
                    year_id,
                    school_id,
                    standard_id,
                    division_id,
                    medium_id,
                    adm_date.isoformat(),
                    lv_date.isoformat() if lv_date else None,
                    gender,
                    dob.isoformat(),
                    age,
                    blood_group,
                ),
            )
            stu_id = cur.lastrowid
            if parent_ids:
                for p_id in parent_ids:
                    conn.execute(
                        "INSERT OR IGNORE INTO students_parents_rel (student_id, parent_id) VALUES (?, ?)",
                        (stu_id, p_id),
                    )
        return self.get_student(stu_id)

    def get_student(self, student_id: int) -> dict[str, Any]:
        row = self.db.fetch_one(
            """
            SELECT st.*, ss.name AS class_name, sch.name AS school_name,
                   ay.name AS academic_year_name, ay.code AS academic_year_code
            FROM student_student st
            LEFT JOIN school_standard ss ON ss.id = st.standard_id
            LEFT JOIN school_school sch ON sch.id = st.school_id
            LEFT JOIN academic_year ay ON ay.id = st.year_id
            WHERE st.id = ?
            """,
            (student_id,),
        )
        if not row:
            raise NotFoundError(f"Student {student_id} not found")
        dob = parse_date(row["date_of_birth"])
        if dob:
            row["age"] = self.compute_age(dob)
        return row

    def verify_document(self, student_id: int) -> dict[str, Any]:
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE student_student SET state = 'verify_document' WHERE id = ?",
                (student_id,),
            )
        return self.get_student(student_id)

    def admission_done(self, student_id: int) -> dict[str, Any]:
        """Confirm student admission: check seats, assign roll_no, reg_code, student_code."""
        stu = self.get_student(student_id)
        if not stu["standard_id"]:
            raise ValidationError("Please select class!")

        ss = self.get_school_standard(stu["standard_id"])
        # Check remaining seats before admitting (if remaining_seats <= 0 and student not already done)
        if ss["remaining_seats"] <= 0 and stu["state"] != "done":
            raise ValidationError(f"Seats of class {ss['standard_name']} are full")

        school = self.db.fetch_one("SELECT * FROM school_school WHERE id = ?", (stu["school_id"],))
        year = self.db.fetch_one("SELECT * FROM academic_year WHERE id = ?", (stu["year_id"],))
        if not school or not year:
            raise UserError("Warning! The standard or school is not defined!")

        with self.db.connection() as conn:
            reg_seq = self.db.next_by_code("student.registration", conn=conn)
            stu_seq = self.db.next_by_code("student.code", conn=conn)
            reg_code = f"{school['state_name']}/{school['city']}/{school['name']}/{reg_seq}"
            student_code = f"{school['code']}/{year['code']}/{stu_seq}"

            conn.execute(
                """
                UPDATE student_student
                SET state = 'done', admission_date = ?, reg_code = ?, student_code = ?
                WHERE id = ?
                """,
                (date.today().isoformat(), reg_code, student_code, student_id),
            )

            # Assign sequential roll_no for students in this school
            school_students = conn.execute(
                "SELECT id FROM student_student WHERE school_id = ? ORDER BY id ASC",
                (stu["school_id"],),
            ).fetchall()
            for idx, s_row in enumerate(school_students, start=1):
                conn.execute(
                    "UPDATE student_student SET roll_no = ? WHERE id = ?",
                    (idx, s_row["id"]),
                )

        self.recompute_school_standard(stu["standard_id"])
        return self.get_student(student_id)

    def cancel_admission(self, student_id: int) -> dict[str, Any]:
        stu = self.get_student(student_id)
        with self.db.connection() as conn:
            conn.execute("UPDATE student_student SET state = 'cancel' WHERE id = ?", (student_id,))
        if stu["standard_id"]:
            self.recompute_school_standard(stu["standard_id"])
        return self.get_student(student_id)

    def set_to_draft(self, student_id: int) -> dict[str, Any]:
        stu = self.get_student(student_id)
        with self.db.connection() as conn:
            conn.execute("UPDATE student_student SET state = 'draft', active = 1 WHERE id = ?", (student_id,))
        if stu["standard_id"]:
            self.recompute_school_standard(stu["standard_id"])
        return self.get_student(student_id)

    def set_alumni(self, student_id: int) -> dict[str, Any]:
        """Set student to alumni with all cross-module checks and deactivations."""
        stu = self.get_student(student_id)
        with self.db.connection() as conn:
            # 1. school_fees check: block if payslip in ('confirm', 'pending')
            unpaid = conn.execute(
                """
                SELECT id FROM student_payslip
                WHERE student_id = ? AND state IN ('confirm', 'pending')
                LIMIT 1
                """,
                (student_id,),
            ).fetchone()
            if unpaid:
                raise ValidationError(
                    "You cannot alumni student because payment of fees of student is remaining!"
                )

            # 2. assignment cascade: deactivate student assignments
            conn.execute(
                "UPDATE school_student_assignment SET active = 0 WHERE student_id = ?",
                (student_id,),
            )

            # 3. exam cascade: deactivate exam results and additional exam results
            conn.execute(
                "UPDATE exam_result SET active = 0 WHERE student_id = ?",
                (student_id,),
            )
            conn.execute(
                "UPDATE additional_exam_result SET active = 0 WHERE student_id = ?",
                (student_id,),
            )

            # 4. library cascade: deactivate library cards
            conn.execute(
                "UPDATE library_card SET active = 0 WHERE student_id = ?",
                (student_id,),
            )

            # 5. school_hostel cascade: deactivate hostel student records & recompute room availability
            hostel_rows = conn.execute(
                """
                SELECT id, room_id FROM hostel_student
                WHERE student_id = ? AND status IN ('reservation', 'pending', 'paid')
                """,
                (student_id,),
            ).fetchall()
            conn.execute(
                """
                UPDATE hostel_student SET active = 0
                WHERE student_id = ? AND status IN ('reservation', 'pending', 'paid')
                """,
                (student_id,),
            )
            for hr in hostel_rows:
                self._recompute_hostel_room_conn(conn, hr["room_id"])

            # 6. school_transport cascade: cancel transport registrations & deactivate participants
            conn.execute(
                "UPDATE transport_registration SET state = 'cancel' WHERE student_id = ?",
                (student_id,),
            )
            conn.execute(
                "UPDATE transport_participant SET active = 0, state = 'over' WHERE name = ?",
                (student_id,),
            )

            # 7. Update student state to alumni
            conn.execute(
                """
                UPDATE student_student
                SET state = 'alumni', active = 0, leave_date = ?
                WHERE id = ?
                """,
                (date.today().isoformat(), student_id),
            )

        if stu["standard_id"]:
            self.recompute_school_standard(stu["standard_id"])
        return self.get_student(student_id)

    def terminate_student(
        self,
        student_id: int,
        *,
        reason: str,
        leave_date: str | date | None = None,
    ) -> dict[str, Any]:
        """Execute `terminate.reason` wizard with all 6 module overrides."""
        stu = self.get_student(student_id)
        lv_dt = parse_date(leave_date) or date.today()

        with self.db.connection() as conn:
            # 1. school_fees guard
            unpaid = conn.execute(
                """
                SELECT id FROM student_payslip
                WHERE student_id = ? AND state IN ('confirm', 'pending')
                LIMIT 1
                """,
                (student_id,),
            ).fetchone()
            if unpaid:
                raise ValidationError(
                    "You can't terminate student because payment of fees of student is remaining!"
                )

            # 2. assignment override
            conn.execute(
                "UPDATE school_student_assignment SET active = 0 WHERE student_id = ?",
                (student_id,),
            )

            # 3. exam override
            conn.execute("UPDATE exam_result SET active = 0 WHERE student_id = ?", (student_id,))
            conn.execute("UPDATE additional_exam_result SET active = 0 WHERE student_id = ?", (student_id,))

            # 4. school_event override: cancel event registrations
            conn.execute(
                "UPDATE event_registration SET state = 'cancel' WHERE part_name_id = ?",
                (student_id,),
            )

            # 5. school_hostel override: deactivate active hostel allocations & recompute rooms
            hostel_rows = conn.execute(
                """
                SELECT id, room_id FROM hostel_student
                WHERE student_id = ? AND status IN ('reservation', 'pending', 'paid')
                """,
                (student_id,),
            ).fetchall()
            conn.execute(
                """
                UPDATE hostel_student SET active = 0
                WHERE student_id = ? AND status IN ('reservation', 'pending', 'paid')
                """,
                (student_id,),
            )
            for hr in hostel_rows:
                self._recompute_hostel_room_conn(conn, hr["room_id"])

            # 6. school reminders & student state
            conn.execute("UPDATE student_reminder SET active = 0 WHERE stu_id = ?", (student_id,))
            conn.execute(
                """
                UPDATE student_student
                SET state = 'terminate', terminate_reason = ?, active = 0, leave_date = ?
                WHERE id = ?
                """,
                (reason.strip(), lv_dt.isoformat(), student_id),
            )

        if stu["standard_id"]:
            self.recompute_school_standard(stu["standard_id"])
        return self.get_student(student_id)

    @staticmethod
    def _recompute_hostel_room_conn(conn: Any, room_id: int) -> None:
        room = conn.execute(
            "SELECT student_per_room FROM hostel_room WHERE id = ?",
            (room_id,),
        ).fetchone()
        if room:
            active_cnt = conn.execute(
                """
                SELECT COUNT(*) AS c FROM hostel_student
                WHERE room_id = ? AND active = 1 AND status NOT IN ('discharge', 'cancel')
                """,
                (room_id,),
            ).fetchone()["c"]
            avail = max(0, int(room["student_per_room"]) - int(active_cnt))
            conn.execute(
                "UPDATE hostel_room SET availability = ? WHERE id = ?",
                (avail, room_id),
            )

    # -------------------------------------------------------------------------
    # Wizards: Assign Roll No & Move Standards (Promote Students)
    # -------------------------------------------------------------------------
    def assign_roll_no(self, *, standard_id: int, medium_id: int) -> list[dict[str, Any]]:
        """Assign sequential roll_no ordered alphabetically by student_name."""
        with self.db.connection() as conn:
            students = conn.execute(
                """
                SELECT id FROM student_student
                WHERE standard_id = ? AND medium_id = ?
                ORDER BY student_name ASC, id ASC
                """,
                (standard_id, medium_id),
            ).fetchall()
            for idx, s in enumerate(students, start=1):
                conn.execute(
                    "UPDATE student_student SET roll_no = ? WHERE id = ?",
                    (idx, s["id"]),
                )
        return [self.get_student(s["id"]) for s in students]

    def move_standards(self, *, academic_year_id: int) -> list[dict[str, Any]]:
        """Promote students from `academic_year_id` to next sequenced academic year.
        Preserves both `school/wizard/move_standards.py` and `exam/wizard/move_standards.py`:
        - If student has an exam result with `result == 'Fail'`, student moves to next academic year
          but stays in the same standard.
        - Otherwise (Pass or no fail result), student moves to next sequenced standard and next academic year.
        """
        year = self.get_academic_year(academic_year_id)
        next_yr_id = self.next_year(year["sequence"])
        if not next_yr_id:
            raise ValidationError(
                "The next sequanced Acedemic year after the selected one is not configured!"
            )

        students = self.db.fetch_all(
            "SELECT * FROM student_student WHERE state = 'done' AND year_id = ?",
            (academic_year_id,),
        )
        moved: list[dict[str, Any]] = []
        affected_standards: set[int] = set()

        for stud in students:
            if not stud["standard_id"]:
                continue
            curr_ss = self.get_school_standard(stud["standard_id"])
            curr_std = self.db.fetch_one(
                "SELECT * FROM standard_standard WHERE id = ?",
                (curr_ss["standard_id"],),
            )
            if not curr_std:
                continue

            # Check latest exam result if any
            exam_res = self.db.fetch_one(
                """
                SELECT percentage, result FROM exam_result
                WHERE student_id = ? AND standard_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (stud["id"], stud["standard_id"]),
            )
            passed = True
            perc = 0.0
            res_label = "Pass"
            if exam_res:
                perc = float(exam_res["percentage"] or 0.0)
                res_label = exam_res["result"] or "Pass"
                if res_label == "Fail":
                    passed = False

            target_ss_id = stud["standard_id"]
            if passed:
                nxt_std = self.next_standard(curr_std["sequence"])
                if nxt_std:
                    nxt_ss = self.db.fetch_one(
                        """
                        SELECT id FROM school_standard
                        WHERE standard_id = ? AND division_id = ?
                          AND school_id = ? AND medium_id = ?
                        LIMIT 1
                        """,
                        (
                            nxt_std["id"],
                            curr_ss["division_id"],
                            stud["school_id"],
                            stud["medium_id"],
                        ),
                    )
                    if nxt_ss:
                        target_ss_id = nxt_ss["id"]

            with self.db.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO student_history
                    (student_id, move_date, academice_year_id, standard_id, percentage, result)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stud["id"],
                        date.today().isoformat(),
                        academic_year_id,
                        stud["standard_id"],
                        perc,
                        res_label,
                    ),
                )
                conn.execute(
                    "UPDATE student_student SET year_id = ?, standard_id = ? WHERE id = ?",
                    (next_yr_id, target_ss_id, stud["id"]),
                )
            affected_standards.add(stud["standard_id"])
            affected_standards.add(target_ss_id)
            moved.append(self.get_student(stud["id"]))

        for ss_id in affected_standards:
            self.recompute_school_standard(ss_id)
        return moved

    # -------------------------------------------------------------------------
    # News, Reminders, Discipline, Awards, Previous School
    # -------------------------------------------------------------------------
    def create_student_news(self, *, subject: str, date_expiry: str | date, description: str = "") -> dict[str, Any]:
        dt = parse_date(date_expiry)
        if not dt or dt < date.today():
            raise ValidationError("Configure expiry date greater than current date!")
        with self.db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO student_news (subject, description, date) VALUES (?, ?, ?)",
                (subject.strip(), description, dt.isoformat()),
            )
            nid = cur.lastrowid
        return self.db.fetch_one("SELECT * FROM student_news WHERE id = ?", (nid,))  # type: ignore[return-value]

    def create_student_reminder(
        self,
        *,
        stu_id: int,
        name: str,
        reminder_date: str | date,
        description: str = "",
    ) -> dict[str, Any]:
        dt = parse_date(reminder_date)
        if not dt or dt < date.today():
            raise ValidationError("Reminder date of must be greater or equal current date !")
        with self.db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO student_reminder (stu_id, name, date, description, active) VALUES (?, ?, ?, ?, 1)",
                (stu_id, name.strip(), dt.isoformat(), description),
            )
            rid = cur.lastrowid
        return self.db.fetch_one("SELECT * FROM student_reminder WHERE id = ?", (rid,))  # type: ignore[return-value]

    def create_previous_school(
        self,
        *,
        student_id: int,
        name: str,
        registration_no: str,
        admission_date: str | date,
        exit_date: str | date,
        course_id: int,
    ) -> dict[str, Any]:
        adm = parse_date(admission_date)
        ext = parse_date(exit_date)
        today = date.today()
        if (adm and adm >= today) or (ext and ext >= today):
            raise ValidationError(
                "Your admission date and exit date should be less than current date!"
            )
        if adm and ext and ext < adm:
            raise ValidationError(
                "Admission date should be less than exit date in previous school!"
            )
        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO student_previous_school
                (previous_school_id, name, registration_no, admission_date, exit_date, course_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    student_id,
                    name.strip(),
                    registration_no.strip(),
                    adm.isoformat() if adm else None,
                    ext.isoformat() if ext else None,
                    course_id,
                ),
            )
            pid = cur.lastrowid
        return self.db.fetch_one("SELECT * FROM student_previous_school WHERE id = ?", (pid,))  # type: ignore[return-value]

    # -------------------------------------------------------------------------
    # List Queries & Dashboard KPIs
    # -------------------------------------------------------------------------
    def list_schools(self) -> list[dict[str, Any]]:
        return self.db.fetch_all("SELECT * FROM school_school ORDER BY id")

    def list_academic_months(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT am.*, ay.name AS year_name
            FROM academic_month am
            JOIN academic_year ay ON ay.id = am.year_id
            ORDER BY am.date_start
            """
        )

    def list_school_standards(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT id FROM school_standard ORDER BY id")
        return [self.get_school_standard(r["id"]) for r in rows]

    def list_subjects(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT id FROM subject_subject ORDER BY id")
        return [self.get_subject(r["id"]) for r in rows]

    def list_teachers(self) -> list[dict[str, Any]]:
        rows = self.db.fetch_all("SELECT id FROM school_teacher WHERE active = 1 ORDER BY id")
        return [self.get_teacher(r["id"]) for r in rows]

    def list_students(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        q = "SELECT id FROM student_student"
        if not include_inactive:
            q += " WHERE active = 1"
        q += " ORDER BY roll_no ASC, id DESC"
        rows = self.db.fetch_all(q)
        return [self.get_student(r["id"]) for r in rows]

    def get_dashboard_kpis(self) -> dict[str, Any]:
        with self.db.connection() as conn:
            active_students = conn.execute(
                "SELECT COUNT(*) AS c FROM student_student WHERE state = 'done' AND active = 1"
            ).fetchone()["c"]
            teachers = conn.execute(
                "SELECT COUNT(*) AS c FROM school_teacher WHERE active = 1"
            ).fetchone()["c"]
            classes = conn.execute("SELECT COUNT(*) AS c FROM school_standard").fetchone()["c"]
            fees_collected = conn.execute(
                "SELECT COALESCE(SUM(paid_amount), 0.0) AS c FROM student_payslip"
            ).fetchone()["c"]
            fees_due = conn.execute(
                "SELECT COALESCE(SUM(due_amount), 0.0) AS c FROM student_payslip WHERE state IN ('confirm', 'pending')"
            ).fetchone()["c"]
            available_books = conn.execute(
                "SELECT COALESCE(SUM(books_available), 0) AS c FROM library_book"
            ).fetchone()["c"]
            hostel_residents = conn.execute(
                "SELECT COUNT(*) AS c FROM hostel_student WHERE active = 1 AND status NOT IN ('discharge', 'cancel')"
            ).fetchone()["c"]
            transport_participants = conn.execute(
                "SELECT COUNT(*) AS c FROM transport_participant WHERE active = 1 AND state != 'over'"
            ).fetchone()["c"]
            return {
                "active_students": int(active_students),
                "teachers": int(teachers),
                "classes": int(classes),
                "fees_collected": float(fees_collected),
                "fees_due": float(fees_due),
                "available_books": int(available_books),
                "hostel_residents": int(hostel_residents),
                "transport_participants": int(transport_participants),
            }

