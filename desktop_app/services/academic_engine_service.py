"""
Phase 4 Academic Engine — Quick Exam Setup, Marks Grid, Tie-Aware Ranks, Report Cards,
Result Gazette, Academic Calendar (S6) & Timetable Substitution (G7, G8, G21, S5, S6).

Strictly under 600 lines per anti-monolith budget (ADVANCEMENT_PLAN.md Section 10.1).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, ValidationError, parse_date
from desktop_app.services.audit_service import AuditService
from desktop_app.services.calendar_timetable_mixin import CalendarTimetableMixin
from desktop_app.services.exam_service import ExamService
from desktop_app.services.settings_service import SettingsService


class AcademicEngineService(CalendarTimetableMixin):
    """High-speed Exam Marks Grid, Olympic Ranker, Calendar & Timetable Substitution Engine."""

    def __init__(
        self,
        db: Database,
        exam_svc: ExamService | None = None,
        audit: AuditService | None = None,
        settings: SettingsService | None = None,
    ) -> None:
        self.db = db
        self.exam_svc = exam_svc or ExamService(db)
        self.audit = audit or AuditService(db)
        self.settings = settings or SettingsService(db, self.audit)

    # -------------------------------------------------------------------------
    # Quick Exam Setup & Auto-Marksheet Initialization (G7)
    # -------------------------------------------------------------------------
    def quick_create_exam(
        self,
        payload: dict[str, Any],
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        name = (payload.get("name") or "").strip()
        if len(name) < 2:
            raise ValidationError("Exam name is required (min 2 characters).")

        d_start = parse_date(payload.get("start_date") or date.today().isoformat(), "Start Date")
        d_end = parse_date(payload.get("end_date") or d_start.isoformat(), "End Date")
        if d_end < d_start:
            raise ValidationError("Exam End Date must be on or after Start Date.")

        raw_classes = payload.get("standard_ids") or (
            [payload["class_id"]] if payload.get("class_id") else []
        )
        class_ids = [int(x) for x in raw_classes if x]
        raw_subjects = payload.get("subject_ids") or []
        subject_ids = [int(x) for x in raw_subjects if x]

        with self.db.connection() as conn:
            year_id = payload.get("academic_year_id")
            if not year_id:
                yr = conn.execute(
                    "SELECT id FROM academic_year WHERE current = 1 ORDER BY id DESC LIMIT 1"
                ).fetchone()
                year_id = int(yr["id"]) if yr else 1
            else:
                year_id = int(year_id)

            grade_id = payload.get("grade_system_id")
            if not grade_id:
                gm = conn.execute("SELECT id FROM grade_master ORDER BY id ASC LIMIT 1").fetchone()
                grade_id = int(gm["id"]) if gm else None
            else:
                grade_id = int(grade_id)

            if not class_ids:
                class_ids = [
                    int(r["id"])
                    for r in conn.execute("SELECT id FROM school_standard ORDER BY id ASC").fetchall()
                ]

            code = self.db.next_by_code("exam.exam", conn=conn)
            cur = conn.execute(
                """
                INSERT INTO exam_exam
                    (name, exam_code, start_date, end_date, state, grade_system_id, academic_year_id, active)
                VALUES (?, ?, ?, ?, 'running', ?, ?, 1)
                """,
                (name, code, d_start.isoformat(), d_end.isoformat(), grade_id, year_id),
            )
            exam_id = int(cur.lastrowid)

            default_teacher = conn.execute(
                "SELECT id FROM school_teacher WHERE active = 1 ORDER BY id ASC LIMIT 1"
            ).fetchone()
            def_tid = int(default_teacher["id"]) if default_teacher else 1

            generated_results = 0
            for cid in class_ids:
                ss = conn.execute("SELECT * FROM school_standard WHERE id = ?", (cid,)).fetchone()
                if not ss:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO exam_standard_rel (exam_id, standard_id) VALUES (?, ?)",
                    (exam_id, ss["standard_id"]),
                )

                # Resolve subjects for this class
                if subject_ids:
                    placeholders = ",".join("?" for _ in subject_ids)
                    subs = conn.execute(
                        f"SELECT * FROM subject_subject WHERE id IN ({placeholders}) ORDER BY id ASC",
                        subject_ids,
                    ).fetchall()
                else:
                    subs = conn.execute(
                        """
                        SELECT sub.* FROM subject_subject sub
                        JOIN subject_standards_rel rel ON rel.subject_id = sub.id
                        WHERE rel.school_standard_id = ?
                        ORDER BY sub.id ASC
                        """,
                        (cid,),
                    ).fetchall()
                    if not subs:
                        subs = conn.execute("SELECT * FROM subject_subject ORDER BY id ASC").fetchall()

                # Ensure an exam timetable exists or create one for this exam + class
                tt_cur = conn.execute(
                    """
                    INSERT INTO time_table (name, standard_id, year_id, timetable_type, exam_id)
                    VALUES (?, ?, ?, 'exam', ?)
                    """,
                    (f"{name} — {ss['name']}", cid, year_id, exam_id),
                )
                tt_id = int(tt_cur.lastrowid)
                for idx, sub in enumerate(subs):
                    slot_start = 9.0 + (idx % 4)
                    conn.execute(
                        """
                        INSERT INTO time_table_line
                            (table_id, teacher_id, subject_id, start_time, end_time, week_day, exm_date, day_of_week)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            tt_id,
                            def_tid,
                            int(sub["id"]),
                            slot_start,
                            slot_start + 1.0,
                            d_start.strftime("%A").lower(),
                            d_start.isoformat(),
                            d_start.strftime("%A"),
                        ),
                    )
                conn.execute(
                    "INSERT INTO exam_schedule_line (exam_id, standard_id, timetable_id) VALUES (?, ?, ?)",
                    (exam_id, cid, tt_id),
                )

                # Generate marksheets for all active enrolled students in this class
                students = conn.execute(
                    """
                    SELECT id, roll_no, standard_id
                    FROM student_student
                    WHERE standard_id = ? AND state = 'done' AND active = 1
                    ORDER BY roll_no ASC, id ASC
                    """,
                    (cid,),
                ).fetchall()
                for stu in students:
                    rcur = conn.execute(
                        """
                        INSERT INTO exam_result
                            (s_exam_ids, student_id, roll_no, standard_id, grade_system_id,
                             total, percentage, result, grade, state, active, remarks)
                        VALUES (?, ?, ?, ?, ?, 0.0, 0.0, 'Pass', '', 'draft', 1, '')
                        """,
                        (exam_id, stu["id"], stu["roll_no"], cid, grade_id),
                    )
                    res_id = int(rcur.lastrowid)
                    for sub in subs:
                        conn.execute(
                            """
                            INSERT INTO exam_subject
                                (exam_id, subject_id, obtain_marks, minimum_marks, maximum_marks, marks_reeval, is_absent)
                            VALUES (?, ?, 0.0, ?, ?, 0.0, 0)
                            """,
                            (
                                res_id,
                                int(sub["id"]),
                                float(sub["minimum_marks"] or 35.0),
                                float(sub["maximum_marks"] or 100.0),
                            ),
                        )
                    self.exam_svc._recompute_result_conn(conn, res_id)
                    generated_results += 1

        if actor:
            self.audit.record(
                user_id=actor.get("id"),
                username=actor.get("username") or "admin",
                role=actor.get("role") or "admin",
                action="exams.quick_create",
                entity_type="exam_exam",
                entity_id=exam_id,
                summary=f"Created exam '{name}' ({code}) with {generated_results} marksheet(s)",
                ip_address=ip_address,
            )
        return {"exam_id": exam_id, "exam_code": code, "generated_results": generated_results}

    # -------------------------------------------------------------------------
    # Spreadsheet Marks Grid (MRK-1..MRK-3, R-T3, F5, F16)
    # -------------------------------------------------------------------------
    def get_marks_grid(self, exam_id: int, class_id: int, subject_id: int) -> dict[str, Any]:
        with self.db.connection() as conn:
            exam = conn.execute("SELECT * FROM exam_exam WHERE id = ?", (exam_id,)).fetchone()
            if not exam:
                raise NotFoundError(f"Exam #{exam_id} not found.")
            cls = conn.execute("SELECT * FROM school_standard WHERE id = ?", (class_id,)).fetchone()
            if not cls:
                raise NotFoundError(f"Class #{class_id} not found.")
            sub = conn.execute("SELECT * FROM subject_subject WHERE id = ?", (subject_id,)).fetchone()
            if not sub:
                raise NotFoundError(f"Subject #{subject_id} not found.")

            # Ensure all enrolled students in class have an exam_result + exam_subject row
            students = conn.execute(
                """
                SELECT id, pid, student_name, middle, last, roll_no
                FROM student_student
                WHERE standard_id = ? AND state = 'done' AND active = 1
                ORDER BY roll_no ASC, id ASC
                """,
                (class_id,),
            ).fetchall()

            rows_out: list[dict[str, Any]] = []
            for stu in students:
                er = conn.execute(
                    "SELECT * FROM exam_result WHERE s_exam_ids = ? AND student_id = ? LIMIT 1",
                    (exam_id, stu["id"]),
                ).fetchone()
                if not er:
                    cur = conn.execute(
                        """
                        INSERT INTO exam_result
                            (s_exam_ids, student_id, roll_no, standard_id, grade_system_id,
                             total, percentage, result, grade, state, active, remarks)
                        VALUES (?, ?, ?, ?, ?, 0.0, 0.0, 'Pass', '', 'draft', 1, '')
                        """,
                        (exam_id, stu["id"], stu["roll_no"], class_id, exam["grade_system_id"]),
                    )
                    er_id = int(cur.lastrowid)
                else:
                    er_id = int(er["id"])

                es = conn.execute(
                    """
                    SELECT es.*, gl.grade AS subject_grade
                    FROM exam_subject es
                    LEFT JOIN grade_line gl ON gl.id = es.grade_line_id
                    WHERE es.exam_id = ? AND es.subject_id = ?
                    LIMIT 1
                    """,
                    (er_id, subject_id),
                ).fetchone()
                if not es:
                    scur = conn.execute(
                        """
                        INSERT INTO exam_subject
                            (exam_id, subject_id, obtain_marks, minimum_marks, maximum_marks, marks_reeval, is_absent)
                        VALUES (?, ?, 0.0, ?, ?, 0.0, 0)
                        """,
                        (
                            er_id,
                            subject_id,
                            float(sub["minimum_marks"] or 35.0),
                            float(sub["maximum_marks"] or 100.0),
                        ),
                    )
                    es_id = int(scur.lastrowid)
                    es = conn.execute(
                        "SELECT es.*, '' AS subject_grade FROM exam_subject es WHERE es.id = ?",
                        (es_id,),
                    ).fetchone()

                er_fresh = conn.execute("SELECT * FROM exam_result WHERE id = ?", (er_id,)).fetchone()
                obt = float(es["obtain_marks"] or 0.0)
                max_m = float(es["maximum_marks"] or sub["maximum_marks"] or 100.0)
                min_m = float(es["minimum_marks"] or sub["minimum_marks"] or 35.0)
                is_abs = bool(es["is_absent"])
                pct = round((obt / max_m) * 100.0, 1) if max_m > 0 and not is_abs else 0.0
                passed = (not is_abs) and (obt >= min_m)

                rows_out.append(
                    {
                        "result_id": er_id,
                        "subject_line_id": int(es["id"]),
                        "student_id": int(stu["id"]),
                        "pid": stu["pid"],
                        "roll_no": stu["roll_no"],
                        "student_name": " ".join(
                            p for p in (stu["student_name"], stu["middle"], stu["last"]) if p
                        ),
                        "obtain_marks": obt,
                        "minimum_marks": min_m,
                        "maximum_marks": max_m,
                        "is_absent": is_abs,
                        "subject_percentage": pct,
                        "subject_grade": es["subject_grade"] or "",
                        "subject_status": "Absent" if is_abs else ("Pass" if passed else "Fail"),
                        "overall_total": float(er_fresh["total"] or 0.0),
                        "overall_percentage": float(er_fresh["percentage"] or 0.0),
                        "overall_grade": er_fresh["grade"] or "",
                        "rank": er_fresh["rank"],
                        "remarks": er_fresh["remarks"] or "",
                        "state": er_fresh["state"],
                    }
                )

        entered = sum(1 for r in rows_out if r["obtain_marks"] > 0 or r["is_absent"])
        avg_pct = (
            round(sum(r["subject_percentage"] for r in rows_out) / len(rows_out), 1)
            if rows_out
            else 0.0
        )
        return {
            "exam": dict(exam),
            "class": dict(cls),
            "subject": dict(sub),
            "rows": rows_out,
            "summary": {
                "total_students": len(rows_out),
                "entered_count": entered,
                "pass_count": sum(1 for r in rows_out if r["subject_status"] == "Pass"),
                "fail_count": sum(1 for r in rows_out if r["subject_status"] != "Pass"),
                "average_pct": avg_pct,
                "highest_marks": max((r["obtain_marks"] for r in rows_out), default=0.0),
            },
        }

    def save_marks_grid(
        self,
        *,
        exam_id: int,
        class_id: int,
        subject_id: int,
        entries: list[dict[str, Any]],
        finalize: bool = False,
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        if not entries:
            raise ValidationError("No marks entries provided.")

        with self.db.connection() as conn:
            affected_results: set[int] = set()
            for item in entries:
                sline_id = int(item["subject_line_id"])
                row = conn.execute(
                    "SELECT * FROM exam_subject WHERE id = ?", (sline_id,)
                ).fetchone()
                if not row:
                    raise NotFoundError(f"Exam subject line #{sline_id} not found.")

                max_m = float(item.get("maximum_marks") or row["maximum_marks"] or 100.0)
                min_m = float(item.get("minimum_marks") or row["minimum_marks"] or 35.0)
                is_abs = 1 if item.get("is_absent") else 0
                raw_marks = 0.0 if is_abs else float(item.get("obtain_marks", 0.0))

                # R-T3 Poka-Yoke: strictly reject < 0 or > maximum_marks
                if raw_marks < 0.0 or raw_marks > max_m:
                    raise ValidationError(
                        f"Marks must be between 0 and {max_m:g} (received {raw_marks:g})."
                    )

                conn.execute(
                    """
                    UPDATE exam_subject
                    SET obtain_marks = ?, minimum_marks = ?, maximum_marks = ?, is_absent = ?
                    WHERE id = ?
                    """,
                    (raw_marks, min_m, max_m, is_abs, sline_id),
                )
                res_id = int(row["exam_id"])
                affected_results.add(res_id)

                if "remarks" in item and item["remarks"] is not None:
                    conn.execute(
                        "UPDATE exam_result SET remarks = ? WHERE id = ?",
                        (str(item["remarks"]).strip()[:250], res_id),
                    )

            for rid in affected_results:
                self._recompute_result_with_absent_conn(conn, rid)
                if finalize:
                    conn.execute(
                        "UPDATE exam_result SET state = 'confirm' WHERE id = ? AND state = 'draft'",
                        (rid,),
                    )

            self._compute_ranks_conn(conn, exam_id, class_id)

        if actor:
            self.audit.record(
                user_id=actor.get("id"),
                username=actor.get("username") or "teacher",
                role=actor.get("role") or "teacher",
                action="exams.marks_grid_save",
                entity_type="exam_exam",
                entity_id=exam_id,
                summary=f"Saved {len(entries)} subject marks for exam #{exam_id} class #{class_id}",
                ip_address=ip_address,
            )
        return self.get_marks_grid(exam_id, class_id, subject_id)

    def _recompute_result_with_absent_conn(self, conn: Any, result_id: int) -> None:
        self.exam_svc._recompute_result_conn(conn, result_id)
        abs_cnt = conn.execute(
            "SELECT COUNT(*) AS c FROM exam_subject WHERE exam_id = ? AND is_absent = 1",
            (result_id,),
        ).fetchone()["c"]
        if abs_cnt > 0:
            conn.execute("UPDATE exam_result SET result = 'Fail' WHERE id = ?", (result_id,))

    # -------------------------------------------------------------------------
    # Olympic Tie-Aware Rank Calculation (R-E1: 1, 2, 2, 4)
    # -------------------------------------------------------------------------
    def _compute_ranks_conn(self, conn: Any, exam_id: int, class_id: int | None = None) -> list[dict[str, Any]]:
        if class_id is not None:
            class_ids = [int(class_id)]
        else:
            class_ids = [
                int(r["standard_id"])
                for r in conn.execute(
                    "SELECT DISTINCT standard_id FROM exam_result WHERE s_exam_ids = ? AND standard_id IS NOT NULL",
                    (exam_id,),
                ).fetchall()
            ]

        all_ranked: list[dict[str, Any]] = []
        for cid in class_ids:
            rows = conn.execute(
                """
                SELECT er.*, s.student_name, s.middle, s.last, s.pid, ss.name AS class_name
                FROM exam_result er
                JOIN student_student s ON s.id = er.student_id
                LEFT JOIN school_standard ss ON ss.id = er.standard_id
                WHERE er.s_exam_ids = ? AND er.standard_id = ? AND er.active = 1
                ORDER BY er.total DESC, er.percentage DESC, er.roll_no ASC, er.id ASC
                """,
                (exam_id, cid),
            ).fetchall()

            last_score: tuple[float, float] | None = None
            current_rank = 0
            for idx, r in enumerate(rows, start=1):
                score_key = (round(float(r["total"] or 0.0), 2), round(float(r["percentage"] or 0.0), 2))
                if last_score is None or score_key != last_score:
                    current_rank = idx
                    last_score = score_key
                conn.execute(
                    "UPDATE exam_result SET rank = ? WHERE id = ?",
                    (current_rank, r["id"]),
                )
                d = dict(r)
                d["rank"] = current_rank
                all_ranked.append(d)
        return all_ranked

    def compute_ranks(
        self,
        exam_id: int,
        class_id: int | None = None,
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> list[dict[str, Any]]:
        with self.db.connection() as conn:
            ranked = self._compute_ranks_conn(conn, exam_id, class_id)
        if actor:
            self.audit.record(
                user_id=actor.get("id"),
                username=actor.get("username") or "exam_incharge",
                role=actor.get("role") or "exam_incharge",
                action="exams.compute_ranks",
                entity_type="exam_exam",
                entity_id=exam_id,
                summary=f"Computed Olympic class ranks for exam #{exam_id} ({len(ranked)} marksheets)",
                ip_address=ip_address,
            )
        return ranked

    # -------------------------------------------------------------------------
    # Report Card Print Bundle & Result Gazette (S5, F6, R-E1)
    # -------------------------------------------------------------------------
    def get_report_cards_bundle(
        self,
        *,
        exam_id: int,
        class_id: int | None = None,
        student_id: int | None = None,
    ) -> dict[str, Any]:
        with self.db.connection() as conn:
            self._compute_ranks_conn(conn, exam_id, class_id)
            clauses = ["er.s_exam_ids = ?", "er.active = 1"]
            params: list[Any] = [exam_id]
            if class_id:
                clauses.append("er.standard_id = ?")
                params.append(class_id)
            if student_id:
                clauses.append("er.student_id = ?")
                params.append(student_id)

            where = " AND ".join(clauses)
            rows = conn.execute(
                f"""
                SELECT er.*, e.name AS exam_name, e.exam_code, e.start_date, e.end_date,
                       s.pid, s.student_name, s.middle, s.last, s.roll_no, s.date_of_birth,
                       ss.name AS class_name, ay.name AS year_name
                FROM exam_result er
                JOIN exam_exam e ON e.id = er.s_exam_ids
                JOIN student_student s ON s.id = er.student_id
                LEFT JOIN school_standard ss ON ss.id = er.standard_id
                LEFT JOIN academic_year ay ON ay.id = e.academic_year_id
                WHERE {where}
                ORDER BY COALESCE(er.rank, 9999) ASC, er.roll_no ASC
                """,
                params,
            ).fetchall()

            cards: list[dict[str, Any]] = []
            for r in rows:
                d = dict(r)
                subs = conn.execute(
                    """
                    SELECT es.*, sub.name AS subject_name, sub.code AS subject_code,
                           gl.grade AS subject_grade
                    FROM exam_subject es
                    JOIN subject_subject sub ON sub.id = es.subject_id
                    LEFT JOIN grade_line gl ON gl.id = es.grade_line_id
                    WHERE es.exam_id = ?
                    ORDER BY sub.id ASC
                    """,
                    (r["id"],),
                ).fetchall()
                d["subjects"] = [dict(s) for s in subs]
                d["max_total"] = sum(float(s["maximum_marks"] or 0.0) for s in subs)

                att = conn.execute(
                    """
                    SELECT COUNT(*) AS tot,
                           SUM(CASE WHEN is_present = 1 THEN 1 ELSE 0 END) AS pres
                    FROM daily_attendance_line
                    WHERE stud_id = ?
                    """,
                    (r["student_id"],),
                ).fetchone()
                tot_att = int(att["tot"] or 0)
                pres_att = int(att["pres"] or 0)
                d["attendance_pct"] = round((pres_att / tot_att) * 100.0, 1) if tot_att > 0 else 100.0
                d["attendance_detail"] = f"{pres_att}/{tot_att}" if tot_att > 0 else "Full"
                cards.append(d)

        return {
            "school": self.settings.get_school_profile(),
            "preferences": self.settings.get_preferences(),
            "report_cards": cards,
        }

    def get_exam_gazette(self, exam_id: int, class_id: int | None = None) -> dict[str, Any]:
        bundle = self.get_report_cards_bundle(exam_id=exam_id, class_id=class_id)
        cards = bundle["report_cards"]
        pass_cnt = sum(1 for c in cards if c.get("result") == "Pass")
        avg_pct = round(sum(float(c.get("percentage") or 0.0) for c in cards) / len(cards), 1) if cards else 0.0
        return {
            "school": bundle["school"],
            "items": cards,
            "summary": {
                "total_students": len(cards),
                "pass_count": pass_cnt,
                "fail_count": len(cards) - pass_cnt,
                "pass_rate_pct": round((pass_cnt / len(cards)) * 100.0, 1) if cards else 0.0,
                "class_average_pct": avg_pct,
                "top_performer": cards[0]["student_name"] if cards else "—",
            },
        }

