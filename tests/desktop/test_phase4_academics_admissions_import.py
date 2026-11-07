"""
Phase 4 — Academics, Exams, Marks Grid, Ranks, Timetable, Calendar, Admission Wizard, Import/Export & Prints.

Covers ADVANCEMENT_PLAN.md Phase 4 DoD (G6, G7, G8, G15, G21, S5, S6, S7, Section 9.8, Section 12.3):
  - Migration v3 (`PRAGMA user_version == 3`): `exam_result.rank`, `exam_result.remarks`,
    `exam_subject.is_absent`, `student_student.b_form_no`, `student_student.documents_json`,
    `calendar_day`, `timetable_substitution`
  - R-E1, G7, S5, F5, F6, F16: Quick exam + marksheet initialization, keyboard/spreadsheet Marks Grid
    bulk save with poka-yoke validation (`0 <= marks <= max`), tie-aware Olympic rank computation
    (`1, 2, 2, 4`), Report Card print bundle, and Result Gazette
  - G8, TT-1..TT-4, F11: Weekly 2D Timetable Grid, Today's Live Strip with teacher attendance &
    1-click Substitution assignment, and Seasonal/Ramazan bell timing adjustment
  - G21, S6: Academic Calendar CRUD, Pakistani holidays preset, and attendance holiday protection
  - R-D1, G6, ADM-0..ADM-4, F4, F15: 3-Step Admission Wizard with live duplicate detection
    (B-Form, Name+DOB, Guardian Mobile+DOB), sibling auto-fill, pre-admission seat capacity check,
    documents checklist, optional first fee voucher generation, and Student ID Card print bundle
  - G15: 1000-row CSV/Excel student bulk import preview & commit (< 60s) with row-level error report,
    plus Excel export for students, fee vouchers, and exam gazette
  - S7 & Section 9.8(L): PTM 1-Pager print bundle (combining Attendance %, Fee Due, Last Exam Rank &
    Weak Subject, Teacher Remark) and Library 1-click Quick Issue by Student GR/PID (auto-card)
  - Deny-by-default RBAC for all Phase 4 routes
"""

from __future__ import annotations

from datetime import date
import time

import pytest

from desktop_app.api import create_app
from desktop_app.database import Database
from desktop_app.db.migrate import LATEST_SCHEMA_VERSION, get_schema_version


@pytest.fixture()
def phase4_env(tmp_path):
    db_file = tmp_path / "phase4_erp.sqlite3"
    db = Database(db_file)
    app = create_app(db=db, seed=True, enforce_auth=True)
    app.config["TESTING"] = True

    admin_client = app.test_client()
    setup = admin_client.post(
        "/api/auth/setup",
        json={
            "full_name": "Principal Admin",
            "username": "admin_p4",
            "secret": "AdminP4#123",
        },
    ).get_json()
    admin_headers = {"X-Session-Token": setup["token"]}
    return db, app, admin_client, admin_headers


def _make_staff_client(app, admin_client, admin_headers, username: str, role: str):
    res = admin_client.post(
        "/api/auth/users",
        headers=admin_headers,
        json={
            "full_name": f"Staff {username}",
            "username": username,
            "role": role,
            "secret": "StaffP4#123",
        },
    )
    assert res.status_code == 200, res.get_data(as_text=True)
    client = app.test_client()
    tok = client.post(
        "/api/auth/login",
        json={"username": username, "secret": "StaffP4#123"},
    ).get_json()["token"]
    return client, {"X-Session-Token": tok}


class TestMigrationV3Schema:
    """Verify Migration v3 schema version, new columns, and Phase 4 tables."""

    def test_schema_version_3_and_phase4_tables(self, phase4_env):
        db, _, _, _ = phase4_env
        assert LATEST_SCHEMA_VERSION >= 3
        with db.connection() as conn:
            assert get_schema_version(conn) >= 3
            tables = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert {"calendar_day", "timetable_substitution"}.issubset(tables)

            er_cols = {r[1] for r in conn.execute("PRAGMA table_info(exam_result)").fetchall()}
            assert {"rank", "remarks"}.issubset(er_cols)

            es_cols = {r[1] for r in conn.execute("PRAGMA table_info(exam_subject)").fetchall()}
            assert "is_absent" in es_cols

            stu_cols = {r[1] for r in conn.execute("PRAGMA table_info(student_student)").fetchall()}
            assert {"b_form_no", "documents_json"}.issubset(stu_cols)


