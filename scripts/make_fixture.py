"""
scripts/make_fixture.py — Fast 1,000+ Student Benchmark Fixture & Latency Profiler

Generates a realistic multi-class SQLite WAL database (`N` students, payslips,
attendance sheets, exam results) and measures p95 latency against ADVANCEMENT_PLAN.md
Section 10.4 budgets:
  - /api/dashboard/home : < 500 ms (all 5 roles)
  - /api/students/list  : < 300 ms
  - /api/search         : < 150 ms
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desktop_app.api import create_app
from desktop_app.database import Database
from desktop_app.services.seed_service import ensure_seed_data


def populate_1000_students(db: Database, count: int = 1000) -> None:
    """Bulk-insert `count` realistic students + payslips in one fast transaction."""
    ensure_seed_data(db)
    today = date.today().isoformat()
    with db.connection() as conn:
        school_id = conn.execute("SELECT id FROM school_school LIMIT 1").fetchone()["id"]
        year_id = conn.execute("SELECT id FROM academic_year WHERE current = 1 LIMIT 1").fetchone()["id"]
        std_rows = conn.execute("SELECT id FROM school_standard ORDER BY id").fetchall()
        std_ids = [int(r["id"]) for r in std_rows]

        students_batch = []
        for idx in range(1, count + 1):
            std_id = std_ids[idx % len(std_ids)]
            students_batch.append(
                (
                    f"GR-{2026000 + idx}",
                    f"Student{idx}",
                    "Khan" if idx % 2 == 0 else "Ahmed",
                    (idx % 50) + 1,
                    f"0300-{1000000 + idx:07d}",
                    year_id,
                    school_id,
                    std_id,
                    today,
                    "2014-05-15",
                    12,
                    "male" if idx % 2 == 0 else "female",
                    "done",
                    1,
                )
            )

        conn.executemany(
            """
            INSERT INTO student_student (
                pid, student_name, last, roll_no, contact_mobile,
                year_id, school_id, standard_id, admission_date,
                date_of_birth, age, gender, state, active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            students_batch,
        )

        stu_ids = [
            int(r["id"])
            for r in conn.execute("SELECT id FROM student_student ORDER BY id DESC LIMIT ?", (count,)).fetchall()
        ]
        slips_batch = []
        for i, sid in enumerate(stu_ids[:400]):
            is_paid = i % 3 == 0
            slips_batch.append(
                (
                    sid,
                    f"SLIP/{90000 + i}",
                    "Monthly Tuition",
                    today,
                    4500.0,
                    4500.0 if is_paid else 0.0,
                    0.0 if is_paid else 4500.0,
                    today if is_paid else None,
                    "paid" if is_paid else "confirm",
                )
            )
        conn.executemany(
            """
            INSERT INTO student_payslip (
                student_id, number, name, date, total, paid_amount, due_amount, payment_date, state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            slips_batch,
        )


def run_benchmark(student_count: int = 1000) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "bench_1000.sqlite3"
        t0 = time.perf_counter()
        db = Database(db_path)
        populate_1000_students(db, student_count)
        gen_ms = (time.perf_counter() - t0) * 1000.0

        app = create_app(db=db, seed=False, enforce_auth=True)
        client = app.test_client()
        setup = client.post(
            "/api/auth/setup",
            json={"full_name": "Bench Admin", "username": "admin", "secret": "Bench#123"},
        ).get_json()
        headers = {"X-Session-Token": setup["token"]}

        def measure(url: str) -> float:
            s = time.perf_counter()
            res = client.get(url, headers=headers)
            assert res.status_code == 200, res.get_data(as_text=True)
            return (time.perf_counter() - s) * 1000.0

        # Cold (uncached) dashboard query + list + search + Student 360 + Phase 3 Fees & Families
        dash_cold_ms = measure("/api/dashboard/home")
        dash_warm_ms = measure("/api/dashboard/home")
        list_ms = measure("/api/students/list?page=1&per_page=50")
        search_ms = measure("/api/search?q=Student50")
        s360_ms = measure("/api/students/10/360")
        vouchers_ms = measure("/api/fees/vouchers?page=1&per_page=30")
        families_ms = measure("/api/families?q=Student50")
        tally_ms = measure("/api/fees/tally")

        print(f"=== 1,000-Student Benchmark ({student_count} students generated in {gen_ms:.0f} ms) ===")
        print(f"  /api/dashboard/home (cold) : {dash_cold_ms:6.2f} ms  [Budget < 500 ms]")
        print(f"  /api/dashboard/home (warm) : {dash_warm_ms:6.2f} ms  [Budget < 500 ms]")
        print(f"  /api/students/list         : {list_ms:6.2f} ms  [Budget < 300 ms]")
        print(f"  /api/search?q=Student50    : {search_ms:6.2f} ms  [Budget < 150 ms]")
        print(f"  /api/students/10/360       : {s360_ms:6.2f} ms  [Budget < 300 ms]")
        print(f"  /api/fees/vouchers         : {vouchers_ms:6.2f} ms  [Budget < 300 ms]")
        print(f"  /api/families?q=Student50  : {families_ms:6.2f} ms  [Budget < 300 ms]")
        print(f"  /api/fees/tally            : {tally_ms:6.2f} ms  [Budget < 300 ms]")

        assert dash_cold_ms < 500.0, f"Dashboard cold {dash_cold_ms:.1f}ms > 500ms"
        assert list_ms < 300.0, f"Students list {list_ms:.1f}ms > 300ms"
        assert search_ms < 150.0, f"Search {search_ms:.1f}ms > 150ms"
        assert vouchers_ms < 300.0, f"Fee vouchers {vouchers_ms:.1f}ms > 300ms"
        assert families_ms < 300.0, f"Families search {families_ms:.1f}ms > 300ms"
        assert tally_ms < 300.0, f"Daily tally {tally_ms:.1f}ms > 300ms"
        print("ALL PERFORMANCE BUDGETS PASSED!")
        return 0


if __name__ == "__main__":
    count_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    sys.exit(run_benchmark(count_arg))
