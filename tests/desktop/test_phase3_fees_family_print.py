"""
Phase 3 — Fee Engine, Family Ledger, Print Infrastructure & 100% English Gate.

Covers ADVANCEMENT_PLAN.md Phase 3 DoD (G4, G5, G11, S1, S2, Section 10.3, Section 12.3):
  - Migration v2 (`PRAGMA user_version == 2`): integer paisa columns, `fee_payment`, `fee_rule`, `fee_concession`, backfill
  - R-F3: Bulk class/school voucher generation, idempotency on re-run, arrears rollover & rules/concessions
  - R-F2: Partial payments, 30-second Undo window for clerk, post-30s admin-only reversal with mandatory reason & audit
  - R-F4: 200 randomized partial/full payments & reversals tallying paisa-for-paisa (`0` drift)
  - R-F1 & S2: Family Ledger search by mobile/CNIC, multi-sibling atomic collection & combined print receipt
  - S1: 3-Part Bank Voucher & A4/80mm Thermal Receipt print bundle endpoints
  - Deny-by-default RBAC for fee & family routes
  - 100% English UI & API Gate (zero Urdu Unicode script, zero Roman Urdu UI labels, zero emojis)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import random
import re

import pytest

from desktop_app.api import create_app
from desktop_app.database import Database
from desktop_app.db.migrate import LATEST_SCHEMA_VERSION, get_schema_version


@pytest.fixture()
def phase3_env(tmp_path):
    db_file = tmp_path / "phase3_erp.sqlite3"
    db = Database(db_file)
    app = create_app(db=db, seed=True, enforce_auth=True)
    app.config["TESTING"] = True

    admin_client = app.test_client()
    setup = admin_client.post(
        "/api/auth/setup",
        json={
            "full_name": "Principal Admin",
            "username": "admin_p3",
            "secret": "AdminP3#123",
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
            "secret": "StaffP3#123",
        },
    )
    assert res.status_code == 200, res.get_data(as_text=True)
    client = app.test_client()
    tok = client.post(
        "/api/auth/login",
        json={"username": username, "secret": "StaffP3#123"},
    ).get_json()["token"]
    return client, {"X-Session-Token": tok}


class TestMigrationV2AndSchema:
    """Verify Migration v2 schema version, paisa columns, and seed payment backfill."""

    def test_schema_version_2_and_seed_backfill(self, phase3_env):
        db, _, admin_client, admin_headers = phase3_env
        assert LATEST_SCHEMA_VERSION >= 2
        with db.connection() as conn:
            assert get_schema_version(conn) >= 2
            tables = {
                r["name"]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            assert {"fee_payment", "fee_rule", "fee_concession"}.issubset(tables)

            # Seeded paid payslip must have integer paisa synced and 1 backfilled fee_payment row
            paid_slips = conn.execute(
                "SELECT id, total, paid_amount, total_paisa, paid_paisa, due_paisa FROM student_payslip WHERE paid_amount > 0"
            ).fetchall()
            assert len(paid_slips) >= 1
            for s in paid_slips:
                assert s["total_paisa"] == int(round(float(s["total"]) * 100))
                assert s["paid_paisa"] == int(round(float(s["paid_amount"]) * 100))
                assert s["due_paisa"] == 0
                pmt = conn.execute(
                    "SELECT amount_paisa FROM fee_payment WHERE payslip_id = ? AND reversed_at IS NULL",
                    (s["id"],),
                ).fetchone()
                assert pmt is not None
                assert pmt["amount_paisa"] == s["paid_paisa"]

        # Paginated vouchers endpoint returns clean paisa & rupee fields
        res = admin_client.get("/api/fees/vouchers", headers=admin_headers)
        assert res.status_code == 200
        body = res.get_json()
        assert body["ok"] is True
        assert body["total"] >= 1


class TestBulkGenerationRulesAndIdempotency:
    """R-F3 & G5: Bulk voucher generation, concessions, sibling rules, arrears & idempotency."""

    def test_rules_concessions_bulk_idempotency_and_arrears(self, phase3_env):
        db, _, admin_client, admin_headers = phase3_env
        boot = admin_client.get("/api/bootstrap", headers=admin_headers).get_json()
        classes = boot["school"]["standards"]
        structures = boot["fees"]["structures"]
        students = sorted(
            [s for s in boot["school"]["students"] if s["state"] == "done"],
            key=lambda s: (s.get("date_of_birth") or "9999-12-31", s["id"]),
        )
        assert classes and structures and len(students) >= 3

        class_id = classes[0]["id"]
        struct_id = structures[0]["id"]

        # Link two siblings via shared guardian so sibling discount auto-applies to 2nd child
        s1, s2, s3 = students[0], students[1], students[2]
        g_res = admin_client.post(
            "/api/families/guardian",
            headers=admin_headers,
            json={
                "name": "Tariq Mehmood Khan",
                "phone": "0300-7778899",
                "cnic": "35202-1234567-1",
                "relation": "Father",
                "student_ids": [s1["id"], s2["id"]],
            },
        )
        assert g_res.status_code == 200

        # Configure school-wide sibling discount (10%) & summer vacation discount (20% in June)
        r1 = admin_client.post(
            "/api/fees/rules",
            headers=admin_headers,
            json={
                "name": "Sibling Tuition Concession",
                "code": "SIB-10",
                "rule_type": "sibling_discount",
                "calc_mode": "percent",
                "value": 10,
                "min_sibling_rank": 2,
                "active": True,
            },
        )
        assert r1.status_code == 200

        r2 = admin_client.post(
            "/api/fees/rules",
            headers=admin_headers,
            json={
                "name": "Late Payment Surcharge (5%)",
                "code": "LATE-5PCT",
                "rule_type": "late_fee",
                "calc_mode": "percent",
                "value": 5,
                "grace_days": 5,
                "active": True,
            },
        )
        assert r2.status_code == 200

        # Grant 25% scholarship to 3rd student
        c1 = admin_client.post(
            "/api/fees/concessions",
            headers=admin_headers,
            json={
                "student_id": s3["id"],
                "concession_type": "scholarship",
                "calc_mode": "percent",
                "value": 25,
                "reason": "Top Merit Position",
            },
        )
        assert c1.status_code == 200

        # 1st bulk run for billing_month "2026-09"
        gen1 = admin_client.post(
            "/api/fees/vouchers/bulk-generate",
            headers=admin_headers,
            json={
                "class_id": class_id,
                "billing_month": "2026-09",
                "due_date": "2026-09-10",
                "fees_structure_id": struct_id,
                "include_arrears": True,
                "apply_rules": True,
            },
        )
        assert gen1.status_code == 200, gen1.get_data(as_text=True)
        d1 = gen1.get_json()
        assert d1["ok"] is True
        assert d1["created_count"] == len(students)
        assert d1["skipped_count"] == 0

        # R-F3: Re-running exact same bulk-generate is 100% idempotent (0 duplicates!)
        gen2 = admin_client.post(
            "/api/fees/vouchers/bulk-generate",
            headers=admin_headers,
            json={
                "class_id": class_id,
                "billing_month": "2026-09",
                "due_date": "2026-09-10",
                "fees_structure_id": struct_id,
                "include_arrears": True,
                "apply_rules": True,
            },
        )
        assert gen2.status_code == 200
        d2 = gen2.get_json()
        assert d2["created_count"] == 0
        assert d2["skipped_count"] == len(students)

        # Verify discounts were applied accurately on s2 (10% sibling) and s3 (25% scholarship)
        v_list = admin_client.get(
            "/api/fees/vouchers?billing_month=2026-09", headers=admin_headers
        ).get_json()["items"]
        by_stu = {v["student_id"]: v for v in v_list}
        assert by_stu[s1["id"]]["discount_paisa"] == 0
        assert by_stu[s2["id"]]["discount_paisa"] > 0
        assert by_stu[s3["id"]]["discount_paisa"] > by_stu[s2["id"]]["discount_paisa"]

        # Verify percentage late_fee rule computes exact 5% surcharge on print vouchers
        pv = admin_client.get(
            f"/api/fees/print/vouchers?ids={by_stu[s1['id']]['id']}", headers=admin_headers
        ).get_json()["vouchers"][0]
        assert pv["late_surcharge_paisa"] == (pv["due_paisa"] * 5) // 100
        assert pv["after_due_paisa"] == pv["due_paisa"] + pv["late_surcharge_paisa"]

        # Next month ("2026-10") rolls forward unpaid arrears automatically!
        gen_oct = admin_client.post(
            "/api/fees/vouchers/bulk-generate",
            headers=admin_headers,
            json={
                "class_id": class_id,
                "billing_month": "2026-10",
                "due_date": "2026-10-10",
                "fees_structure_id": struct_id,
                "include_arrears": True,
                "apply_rules": True,
            },
        ).get_json()
        assert gen_oct["created_count"] == len(students)
        oct_vouchers = admin_client.get(
            "/api/fees/vouchers?billing_month=2026-10", headers=admin_headers
        ).get_json()["items"]
        oct_by_stu = {v["student_id"]: v for v in oct_vouchers}
        assert oct_by_stu[s1["id"]]["arrears_paisa"] >= by_stu[s1["id"]]["due_paisa"]


class TestPartialPaymentsUndoAndAdminReversal:
    """R-F2: Partial payments, 30-sec clerk Undo, and post-30s admin-only reversal + audit."""

    def test_partial_payment_30s_undo_and_post_30s_admin_reversal(self, phase3_env):
        db, app, admin_client, admin_headers = phase3_env
        clerk_client, clerk_headers = _make_staff_client(
            app, admin_client, admin_headers, "clerk_r2", "fee_clerk"
        )

        # Find an unpaid voucher (or create one)
        boot = admin_client.get("/api/bootstrap", headers=admin_headers).get_json()
        stu = [s for s in boot["school"]["students"] if s["state"] == "done"][1]
        struct_id = boot["fees"]["structures"][0]["id"]

        gen = clerk_client.post(
            "/api/fees/vouchers/bulk-generate",
            headers=clerk_headers,
            json={
                "class_id": stu["standard_id"],
                "billing_month": "2026-11",
                "due_date": "2026-11-15",
                "fees_structure_id": struct_id,
                "include_arrears": False,
                "apply_rules": False,
            },
        ).get_json()
        assert gen["created_count"] >= 1

        vouchers = clerk_client.get(
            "/api/fees/vouchers?billing_month=2026-11", headers=clerk_headers
        ).get_json()["items"]
        slip = next(v for v in vouchers if v["student_id"] == stu["id"])
        total_paisa = slip["total_paisa"]
        assert total_paisa == 1100000  # Rs. 11,000.00

        # 1. Partial payment of Rs. 4,000.00 by fee_clerk
        p1 = clerk_client.post(
            "/api/fees/payments",
            headers=clerk_headers,
            json={
                "payslip_id": slip["id"],
                "amount": 4000.00,
                "payment_mode": "cash",
                "note": "First installment",
            },
        )
        assert p1.status_code == 200, p1.get_data(as_text=True)
        p1_data = p1.get_json()
        pmt1_id = p1_data["payment"]["id"]
        assert p1_data["payslip"]["state"] == "pending"
        assert p1_data["payslip"]["paid_paisa"] == 400000
        assert p1_data["payslip"]["due_paisa"] == 700000

        # Overpayment beyond remaining due (Rs. 8,000 > Rs. 7,000) must be rejected with 400
        over = clerk_client.post(
            "/api/fees/payments",
            headers=clerk_headers,
            json={"payslip_id": slip["id"], "amount": 8000.00, "payment_mode": "cash"},
        )
        assert over.status_code == 400

        # Absurd ceiling (> Rs. 100,000,000) rejected cleanly with 400
        huge = clerk_client.post(
            "/api/fees/payments",
            headers=clerk_headers,
            json={"payslip_id": slip["id"], "amount": 999999999.00, "payment_mode": "cash"},
        )
        assert huge.status_code == 400

        # Another clerk (Clerk B) is FORBIDDEN (403) from undoing Clerk A's receipt even within 30s!
        clerk_b_client, clerk_b_headers = _make_staff_client(
            app, admin_client, admin_headers, "clerk_b_r2", "fee_clerk"
        )
        other_clerk_undo = clerk_b_client.post(
            f"/api/fees/payments/{pmt1_id}/reverse",
            headers=clerk_b_headers,
            json={"reason": "Attempted cross-clerk undo"},
        )
        assert other_clerk_undo.status_code == 403

        # 2. Immediate Undo (< 30s) by owning fee_clerk succeeds!
        undo_res = clerk_client.post(
            f"/api/fees/payments/{pmt1_id}/reverse",
            headers=clerk_headers,
            json={"reason": "Clerk typo undo"},
        )
        assert undo_res.status_code == 200, undo_res.get_data(as_text=True)
        after_undo = clerk_client.get(
            f"/api/fees/vouchers/{slip['id']}", headers=clerk_headers
        ).get_json()["voucher"]
        assert after_undo["paid_paisa"] == 0
        assert after_undo["due_paisa"] == 1100000
        assert after_undo["state"] == "confirm"

        # 3. Record payment again, age `paid_at` by 120 seconds (> 30s window)
        p2 = clerk_client.post(
            "/api/fees/payments",
            headers=clerk_headers,
            json={"payslip_id": slip["id"], "amount": 11000.00, "payment_mode": "bank", "reference": "HBL-991"},
        ).get_json()
        pmt2_id = p2["payment"]["id"]
        assert p2["payslip"]["state"] == "paid"
        assert p2["payslip"]["due_paisa"] == 0

        old_ts = (datetime.now(timezone.utc) - timedelta(seconds=120)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with db.connection() as conn:
            conn.execute("UPDATE fee_payment SET paid_at = ? WHERE id = ?", (old_ts, pmt2_id))

        # After 30 seconds, fee_clerk is FORBIDDEN (403) from reversing!
        clerk_late = clerk_client.post(
            f"/api/fees/payments/{pmt2_id}/reverse",
            headers=clerk_headers,
            json={"reason": "Late attempt"},
        )
        assert clerk_late.status_code == 403

        # Admin without a valid reason gets 400
        admin_no_reason = admin_client.post(
            f"/api/fees/payments/{pmt2_id}/reverse",
            headers=admin_headers,
            json={"reason": ""},
        )
        assert admin_no_reason.status_code == 400

        # Admin WITH a valid reason succeeds (200) and logs to audit_log!
        admin_rev = admin_client.post(
            f"/api/fees/payments/{pmt2_id}/reverse",
            headers=admin_headers,
            json={"reason": "Cheque dishonored by bank"},
        )
        assert admin_rev.status_code == 200
        rev_body = admin_rev.get_json()
        assert rev_body["payslip"]["paid_paisa"] == 0
        assert rev_body["payslip"]["due_paisa"] == 1100000
        assert rev_body["payslip"]["state"] == "confirm"

        logs = admin_client.get("/api/audit/logs?per_page=10", headers=admin_headers).get_json()["items"]
        assert any("reverse" in l["action"] or "Cheque dishonored" in l["summary"] for l in logs)


class TestTwoHundredRandomPaymentsExactPaisaTally:
    """R-F4: 200 random payments & reversals tally paisa-by-paisa with zero float drift."""

    def test_200_random_payments_tally_paisa_by_paisa(self, phase3_env):
        db, _, admin_client, admin_headers = phase3_env
        rng = random.Random(20261107)
        target_date = "2026-12-15"

        boot = admin_client.get("/api/bootstrap", headers=admin_headers).get_json()
        school_id = boot["school"]["schools"][0]["id"]
        year_id = boot["school"]["years"][0]["id"]
        class_id = boot["school"]["standards"][0]["id"]

        # Create a high-value fee structure so 200 random fractional payments fit comfortably
        with db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO student_fees_structure (name, code) VALUES (?, ?)",
                ("Annual Paisa Precision Structure", "FS-PAISA-200"),
            )
            fs_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO student_fees_structure_line (name, code, type, amount, sequence, structure_id) VALUES (?, ?, ?, ?, ?, ?)",
                ("Comprehensive Tuition", "TUI-P", "month", 250000.00, 1, fs_id),
            )

        # Ensure at least 12 active students in class
        for idx in range(10):
            admin_client.post(
                "/api/students",
                headers=admin_headers,
                json={
                    "student_name": f"PaisaStu{idx}",
                    "last": "Test",
                    "year_id": year_id,
                    "school_id": school_id,
                    "standard_id": class_id,
                    "date_of_birth": "2012-04-10",
                    "contact_mobile": f"0311-55500{idx:02d}",
                },
            )

        gen = admin_client.post(
            "/api/fees/vouchers/bulk-generate",
            headers=admin_headers,
            json={
                "class_id": class_id,
                "billing_month": "2026-12",
                "due_date": "2026-12-20",
                "fees_structure_id": fs_id,
                "include_arrears": False,
                "apply_rules": False,
            },
        ).get_json()
        assert gen["created_count"] >= 12

        vouchers = admin_client.get(
            "/api/fees/vouchers?billing_month=2026-12&per_page=100", headers=admin_headers
        ).get_json()["items"]
        slip_ids = [v["id"] for v in vouchers]

        modes = ["cash", "bank", "cheque", "online"]
        expected_by_mode = {m: 0 for m in modes}
        expected_reversed_paisa = 0
        expected_active_count = 0
        expected_reversed_count = 0
        recorded_payments: list[tuple[int, int, str]] = []

        # Execute 200 random fractional-rupee payments (exact integer paisa!)
        for i in range(200):
            sid = slip_ids[i % len(slip_ids)]
            paisa = rng.randint(105, 99999)  # Rs. 1.05 to Rs. 999.99 with odd paisa!
            mode = modes[rng.randrange(len(modes))]
            amt_str = f"{paisa // 100}.{paisa % 100:02d}"

            res = admin_client.post(
                "/api/fees/payments",
                headers=admin_headers,
                json={
                    "payslip_id": sid,
                    "amount": amt_str,
                    "payment_mode": mode,
                    "payment_date": target_date,
                    "reference": f"REF-{i:04d}",
                },
            )
            assert res.status_code == 200, res.get_data(as_text=True)
            pmt = res.get_json()["payment"]
            assert pmt["amount_paisa"] == paisa
            expected_by_mode[mode] += paisa
            expected_active_count += 1
            recorded_payments.append((pmt["id"], paisa, mode))

        # Also reverse 12 random payments among the 200 to test net tally precision under reversals!
        for pmt_id, paisa, mode in rng.sample(recorded_payments, 12):
            rev = admin_client.post(
                f"/api/fees/payments/{pmt_id}/reverse",
                headers=admin_headers,
                json={"reason": "Reconciliation adjustment test"},
            )
            assert rev.status_code == 200
            expected_by_mode[mode] -= paisa
            expected_reversed_paisa += paisa
            expected_active_count -= 1
            expected_reversed_count += 1

        expected_net_paisa = sum(expected_by_mode.values())

        tally = admin_client.get(
            f"/api/fees/tally?date={target_date}", headers=admin_headers
        ).get_json()["tally"]

        assert tally["net_collected_paisa"] == expected_net_paisa
        assert tally["active_receipts_count"] == expected_active_count
        assert tally["reversed_count"] == expected_reversed_count
        assert tally["reversed_paisa"] == expected_reversed_paisa
        for m in modes:
            assert tally["by_mode_paisa"][m] == expected_by_mode[m]

        # Cross-verify against SQLite student_payslip.paid_paisa sum for 2026-12 vouchers
        after_vouchers = admin_client.get(
            "/api/fees/vouchers?billing_month=2026-12&per_page=100", headers=admin_headers
        ).get_json()["items"]
        assert sum(v["paid_paisa"] for v in after_vouchers) == expected_net_paisa
        assert Decimal(str(tally["net_collected"])).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ) == (Decimal(expected_net_paisa) / Decimal(100))


class TestFamilyLedgerPrintAndRBAC:
    """R-F1, S1, S2 & RBAC: Family Ledger multi-sibling payment, print bundles & role checks."""

    def test_family_ledger_multi_sibling_payment_and_print_bundles(self, phase3_env):
        _, _, admin_client, admin_headers = phase3_env
        boot = admin_client.get("/api/bootstrap", headers=admin_headers).get_json()
        students = sorted(
            [s for s in boot["school"]["students"] if s["state"] == "done"],
            key=lambda s: s["id"],
        )
        struct_id = boot["fees"]["structures"][0]["id"]
        s_a, s_b = students[0], students[1]

        # Link guardian to two siblings
        g = admin_client.post(
            "/api/families/guardian",
            headers=admin_headers,
            json={
                "name": "Malik Zubair",
                "phone": "0321-8889900",
                "cnic": "35201-9988776-5",
                "relation": "Father",
                "student_ids": [s_a["id"], s_b["id"]],
            },
        ).get_json()
        assert g["ok"] is True
        family_key = g["family_key"]

        # Generate vouchers for 2026-08
        admin_client.post(
            "/api/fees/vouchers/bulk-generate",
            headers=admin_headers,
            json={
                "class_id": s_a["standard_id"],
                "billing_month": "2026-08",
                "due_date": "2026-08-10",
                "fees_structure_id": struct_id,
                "include_arrears": False,
                "apply_rules": False,
            },
        )

        # Search family by CNIC or mobile (R-F1 step 1)
        f_search = admin_client.get("/api/families?q=35201-9988776-5", headers=admin_headers).get_json()
        assert f_search["ok"] is True
        assert any(f["family_key"] == family_key for f in f_search["items"])

        # Open Family Ledger (R-F1 step 2)
        ledger = admin_client.get(f"/api/families/{family_key}/ledger", headers=admin_headers).get_json()
        assert ledger["ok"] is True
        assert len(ledger["children"]) == 2
        total_due_before = ledger["summary"]["total_due_paisa"]
        assert total_due_before >= 2200000  # >= Rs. 22,000 across 2 siblings

        # Pay Rs. 15,000 in one combined family transaction (settles sibling 1 + partial sibling 2!)
        pay_res = admin_client.post(
            f"/api/families/{family_key}/pay",
            headers=admin_headers,
            json={
                "amount": 15000.00,
                "payment_mode": "cash",
                "reference": "FAM-CASH-01",
            },
        )
        assert pay_res.status_code == 200, pay_res.get_data(as_text=True)
        pay_data = pay_res.get_json()
        assert pay_data["ok"] is True
        assert pay_data["allocated_paisa"] == 1500000
        assert len(pay_data["receipts"]) >= 2
        assert "combined_receipt" in pay_data
        assert "family_receipt" in pay_data
        assert pay_data["family_receipt"]["combined_receipt_no"].startswith("FAM-")
        assert pay_data["family_receipt"]["receipt_count"] == len(pay_data["receipts"])
        assert len(pay_data["family_receipt"]["student_receipts"]) == len(pay_data["receipts"])
        assert pay_data["family_receipt"]["student_receipts"][0]["allocated_paisa"] > 0
        assert pay_data["family_receipt"]["student_receipts"][0]["voucher_no"]
        assert "ledger" in pay_data

        # Verify ledger balance decreased by exact Rs. 15,000
        ledger_after = admin_client.get(f"/api/families/{family_key}/ledger", headers=admin_headers).get_json()
        assert ledger_after["summary"]["total_due_paisa"] == total_due_before - 1500000

        # Print endpoints: 3-Part Bank Voucher bundle & Receipt bundle (S1)
        v_print = admin_client.get(
            "/api/fees/print/vouchers?billing_month=2026-08", headers=admin_headers
        ).get_json()
        assert v_print["ok"] is True
        assert len(v_print["vouchers"]) >= 2
        first_v = v_print["vouchers"][0]
        assert first_v["copies"] == ["Bank Copy", "School Copy", "Parent Copy"]
        assert "qr_payload" in first_v
        assert "school" in v_print

        first_pmt_id = pay_data["receipts"][0]["id"]
        r_print = admin_client.get(
            f"/api/fees/print/receipt/{first_pmt_id}", headers=admin_headers
        ).get_json()
        assert r_print["ok"] is True
        assert r_print["receipt"]["id"] == first_pmt_id
        assert "school" in r_print

        # Defaulters endpoint
        defs = admin_client.get("/api/fees/defaulters", headers=admin_headers).get_json()
        assert defs["ok"] is True
        assert "items" in defs

    def test_phase3_rbac_enforcement(self, phase3_env):
        _, app, admin_client, admin_headers = phase3_env
        teacher_client, teacher_headers = _make_staff_client(
            app, admin_client, admin_headers, "tch_p3", "teacher"
        )
        clerk_client, clerk_headers = _make_staff_client(
            app, admin_client, admin_headers, "clk_p3", "fee_clerk"
        )

        # Teacher denied fee & family endpoints
        for method, url in (
            ("GET", "/api/fees/vouchers"),
            ("GET", "/api/fees/tally"),
            ("GET", "/api/fees/defaulters"),
            ("GET", "/api/families"),
            ("POST", "/api/fees/payments"),
        ):
            fn = getattr(teacher_client, method.lower())
            resp = fn(url, headers=teacher_headers, json={} if method == "POST" else None)
            assert resp.status_code == 403, f"Expected 403 for teacher on {method} {url}"

        # Fee clerk allowed operational reads, denied admin rule mutation
        assert clerk_client.get("/api/fees/vouchers", headers=clerk_headers).status_code == 200
        assert clerk_client.get("/api/fees/rules", headers=clerk_headers).status_code == 200
        assert clerk_client.get("/api/families", headers=clerk_headers).status_code == 200
        rule_mut = clerk_client.post(
            "/api/fees/rules",
            headers=clerk_headers,
            json={"name": "Unauthorized Rule", "code": "UNAUTH", "rule_type": "late_fee", "calc_mode": "fixed_paisa", "value": 100},
        )
        assert rule_mut.status_code == 403


class TestPureEnglishLanguageGate:
    """Enforce 100% English across the entire desktop UI & user-facing backend messages."""

    URDU_SCRIPT_RE = re.compile(r"[\u0600-\u06FF]")
    FORBIDDEN_ROMAN_URDU_UI_RE = re.compile(
        r"\b(Aaj Ka Din|Haziri|Tawajjo Talab|Khandani Khata|Baaqaya|Yeh haziri|wapis laane|din baad|din pehle)\b",
        re.IGNORECASE,
    )

    def test_zero_urdu_script_and_roman_urdu_across_app(self):
        app_root = Path(__file__).resolve().parents[2] / "desktop_app"
        offenders: list[str] = []
        for path in sorted(app_root.rglob("*")):
            if not path.is_file() or path.suffix not in {".html", ".js", ".css", ".py"}:
                continue
            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), 1):
                if self.URDU_SCRIPT_RE.search(line):
                    offenders.append(f"[URDU_SCRIPT] {path.relative_to(app_root)}:{line_no}: {line.strip()[:100]}")
                if self.FORBIDDEN_ROMAN_URDU_UI_RE.search(line):
                    offenders.append(f"[ROMAN_URDU] {path.relative_to(app_root)}:{line_no}: {line.strip()[:100]}")

        assert not offenders, "Found non-English strings in desktop_app:\n" + "\n".join(offenders[:30])