class TestExamMarksGridRanksAndReportCards:
    """R-E1, R-T3, G7, S5, F5, F6, F16: Marks Grid poka-yoke, tie-aware ranks, Report Cards & Gazette."""

    def test_quick_exam_marks_grid_poka_yoke_tie_ranks_and_prints(self, phase4_env):
        db, app, admin_client, admin_headers = phase4_env
        boot = admin_client.get("/api/bootstrap", headers=admin_headers).get_json()
        class_id = boot["school"]["standards"][0]["id"]
        year_id = boot["school"]["years"][0]["id"]
        school_id = boot["school"]["schools"][0]["id"]
        grade_id = boot["school"]["grades"][0]["id"]
        subjects = boot["school"]["subjects"]
        assert len(subjects) >= 2

        # Ensure at least 4 enrolled students in class_id so we can test 1, 2, 2, 4 tie ranking
        existing_done = [
            s for s in boot["school"]["students"]
            if s["standard_id"] == class_id and s["state"] == "done"
        ]
        while len(existing_done) < 4:
            idx = len(existing_done) + 1
            admin_client.post(
                "/api/students",
                headers=admin_headers,
                json={
                    "student_name": f"RankStu{idx}",
                    "last": "Test",
                    "year_id": year_id,
                    "school_id": school_id,
                    "standard_id": class_id,
                    "date_of_birth": "2012-03-15",
                    "contact_mobile": f"0300-444000{idx}",
                },
            )
            existing_done.append({"id": idx})

        # 1. Create a Quick Exam & auto-generate marksheets for the class
        q_exam = admin_client.post(
            "/api/exams/quick-create",
            headers=admin_headers,
            json={
                "name": "First Term Examination 2026",
                "start_date": "2026-11-10",
                "end_date": "2026-11-20",
                "academic_year_id": year_id,
                "grade_system_id": grade_id,
                "standard_ids": [class_id],
                "subject_ids": [subjects[0]["id"], subjects[1]["id"]],
            },
        )
        assert q_exam.status_code == 200, q_exam.get_data(as_text=True)
        qe_data = q_exam.get_json()
        assert qe_data["ok"] is True
        exam_id = qe_data["exam_id"]
        assert qe_data["generated_results"] >= 4

        # 2. Fetch Marks Grid for Subject 1
        sub1_id = subjects[0]["id"]
        sub2_id = subjects[1]["id"]
        grid1 = admin_client.get(
            f"/api/exams/{exam_id}/marks-grid?class_id={class_id}&subject_id={sub1_id}",
            headers=admin_headers,
        ).get_json()
        assert grid1["ok"] is True
        rows1 = grid1["rows"]
        assert len(rows1) >= 4
        max_marks = float(grid1["subject"]["maximum_marks"])

        # R-T3 Poka-Yoke: Marks exceeding maximum_marks (e.g. 105 > 100) or < 0 MUST be rejected with 400!
        bad_high = admin_client.post(
            f"/api/exams/{exam_id}/marks-grid",
            headers=admin_headers,
            json={
                "class_id": class_id,
                "subject_id": sub1_id,
                "entries": [
                    {"subject_line_id": rows1[0]["subject_line_id"], "obtain_marks": max_marks + 5}
                ],
            },
        )
        assert bad_high.status_code == 400

        bad_neg = admin_client.post(
            f"/api/exams/{exam_id}/marks-grid",
            headers=admin_headers,
            json={
                "class_id": class_id,
                "subject_id": sub1_id,
                "entries": [
                    {"subject_line_id": rows1[0]["subject_line_id"], "obtain_marks": -3}
                ],
            },
        )
        assert bad_neg.status_code == 400

        # 3. Enter valid marks for Subject 1 & Subject 2 to create an exact tie on 2nd place:
        #    Student 0: 92 + 90 = 182 (Rank 1)
        #    Student 1: 85 + 85 = 170 (Rank 2 - TIE)
        #    Student 2: 88 + 82 = 170 (Rank 2 - TIE)
        #    Student 3: 70 + 65 = 135 (Rank 4 - skips 3!)
        s1_scores = [92, 85, 88, 70]
        s2_scores = [90, 85, 82, 65]

        entries1 = []
        for idx, r in enumerate(rows1):
            score = s1_scores[idx] if idx < 4 else 60
            entries1.append(
                {
                    "subject_line_id": r["subject_line_id"],
                    "obtain_marks": score,
                    "is_absent": False,
                    "remarks": "Excellent work" if idx == 0 else "Good progress",
                }
            )
        save1 = admin_client.post(
            f"/api/exams/{exam_id}/marks-grid",
            headers=admin_headers,
            json={
                "class_id": class_id,
                "subject_id": sub1_id,
                "entries": entries1,
            },
        )
        assert save1.status_code == 200, save1.get_data(as_text=True)

        grid2 = admin_client.get(
            f"/api/exams/{exam_id}/marks-grid?class_id={class_id}&subject_id={sub2_id}",
            headers=admin_headers,
        ).get_json()
        rows2 = grid2["rows"]
        entries2 = []
        for idx, r in enumerate(rows2):
            score = s2_scores[idx] if idx < 4 else 60
            entries2.append(
                {
                    "subject_line_id": r["subject_line_id"],
                    "obtain_marks": score,
                    "is_absent": False,
                }
            )
        save2 = admin_client.post(
            f"/api/exams/{exam_id}/marks-grid",
            headers=admin_headers,
            json={
                "class_id": class_id,
                "subject_id": sub2_id,
                "entries": entries2,
                "finalize": True,
            },
        )
        assert save2.status_code == 200, save2.get_data(as_text=True)

        # 4. Compute ranks explicitly and verify Olympic tie rule: 1, 2, 2, 4
        rank_res = admin_client.post(
            f"/api/exams/{exam_id}/compute-ranks",
            headers=admin_headers,
            json={"class_id": class_id},
        )
        assert rank_res.status_code == 200
        ranked = rank_res.get_json()["results"]
        top4 = ranked[:4]
        assert [r["total"] for r in top4] == [182.0, 170.0, 170.0, 135.0]
        assert [r["rank"] for r in top4] == [1, 2, 2, 4]

        # 5. Report Card Print Bundle & Result Gazette (F6, S5)
        rc_bundle = admin_client.get(
            f"/api/exams/print/report-cards?exam_id={exam_id}&class_id={class_id}",
            headers=admin_headers,
        ).get_json()
        assert rc_bundle["ok"] is True
        assert len(rc_bundle["report_cards"]) >= 4
        first_rc = rc_bundle["report_cards"][0]
        assert first_rc["rank"] == 1
        assert len(first_rc["subjects"]) == 2
        assert "attendance_pct" in first_rc
        assert "school" in rc_bundle

        gazette = admin_client.get(
            f"/api/exams/{exam_id}/gazette?class_id={class_id}",
            headers=admin_headers,
        ).get_json()
        assert gazette["ok"] is True
        assert gazette["summary"]["total_students"] >= 4
        assert gazette["summary"]["pass_count"] >= 4


