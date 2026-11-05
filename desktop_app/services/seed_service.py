"""Idempotent demo/seed data initializer for all 10 School Management ERP modules."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

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


def ensure_seed_data(db: Database) -> dict[str, Any]:
    """Populate initial School Management ERP records across all 10 modules if DB is empty."""
    existing = db.fetch_one("SELECT COUNT(*) AS cnt FROM school_school")
    if existing and int(existing["cnt"]) > 0:
        return {"seeded": False}

    school_svc = SchoolService(db)
    fees_svc = FeesService(db)
    att_svc = AttendanceService(db)
    assign_svc = AssignmentService(db)
    tt_svc = TimetableService(db)
    exam_svc = ExamService(db)
    lib_svc = LibraryService(db)
    event_svc = EventService(db)
    hostel_svc = HostelService(db)
    trans_svc = TransportService(db)

    today = date.today()
    year_start = date(today.year, 1, 1)
    year_end = date(today.year, 12, 31)
    month_start = date(today.year, today.month, 1)
    if today.month == 12:
        month_end = date(today.year, 12, 31)
    else:
        month_end = date(today.year, today.month + 1, 1) - timedelta(days=1)

    # 1. Module 1: Core School, Grading, Academic Year, Standards, Teachers, Students
    grade_master = school_svc.create_grade_master(
        name="Standard GPA & Letter Grading",
        lines=[
            {"from_mark": 85, "to_mark": 100, "grade": "A+", "fail": False, "sequence": 1},
            {"from_mark": 70, "to_mark": 84.99, "grade": "A", "fail": False, "sequence": 2},
            {"from_mark": 55, "to_mark": 69.99, "grade": "B", "fail": False, "sequence": 3},
            {"from_mark": 35, "to_mark": 54.99, "grade": "C", "fail": False, "sequence": 4},
            {"from_mark": 0, "to_mark": 34.99, "grade": "F", "fail": True, "sequence": 5},
        ],
    )
    grade_master_id = grade_master["id"]

    year_rec = school_svc.create_academic_year(
        sequence=1,
        name=f"Academic Year {today.year}",
        code=f"AY-{today.year}",
        date_start=year_start.isoformat(),
        date_stop=year_end.isoformat(),
        grade_id=grade_master_id,
        current=True,
    )
    year_id = year_rec["id"]

    next_year_rec = school_svc.create_academic_year(
        sequence=2,
        name=f"Academic Year {today.year + 1}",
        code=f"AY-{today.year + 1}",
        date_start=date(today.year + 1, 1, 1).isoformat(),
        date_stop=date(today.year + 1, 12, 31).isoformat(),
        grade_id=grade_master_id,
        current=False,
    )
    next_year_id = next_year_rec["id"]

    month_rec = school_svc.create_academic_month(
        name=today.strftime("%B %Y"),
        code=today.strftime("%b-%y").upper(),
        date_start=month_start.isoformat(),
        date_stop=month_end.isoformat(),
        year_id=year_id,
    )
    month_id = month_rec["id"]

    school_rec = school_svc.create_school(
        name="Greenfield International Academy",
        code="GIA-01",
        required_age=6,
        city="Lahore",
        contact_phone="+92-42-35761000",
        currency_symbol="Rs.",
    )
    school_id = school_rec["id"]

    medium_id = school_svc.create_medium(sequence=1, name="English Medium", code="ENG")["id"]
    div_a_id = school_svc.create_division(sequence=1, name="Section A", code="SEC-A")["id"]
    std_9_base = school_svc.create_standard(sequence=9, name="Grade 9", code="G9")["id"]
    std_10_base = school_svc.create_standard(sequence=10, name="Grade 10", code="G10")["id"]

    room_101 = school_svc.create_classroom(name="Room 101 - Main Wing", number="R-101")["id"]
    room_102 = school_svc.create_classroom(name="Room 102 - Science Wing", number="R-102")["id"]

    t1_id = school_svc.create_teacher(
        name="Prof. Tariq Mahmood",
        work_email="tariq.mahmood@greenfield.edu",
        phone_numbers="0300-1112233",
        department="Mathematics & Physics",
        school_id=school_id,
    )["id"]
    t2_id = school_svc.create_teacher(
        name="Dr. Ayesha Siddiqui",
        work_email="ayesha.siddiqui@greenfield.edu",
        phone_numbers="0321-4445566",
        department="Computer Science & English",
        school_id=school_id,
    )["id"]

    class_9_id = school_svc.create_school_standard(
        school_id=school_id,
        standard_id=std_9_base,
        division_id=div_a_id,
        medium_id=medium_id,
        capacity=35,
        user_id=t1_id,
        class_room_id=room_101,
    )["id"]
    class_10_id = school_svc.create_school_standard(
        school_id=school_id,
        standard_id=std_10_base,
        division_id=div_a_id,
        medium_id=medium_id,
        capacity=35,
        user_id=t2_id,
        class_room_id=room_102,
    )["id"]

    sub_math = school_svc.create_subject(
        name="Mathematics",
        code="MATH-09",
        maximum_marks=100,
        minimum_marks=35,
        standard_id=std_9_base,
        school_standard_ids=[class_9_id, class_10_id],
        teacher_ids=[t1_id],
    )["id"]
    sub_cs = school_svc.create_subject(
        name="Computer Science",
        code="CS-09",
        maximum_marks=100,
        minimum_marks=35,
        standard_id=std_9_base,
        school_standard_ids=[class_9_id, class_10_id],
        teacher_ids=[t2_id],
    )["id"]

    stu1_id = school_svc.create_student(
        student_name="Hamza",
        middle="Ali",
        last="Khan",
        year_id=year_id,
        school_id=school_id,
        standard_id=class_9_id,
        date_of_birth=date(today.year - 14, 5, 12).isoformat(),
        admission_date=today.isoformat(),
        gender="male",
        email="hamza.khan@student.edu",
        contact_mobile="0333-9001122",
    )["id"]
    school_svc.admission_done(stu1_id)

    stu2_id = school_svc.create_student(
        student_name="Fatima",
        middle="Zahra",
        last="Ahmed",
        year_id=year_id,
        school_id=school_id,
        standard_id=class_9_id,
        date_of_birth=date(today.year - 14, 8, 20).isoformat(),
        admission_date=today.isoformat(),
        gender="female",
        email="fatima.ahmed@student.edu",
        contact_mobile="0333-9003344",
    )["id"]
    school_svc.admission_done(stu2_id)

    stu3_id = school_svc.create_student(
        student_name="Zain",
        middle="Ul",
        last="Abideen",
        year_id=year_id,
        school_id=school_id,
        standard_id=class_9_id,
        date_of_birth=date(today.year - 15, 2, 10).isoformat(),
        admission_date=today.isoformat(),
        gender="male",
        email="zain.abideen@student.edu",
        contact_mobile="0333-9005566",
    )["id"]
    school_svc.admission_done(stu3_id)
    school_svc.assign_roll_no(standard_id=class_9_id, medium_id=medium_id)

    # 2. Module 2: School Fees
    fee_struct_id = fees_svc.create_fees_structure(
        name="Grade 9 Standard Fee Structure",
        code="FS-G9",
        lines=[
            {"name": "Monthly Tuition Fee", "code": "TUI", "type": "month", "amount": 8500.0},
            {"name": "Science & Computer Lab Fee", "code": "LAB", "type": "month", "amount": 1500.0},
            {"name": "Sports & Activity Fund", "code": "SPT", "type": "year", "amount": 1000.0},
        ],
    )["id"]
    reg_id = fees_svc.create_fees_register(
        name=f"Grade 9 Fees - {today.strftime('%B %Y')}",
        register_date=today.isoformat(),
        fees_structure_id=fee_struct_id,
        standard_id=std_9_base,
    )["id"]
    fees_svc.fees_register_confirm(reg_id)
    slips = fees_svc.list_payslips()
    if slips:
        fees_svc.payslip_confirm(slips[0]["id"])
        fees_svc.student_pay_fees(slips[0]["id"], payment_amount=11000.0)

    # 3. Module 3: School Attendance
    att_id = att_svc.create_daily_attendance(
        standard_id=class_9_id,
        user_id=t1_id,
        att_date=today.isoformat(),
    )["id"]
    att_svc.attendance_validate(att_id)

    # 4. Module 4: Assignment
    fmt_id = assign_svc.create_file_format(name="pdf")["id"]
    t_assign_id = assign_svc.create_teacher_assignment(
        name="Quadratic Equations & Linear Algebra Problem Set",
        subject_id=sub_math,
        standard_id=class_9_id,
        teacher_id=t1_id,
        assign_date=today.isoformat(),
        due_date=(today + timedelta(days=7)).isoformat(),
        type_submission="softcopy",
        file_format_id=fmt_id,
        attached_homework="Solve exercises 4.1 to 4.4 with complete steps.",
    )["id"]
    assign_svc.active_teacher_assignment(t_assign_id)

    # 5. Module 5: Timetable (Regular + Exam)
    tt_svc.create_timetable(
        name="Grade 9-A Weekly Regular Schedule",
        standard_id=class_9_id,
        year_id=year_id,
        timetable_type="regular",
        class_room_id=room_101,
        lines=[
            {
                "teacher_id": t1_id,
                "subject_id": sub_math,
                "start_time": 8.0,
                "end_time": 9.0,
                "week_day": "monday",
                "class_room_id": room_101,
            },
            {
                "teacher_id": t2_id,
                "subject_id": sub_cs,
                "start_time": 9.0,
                "end_time": 10.0,
                "week_day": "monday",
                "class_room_id": room_101,
            },
        ],
    )

    exam_tt_id = tt_svc.create_timetable(
        name="Mid-Term Examination Timetable - Grade 9",
        standard_id=class_9_id,
        year_id=year_id,
        timetable_type="exam",
        class_room_id=room_101,
        lines=[
            {
                "teacher_id": t1_id,
                "subject_id": sub_math,
                "start_time": 9.0,
                "end_time": 12.0,
                "exm_date": (today + timedelta(days=2)).isoformat(),
                "class_room_id": room_101,
            },
            {
                "teacher_id": t2_id,
                "subject_id": sub_cs,
                "start_time": 9.0,
                "end_time": 12.0,
                "exm_date": (today + timedelta(days=3)).isoformat(),
                "class_room_id": room_101,
            },
        ],
    )["id"]

    # 6. Module 6: Exam & Results
    exam_id = exam_svc.create_exam(
        name="Mid-Term Examination",
        start_date=(today + timedelta(days=1)).isoformat(),
        end_date=(today + timedelta(days=10)).isoformat(),
        grade_system_id=grade_master_id,
        academic_year_id=year_id,
        standard_ids=[std_9_base],
        schedule_lines=[{"standard_id": class_9_id, "timetable_id": exam_tt_id}],
    )
    exam_svc.set_exam_running(exam_id)
    res_ids = exam_svc.generate_result(exam_id)
    for idx, r_id in enumerate(res_ids):
        sub_rows = db.fetch_all("SELECT id FROM exam_subject WHERE exam_id = ?", (r_id,))
        for s_idx, sr in enumerate(sub_rows):
            exam_svc.update_exam_subject_marks(sr["id"], obtain_marks=88.0 - (idx * 6) - (s_idx * 4))
        exam_svc.confirm_exam_result(r_id)

    # 7. Module 7: Library
    rack_id = lib_svc.create_rack("Computer Science & Math Shelf", "RACK-CS-01")
    author_id = lib_svc.create_author("Donald E. Knuth", biography="Author of The Art of Computer Programming")
    book1_id = lib_svc.create_book(
        name="Introduction to Algorithms & Discrete Mathematics",
        isbn="978-0-262-03384-8",
        code="BK-001",
        barcode="BC-9780262033848",
        author_id=author_id,
        rack_id=rack_id,
        qty_available=5,
        day_to_return_book=14,
        fine_late_return=20.0,
        fine_lost=1500.0,
    )
    lib_svc.create_book(
        name="Modern Physics & Calculus Fundamentals",
        isbn="978-0-321-50062-5",
        code="BK-002",
        barcode="BC-9780321500625",
        author_id=author_id,
        rack_id=rack_id,
        qty_available=3,
        day_to_return_book=14,
        fine_late_return=20.0,
        fine_lost=1200.0,
    )
    card1_id = lib_svc.create_library_card(
        user="student",
        student_id=stu1_id,
        book_limit=3,
        start_date=today.isoformat(),
        duration=12,
    )
    lib_svc.running_state_card(card1_id)
    issue1_id = lib_svc.create_book_issue(book1_id, card1_id, date_issue=today.isoformat())
    lib_svc.issue_book(issue1_id)

    # 8. Module 8: School Event
    ev_id = event_svc.create_event(
        name="Annual Science & Robotics Olympiad",
        start_date=(today + timedelta(days=5)).isoformat(),
        end_date=(today + timedelta(days=7)).isoformat(),
        event_type="inter",
        contact_teacher_id=t2_id,
        standard_ids=[class_9_id],
    )
    ev_reg_id = event_svc.create_registration(ev_id, stu1_id)
    event_svc.confirm_registration(ev_reg_id)

    # 9. Module 9: School Hostel
    hostel_id = hostel_svc.create_hostel_type(
        name="Jinnah Boys Hostel",
        hostel_type="male",
        rector_name="Mr. Kamran Akmal",
        city="Lahore",
    )
    h_room_id = hostel_svc.create_hostel_room(
        hostel_id=hostel_id,
        room_no="B-101",
        floor_no=1,
        student_per_room=3,
        rent_amount=6000.0,
    )
    hs_id = hostel_svc.create_hostel_student(
        student_id=stu1_id,
        hostel_info_id=hostel_id,
        room_id=h_room_id,
        duration=6,
        admission_date=today.isoformat(),
    )
    hostel_svc.reservation_state(hs_id)
    hostel_svc.pay_hostel_fees(hs_id)

    # 10. Module 10: School Transport
    veh1_id = trans_svc.create_vehicle(
        license_plate="LEB-2026",
        model_name="Hino School Coaster",
        driver_name="Muhammad Rafiq",
        driver_licence_no="DL-LHR-99881",
        seats=28,
    )
    veh2_id = trans_svc.create_vehicle(
        license_plate="LEB-4050",
        model_name="Toyota Hiace Commuter",
        driver_name="Rashid Minhas",
        driver_licence_no="DL-LHR-99882",
        seats=16,
    )
    route_id = trans_svc.create_transport_route(
        name="Route 1 - Gulberg & Model Town Express",
        start_date=today.isoformat(),
        end_date=(today + timedelta(days=180)).isoformat(),
        amount=3500.0,
        contact_person="Muhammad Rafiq",
        vehicle_ids=[veh1_id, veh2_id],
    )
    trans_svc.transport_open(route_id)
    tr_reg_id = trans_svc.create_transport_registration(
        route_id=route_id,
        student_id=stu2_id,
        vehicle_id=veh1_id,
        registration_month=3,
        reg_date=today.isoformat(),
    )
    trans_svc.trans_regi_confirm(tr_reg_id)
    trans_svc.pay_transport_fees(tr_reg_id)

    return {
        "seeded": True,
        "school_id": school_id,
        "year_id": year_id,
        "next_year_id": next_year_id,
        "month_id": month_id,
        "class_9_id": class_9_id,
        "class_10_id": class_10_id,
    }
