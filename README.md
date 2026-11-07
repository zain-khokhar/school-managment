# School Management Desktop ERP

Offline-first Windows Desktop ERP built on **Python 3.12 + Flask + SQLite WAL + pywebview**, integrating all 10 school management domains (`school`, `school_fees`, `school_attendance`, `assignment`, `timetable`, `exam`, `library`, `school_event`, `school_hostel`, `school_transport`) with an institutional paper-and-ink enterprise interface (100% English UI, zero emojis, tabular-nums typography).

---

## Key Capabilities (Phases 1 – 3)

- **Exact-Paisa Fee Engine, Concessions & Idempotent Bulk Vouchers (Phase 3)**:
  - All monetary storage and calculations run in integer paisa (`1 PKR = 100 paisa`) — zero IEEE-754 floating-point drift across partial receipts, concessions, and daily cash tallies.
  - Configurable school-wide fee rules (`sibling_discount`, `late_fee`, `vacation_discount`, `custom_discount`) and individual student scholarships/concessions (`fee_concession`).
  - Idempotent monthly class/school voucher generator with automatic unpaid arrears carry-forward (`rolled_over` state prevents double-counting).
  - Partial and full fee collection across `Cash`, `Bank`, `Cheque`, and `Online` modes, 30-second clerk quick-undo window, and post-30s Administrator/Principal-only reversal with mandatory audit reason.
- **Consolidated Family Ledger & Print Infrastructure (Phase 3)**:
  - Search families by guardian name, mobile, CNIC, student name, or GR number; link siblings under a shared guardian (`school_parent` + `students_parents_rel`).
  - Single-transaction multi-sibling fee collection auto-allocating oldest due vouchers first and producing both itemized student receipts and a combined Family Receipt.
  - Isolated `@media print` engine for **3-Part Horizontal A4 Landscape Bank Fee Vouchers** (`Bank Copy`, `School Copy`, `Parent Copy` with deterministic offline verification barcode), **Official A4 Fee Slips**, and **80mm Thermal POS Roll Receipts**.
- **Offline Role-Based Access Control (RBAC) & Audit Trail (Phase 2)**:
  - `PBKDF2-HMAC-SHA256` (`260,000` iterations + per-user random salt) authentication, SHA-256 hashed session tokens (`HttpOnly; SameSite=Strict`), and 5-attempt / 15-minute brute-force lockout.
  - First-Run Principal/Admin Setup with a printable one-time **Emergency Recovery Code (`RK-XXXX-XXXX-XXXX`)** that automatically rotates upon use.
  - Deny-by-default route matrix across 7 staff roles (`admin`, `principal`, `teacher`, `fee_clerk`, `front_desk`, `exam_incharge`, `librarian`) + append-only `audit_log` with automatic secret redaction.
- **5 Role-Aware Daily Command Center Homes (`< 50 ms` on 1,000 students)**:
  - Tailored operational home screens for **Principal / Admin**, **Teacher**, **Fee Clerk**, **Front Desk**, and **Exam In-Charge**, plus unified **Student 360° Profile** and **SQLite WAL Safe Backup & Restore**.

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

# 1,000-student latency benchmark (< 500 ms dashboard, < 300 ms list/fees, < 150 ms search)
python scripts/make_fixture.py 1000
```
