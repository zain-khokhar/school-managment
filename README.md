# School Management Desktop ERP

Offline-first Windows Desktop ERP built on **Python 3.12 + Flask + SQLite WAL + pywebview**, integrating all 10 school management domains (`school`, `school_fees`, `school_attendance`, `assignment`, `timetable`, `exam`, `library`, `school_event`, `school_hostel`, `school_transport`) under the **"Kaghaz aur Siyahi"** design system.

---

## Key Capabilities (Phase 1 & Phase 2)

- **Offline Role-Based Access Control (RBAC) & Audit Trail**:
  - `PBKDF2-HMAC-SHA256` (`260,000` iterations + per-user random salt) authentication, SHA-256 hashed session tokens (`HttpOnly; SameSite=Strict`), and 5-attempt / 15-minute brute-force lockout.
  - First-Run Principal/Admin Setup with a printable/copyable one-time **Emergency Recovery Code (`RK-XXXX-XXXX-XXXX`)** that automatically rotates upon use.
  - Deny-by-default route matrix across 7 staff roles (`admin`, `principal`, `teacher`, `fee_clerk`, `front_desk`, `exam_incharge`, `librarian`) + append-only `audit_log` with automatic secret redaction.
- **5 Role-Aware "Aaj Ka Din" Operational Homes (`< 50 ms` on 1,000 students)**:
  - **Principal / Admin**: Today's fee collection vs yesterday, attendance %, fee arrears, actionable exception queue (inline leave approval, 1-click backup, unmarked class roll call), setup checklist, and live staff activity feed.
  - **Teacher**: Assigned classes, 1-click roll call, daily timetable periods, pending marks, active homework.
  - **Fee Clerk**: Daily collection tally, arrears summary, quick voucher counter with confirmation guard.
  - **Front Desk**: Admissions today, live class seat availability meter, incomplete admissions queue.
  - **Exam In-Charge**: Active exams, marksheet completion matrix, re-evaluation requests.
- **Student 360° Unified Profile**:
  - Single-click student workspace with 6 smart buttons (Attendance %, Fee Balance, Latest Exam, Library Books, Transport Route, Boarding/Hostel), 5 detail tabs, sibling detection, and verified audit timeline.
- **SQLite WAL Safety, Migrations & Settings**:
  - Versioned `PRAGMA user_version` schema migrations (`desktop_app/db/migrate.py`).
  - Online `sqlite3.Connection.backup()` snapshots, `PRAGMA integrity_check`, automatic pre-restore safety snapshot, bilingual Urdu print toggle (`D3`), and Hostel/Transport module visibility controls.

---

## Quick Start (Development)

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run startup self-test (verifies SQLite integrity, 401 auth gate & UI shell)
python run_desktop.py --self-test

# 3. Launch native desktop application window
python run_desktop.py
```

---

## Verification, Tests & Benchmarks

```powershell
# Python unit & integration suite with coverage (>= 80% gate)
python -m pytest tests/ --cov=desktop_app --cov-report=term-missing

# Built-in Node.js UI unit tests & static ES-module import/syntax verifier
node --test tests/js/format_and_icons.test.mjs
python scripts/verify_js_modules.py

# Anti-monolith file size check (JS <= 300, Routes <= 400, Services/CSS <= 600 lines)
python scripts/check_file_sizes.py

# 1,000-student latency benchmark (< 500 ms dashboard, < 300 ms list, < 150 ms search)
python scripts/make_fixture.py 1000
```

---

## Standalone `.exe` Packaging

```powershell
pyinstaller --noconfirm SchoolManagementERP.spec
Copy-Item -Force dist\SchoolManagementERP.exe .\SchoolManagementERP.exe
.\SchoolManagementERP.exe --self-test
```
