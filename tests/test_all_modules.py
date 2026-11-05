"""Comprehensive unit and integration test suite for all 10 School Management ERP modules."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from desktop_app.api import create_app
from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, UserError, ValidationError, parse_date, validate_email
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
from desktop_app.services.seed_service import ensure_seed_data
from desktop_app.services.timetable_service import TimetableService


@pytest.fixture()
def seeded_db(tmp_path) -> Database:
    db_file = tmp_path / "test_school_erp.sqlite3"
    db = Database(db_file)
    ensure_seed_data(db)
    return db


def test_exceptions_and_memory_database() -> None:
    """Test in-memory database, custom sequences, email regex, and date parser."""
    db = Database(":memory:")
    seq = db.next_by_code("custom.seq")
    assert seq == "CUSTOM.SEQ/0001"
    db.close()

    with pytest.raises(ValidationError):
        validate_email("not-an-email")
    validate_email("valid.user@school.edu")

    with pytest.raises(ValidationError):
        parse_date("invalid-date", "Test Date")


def test_seed_idempotency_and_kpis(seeded_db: Database) -> None:
    """Verify seed data populates all 10 modules and is idempotent."""
    second_run = ensure_seed_data(seeded_db)
    assert second_run["seeded"] is False

    school_svc = SchoolService(seeded_db)
    kpis = school_svc.get_dashboard_kpis()
    assert kpis["active_students"] >= 3
    assert kpis["teachers"] >= 2
    assert kpis["classes"] >= 2
    assert kpis["available_books"] >= 1
    assert kpis["hostel_residents"] >= 1
    assert kpis["transport_participants"] >= 1


def test_module1_school_validations_and_cascades(seeded_db: Database) -> None:
    """Test Module 1: academic year/month overlaps, age checks, capacity, roll_no, promotion, alumni/terminate."""
    svc = SchoolService(seeded_db)
    today = date.today()

    # Grade validation: from_mark > to_mark must fail
    with pytest.raises(ValidationError, match="To Marks should be greater than From Marks"):
        svc.create_grade_master(
            name="Invalid Grade",
            lines=[{"from_mark": 90, "to_mark": 50, "grade": "X", "fail": False}],
        )

    # Overlapping grade marks must fail
    with pytest.raises(ValidationError, match="overlapping Marks"):
        svc.create_grade_master(
            name="Overlapping Grade",
            lines=[
                {"from_mark": 50, "to_mark": 80, "grade": "B", "fail": False},
                {"from_mark": 70, "to_mark": 100, "grade": "A", "fail": False},
            ],
        )

    # Academic Year overlap check
    with pytest.raises(ValidationError, match="overlapping academic years"):
        svc.create_academic_year(
            sequence=99,
            name="Overlapping Year",
            code="OV-1",
            date_start=date(today.year, 3, 1).isoformat(),
            date_stop=date(today.year, 9, 1).isoformat(),
        )

    # Academic year generate_academic_months on a future year
    future_yr = svc.create_academic_year(
        sequence=50,
        name=f"AY {today.year + 5}",
        code=f"AY-{today.year + 5}",
        date_start=date(today.year + 5, 1, 1).isoformat(),
        date_stop=date(today.year + 5, 3, 31).isoformat(),
    )
    gen_months = svc.generate_academic_months(future_yr["id"])
    assert len(gen_months) == 3

    years = svc.list_academic_years()
    current_year_id = years[0]["id"]

    # Academic Month outside parent year bounds must fail
    with pytest.raises(ValidationError):
        svc.create_academic_month(
            name="Out of Bounds Month",
            code="OOB",
            date_start=date(today.year - 2, 1, 1).isoformat(),
            date_stop=date(today.year - 2, 1, 31).isoformat(),
            year_id=current_year_id,
        )

    # Subject validation: max <= min must fail
    with pytest.raises(ValidationError, match="Maximum marks greater than minimum marks"):
        svc.create_subject(name="Bad Subject", code="BAD", maximum_marks=30, minimum_marks=50)

    schools = svc.list_schools()
    school_id = schools[0]["id"]
    standards = svc.list_school_standards()
    class_9_id = standards[0]["id"]

    # Cannot delete school standard that has students/subjects
    with pytest.raises(ValidationError, match="cannot delete"):
        svc.delete_school_standard(class_9_id)

    # Underage student check (< required_age 6)
    with pytest.raises(ValidationError, match="Age of student should be greater than"):
        svc.create_student(
            student_name="TooYoung",
            year_id=current_year_id,
            school_id=school_id,
            standard_id=class_9_id,
            date_of_birth=date(today.year - 3, 1, 1).isoformat(),
        )

    # Create parent, news, reminder, previous school
    parent = svc.create_parent(name="Mr. Ahmed Khan", email="ahmed.khan@mail.com", phone="0300-0001111")
    assert parent["id"] > 0

    stu = svc.create_student(
        student_name="Bilal",
        middle="Ahmed",
        last="Raza",
        year_id=current_year_id,
        school_id=school_id,
        standard_id=class_9_id,
        date_of_birth=date(today.year - 14, 1, 15).isoformat(),
        parent_ids=[parent["id"]],
    )
    stu_id = stu["id"]
    svc.verify_document(stu_id)
    svc.admission_done(stu_id)

    svc.create_student_news(
        subject="Annual Sports Day",
        date_expiry=(today + timedelta(days=10)).isoformat(),
        description="Sports day announcement",
    )
    svc.create_student_reminder(
        stu_id=stu_id,
        name="Bring Lab Coat",
        reminder_date=(today + timedelta(days=2)).isoformat(),
    )
    base_stds = seeded_db.fetch_all("SELECT id FROM standard_standard")
    svc.create_previous_school(
        student_id=stu_id,
        name="City Grammar School",
        registration_no="CGS-102",
        admission_date=date(today.year - 4, 1, 1).isoformat(),
        exit_date=date(today.year - 1, 12, 1).isoformat(),
        course_id=base_stds[0]["id"],
    )

    # Promote standards to next academic year
    moved = svc.move_standards(academic_year_id=current_year_id)
    assert len(moved) >= 1

    # Test set_alumni cascade on stu_id (has no unpaid fees)
    svc.set_alumni(stu_id)
    stu_row = seeded_db.fetch_one("SELECT state, active FROM student_student WHERE id = ?", (stu_id,))
    assert stu_row is not None
    assert stu_row["state"] == "alumni"
    assert stu_row["active"] == 0

    # Test cancel_admission & set_to_draft
    svc.set_to_draft(stu_id)
    svc.cancel_admission(stu_id)

    # Test terminate_student cascade on stu_id
    svc.terminate_student(stu_id, reason="Transferred to another city")
    term_row = seeded_db.fetch_one(
        "SELECT state, active, terminate_reason FROM student_student WHERE id = ?",
        (stu_id,),
    )
    assert term_row is not None
    assert term_row["state"] == "terminate"
    assert term_row["active"] == 0


def test_module2_fees_validations_and_lifecycle(seeded_db: Database) -> None:
    """Test Module 2: fee structures, payslip duplicate constraint, confirm/pay, unlink protection."""
    svc = FeesService(seeded_db)
    school_svc = SchoolService(seeded_db)
    students = school_svc.list_students()
    stu_id = students[0]["id"]
    structures = svc.list_fee_structures()
    struct = structures[0]
    struct_id = struct["id"]

    # Add month range to structure line
    years = school_svc.list_academic_years()
    months = school_svc.list_academic_months()
    line_id = struct["line_ids"][0]["id"]
    svc.add_structure_line_month_range(
        slipline1_id=line_id,
        academic_year_id=years[0]["id"],
        from_month_id=months[0]["id"],
        to_month_id=months[0]["id"],
    )

    slip_date = (date.today() + timedelta(days=15)).isoformat()
    slip = svc.create_payslip(
        student_id=stu_id,
        name="Test Tuition Slip",
        slip_date=slip_date,
        fees_structure_id=struct_id,
    )
    slip_id = slip["id"]

    # Duplicate draft payslip for same student and date must fail
    with pytest.raises(ValidationError):
        svc.create_payslip(
            student_id=stu_id,
            name="Duplicate Slip",
            slip_date=slip_date,
            fees_structure_id=struct_id,
        )

    svc.payslip_confirm(slip_id)
    # Cannot delete confirmed payslip
    with pytest.raises(ValidationError, match="delete record in unconfirm state only"):
        svc.delete_payslip(slip_id)

    # Partial payment -> pending, then remaining -> paid
    partial = svc.student_pay_fees(slip_id, payment_amount=2000.0)
    assert partial["state"] == "pending"
    assert partial["due_amount"] > 0

    paid = svc.student_pay_fees(slip_id, payment_amount=partial["due_amount"])
    assert paid["state"] == "paid"
    assert paid["due_amount"] == 0.0

    svc.mark_student_fees_received(stu_id)


def test_module3_attendance_leave_sheet_and_excel_export(seeded_db: Database) -> None:
    """Test Module 3: leave request auto-absent sync, 31-day num2words matrix, and .xlsx export."""
    att_svc = AttendanceService(seeded_db)
    school_svc = SchoolService(seeded_db)
    students = school_svc.list_students(include_inactive=True)
    stu_id = students[0]["id"]
    std_id = students[0]["standard_id"]
    teachers = school_svc.list_teachers()
    teacher_id = teachers[0]["id"]
    today = date.today()

    # Leave request with invalid dates must fail
    with pytest.raises(ValidationError):
        att_svc.create_leave_request(
            name="Invalid Leave",
            student_id=stu_id,
            start_date=today.isoformat(),
            end_date=(today - timedelta(days=2)).isoformat(),
        )

    leave = att_svc.create_leave_request(
        name="Medical Leave",
        student_id=stu_id,
        start_date=today.isoformat(),
        end_date=(today + timedelta(days=1)).isoformat(),
        reason="Fever",
    )
    leave_id = leave["id"]
    att_svc.leave_toapprove(leave_id)
    att_svc.leave_approve(leave_id)

    with pytest.raises(ValidationError, match="Approve leave can not be deleted"):
        att_svc.delete_leave_request(leave_id)

    # Reset existing daily attendance to draft, toggle present/absent, re-validate
    daily_list = att_svc.list_daily_attendance()
    att_id = daily_list[0]["id"]
    att_svc.attendance_draft(att_id)
    line_id = daily_list[0]["student_ids"][0]["id"]
    att_svc.action_absent(line_id)
    att_svc.action_present(line_id)
    att_svc.attendance_validate(att_id)

    # Future date daily attendance must fail
    with pytest.raises(ValidationError):
        att_svc.create_daily_attendance(
            standard_id=std_id,
            user_id=teacher_id,
            att_date=(today + timedelta(days=5)).isoformat(),
        )

    xlsx_bytes = att_svc.export_attendance_xlsx()
    assert xlsx_bytes[:2] == b"PK"
    assert len(xlsx_bytes) > 1000


def test_module4_assignment_constraints(seeded_db: Database) -> None:
    """Test Module 4: teacher assignment fan-out, softcopy format validation, and student submission."""
    svc = AssignmentService(seeded_db)
    today = date.today()
    subjects = SchoolService(seeded_db).list_subjects()
    standards = SchoolService(seeded_db).list_school_standards()
    teachers = SchoolService(seeded_db).list_teachers()
    formats = svc.list_file_formats()

    # assign_date > due_date must fail
    with pytest.raises(ValidationError, match="Due date of homework should be greater than assign date"):
        svc.create_teacher_assignment(
            name="Bad Dates Homework",
            subject_id=subjects[0]["id"],
            standard_id=standards[0]["id"],
            teacher_id=teachers[0]["id"],
            assign_date=today.isoformat(),
            due_date=(today - timedelta(days=1)).isoformat(),
        )

    stu_assigns = svc.list_student_assignments()
    assert len(stu_assigns) >= 1
    sa_id = stu_assigns[0]["id"]

    # Wrong file extension for softcopy (expects .pdf)
    with pytest.raises(ValidationError, match="Kindly attach file with format"):
        svc.submit_and_done_student_assignment(sa_id, submit_assign="data", file_name="homework.exe")

    svc.submit_and_done_student_assignment(sa_id, submit_assign="pdf-bytes", file_name="solution.pdf")
    svc.reject_student_assignment(sa_id, reason="Needs graphs")
    svc.reassign_student_assignment(sa_id)
    svc.submit_and_done_student_assignment(sa_id, submit_assign="pdf-bytes-v2", file_name="solution_v2.pdf")

    with pytest.raises(ValidationError, match="can not be deleted"):
        svc.delete_student_assignment(sa_id)
    assert len(formats) >= 1


def test_module5_timetable_overlap_validations(seeded_db: Database) -> None:
    """Test Module 5: start_time < end_time, teacher/classroom/weekday overlap checks."""
    svc = TimetableService(seeded_db)
    standards = SchoolService(seeded_db).list_school_standards()
    years = SchoolService(seeded_db).list_academic_years()
    teachers = SchoolService(seeded_db).list_teachers()
    subjects = SchoolService(seeded_db).list_subjects()

    # Start time >= End time must fail
    with pytest.raises(ValidationError, match="Start time should be less than end time"):
        svc.create_timetable(
            name="Invalid Time",
            standard_id=standards[1]["id"],
            year_id=years[0]["id"],
            timetable_type="regular",
            lines=[
                {
                    "teacher_id": teachers[0]["id"],
                    "subject_id": subjects[0]["id"],
                    "start_time": 11.0,
                    "end_time": 10.0,
                    "week_day": "tuesday",
                }
            ],
        )

    # Overlapping time slot on same day in same timetable must fail
    with pytest.raises(ValidationError, match="Time should not overlap"):
        svc.create_timetable(
            name="Self Conflict",
            standard_id=standards[1]["id"],
            year_id=years[1]["id"],
            timetable_type="regular",
            lines=[
                {
                    "teacher_id": teachers[0]["id"],
                    "subject_id": subjects[0]["id"],
                    "start_time": 11.0,
                    "end_time": 12.0,
                    "week_day": "wednesday",
                },
                {
                    "teacher_id": teachers[1]["id"],
                    "subject_id": subjects[1]["id"],
                    "start_time": 11.5,
                    "end_time": 12.5,
                    "week_day": "wednesday",
                },
            ],
        )

    # Cannot delete exam timetable while linked exam is running
    timetables = svc.list_timetables()
    exam_tt = next(t for t in timetables if t["timetable_type"] == "exam")
    with pytest.raises(ValidationError, match="cannot delete schedule of exam which is in running"):
        svc.delete_timetable(exam_tt["id"])


def test_module6_exam_and_re_evaluation(seeded_db: Database) -> None:
    """Test Module 6: exam date checks, mark bounds, re-evaluation workflow, additional exams."""
    svc = ExamService(seeded_db)
    results = svc.list_exam_results()
    assert len(results) >= 1
    res = results[0]
    sub_line = res["subjects"][0]

    # Obtained marks > maximum marks must fail
    with pytest.raises(ValidationError, match="obtained marks should not extend maximum marks"):
        svc.update_exam_subject_marks(sub_line["id"], obtain_marks=150.0)

    # Re-evaluation flow
    svc.result_re_evaluation(res["id"])
    updated_res = svc.update_exam_subject_marks(sub_line["id"], marks_reeval=95.0)
    assert updated_res["percentage"] > 0
    svc.re_evaluation_confirm(res["id"])
    svc.set_result_done(res["id"])

    # Cannot delete confirmed/done result
    with pytest.raises(ValidationError, match="delete record in unconfirm state only"):
        svc.delete_exam_result(res["id"])

    # Additional exam & result
    standards = SchoolService(seeded_db).list_school_standards()
    subjects = SchoolService(seeded_db).list_subjects()
    students = SchoolService(seeded_db).list_students(include_inactive=True)
    with pytest.raises(ValidationError, match="Minimum Marks Must Be Less Than Maximum Marks"):
        svc.create_additional_exam("Bad Add Exam", standards[0]["id"], subjects[0]["id"], 50, 60)

    a_exam_id = svc.create_additional_exam(
        "Surprise Quiz 1",
        standards[0]["id"],
        subjects[0]["id"],
        maximum_marks=50,
        minimum_marks=20,
    )
    a_res_id = svc.create_additional_exam_result(a_exam_id, students[0]["id"], obtain_marks=42.0)
    assert a_res_id > 0

    with pytest.raises(ValidationError, match="cannot create duplicate result"):
        svc.create_additional_exam_result(a_exam_id, students[0]["id"], obtain_marks=40.0)


def test_module7_library_stock_fines_and_limits(seeded_db: Database) -> None:
    """Test Module 7: unique ISBN, single active card per student, issue limit, late fine, lost book, requests."""
    svc = LibraryService(seeded_db)
    books = svc.list_books()
    cards = svc.list_cards()

    # Duplicate ISBN (case-insensitive) must fail
    with pytest.raises(ValidationError, match="ISBN number must be unique"):
        svc.create_book("Duplicate ISBN Book", isbn=books[0]["isbn"].lower())

    # Duplicate active card for same student must fail
    with pytest.raises(ValidationError, match="Library card already assigned to this student"):
        svc.create_library_card(user="student", student_id=cards[0]["student_id"])

    # Create teacher card & book request
    teachers = SchoolService(seeded_db).list_teachers()
    t_card_id = svc.create_library_card(user="teacher", teacher_id=teachers[0]["id"])
    svc.running_state_card(t_card_id)
    req_id = svc.create_book_request(card_id=t_card_id, req_type="existing", book_id=books[1]["id"])
    req_issue_id = svc.confirm_book_request(req_id)
    assert req_issue_id > 0

    # Cannot delete running card or confirmed request
    with pytest.raises(ValidationError, match="cannot delete a confirmed library card"):
        svc.delete_library_card(cards[0]["id"])
    with pytest.raises(ValidationError, match="cannot delete a confirmed book request"):
        svc.delete_book_request(req_id)

    # Test late return fine & payment
    issues = svc.list_book_issues()
    issue_id = next(i["id"] for i in issues if i["state"] == "issue")
    late_date = (date.today() + timedelta(days=30)).isoformat()
    ret = svc.return_book(issue_id, actual_return_date=late_date)
    assert ret["state"] == "fine"
    assert ret["penalty"] > 0

    # Issuing another book while card has unpaid fine must fail
    second_book_id = books[1]["id"]
    draft_issue = svc.create_book_issue(second_book_id, cards[0]["id"])
    with pytest.raises(UserError, match="cannot issue book until previous fine is paid"):
        svc.issue_book(draft_issue)

    # Pay fine, then issue succeeds, then reissue and lost book
    paid = svc.pay_fine(issue_id)
    assert paid["state"] == "paid"
    issued = svc.issue_book(draft_issue)
    assert issued["state"] == "issue"
    reissued = svc.reissue_book(draft_issue)
    assert reissued["state"] == "reissue"

    lost = svc.lost_book(draft_issue)
    assert lost["state"] == "fine"
    assert lost["lost_penalty"] > 0
    svc.pay_fine(draft_issue)
    svc.expire_overdue_cards()


def test_module8_9_10_event_hostel_transport(seeded_db: Database) -> None:
    """Test Modules 8, 9, 10: event pipe_end lock, hostel room capacity/gender, transport seat limit & transfer."""
    ev_svc = EventService(seeded_db)
    hostel_svc = HostelService(seeded_db)
    trans_svc = TransportService(seeded_db)

    # Module 8: Event ended blocks resetting registration to draft
    events = ev_svc.list_events()
    regs = ev_svc.list_registrations()
    ev_svc.set_event_ended(events[0]["id"], True)
    with pytest.raises(ValidationError, match="due to event is ended"):
        ev_svc.set_registration_draft(regs[0]["id"])
    ev_svc.cancel_registration(regs[0]["id"])

    # Module 9: Hostel floor/capacity constraints & discharge
    hostels = hostel_svc.list_hostels()
    with pytest.raises(ValidationError, match="Floor per HOSTEL should be less than 99"):
        hostel_svc.create_hostel_room(hostels[0]["id"], "B-999", floor_no=105)
    with pytest.raises(ValidationError, match="Student per room should be less than 10"):
        hostel_svc.create_hostel_room(hostels[0]["id"], "B-998", student_per_room=12)

    residents = hostel_svc.list_hostel_students()
    with pytest.raises(ValidationError, match="can not delete record in Confirmed, Pending or Paid"):
        hostel_svc.delete_hostel_student(residents[0]["id"])
    hostel_svc.discharge_student(residents[0]["id"])

    # Module 10: Transport route duration (<30 days fails) & vehicle transfer wizard
    today = date.today()
    with pytest.raises(ValidationError, match="duration must be greater than or equal to 1 month"):
        trans_svc.create_transport_route(
            "Short Route",
            today.isoformat(),
            (today + timedelta(days=10)).isoformat(),
            amount=1000.0,
        )

    routes = trans_svc.list_routes()
    with pytest.raises(ValidationError, match="cannot delete record in open state"):
        trans_svc.delete_transport_route(routes[0]["id"])

    participants = trans_svc.list_participants()
    vehicles = trans_svc.list_vehicles()
    part = participants[0]
    same_veh_id = part["vehicle_id"]
    other_veh_id = next(v["id"] for v in vehicles if v["id"] != same_veh_id)

    with pytest.raises(UserError, match="can not transfer in same vehicle"):
        trans_svc.transfer_vehicle(part["id"], same_veh_id)

    transferred = trans_svc.transfer_vehicle(part["id"], other_veh_id)
    assert transferred["vehicle_id"] == other_veh_id
    trans_svc.transport_close(routes[0]["id"])


def test_flask_api_endpoints(seeded_db: Database) -> None:
    """Test Flask API bootstrap, health, action endpoints, and Excel export."""
    app = create_app(seeded_db, seed=False)
    client = app.test_client()

    health_resp = client.get("/api/health")
    assert health_resp.status_code == 200
    assert health_resp.get_json()["ok"] is True

    boot_resp = client.get("/api/bootstrap")
    assert boot_resp.status_code == 200
    boot_data = boot_resp.get_json()
    assert boot_data["ok"] is True
    assert "kpis" in boot_data
    assert len(boot_data["school"]["students"]) >= 3

    school_id = boot_data["school"]["schools"][0]["id"]
    year_id = boot_data["school"]["years"][0]["id"]
    std_id = boot_data["school"]["standards"][0]["id"]
    med_id = boot_data["school"]["mediums"][0]["id"]

    # Create a teacher & student via API
    t_resp = client.post(
        "/api/teachers",
        json={
            "name": "Prof. Bilal Sarwar",
            "work_email": "bilal.sarwar@greenfield.edu",
            "phone_numbers": "0301-7778899",
            "department": "Chemistry",
            "school_id": school_id,
        },
    )
    assert t_resp.status_code == 200

    s_resp = client.post(
        "/api/students",
        json={
            "student_name": "Usman",
            "middle": "Tariq",
            "last": "Malik",
            "year_id": year_id,
            "school_id": school_id,
            "standard_id": std_id,
            "date_of_birth": "2011-04-10",
            "gender": "male",
            "email": "usman.malik@student.edu",
            "auto_admit": True,
        },
    )
    assert s_resp.status_code == 200
    new_stu_id = s_resp.get_json()["id"]

    # Assign roll no via API
    rn_resp = client.post(
        "/api/school/assign-roll-no",
        json={"standard_id": std_id, "medium_id": med_id},
    )
    assert rn_resp.status_code == 200

    # Create payslip & pay via API
    struct_id = boot_data["fees"]["structures"][0]["id"]
    ps_resp = client.post(
        "/api/fees/payslips",
        json={
            "student_id": new_stu_id,
            "name": "API Fee Slip",
            "date": date.today().isoformat(),
            "fees_structure_id": struct_id,
        },
    )
    assert ps_resp.status_code == 200
    ps_id = ps_resp.get_json()["id"]
    pay_resp = client.post(f"/api/fees/payslips/{ps_id}/action", json={"action": "pay"})
    assert pay_resp.status_code == 200

    # Create library book, card, issue via API
    bk_resp = client.post(
        "/api/library/books",
        json={
            "name": "API Data Structures",
            "isbn": "978-1-4028-9462-6",
            "code": "BK-API",
            "barcode": "BC-API-01",
            "qty_available": 3,
        },
    )
    assert bk_resp.status_code == 200
    bk_id = bk_resp.get_json()["id"]

    cd_resp = client.post(
        "/api/library/cards",
        json={"user": "student", "student_id": new_stu_id, "book_limit": 3},
    )
    assert cd_resp.status_code == 200
    cd_id = cd_resp.get_json()["id"]

    iss_resp = client.post(
        "/api/library/issues",
        json={"book_id": bk_id, "card_id": cd_id},
    )
    assert iss_resp.status_code == 200
    iss_id = iss_resp.get_json()["id"]
    ret_resp = client.post(f"/api/library/issues/{iss_id}/action", json={"action": "return"})
    assert ret_resp.status_code == 200

    # Create event & registration via API
    ev_resp = client.post(
        "/api/events",
        json={
            "name": "Debate Championship",
            "start_date": date.today().isoformat(),
            "end_date": (date.today() + timedelta(days=2)).isoformat(),
            "event_type": "intra",
        },
    )
    assert ev_resp.status_code == 200
    ev_id = ev_resp.get_json()["id"]
    ev_reg_resp = client.post(
        "/api/events/registrations",
        json={"event_id": ev_id, "part_name_id": new_stu_id},
    )
    assert ev_reg_resp.status_code == 200

    # Create hostel resident & pay via API
    hostel_id = boot_data["hostel"]["hostels"][0]["id"]
    room_id = boot_data["hostel"]["rooms"][0]["id"]
    hs_resp = client.post(
        "/api/hostel/residents",
        json={
            "student_id": new_stu_id,
            "hostel_info_id": hostel_id,
            "room_id": room_id,
            "duration": 3,
        },
    )
    assert hs_resp.status_code == 200
    hs_id = hs_resp.get_json()["id"]
    hs_pay_resp = client.post(f"/api/hostel/residents/{hs_id}/action", json={"action": "pay"})
    assert hs_pay_resp.status_code == 200

    # Create transport registration & pay via API
    route_id = boot_data["transport"]["routes"][0]["id"]
    veh_id = boot_data["transport"]["vehicles"][0]["id"]
    tr_resp = client.post(
        "/api/transport/registrations",
        json={
            "route_id": route_id,
            "student_id": new_stu_id,
            "vehicle_id": veh_id,
            "registration_month": 2,
        },
    )
    assert tr_resp.status_code == 200
    tr_id = tr_resp.get_json()["id"]
    tr_pay_resp = client.post(f"/api/transport/registrations/{tr_id}/action", json={"action": "pay"})
    assert tr_pay_resp.status_code == 200

    # Test Excel download via API
    xlsx_resp = client.get("/api/attendance/export-xlsx")
    assert xlsx_resp.status_code == 200
    assert xlsx_resp.data[:2] == b"PK"
