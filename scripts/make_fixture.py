"""
scripts/make_fixture.py — Advanced Pakistani School Dataset & Telemetry Benchmark (D4)

Generates a realistic 210-student Pakistani private school SQLite database
(`tests/fixtures/pakistani_school_200.sqlite3`) and runs automated API
performance + workflow benchmarks, writing structured diagnostic logs to
`logs/phase1_telemetry.jsonl` so bottlenecks and improvements are measured with evidence.

Usage:
    python scripts/make_fixture.py
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import json
from pathlib import Path
import random
import sys
import time

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from desktop_app.api import create_app
from desktop_app.database import Database
from desktop_app.services.assignment_service import AssignmentService
from desktop_app.services.attendance_service import AttendanceService
from desktop_app.services.event_hostel_transport_service import (
    EventService,
    HostelService,
    TransportService,
)
from desktop_app.services.exam_service import ExamService
from desktop_app.services.fees_service import FeesService
from desktop_app.services.library_service import LibraryService
from desktop_app.services.school_service import SchoolService
from desktop_app.services.timetable_service import TimetableService

FIRST_NAMES_MALE = [
    "Muhammad Ibrahim", "Syed Hassan", "Hafiz Abdullah", "Umar Farooq",
    "Bilal Ahmed", "Zain Ul Abideen", "Hamza Ali", "Usman Ghani",
    "Saad Bin Tariq", "Huzaifa Majeed", "Fahad Mustafa", "Rayyan Qureshi",
    "Ahsan Iqbal", "Taha Siddiqui", "Mustafa Kamal", "Danish Mehmood",
    "Salman Haider", "Arslan Javed", "Talha Zubair", "Ammar Yasir",
]

FIRST_NAMES_FEMALE = [
    "Ayesha Noor", "Fatima Zahra", "Zainab Bibi", "Maryam Nawaz",
    "Khadija Tul Kubra", "Hafsa Siddiqui", "Amina Tariq", "Sana Javed",
    "Hira Mani", "Noor Ul Ain", "Mahnoor Baloch", "Iqra Aziz",
    "arooj Fatima", "duaa Zehra", "Aleena Raza", "Mehwish Hayat",
    "Bushra Ansari", "Rabia Basri", "Momina Mustehsan", "Laiba Khan",
]

FAMILY_SURNAMES = [
    "Khan", "Qureshi", "Siddiqui", "Raza", "Chaudhry", "Malik",
    "Sheikh", "Hashmi", "Cheema", "Bajwa", "Ansari", "Mirza",
    "Abbasi", "Gillani", "Mughal", "Butt", "Rana", "Farooqi",
]

TEACHERS_DATA = [
    ("Ustad Tariq Mahmood", "tariq.mahmood@alqalam.edu.pk", "0300-4112233", "Mathematics & Physics"),
    ("Dr. Ayesha Siddiqui", "ayesha.siddiqui@alqalam.edu.pk", "0321-4445566", "Computer Science"),
    ("Maulana Abdul Rehman", "abdul.rehman@alqalam.edu.pk", "0333-4889900", "Islamiyat & Urdu"),
    ("Ms. Nadia Jamil", "nadia.jamil@alqalam.edu.pk", "0345-4221100", "English Literature"),
    ("Sir Kamran Akmal", "kamran.akmal@alqalam.edu.pk", "0301-4776655", "Chemistry & Biology"),
    ("Ms. Farah Sadia", "farah.sadia@alqalam.edu.pk", "0312-4998877", "Pakistan Studies"),
]


def build_pakistani_school_fixture(db_path: Path, target_students: int = 210) -> dict:
    """Create a rich, non-generic Pakistani school fixture in SQLite."""
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    rng = random.Random(20261106)
    db = Database(db_path)
    school_svc = SchoolService(db)
    fees_svc = FeesService(db)
    att_svc = AttendanceService(db)

    t0 = time.perf_counter()
    today = date.today()

    # 1. BISE Lahore style Grading System
    grade_master = school_svc.create_grade_master(
        name="BISE Lahore Matriculation Grading",
        lines=[
            {"from_mark": 80, "to_mark": 100, "grade": "A+", "fail": False, "sequence": 1},
            {"from_mark": 70, "to_mark": 79.99, "grade": "A", "fail": False, "sequence": 2},
            {"from_mark": 60, "to_mark": 69.99, "grade": "B", "fail": False, "sequence": 3},
            {"from_mark": 50, "to_mark": 59.99, "grade": "C", "fail": False, "sequence": 4},
            {"from_mark": 33, "to_mark": 49.99, "grade": "D", "fail": False, "sequence": 5},
            {"from_mark": 0, "to_mark": 32.99, "grade": "F", "fail": True, "sequence": 6},
        ],
    )

    year_rec = school_svc.create_academic_year(
        sequence=1,
        name=f"Session {today.year}-{str(today.year + 1)[-2:]}",
        code=f"SES-{today.year}",
        date_start=date(today.year, 1, 1).isoformat(),
        date_stop=date(today.year, 12, 31).isoformat(),
        grade_id=grade_master["id"],
        current=True,
    )
    year_id = year_rec["id"]

    school_svc.create_academic_month(
        name=today.strftime("%B %Y"),
        code=today.strftime("%b-%y").upper(),
        date_start=date(today.year, today.month, 1).isoformat(),
        date_stop=today.isoformat(),
        year_id=year_id,
    )

    school_rec = school_svc.create_school(
        name="Al-Qalam Grammar High School (Lahore)",
        code="AQG-LHR",
        required_age=5,
        city="Lahore",
        contact_phone="042-35761990",
        currency_symbol="Rs.",
    )
    school_id = school_rec["id"]

    medium_id = school_svc.create_medium(sequence=1, name="English & Urdu Dual Medium", code="DUAL")["id"]
    div_a = school_svc.create_division(sequence=1, name="Section Iqbal", code="IQB")["id"]
    div_b = school_svc.create_division(sequence=2, name="Section Jinnah", code="JIN")["id"]

    # 2. Teachers
    teacher_ids: list[int] = []
    for t_name, t_email, t_phone, t_dept in TEACHERS_DATA:
        tid = school_svc.create_teacher(
            name=t_name,
            work_email=t_email,
            phone_numbers=t_phone,
            department=t_dept,
            school_id=school_id,
        )["id"]
        teacher_ids.append(tid)

    # 3. 6 Classes (Grade 6 through Grade 10 + 2 sections for Grade 9)
    class_configs = [
        (6, "Grade 6", div_a, "Room 101 - Ground Floor", teacher_ids[0]),
        (7, "Grade 7", div_a, "Room 102 - Ground Floor", teacher_ids[1]),
        (8, "Grade 8", div_a, "Room 201 - First Floor", teacher_ids[2]),
        (9, "Grade 9 (Sci)", div_a, "Room 202 - Science Block", teacher_ids[3]),
        (9, "Grade 9 (Arts)", div_b, "Room 203 - Iqbal Block", teacher_ids[4]),
        (10, "Grade 10 (Matric)", div_a, "Room 301 - Senior Wing", teacher_ids[5]),
    ]

    school_standard_ids: list[int] = []
    base_standard_ids: list[int] = []

    for idx, (seq, gname, div_id, room_name, tid) in enumerate(class_configs, start=1):
        base_std = school_svc.create_standard(
            sequence=seq * 10 + idx,
            name=gname,
            code=f"G{seq}-{idx}",
        )["id"]
        base_standard_ids.append(base_std)
        room_id = school_svc.create_classroom(name=room_name, number=f"R-{100 + idx}")["id"]
        ss_id = school_svc.create_school_standard(
            school_id=school_id,
            standard_id=base_std,
            division_id=div_id,
            medium_id=medium_id,
            capacity=45,
            user_id=tid,
            class_room_id=room_id,
        )["id"]
        school_standard_ids.append(ss_id)

    # 4. Generate 65 Pakistani Family Mobile Numbers (so siblings share guardian mobile)
    family_pool = []
    for f_idx in range(65):
        surname = FAMILY_SURNAMES[f_idx % len(FAMILY_SURNAMES)]
        prefix = rng.choice(["0300", "0321", "0333", "0345", "0312"])
        mobile = f"{prefix}-{4100000 + f_idx * 137:07d}"
        family_pool.append((surname, mobile))

    # 5. Admit 210 Students distributed across the 6 classes
    admitted_ids: list[int] = []
    for i in range(target_students):
        ss_id = school_standard_ids[i % len(school_standard_ids)]
        surname, guardian_mobile = family_pool[i % len(family_pool)]
        is_female = (i % 2 == 1)
        first_name = (
            FIRST_NAMES_FEMALE[(i // 2) % len(FIRST_NAMES_FEMALE)]
            if is_female
            else FIRST_NAMES_MALE[(i // 2) % len(FIRST_NAMES_MALE)]
        )
        dob_year = today.year - rng.randint(11, 16)
        dob_month = rng.randint(1, 12)
        dob_day = rng.randint(1, 28)

        stu = school_svc.create_student(
            student_name=first_name.title(),
            middle="",
            last=surname,
            year_id=year_id,
            school_id=school_id,
            standard_id=ss_id,
            date_of_birth=date(dob_year, dob_month, dob_day).isoformat(),
            admission_date=(today - timedelta(days=rng.randint(30, 180))).isoformat(),
            gender="female" if is_female else "male",
            email=f"stu{i + 1}@alqalam.edu.pk",
            contact_mobile=guardian_mobile,
        )
        # Keep ~5% in draft state to test "Admit" button in UI, admit the rest
        if i % 20 != 0:
            school_svc.admission_done(stu["id"])
            admitted_ids.append(stu["id"])

    for ss_id in school_standard_ids:
        school_svc.assign_roll_no(standard_id=ss_id, medium_id=medium_id)

    # 6. Create Fee Structure & Class-wise Fee Registers
    fee_struct = fees_svc.create_fees_structure(
        name="Matriculation Monthly Fee Challan",
        code="CHALLAN-STD",
        lines=[
            {"name": "Monthly Tuition Fee", "code": "TUI", "type": "month", "amount": 6500.0},
            {"name": "Computer & Science Lab", "code": "LAB", "type": "month", "amount": 1200.0},
            {"name": "Generator & Allied Charges", "code": "GEN", "type": "month", "amount": 500.0},
        ],
    )
    reg = fees_svc.create_fees_register(
        name=f"Grade 6 & 7 Fee Register — {today.strftime('%B %Y')}",
        register_date=today.isoformat(),
        fees_structure_id=fee_struct["id"],
        standard_id=base_standard_ids[0],
    )
    fees_svc.fees_register_confirm(reg["id"])
    slips = fees_svc.list_payslips()
    for idx, slip in enumerate(slips):
        fees_svc.payslip_confirm(slip["id"])
        if idx % 2 == 0:
            fees_svc.student_pay_fees(slip["id"], payment_amount=8200.0)

    # 7. Create Multi-Day Attendance History + Today's Sheets
    # Validate Class 1 for yesterday; keep Class 1 & Class 2 ready for today
    yesterday = (today - timedelta(days=1)).isoformat()
    att_yest = att_svc.create_daily_attendance(
        standard_id=school_standard_ids[0],
        user_id=teacher_ids[0],
        att_date=yesterday,
    )
    att_svc.attendance_validate(att_yest["id"])

    # Create today's DRAFT attendance sheet on Class 1 so teacher can immediately test bulk-mark
    att_today_draft = att_svc.create_daily_attendance(
        standard_id=school_standard_ids[0],
        user_id=teacher_ids[0],
        att_date=today.isoformat(),
    )

    # 8. Subjects, Assignments, Timetable, Exam, Library, Events, Hostel, Transport
    assign_svc = AssignmentService(db)
    tt_svc = TimetableService(db)
    exam_svc = ExamService(db)
    lib_svc = LibraryService(db)
    event_svc = EventService(db)
    hostel_svc = HostelService(db)
    trans_svc = TransportService(db)

    sub_math = school_svc.create_subject(
        name="Mathematics (Al-Jabr)",
        code="MATH-06",
        maximum_marks=100,
        minimum_marks=33,
        standard_id=base_standard_ids[0],
        school_standard_ids=school_standard_ids[:2],
        teacher_ids=[teacher_ids[0]],
    )["id"]
    sub_cs = school_svc.create_subject(
        name="Computer Science",
        code="CS-06",
        maximum_marks=100,
        minimum_marks=33,
        standard_id=base_standard_ids[0],
        school_standard_ids=school_standard_ids[:2],
        teacher_ids=[teacher_ids[1]],
    )["id"]

    fmt_id = assign_svc.create_file_format(name="pdf")["id"]
    t_assign_id = assign_svc.create_teacher_assignment(
        name="Chapter 4: Algebraic Expressions & Factorization",
        subject_id=sub_math,
        standard_id=school_standard_ids[0],
        teacher_id=teacher_ids[0],
        assign_date=today.isoformat(),
        due_date=(today + timedelta(days=7)).isoformat(),
        type_submission="softcopy",
        file_format_id=fmt_id,
        attached_homework="Solve BISE exercise 4.1 to 4.3 completely.",
    )["id"]
    assign_svc.active_teacher_assignment(t_assign_id)

    tt_svc.create_timetable(
        name="Grade 6 (Section Iqbal) Regular Schedule",
        standard_id=school_standard_ids[0],
        year_id=year_id,
        timetable_type="regular",
        class_room_id=1,
        lines=[
            {
                "teacher_id": teacher_ids[0],
                "subject_id": sub_math,
                "start_time": 8.0,
                "end_time": 9.0,
                "week_day": "monday",
                "class_room_id": 1,
            },
            {
                "teacher_id": teacher_ids[1],
                "subject_id": sub_cs,
                "start_time": 9.0,
                "end_time": 10.0,
                "week_day": "monday",
                "class_room_id": 1,
            },
        ],
    )

    exam_tt_id = tt_svc.create_timetable(
        name="First Term Examination Date Sheet — Grade 6",
        standard_id=school_standard_ids[0],
        year_id=year_id,
        timetable_type="exam",
        class_room_id=1,
        lines=[
            {
                "teacher_id": teacher_ids[0],
                "subject_id": sub_math,
                "start_time": 9.0,
                "end_time": 12.0,
                "exm_date": (today + timedelta(days=2)).isoformat(),
                "class_room_id": 1,
            },
        ],
    )["id"]

    exam_id = exam_svc.create_exam(
        name="First Term Examination 2026",
        start_date=(today + timedelta(days=1)).isoformat(),
        end_date=(today + timedelta(days=10)).isoformat(),
        grade_system_id=grade_master["id"],
        academic_year_id=year_id,
        standard_ids=[base_standard_ids[0]],
        schedule_lines=[{"standard_id": school_standard_ids[0], "timetable_id": exam_tt_id}],
    )
    exam_svc.set_exam_running(exam_id)
    res_ids = exam_svc.generate_result(exam_id)
    for idx, r_id in enumerate(res_ids[:10]):
        sub_rows = db.fetch_all("SELECT id FROM exam_subject WHERE exam_id = ?", (r_id,))
        for s_idx, sr in enumerate(sub_rows):
            exam_svc.update_exam_subject_marks(sr["id"], obtain_marks=max(40.0, 92.0 - (idx * 3) - (s_idx * 4)))
        exam_svc.confirm_exam_result(r_id)

    rack_id = lib_svc.create_rack("Iqbal Hall — Science & Islamic Studies", "RACK-IQB-01")
    author_id = lib_svc.create_author("Allama Muhammad Iqbal", biography="Poet of the East & Philosopher")
    book1_id = lib_svc.create_book(
        name="Kulliyat-e-Iqbal (Urdu & Persian)",
        isbn="978-969-416-001-2",
        code="BK-IQB-01",
        barcode="BC-9789694160012",
        author_id=author_id,
        rack_id=rack_id,
        qty_available=8,
        day_to_return_book=14,
        fine_late_return=20.0,
        fine_lost=1200.0,
    )
    card1_id = lib_svc.create_library_card(
        user="student",
        student_id=admitted_ids[0],
        book_limit=3,
        start_date=today.isoformat(),
        duration=12,
    )
    lib_svc.running_state_card(card1_id)
    issue1_id = lib_svc.create_book_issue(book1_id, card1_id, date_issue=today.isoformat())
    lib_svc.issue_book(issue1_id)

    ev_id = event_svc.create_event(
        name="Annual Milad & Qiraat Competition",
        start_date=(today + timedelta(days=5)).isoformat(),
        end_date=(today + timedelta(days=6)).isoformat(),
        event_type="intra",
        contact_teacher_id=teacher_ids[2],
        standard_ids=school_standard_ids[:3],
    )
    ev_reg_id = event_svc.create_registration(ev_id, admitted_ids[0])
    event_svc.confirm_registration(ev_reg_id)

    hostel_id = hostel_svc.create_hostel_type(
        name="Jinnah Scholars Boys Hostel",
        hostel_type="male",
        rector_name="Sir Kamran Akmal",
        city="Lahore",
    )
    h_room_id = hostel_svc.create_hostel_room(
        hostel_id=hostel_id,
        room_no="B-101",
        floor_no=1,
        student_per_room=4,
        rent_amount=7500.0,
    )
    hs_id = hostel_svc.create_hostel_student(
        student_id=admitted_ids[1],
        hostel_info_id=hostel_id,
        room_id=h_room_id,
        duration=6,
        admission_date=today.isoformat(),
    )
    hostel_svc.reservation_state(hs_id)
    hostel_svc.pay_hostel_fees(hs_id)

    veh1_id = trans_svc.create_vehicle(
        license_plate="LEB-2026",
        model_name="Hino Pak School Coaster",
        driver_name="Ustad Muhammad Rafiq",
        driver_licence_no="DL-LHR-99881",
        seats=32,
    )
    route_id = trans_svc.create_transport_route(
        name="Route 1 — Gulberg, Model Town & Johar Town",
        start_date=today.isoformat(),
        end_date=(today + timedelta(days=180)).isoformat(),
        amount=4000.0,
        contact_person="Ustad Muhammad Rafiq",
        vehicle_ids=[veh1_id],
    )
    trans_svc.transport_open(route_id)
    tr_reg_id = trans_svc.create_transport_registration(
        route_id=route_id,
        student_id=admitted_ids[1],
        vehicle_id=veh1_id,
        registration_month=3,
        reg_date=today.isoformat(),
    )
    trans_svc.trans_regi_confirm(tr_reg_id)
    trans_svc.pay_transport_fees(tr_reg_id)

    build_sec = round(time.perf_counter() - t0, 2)
    return {
        "db_path": str(db_path),
        "students_created": target_students,
        "admitted_count": len(admitted_ids),
        "classes_count": len(school_standard_ids),
        "families_count": len(family_pool),
        "draft_attendance_id": att_today_draft["id"],
        "first_class_id": school_standard_ids[0],
        "build_seconds": build_sec,
    }


def run_telemetry_benchmarks(db_path: Path, meta: dict, log_path: Path) -> dict:
    """Run API benchmarks on the 210-student fixture and write JSONL telemetry logs."""
    db = Database(db_path)
    app = create_app(db=db, seed=False)
    app.config["TESTING"] = True

    metrics: dict[str, dict] = {}

    with app.test_client() as client:
        # 1. Measure Legacy /api/bootstrap (loads everything)
        t0 = time.perf_counter()
        r_boot = client.get("/api/bootstrap")
        boot_ms = round((time.perf_counter() - t0) * 1000, 2)
        boot_kb = round(len(r_boot.data) / 1024, 2)
        metrics["bootstrap_210_students"] = {"ms": boot_ms, "kb": boot_kb, "status": r_boot.status_code}

        # 2. Measure Phase 1 Paginated /api/students/list (page 1, 50 items)
        t0 = time.perf_counter()
        r_list = client.get("/api/students/list?page=1&per_page=50")
        list_ms = round((time.perf_counter() - t0) * 1000, 2)
        list_kb = round(len(r_list.data) / 1024, 2)
        metrics["students_paginated_p1"] = {"ms": list_ms, "kb": list_kb, "status": r_list.status_code}

        # 3. Measure Sibling / Guardian Mobile Search
        t0 = time.perf_counter()
        r_fam = client.get("/api/students/list?q=0300-4100000")
        fam_ms = round((time.perf_counter() - t0) * 1000, 2)
        fam_json = r_fam.get_json()
        metrics["guardian_mobile_search"] = {
            "ms": fam_ms,
            "matches": fam_json.get("total", 0),
            "status": r_fam.status_code,
        }

        # 4. Measure Today Attendance Fetch
        cid = meta["first_class_id"]
        t0 = time.perf_counter()
        r_today = client.get(f"/api/attendance/today/{cid}")
        today_ms = round((time.perf_counter() - t0) * 1000, 2)
        att_data = r_today.get_json().get("attendance")
        lines = att_data.get("student_ids", []) if att_data else []
        metrics["attendance_today_fetch"] = {
            "ms": today_ms,
            "class_size": len(lines),
            "status": r_today.status_code,
        }

        # 5. Measure Bulk-Mark Attendance (mark 4 students absent in 1 transaction)
        att_id = meta["draft_attendance_id"]
        payload = [
            {"line_id": l["id"], "is_absent": (idx < 4)}
            for idx, l in enumerate(lines)
        ]
        t0 = time.perf_counter()
        r_bulk = client.post(
            f"/api/attendance/daily/{att_id}/bulk-mark",
            data=json.dumps({"lines": payload}),
            content_type="application/json",
        )
        bulk_ms = round((time.perf_counter() - t0) * 1000, 2)
        bulk_json = r_bulk.get_json()
        metrics["attendance_bulk_mark"] = {
            "ms": bulk_ms,
            "students_marked": len(payload),
            "absent_count": bulk_json.get("total_absent"),
            "status": r_bulk.status_code,
        }

        # 6. Measure Global Search (/api/search?q=Khan)
        t0 = time.perf_counter()
        r_search = client.get("/api/search?q=Khan")
        search_ms = round((time.perf_counter() - t0) * 1000, 2)
        search_json = r_search.get_json()
        metrics["global_search"] = {
            "ms": search_ms,
            "results_count": len(search_json.get("results", [])),
            "status": r_search.status_code,
        }

    speedup_x = round(boot_ms / max(list_ms, 0.1), 1)
    payload_reduction_pct = round((1 - (list_kb / max(boot_kb, 0.1))) * 100, 1)

    record = {
        "timestamp": datetime.now().isoformat(),
        "phase": "Phase 1",
        "fixture": meta,
        "benchmarks": metrics,
        "improvements": {
            "students_list_speedup_vs_bootstrap": f"{speedup_x}x faster",
            "payload_reduction_pct": f"{payload_reduction_pct}% smaller payload",
            "all_within_phase1_budget": (
                list_ms < 300 and search_ms < 150 and bulk_ms < 200
            ),
        },
    }

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return record


if __name__ == "__main__":
    import shutil
    fixture_db = ROOT_DIR / "tests" / "fixtures" / "pakistani_school_200.sqlite3"
    default_db = ROOT_DIR / "school_erp.sqlite3"
    telemetry_log = ROOT_DIR / "logs" / "phase1_telemetry.jsonl"

    print("Building 210-student Pakistani School fixture (all 10 modules)...")
    meta_info = build_pakistani_school_fixture(fixture_db, target_students=210)
    print(f"Fixture ready in {meta_info['build_seconds']}s -> {fixture_db}")

    shutil.copy2(fixture_db, default_db)
    print(f"Default runtime database populated -> {default_db}")

    print("Running Phase 1 telemetry & API benchmarks...")
    report = run_telemetry_benchmarks(fixture_db, meta_info, telemetry_log)

    print("\n=== PHASE 1 BENCHMARK & TELEMETRY SUMMARY ===")
    for k, v in report["benchmarks"].items():
        print(f"  {k:28s} : {v}")
    print("  -------------------------------------------")
    for k, v in report["improvements"].items():
        print(f"  {k:28s} : {v}")
    print(f"\nTelemetry appended to: {telemetry_log}")