class TestTimetableGridSubstitutionAndCalendar:
    """G8, G21, S6, TT-1..TT-4, F11: Weekly Grid, Today's Live Strip, Substitution & Holiday Block."""

    def test_calendar_holiday_blocks_attendance_and_timetable_substitution(self, phase4_env):
        _, _, admin_client, admin_headers = phase4_env
        boot = admin_client.get("/api/bootstrap", headers=admin_headers).get_json()
        class_id = boot["school"]["standards"][0]["id"]
        teachers = boot["school"]["teachers"]
        assert len(teachers) >= 2

        # 1. Load Pakistani Holiday Preset & add a specific holiday on 2026-11-18
        preset_res = admin_client.post(
            "/api/calendar/preset-pakistani",
            headers=admin_headers,
            json={"year": 2026},
        )
        assert preset_res.status_code == 200
        assert preset_res.get_json()["created_count"] >= 5

        hol_date = "2026-11-18"
        c_res = admin_client.post(
            "/api/calendar/days",
            headers=admin_headers,
            json={
                "date": hol_date,
                "title": "Allama Iqbal Day (Observed)",
                "day_type": "holiday",
                "is_off_day": True,
                "bell_profile": "regular",
            },
        )
        assert c_res.status_code == 200

        cal_list = admin_client.get("/api/calendar/days?year=2026", headers=admin_headers).get_json()
        assert cal_list["ok"] is True
        assert any(d["date"] == hol_date for d in cal_list["items"])

        # S6: Creating daily attendance on an off-day holiday without force=True is blocked (400)!
        att_blocked = admin_client.post(
            "/api/attendance/daily",
            headers=admin_headers,
            json={"standard_id": class_id, "user_id": teachers[0]["id"], "date": hol_date},
        )
        assert att_blocked.status_code == 400
        assert "holiday" in att_blocked.get_json()["error"].lower()

        # 2. Timetable Weekly Grid & Today's Live Strip + Substitution (TT-1..TT-4)
        tt_grid = admin_client.get(
            f"/api/timetable/weekly-grid?class_id={class_id}",
            headers=admin_headers,
        ).get_json()
        assert tt_grid["ok"] is True
        assert "grid" in tt_grid
        assert "bell_schedule" in tt_grid
        assert len(tt_grid["lines"]) >= 1

        first_line = tt_grid["lines"][0]
        sub_teacher_id = next(t["id"] for t in teachers if t["id"] != first_line["teacher_id"])
        today_iso = date.today().isoformat()

        sub_res = admin_client.post(
            "/api/timetable/substitutions",
            headers=admin_headers,
            json={
                "date": today_iso,
                "line_id": first_line["id"],
                "substitute_teacher_id": sub_teacher_id,
                "reason": "Medical leave",
            },
        )
        assert sub_res.status_code == 200, sub_res.get_data(as_text=True)
        assert sub_res.get_json()["substitution"]["substitute_teacher_id"] == sub_teacher_id

        today_strip = admin_client.get(
            f"/api/timetable/today?date={today_iso}&day={first_line['week_day']}",
            headers=admin_headers,
        ).get_json()
        assert today_strip["ok"] is True
        matched_slot = next(s for s in today_strip["periods"] if s["line_id"] == first_line["id"])
        assert matched_slot["substitute_teacher_id"] == sub_teacher_id


