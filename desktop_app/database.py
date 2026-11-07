"""High-performance SQLite database engine with WAL mode and schema for all 10 modules."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
import sys
from typing import Any, Iterator

from desktop_app.db.migrate import apply_migrations


def get_default_db_path() -> Path:
    """Resolve persistent SQLite database path for both source and PyInstaller .exe runs."""
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent.parent
    return base_dir / "school_erp.sqlite3"


SCHEMA_SQL = """
-- Sequences (mirrors ir.sequence)
CREATE TABLE IF NOT EXISTS ir_sequence (
    code TEXT PRIMARY KEY,
    prefix TEXT NOT NULL,
    padding INTEGER NOT NULL DEFAULT 4,
    next_val INTEGER NOT NULL DEFAULT 1
);

-- =========================================================================
-- MODULE 1: school
-- =========================================================================
CREATE TABLE IF NOT EXISTS grade_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS grade_line (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    grade_id INTEGER NOT NULL REFERENCES grade_master(id) ON DELETE CASCADE,
    from_mark REAL NOT NULL,
    to_mark REAL NOT NULL,
    grade TEXT NOT NULL,
    sequence INTEGER DEFAULT 1,
    fail INTEGER NOT NULL DEFAULT 0,
    name TEXT
);

CREATE TABLE IF NOT EXISTS academic_year (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    date_start TEXT NOT NULL,
    date_stop TEXT NOT NULL,
    grade_id INTEGER REFERENCES grade_master(id) ON DELETE SET NULL,
    current INTEGER NOT NULL DEFAULT 0,
    description TEXT
);

CREATE TABLE IF NOT EXISTS academic_month (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    date_start TEXT NOT NULL,
    date_stop TEXT NOT NULL,
    year_id INTEGER NOT NULL REFERENCES academic_year(id) ON DELETE CASCADE,
    description TEXT,
    UNIQUE(date_start, date_stop, year_id)
);

