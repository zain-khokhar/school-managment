"""
Phase 4 Student ID Cards, PTM 1-Pager (S7) & Library 1-Click Quick Issue Mixin (G11, F14).

Extracted from `admission_import_service.py` so every Python service stays under 600 lines.
"""

from __future__ import annotations

from typing import Any

from desktop_app.services.fee_engine_service import from_paisa


class StudentPrintsAndCampusMixin:
    """Provides Student ID Cards, PTM 1-Pager bundles, and Library 1-Click Quick Issue."""

    db: Any
    settings: Any
    lib_svc: Any
    audit: Any

    # -------------------------------------------------------------------------
    # G11 & S7: Student ID Cards & PTM 1-Pager Print Bundles
    # -------------------------------------------------------------------------
    def get_id_cards_bundle(
        self,
        *,
        student_ids: list[int] | None = None,
        class_id: int | None = None,
    ) -> dict[str, Any]:
        clauses = ["s.active = 1"]
        params: list[Any] = []
        if student_ids:
            ph = ",".join("?" for _ in student_ids)
            clauses.append(f"s.id IN ({ph})")
            params.extend(int(x) for x in student_ids)
        if class_id:
            clauses.append("s.standard_id = ?")
            params.append(int(class_id))

        rows = self.db.fetch_all(
            f"""
            SELECT s.id, s.pid, s.student_name, s.middle, s.last, s.roll_no,
                   s.date_of_birth, s.blood_group, s.contact_mobile, s.b_form_no,
                   ss.name AS class_name, ay.name AS year_name
            FROM student_student s
            LEFT JOIN school_standard ss ON ss.id = s.standard_id
            LEFT JOIN academic_year ay ON ay.id = s.year_id
            WHERE {' AND '.join(clauses)}
            ORDER BY ss.name ASC, s.roll_no ASC, s.id ASC
            LIMIT 120
            """,
            tuple(params),
        )
        return {
            "school": self.settings.get_school_profile(),
            "cards": rows,
        }

    def get_ptm_sheets_bundle(
        self,
        *,
        student_ids: list[int] | None = None,
        class_id: int | None = None,
    ) -> dict[str, Any]:
        cards_bundle = self.get_id_cards_bundle(student_ids=student_ids, class_id=class_id)
        sheets: list[dict[str, Any]] = []
        with self.db.connection() as conn:
            for stu in cards_bundle["cards"]:
                sid = int(stu["id"])
                att = conn.execute(
                    """
                    SELECT COUNT(*) AS tot,
                           SUM(CASE WHEN is_present = 1 THEN 1 ELSE 0 END) AS pres
                    FROM daily_attendance_line WHERE stud_id = ?
                    """,
                    (sid,),
                ).fetchone()
                tot_d = int(att["tot"] or 0)
                pres_d = int(att["pres"] or 0)
                att_pct = round((pres_d / tot_d) * 100.0, 1) if tot_d > 0 else 100.0

                fee_row = conn.execute(
                    """
                    SELECT COALESCE(SUM(CASE WHEN due_paisa > 0 THEN due_paisa ELSE CAST(ROUND(due_amount * 100) AS INTEGER) END), 0) AS due_p
                    FROM student_payslip
                    WHERE student_id = ? AND state IN ('confirm', 'pending')
                    """,
                    (sid,),
                ).fetchone()
                due_p = int(fee_row["due_p"] or 0)

                last_er = conn.execute(
                    """
                    SELECT er.*, e.name AS exam_name
                    FROM exam_result er
                    JOIN exam_exam e ON e.id = er.s_exam_ids
                    WHERE er.student_id = ? AND er.active = 1
                    ORDER BY er.id DESC LIMIT 1
                    """,
                    (sid,),
                ).fetchone()
                latest_exam = None
                weak_subject = "None"
                if last_er:
                    latest_exam = dict(last_er)
                    w_sub = conn.execute(
                        """
                        SELECT sub.name, es.obtain_marks, es.maximum_marks
                        FROM exam_subject es
                        JOIN subject_subject sub ON sub.id = es.subject_id
                        WHERE es.exam_id = ?
                        ORDER BY es.obtain_marks ASC LIMIT 1
                        """,
                        (last_er["id"],),
                    ).fetchone()
                    if w_sub:
                        weak_subject = f"{w_sub['name']} ({w_sub['obtain_marks']:g}/{w_sub['maximum_marks']:g})"

                sheets.append(
                    {
                        "student": stu,
                        "attendance_pct": att_pct,
                        "attendance_detail": f"{pres_d}/{tot_d} days" if tot_d > 0 else "100% (No absences)",
                        "fee_due_paisa": due_p,
                        "fee_due": from_paisa(due_p),
                        "latest_exam": latest_exam,
                        "weak_subject": weak_subject,
                        "teacher_remark": (
                            latest_exam.get("remarks")
                            if latest_exam and latest_exam.get("remarks")
                            else "Consistent effort; regular revision recommended at home."
                        ),
                    }
                )
        return {
            "school": cards_bundle["school"],
            "sheets": sheets,
        }

    # -------------------------------------------------------------------------
    # F14 & Section 9.8(L): Library 1-Click Quick Issue by Student GR (Auto-Card)
    # -------------------------------------------------------------------------
    def quick_issue_book_by_student(
        self,
        *,
        student_id: int,
        book_id: int,
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        card = self.db.fetch_one(
            """
            SELECT * FROM library_card
            WHERE student_id = ? AND state = 'running' AND active = 1
            ORDER BY id DESC LIMIT 1
            """,
            (student_id,),
        )
        if card:
            card_id = int(card["id"])
            card_code = card["code"]
        else:
            card_id = self.lib_svc.create_library_card(
                user="student",
                student_id=student_id,
                book_limit=5,
                duration=12,
                allow_past_dates=True,
            )
            card_code = self.lib_svc.running_state_card(card_id)

        issue_id = self.lib_svc.create_book_issue(book_id=book_id, card_id=card_id)
        issued = self.lib_svc.issue_book(issue_id)
        if actor:
            self.audit.record(
                user_id=actor.get("id"),
                username=actor.get("username") or "admin",
                role=actor.get("role") or "admin",
                action="library.quick_issue",
                entity_type="library_book_issue",
                entity_id=issue_id,
                summary=f"Quick-issued book #{book_id} to student #{student_id} ({card_code})",
                ip_address=ip_address,
            )
        return {"issue": issued, "card_id": card_id, "card_code": card_code}