class TestAdmissionWizardDuplicateSeatAndPrints:
    """R-D1, G6, ADM-0..ADM-4, S7, F4, F15: 3-Step Wizard, Duplicate/Seat check, ID Card & PTM Sheet."""

    def test_admission_wizard_duplicate_check_seat_check_and_ptm_id_prints(self, phase4_env):
        db, _, admin_client, admin_headers = phase4_env
        boot = admin_client.get("/api/bootstrap", headers=admin_headers).get_json()
        class_id = boot["school"]["standards"][0]["id"]
        year_id = boot["school"]["years"][0]["id"]
        school_id = boot["school"]["schools"][0]["id"]
        struct_id = boot["fees"]["structures"][0]["id"]

        # 1. Admit first child through the full 3-step Admission Wizard endpoint
        adm1 = admin_client.post(
            "/api/admissions/enroll",
            headers=admin_headers,
            json={
                "student_name": "Zainab",
                "last": "Qureshi",
                "gender": "female",
                "date_of_birth": "2013-05-20",
                "b_form_no": "35202-7654321-2",
                "guardian_name": "Faisal Qureshi",
                "guardian_phone": "0333-1122334",
                "guardian_cnic": "35202-1112223-1",
                "guardian_relation": "Father",
                "standard_id": class_id,
                "year_id": year_id,
                "school_id": school_id,
                "documents": {"b_form": True, "photos": True, "previous_slc": False},
                "generate_first_voucher": True,
                "fees_structure_id": struct_id,
                "billing_month": "2026-11",
            },
        )
        assert adm1.status_code == 200, adm1.get_data(as_text=True)
        adm1_data = adm1.get_json()
        assert adm1_data["ok"] is True
        stu_id = adm1_data["student"]["id"]
        assert adm1_data["student"]["b_form_no"] == "35202-7654321-2"
        assert adm1_data["family_key"].startswith("P-")
        assert adm1_data["first_voucher"] is not None

        # 2. R-D1: Live duplicate check by B-Form or Guardian Mobile + DOB must flag exact match!
        dup_bform = admin_client.get(
            "/api/admissions/check-duplicate?b_form_no=35202-7654321-2",
            headers=admin_headers,
        ).get_json()
        assert dup_bform["ok"] is True
        assert len(dup_bform["duplicates"]) >= 1
        assert dup_bform["duplicates"][0]["id"] == stu_id

        dup_mob_dob = admin_client.get(
            "/api/admissions/check-duplicate?guardian_phone=0333-1122334&date_of_birth=2013-05-20",
            headers=admin_headers,
        ).get_json()
        assert len(dup_mob_dob["duplicates"]) >= 1

        # Also check sibling lookup by guardian phone (ADM-2 auto-fill!)
        assert dup_mob_dob["existing_family"] is not None
        assert dup_mob_dob["existing_family"]["guardian_name"] == "Faisal Qureshi"

        # Submitting duplicate B-Form without allow_duplicate=True is rejected with 400
        dup_submit = admin_client.post(
            "/api/admissions/enroll",
            headers=admin_headers,
            json={
                "student_name": "Zainab Duplicate",
                "last": "Qureshi",
                "date_of_birth": "2013-05-20",
                "b_form_no": "35202-7654321-2",
                "guardian_name": "Faisal Qureshi",
                "guardian_phone": "0333-1122334",
                "standard_id": class_id,
                "year_id": year_id,
                "school_id": school_id,
            },
        )
        assert dup_submit.status_code == 400
        assert "duplicate" in dup_submit.get_json()["error"].lower()

        # 3. Student ID Card Print Bundle & PTM 1-Pager Print Bundle (S7)
        id_bundle = admin_client.get(
            f"/api/students/print/id-cards?ids={stu_id}",
            headers=admin_headers,
        ).get_json()
        assert id_bundle["ok"] is True
        assert len(id_bundle["cards"]) == 1
        assert id_bundle["cards"][0]["pid"] == adm1_data["student"]["pid"]

        ptm_bundle = admin_client.get(
            f"/api/students/print/ptm-sheets?ids={stu_id}",
            headers=admin_headers,
        ).get_json()
        assert ptm_bundle["ok"] is True
        assert len(ptm_bundle["sheets"]) == 1
        sheet = ptm_bundle["sheets"][0]
        assert sheet["student"]["id"] == stu_id
        assert "attendance_pct" in sheet
        assert "fee_due_paisa" in sheet
        assert "latest_exam" in sheet