CREATE TABLE IF NOT EXISTS standard_medium (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence INTEGER NOT NULL,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS standard_division (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence INTEGER NOT NULL,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS standard_standard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    code TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS class_room (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    number TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS school_school (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE,
    required_age INTEGER NOT NULL DEFAULT 6,
    street TEXT,
    city TEXT DEFAULT 'Metropolis',
    state_name TEXT DEFAULT 'State',
    country_name TEXT DEFAULT 'Country',
    contact_phone TEXT,
    contact_mobile TEXT,
    currency_symbol TEXT DEFAULT 'Rs.'
);

CREATE TABLE IF NOT EXISTS school_teacher (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    work_email TEXT,
    phone_numbers TEXT,
    birthday TEXT,
    department TEXT,
    standard_id INTEGER,
    school_id INTEGER REFERENCES school_school(id) ON DELETE SET NULL,
    is_parent INTEGER NOT NULL DEFAULT 0,
    stu_parent_id INTEGER,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS school_parent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    relation_name TEXT DEFAULT 'Guardian',
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS school_standard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    school_id INTEGER NOT NULL REFERENCES school_school(id) ON DELETE RESTRICT,
    standard_id INTEGER NOT NULL REFERENCES standard_standard(id) ON DELETE RESTRICT,
    division_id INTEGER NOT NULL REFERENCES standard_division(id) ON DELETE RESTRICT,
    medium_id INTEGER NOT NULL REFERENCES standard_medium(id) ON DELETE RESTRICT,
    user_id INTEGER REFERENCES school_teacher(id) ON DELETE SET NULL,
    capacity INTEGER NOT NULL CHECK(capacity > 0),
    total_students INTEGER NOT NULL DEFAULT 0,
    remaining_seats INTEGER NOT NULL DEFAULT 0,
    class_room_id INTEGER REFERENCES class_room(id) ON DELETE SET NULL,
    UNIQUE(standard_id, division_id, school_id)
);

CREATE TABLE IF NOT EXISTS subject_subject (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    maximum_marks INTEGER NOT NULL DEFAULT 100,
    minimum_marks INTEGER NOT NULL DEFAULT 35,
    weightage INTEGER DEFAULT 1,
    standard_id INTEGER REFERENCES standard_standard(id) ON DELETE SET NULL,
    is_practical INTEGER NOT NULL DEFAULT 0,
    is_elective_subject INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS subject_standards_rel (
    school_standard_id INTEGER NOT NULL REFERENCES school_standard(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subject_subject(id) ON DELETE RESTRICT,
    PRIMARY KEY (school_standard_id, subject_id)
);

CREATE TABLE IF NOT EXISTS subject_teacher_rel (
    subject_id INTEGER NOT NULL REFERENCES subject_subject(id) ON DELETE CASCADE,
    teacher_id INTEGER NOT NULL REFERENCES school_teacher(id) ON DELETE CASCADE,
    PRIMARY KEY (subject_id, teacher_id)
);

CREATE TABLE IF NOT EXISTS subject_syllabus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_id INTEGER NOT NULL REFERENCES school_standard(id) ON DELETE RESTRICT,
    subject_id INTEGER NOT NULL REFERENCES subject_subject(id) ON DELETE CASCADE,
    syllabus_doc TEXT
);

CREATE TABLE IF NOT EXISTS student_cast (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS mother_toungue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS student_student (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pid TEXT NOT NULL,
    student_name TEXT NOT NULL,
    middle TEXT NOT NULL DEFAULT '',
    last TEXT NOT NULL DEFAULT '',
    reg_code TEXT,
    student_code TEXT,
    roll_no INTEGER DEFAULT 0,
    email TEXT,
    contact_phone TEXT,
    contact_mobile TEXT,
    year_id INTEGER NOT NULL REFERENCES academic_year(id) ON DELETE RESTRICT,
    school_id INTEGER NOT NULL REFERENCES school_school(id) ON DELETE RESTRICT,
    standard_id INTEGER REFERENCES school_standard(id) ON DELETE RESTRICT,
    division_id INTEGER REFERENCES standard_division(id) ON DELETE SET NULL,
    medium_id INTEGER REFERENCES standard_medium(id) ON DELETE SET NULL,
    admission_date TEXT NOT NULL,
    leave_date TEXT,
    gender TEXT DEFAULT 'male',
    date_of_birth TEXT NOT NULL,
    age INTEGER NOT NULL DEFAULT 0,
    maritual_status TEXT DEFAULT 'unmarried',
    cast_id INTEGER REFERENCES student_cast(id) ON DELETE SET NULL,
    mother_tongue_id INTEGER REFERENCES mother_toungue(id) ON DELETE SET NULL,
    blood_group TEXT,
    height REAL DEFAULT 0,
    weight REAL DEFAULT 0,
    doctor TEXT,
    doctor_phone TEXT,
    remark TEXT,
    terminate_reason TEXT,
    state TEXT NOT NULL DEFAULT 'draft',
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS students_parents_rel (
    student_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    parent_id INTEGER NOT NULL REFERENCES school_parent(id) ON DELETE CASCADE,
    PRIMARY KEY (student_id, parent_id)
);

CREATE TABLE IF NOT EXISTS student_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    move_date TEXT NOT NULL,
    academice_year_id INTEGER NOT NULL REFERENCES academic_year(id) ON DELETE CASCADE,
    standard_id INTEGER NOT NULL REFERENCES school_standard(id) ON DELETE CASCADE,
    percentage REAL DEFAULT 0.0,
    result TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS student_reminder (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stu_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    description TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS student_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT NOT NULL,
    description TEXT,
    date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS student_descipline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    teacher_id INTEGER REFERENCES school_teacher(id) ON DELETE SET NULL,
    date TEXT NOT NULL,
    class_id INTEGER REFERENCES standard_standard(id) ON DELETE SET NULL,
    note TEXT,
    action_taken TEXT
);

CREATE TABLE IF NOT EXISTS student_award (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    award_list_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS student_previous_school (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    previous_school_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    registration_no TEXT NOT NULL,
    admission_date TEXT,
    exit_date TEXT,
    course_id INTEGER NOT NULL REFERENCES standard_standard(id) ON DELETE RESTRICT
);

-- =========================================================================
-- MODULE 2: school_fees
-- =========================================================================
CREATE TABLE IF NOT EXISTS student_fees_structure (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS student_fees_structure_line (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    structure_id INTEGER REFERENCES student_fees_structure(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'month',
    amount REAL NOT NULL DEFAULT 0.0,
    sequence TEXT
);

CREATE TABLE IF NOT EXISTS student_payslip_line_line (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slipline1_id INTEGER NOT NULL REFERENCES student_fees_structure_line(id) ON DELETE CASCADE,
    sequence INTEGER DEFAULT 1,
    academic_year_id INTEGER REFERENCES academic_year(id) ON DELETE CASCADE,
    from_month_id INTEGER REFERENCES academic_month(id) ON DELETE CASCADE,
    to_month_id INTEGER REFERENCES academic_month(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS student_fees_register (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    number TEXT NOT NULL DEFAULT 'New',
    total_amount REAL NOT NULL DEFAULT 0.0,
    state TEXT NOT NULL DEFAULT 'draft',
    journal_name TEXT DEFAULT 'Tuition Fees Journal',
    fees_structure_id INTEGER REFERENCES student_fees_structure(id) ON DELETE RESTRICT,
    standard_id INTEGER REFERENCES standard_standard(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS student_payslip (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fees_structure_id INTEGER REFERENCES student_fees_structure(id) ON DELETE SET NULL,
    standard_id INTEGER REFERENCES school_standard(id) ON DELETE SET NULL,
    division_id INTEGER REFERENCES standard_division(id) ON DELETE SET NULL,
    medium_id INTEGER REFERENCES standard_medium(id) ON DELETE SET NULL,
    register_id INTEGER REFERENCES student_fees_register(id) ON DELETE CASCADE,
    name TEXT,
    number TEXT NOT NULL DEFAULT '/',
    student_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    total REAL NOT NULL DEFAULT 0.0,
    paid_amount REAL NOT NULL DEFAULT 0.0,
    due_amount REAL NOT NULL DEFAULT 0.0,
    payment_date TEXT,
    journal_name TEXT DEFAULT 'Tuition Fees Journal',
    type TEXT NOT NULL DEFAULT 'out_invoice',
    state TEXT NOT NULL DEFAULT 'draft',
    UNIQUE(student_id, date, state)
);

CREATE TABLE IF NOT EXISTS student_payslip_line (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slip_id INTEGER NOT NULL REFERENCES student_payslip(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    code TEXT NOT NULL,
    type TEXT NOT NULL,
    amount REAL NOT NULL DEFAULT 0.0,
    description TEXT
);

-- =========================================================================
-- MODULE 3: school_attendance
-- =========================================================================
CREATE TABLE IF NOT EXISTS studentleave_request (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    student_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    roll_no INTEGER,
    standard_id INTEGER NOT NULL REFERENCES school_standard(id) ON DELETE CASCADE,
    teacher_id INTEGER REFERENCES school_teacher(id) ON DELETE SET NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    days INTEGER NOT NULL DEFAULT 0,
    reason TEXT,
    state TEXT NOT NULL DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS daily_attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    standard_id INTEGER NOT NULL REFERENCES school_standard(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES school_teacher(id) ON DELETE RESTRICT,
    state TEXT NOT NULL DEFAULT 'draft',
    total_student INTEGER NOT NULL DEFAULT 0,
    total_presence INTEGER NOT NULL DEFAULT 0,
    total_absent INTEGER NOT NULL DEFAULT 0,
    is_generate INTEGER NOT NULL DEFAULT 0,
    subject_id INTEGER REFERENCES subject_subject(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS daily_attendance_line (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_id INTEGER NOT NULL REFERENCES daily_attendance(id) ON DELETE CASCADE,
    stud_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    roll_no INTEGER DEFAULT 0,
    is_present INTEGER NOT NULL DEFAULT 0,
    is_absent INTEGER NOT NULL DEFAULT 0,
    present_absentcheck INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS attendance_sheet (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    standard_id INTEGER NOT NULL REFERENCES school_standard(id) ON DELETE CASCADE,
    month_id INTEGER NOT NULL REFERENCES academic_month(id) ON DELETE CASCADE,
    year_id INTEGER NOT NULL REFERENCES academic_year(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES school_teacher(id) ON DELETE SET NULL,
    attendance_type TEXT DEFAULT 'daily'
);

CREATE TABLE IF NOT EXISTS attendance_sheet_line (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    standard_id INTEGER NOT NULL REFERENCES attendance_sheet(id) ON DELETE CASCADE,
    roll_no INTEGER NOT NULL,
    name TEXT NOT NULL,
    one INTEGER NOT NULL DEFAULT 0,
    two INTEGER NOT NULL DEFAULT 0,
    three INTEGER NOT NULL DEFAULT 0,
    four INTEGER NOT NULL DEFAULT 0,
    five INTEGER NOT NULL DEFAULT 0,
    six INTEGER NOT NULL DEFAULT 0,
    seven INTEGER NOT NULL DEFAULT 0,
    eight INTEGER NOT NULL DEFAULT 0,
    nine INTEGER NOT NULL DEFAULT 0,
    ten INTEGER NOT NULL DEFAULT 0,
    eleven INTEGER NOT NULL DEFAULT 0,
    twelve INTEGER NOT NULL DEFAULT 0,
    thirteen INTEGER NOT NULL DEFAULT 0,
    fourteen INTEGER NOT NULL DEFAULT 0,
    fifteen INTEGER NOT NULL DEFAULT 0,
    sixteen INTEGER NOT NULL DEFAULT 0,
    seventeen INTEGER NOT NULL DEFAULT 0,
    eighteen INTEGER NOT NULL DEFAULT 0,
    nineteen INTEGER NOT NULL DEFAULT 0,
    twenty INTEGER NOT NULL DEFAULT 0,
    twentyone INTEGER NOT NULL DEFAULT 0,
    twentytwo INTEGER NOT NULL DEFAULT 0,
    twentythree INTEGER NOT NULL DEFAULT 0,
    twentyfour INTEGER NOT NULL DEFAULT 0,
    twentyfive INTEGER NOT NULL DEFAULT 0,
    twentysix INTEGER NOT NULL DEFAULT 0,
    twentyseven INTEGER NOT NULL DEFAULT 0,
    twentyeight INTEGER NOT NULL DEFAULT 0,
    twentynine INTEGER NOT NULL DEFAULT 0,
    thirty INTEGER NOT NULL DEFAULT 0,
    thirtyone INTEGER NOT NULL DEFAULT 0
);

-- =========================================================================
-- MODULE 4: assignment
-- =========================================================================
CREATE TABLE IF NOT EXISTS file_format (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS school_teacher_assignment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    subject_id INTEGER NOT NULL REFERENCES subject_subject(id) ON DELETE CASCADE,
    standard_id INTEGER NOT NULL REFERENCES school_standard(id) ON DELETE CASCADE,
    teacher_id INTEGER NOT NULL REFERENCES school_teacher(id) ON DELETE CASCADE,
    assign_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    attached_homework TEXT,
    attach_files TEXT,
    type_submission TEXT NOT NULL DEFAULT 'hardcopy',
    file_format_id INTEGER REFERENCES file_format(id) ON DELETE SET NULL,
    state TEXT NOT NULL DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS school_student_assignment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    subject_id INTEGER NOT NULL REFERENCES subject_subject(id) ON DELETE CASCADE,
    standard_id INTEGER NOT NULL REFERENCES school_standard(id) ON DELETE CASCADE,
    teacher_id INTEGER NOT NULL REFERENCES school_teacher(id) ON DELETE CASCADE,
    assign_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    student_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    stud_roll_no INTEGER,
    teacher_assignment_id INTEGER REFERENCES school_teacher_assignment(id) ON DELETE CASCADE,
    submission_type TEXT NOT NULL DEFAULT 'hardcopy',
    attachfile_format TEXT,
    attached_homework TEXT,
    submit_assign TEXT,
    file_name TEXT,
    state TEXT NOT NULL DEFAULT 'draft',
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS assignment_reject_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL REFERENCES school_student_assignment(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    rejected_at TEXT NOT NULL
);

-- =========================================================================
-- MODULE 5: timetable
-- =========================================================================
CREATE TABLE IF NOT EXISTS time_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    standard_id INTEGER NOT NULL REFERENCES school_standard(id) ON DELETE CASCADE,
    year_id INTEGER NOT NULL REFERENCES academic_year(id) ON DELETE CASCADE,
    timetable_type TEXT NOT NULL DEFAULT 'regular',
    class_room_id INTEGER REFERENCES class_room(id) ON DELETE SET NULL,
    exam_id INTEGER
);

CREATE TABLE IF NOT EXISTS time_table_line (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id INTEGER NOT NULL REFERENCES time_table(id) ON DELETE CASCADE,
    teacher_id INTEGER REFERENCES school_teacher(id) ON DELETE SET NULL,
    subject_id INTEGER NOT NULL REFERENCES subject_subject(id) ON DELETE CASCADE,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    week_day TEXT,
    exm_date TEXT,
    day_of_week TEXT,
    class_room_id INTEGER REFERENCES class_room(id) ON DELETE SET NULL
);

-- =========================================================================
-- MODULE 6: exam
-- =========================================================================
CREATE TABLE IF NOT EXISTS exam_exam (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    exam_code TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'draft',
    grade_system_id INTEGER REFERENCES grade_master(id) ON DELETE SET NULL,
    academic_year_id INTEGER REFERENCES academic_year(id) ON DELETE SET NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS exam_standard_rel (
    exam_id INTEGER NOT NULL REFERENCES exam_exam(id) ON DELETE CASCADE,
    standard_id INTEGER NOT NULL REFERENCES standard_standard(id) ON DELETE CASCADE,
    PRIMARY KEY (exam_id, standard_id)
);

CREATE TABLE IF NOT EXISTS exam_schedule_line (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL REFERENCES exam_exam(id) ON DELETE CASCADE,
    standard_id INTEGER NOT NULL REFERENCES school_standard(id) ON DELETE CASCADE,
    timetable_id INTEGER NOT NULL REFERENCES time_table(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS exam_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    s_exam_ids INTEGER NOT NULL REFERENCES exam_exam(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    roll_no INTEGER,
    standard_id INTEGER REFERENCES school_standard(id) ON DELETE SET NULL,
    grade_system_id INTEGER REFERENCES grade_master(id) ON DELETE SET NULL,
    total REAL NOT NULL DEFAULT 0.0,
    percentage REAL NOT NULL DEFAULT 0.0,
    result TEXT DEFAULT 'Pass',
    grade TEXT DEFAULT '',
    state TEXT NOT NULL DEFAULT 'draft',
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS exam_subject (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL REFERENCES exam_result(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subject_subject(id) ON DELETE CASCADE,
    obtain_marks REAL NOT NULL DEFAULT 0.0,
    minimum_marks REAL NOT NULL DEFAULT 35.0,
    maximum_marks REAL NOT NULL DEFAULT 100.0,
    marks_reeval REAL NOT NULL DEFAULT 0.0,
    grade_line_id INTEGER REFERENCES grade_line(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS additional_exam (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    addtional_exam_code TEXT NOT NULL,
    standard_id INTEGER REFERENCES school_standard(id) ON DELETE CASCADE,
    subject_id INTEGER REFERENCES subject_subject(id) ON DELETE CASCADE,
    exam_date TEXT,
    maximum_marks INTEGER NOT NULL,
    minimum_marks INTEGER NOT NULL,
    weightage TEXT
);

CREATE TABLE IF NOT EXISTS additional_exam_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    a_exam_id INTEGER NOT NULL REFERENCES additional_exam(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    roll_no INTEGER,
    standard_id INTEGER REFERENCES school_standard(id) ON DELETE SET NULL,
    obtain_marks REAL NOT NULL DEFAULT 0.0,
    result TEXT NOT NULL DEFAULT 'Fail',
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(a_exam_id, student_id)
);

-- =========================================================================
-- MODULE 7: library
-- =========================================================================
CREATE TABLE IF NOT EXISTS library_rack (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    code TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS library_author (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    birth_date TEXT,
    death_date TEXT,
    biography TEXT,
    note TEXT
);

CREATE TABLE IF NOT EXISTS library_book (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    isbn TEXT UNIQUE,
    code TEXT,
    barcode TEXT,
    author_id INTEGER REFERENCES library_author(id) ON DELETE SET NULL,
    rack_id INTEGER REFERENCES library_rack(id) ON DELETE SET NULL,
    qty_available INTEGER NOT NULL DEFAULT 1,
    books_available INTEGER NOT NULL DEFAULT 1,
    availability TEXT NOT NULL DEFAULT 'available',
    day_to_return_book INTEGER NOT NULL DEFAULT 14,
    fine_late_return REAL NOT NULL DEFAULT 10.0,
    fine_lost REAL NOT NULL DEFAULT 500.0,
    is_ebook INTEGER NOT NULL DEFAULT 0,
    is_subscription INTEGER NOT NULL DEFAULT 0,
    subscrption_amt REAL NOT NULL DEFAULT 0.0,
    attach_ebook TEXT,
    back TEXT DEFAULT 'paper',
    nbpage INTEGER DEFAULT 200,
    UNIQUE(barcode, code)
);

CREATE TABLE IF NOT EXISTS library_card (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL DEFAULT 'New',
    book_limit INTEGER NOT NULL DEFAULT 3,
    user TEXT NOT NULL DEFAULT 'student',
    student_id INTEGER REFERENCES student_student(id) ON DELETE CASCADE,
    teacher_id INTEGER REFERENCES school_teacher(id) ON DELETE CASCADE,
    standard_id INTEGER REFERENCES school_standard(id) ON DELETE SET NULL,
    roll_no INTEGER,
    card_name TEXT,
    start_date TEXT NOT NULL,
    duration INTEGER NOT NULL DEFAULT 12,
    end_date TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'draft',
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS library_book_request (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    req_id TEXT NOT NULL DEFAULT 'New',
    card_id INTEGER NOT NULL REFERENCES library_card(id) ON DELETE CASCADE,
    type TEXT NOT NULL DEFAULT 'existing',
    book_id INTEGER REFERENCES library_book(id) ON DELETE SET NULL,
    ebook_id INTEGER REFERENCES library_book(id) ON DELETE SET NULL,
    new_book TEXT,
    book_name TEXT,
    book_issue_id INTEGER,
    state TEXT NOT NULL DEFAULT 'draft',
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS library_book_issue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES library_book(id) ON DELETE RESTRICT,
    issue_code TEXT NOT NULL DEFAULT 'New',
    book_request_id INTEGER REFERENCES library_book_request(id) ON DELETE SET NULL,
    card_id INTEGER NOT NULL REFERENCES library_card(id) ON DELETE CASCADE,
    user TEXT,
    student_id INTEGER REFERENCES student_student(id) ON DELETE SET NULL,
    teacher_id INTEGER REFERENCES school_teacher(id) ON DELETE SET NULL,
    standard_id INTEGER REFERENCES school_standard(id) ON DELETE SET NULL,
    roll_no INTEGER,
    card_name TEXT,
    date_issue TEXT NOT NULL,
    day_to_return_book INTEGER NOT NULL DEFAULT 14,
    date_return TEXT,
    actual_return_date TEXT,
    penalty REAL NOT NULL DEFAULT 0.0,
    lost_penalty REAL NOT NULL DEFAULT 0.0,
    subscription_amt REAL NOT NULL DEFAULT 0.0,
    ebook_download TEXT,
    state TEXT NOT NULL DEFAULT 'draft'
);

-- =========================================================================
-- MODULE 8: school_event
-- =========================================================================
CREATE TABLE IF NOT EXISTS school_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    event_type TEXT NOT NULL DEFAULT 'intra',
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    contact_teacher_id INTEGER REFERENCES school_teacher(id) ON DELETE SET NULL,
    pipe_end INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS school_event_standard_rel (
    event_id INTEGER NOT NULL REFERENCES school_event(id) ON DELETE CASCADE,
    standard_id INTEGER NOT NULL REFERENCES school_standard(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, standard_id)
);

CREATE TABLE IF NOT EXISTS event_registration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL REFERENCES school_event(id) ON DELETE CASCADE,
    part_name_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    student_standard_id INTEGER REFERENCES school_standard(id) ON DELETE SET NULL,
    state TEXT NOT NULL DEFAULT 'draft'
);

-- =========================================================================
-- MODULE 9: school_hostel
-- =========================================================================
CREATE TABLE IF NOT EXISTS hostel_type (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'common',
    rector_name TEXT,
    other_info TEXT,
    city TEXT
);

CREATE TABLE IF NOT EXISTS hostel_amenities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS hostel_room (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hostel_id INTEGER NOT NULL REFERENCES hostel_type(id) ON DELETE CASCADE,
    floor_no INTEGER NOT NULL DEFAULT 1 CHECK(floor_no < 99),
    room_no TEXT NOT NULL,
    student_per_room INTEGER NOT NULL CHECK(student_per_room > 0 AND student_per_room < 10),
    availability REAL NOT NULL DEFAULT 0,
    rent_amount REAL NOT NULL DEFAULT 0.0,
    UNIQUE(room_no, hostel_id)
);

CREATE TABLE IF NOT EXISTS hostel_student (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hostel_id TEXT NOT NULL DEFAULT 'New',
    student_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    school_id INTEGER REFERENCES school_school(id) ON DELETE SET NULL,
    hostel_info_id INTEGER NOT NULL REFERENCES hostel_type(id) ON DELETE RESTRICT,
    room_id INTEGER NOT NULL REFERENCES hostel_room(id) ON DELETE RESTRICT,
    duration INTEGER NOT NULL,
    admission_date TEXT NOT NULL,
    discharge_date TEXT NOT NULL,
    acutal_discharge_date TEXT,
    room_rent REAL NOT NULL DEFAULT 0.0,
    tax_amount REAL NOT NULL DEFAULT 0.0,
    paid_amount REAL NOT NULL DEFAULT 0.0,
    remaining_amount REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'draft',
    hostel_types TEXT,
    stud_gender TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    CHECK(discharge_date >= admission_date)
);

-- =========================================================================
-- MODULE 10: school_transport
-- =========================================================================
CREATE TABLE IF NOT EXISTS fleet_vehicle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    license_plate TEXT NOT NULL UNIQUE,
    model_name TEXT NOT NULL,
    driver_name TEXT,
    driver_licence_no TEXT UNIQUE,
    seats INTEGER NOT NULL DEFAULT 30
);

CREATE TABLE IF NOT EXISTS student_transport (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    contact_person TEXT,
    amount REAL NOT NULL DEFAULT 0.0,
    state TEXT NOT NULL DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS transport_vehicle_rel (
    transport_id INTEGER NOT NULL REFERENCES student_transport(id) ON DELETE CASCADE,
    vehicle_id INTEGER NOT NULL REFERENCES fleet_vehicle(id) ON DELETE CASCADE,
    PRIMARY KEY (transport_id, vehicle_id)
);

CREATE TABLE IF NOT EXISTS transport_participant (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    amount REAL NOT NULL DEFAULT 0.0,
    transport_id INTEGER NOT NULL REFERENCES student_transport(id) ON DELETE CASCADE,
    stu_pid_id TEXT NOT NULL,
    tr_reg_date TEXT NOT NULL,
    tr_end_date TEXT NOT NULL,
    months INTEGER NOT NULL DEFAULT 1,
    vehicle_id INTEGER NOT NULL REFERENCES fleet_vehicle(id) ON DELETE RESTRICT,
    state TEXT NOT NULL DEFAULT 'running',
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS transport_registration (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name INTEGER NOT NULL REFERENCES student_transport(id) ON DELETE RESTRICT,
    student_id INTEGER NOT NULL REFERENCES student_student(id) ON DELETE CASCADE,
    vehicle_id INTEGER NOT NULL REFERENCES fleet_vehicle(id) ON DELETE RESTRICT,
    reg_date TEXT NOT NULL,
    reg_end_date TEXT NOT NULL,
    registration_month INTEGER NOT NULL,
    monthly_amount REAL NOT NULL DEFAULT 0.0,
    transport_fees REAL NOT NULL DEFAULT 0.0,
    paid_amount REAL NOT NULL DEFAULT 0.0,
    tax_amount REAL NOT NULL DEFAULT 0.0,
    remain_amt REAL NOT NULL DEFAULT 0.0,
    state TEXT NOT NULL DEFAULT 'draft'
);

-- High-speed Indexes
CREATE INDEX IF NOT EXISTS idx_student_standard ON student_student(standard_id, state);
CREATE INDEX IF NOT EXISTS idx_student_year ON student_student(year_id, state);
CREATE INDEX IF NOT EXISTS idx_payslip_student ON student_payslip(student_id, state);
CREATE INDEX IF NOT EXISTS idx_daily_att_std_date ON daily_attendance(standard_id, date);
CREATE INDEX IF NOT EXISTS idx_leave_student_dates ON studentleave_request(student_id, state, start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_tt_line_table ON time_table_line(table_id, week_day);
CREATE INDEX IF NOT EXISTS idx_exam_result_student ON exam_result(student_id, s_exam_ids);
CREATE INDEX IF NOT EXISTS idx_book_issue_card ON library_book_issue(card_id, state);
CREATE INDEX IF NOT EXISTS idx_hostel_student_room ON hostel_student(room_id, status);
CREATE INDEX IF NOT EXISTS idx_transport_part_vehicle ON transport_participant(vehicle_id, state);
"""

DEFAULT_SEQUENCES = [
    ("student.student", "PID/", 4),
    ("student.registration", "REG/", 4),
    ("student.code", "STU/", 4),
    ("student.document", "DOC/", 4),
    ("document.type", "DT/", 3),
    ("student.fees.register", "FREG/", 4),
    ("student.fees.structure.line", "FSL/", 3),
    ("student.payslip", "SLIP/", 4),
    ("exam.exam", "EXM/", 4),
    ("additional.exam", "AEXM/", 4),
    ("library.card", "LCARD/", 4),
    ("library.book.issue", "ISS/", 4),
    ("library.book.request", "REQ/", 4),
    ("hostel.student", "HST/", 4),
]


class Database:
    """Thread-safe, fast SQLite database manager with WAL mode and sequence support."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = str(db_path) if db_path is not None else str(get_default_db_path())
        self._memory_conn: sqlite3.Connection | None = None
        if self.db_path == ":memory:":
            self._memory_conn = self._create_connection()
        self.init_schema()

    def _create_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        if self.db_path != ":memory:":
            conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA cache_size = -64000;")
        return conn

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Yield a transactional SQLite connection."""
        if self._memory_conn is not None:
            try:
                yield self._memory_conn
                self._memory_conn.commit()
            except Exception:
                self._memory_conn.rollback()
                raise
        else:
            conn = self._create_connection()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

    def init_schema(self) -> None:
        """Create all tables, indexes, and default sequences."""
        with self.connection() as conn:
            if self.db_path != ":memory:":
                conn.execute("PRAGMA journal_mode = WAL;")
            conn.executescript(SCHEMA_SQL)
            for code, prefix, padding in DEFAULT_SEQUENCES:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO ir_sequence (code, prefix, padding, next_val)
                    VALUES (?, ?, ?, 1)
                    """,
                    (code, prefix, padding),
                )
            apply_migrations(conn)

    def next_by_code(self, code: str, conn: sqlite3.Connection | None = None) -> str:
        """Generate next sequence string for a given Odoo sequence code."""
        if conn is not None:
            return self._next_by_code_conn(conn, code)
        with self.connection() as c:
            return self._next_by_code_conn(c, code)

    def _next_by_code_conn(self, conn: sqlite3.Connection, code: str) -> str:
        row = conn.execute(
            "SELECT prefix, padding, next_val FROM ir_sequence WHERE code = ?",
            (code,),
        ).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO ir_sequence (code, prefix, padding, next_val) VALUES (?, ?, 4, 2)",
                (code, f"{code.upper()}/"),
            )
            return f"{code.upper()}/0001"
        formatted = f"{row['prefix']}{row['next_val']:0{row['padding']}d}"
        conn.execute(
            "UPDATE ir_sequence SET next_val = next_val + 1 WHERE code = ?",
            (code,),
        )
        return formatted

    def fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        """Execute SELECT query and return list of dicts."""
        with self.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        """Execute SELECT query and return single dict or None."""
        with self.connection() as conn:
            row = conn.execute(query, params).fetchone()
            return dict(row) if row else None

    def close(self) -> None:
        """Close persistent in-memory connection if used."""
        if self._memory_conn is not None:
            self._memory_conn.close()
            self._memory_conn = None