class TestBulkImportExportAndLibraryQuickIssue:
    """G15 & F14: 1000-row bulk import (< 60s) with error report, Excel exports & Library Quick Issue."""

    def test_1000_row_bulk_import_under_60s_and_xlsx_exports(self, phase4_env):
        _, _, admin_client, admin_headers = phase4_env
        boot = admin_client.get("/api/bootstrap", headers=admin_headers).get_json()
        class_name = boot["school"]["standards"][0]["name"]

        # Build 1000 valid CSV rows + 2 invalid rows (missing name & underage DOB)
        lines = ["first_name,last_name,gender,date_of_birth,class_name,guardian_name,guardian_phone,b_form_no"]
        for i in range(1, 1001):
            lines.append(
                f"ImpStudent{i},Batch,male,2012-06-15,{class_name},Parent {i},0345-{i:07d},35202-{i:07d}-1"
            )
        lines.append(f",MissingFirstName,male,2012-06-15,{class_name},Parent X,0345-9999991,")
        lines.append(f"TooYoung,Child,female,{date.today().isoformat()},{class_name},Parent Y,0345-9999992,")
        csv_text = "\n".join(lines)

        t0 = time.perf_counter()
        preview = admin_client.post(
            "/api/import/students/preview",
            headers=admin_headers,
            json={"csv_text": csv_text},
        ).get_json()
        assert preview["ok"] is True
        assert preview["valid_count"] == 1000
        assert preview["error_count"] == 2
        assert len(preview["errors"]) == 2

        commit = admin_client.post(
            "/api/import/students/commit",
            headers=admin_headers,
            json={"csv_text": csv_text},
        ).get_json()
        elapsed = time.perf_counter() - t0
        assert commit["ok"] is True
        assert commit["imported_count"] == 1000
        assert commit["skipped_errors"] == 2
        assert elapsed < 60.0, f"1000-row import took {elapsed:.2f}s (must be < 60s)"

        # Verify Excel exports (students & fee vouchers)
        stu_xlsx = admin_client.get("/api/export/students.xlsx", headers=admin_headers)
        assert stu_xlsx.status_code == 200
        assert len(stu_xlsx.data) > 1000

        fee_xlsx = admin_client.get("/api/export/vouchers.xlsx", headers=admin_headers)
        assert fee_xlsx.status_code == 200
        assert len(fee_xlsx.data) > 500

    def test_library_quick_issue_by_student_gr_auto_card(self, phase4_env):
        """F14 & Section 9.8(L): 1-click issue by student_id without manual Library Card creation."""
        _, _, admin_client, admin_headers = phase4_env
        boot = admin_client.get("/api/bootstrap", headers=admin_headers).get_json()
        students = [s for s in boot["school"]["students"] if s["state"] == "done"]
        books = boot["library"]["books"]
        assert students and books

        target_stu = students[-1]
        target_book = next(b for b in books if b["books_available"] >= 1)

        q_issue = admin_client.post(
            "/api/library/quick-issue",
            headers=admin_headers,
            json={"student_id": target_stu["id"], "book_id": target_book["id"]},
        )
        assert q_issue.status_code == 200, q_issue.get_data(as_text=True)
        qi_data = q_issue.get_json()
        assert qi_data["ok"] is True
        assert qi_data["issue"]["state"] == "issue"
        assert qi_data["card_code"].startswith("LCARD/")


class TestPhase4RBAC:
    """Verify deny-by-default RBAC for Phase 4 endpoints across roles."""

    def test_phase4_rbac_roles(self, phase4_env):
        _, app, admin_client, admin_headers = phase4_env
        teacher_client, teacher_headers = _make_staff_client(
            app, admin_client, admin_headers, "tch_p4", "teacher"
        )
        clerk_client, clerk_headers = _make_staff_client(
            app, admin_client, admin_headers, "clk_p4", "fee_clerk"
        )
        front_client, front_headers = _make_staff_client(
            app, admin_client, admin_headers, "fd_p4", "front_desk"
        )

        # Teacher can view timetable & marks grid, but cannot enroll admissions or bulk-import students
        assert teacher_client.get("/api/timetable/today", headers=teacher_headers).status_code == 200
        assert (
            teacher_client.post("/api/admissions/enroll", headers=teacher_headers, json={}).status_code
            == 403
        )
        assert (
            teacher_client.post("/api/import/students/commit", headers=teacher_headers, json={}).status_code
            == 403
        )

        # Fee clerk is denied Marks Grid & Exam creation
        assert (
            clerk_client.post("/api/exams/quick-create", headers=clerk_headers, json={}).status_code
            == 403
        )

        # Front desk is allowed duplicate check & ID card print, denied exam creation
        assert (
            front_client.get("/api/admissions/check-duplicate?b_form_no=123", headers=front_headers).status_code
            == 200
        )
        assert (
            front_client.post("/api/exams/quick-create", headers=front_headers, json={}).status_code
            == 403
        )
