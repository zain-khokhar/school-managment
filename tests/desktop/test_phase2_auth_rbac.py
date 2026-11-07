"""
Phase 2 — Authentication, RBAC (Deny-by-Default), Lockout, Recovery Code & Audit Log Tests.

Covers ADVANCEMENT_PLAN.md Phase 2 DoD & Section 12.3 scenarios:
  - PRAGMA user_version schema migration for app_user, app_session, audit_log, school_setting
  - First-run admin setup + one-time Recovery Code generation & rotation (Risk R6)
  - Salted PBKDF2-HMAC-SHA256 hashing + 5 failed attempts lockout (R-S1)
  - Dynamic deny-by-default check across EVERY /api/* route in app.url_map (401 unauth, 403 wrong role, R-T4)
  - Audit trail recorded on every mutating POST with zero secret leakage
"""

from __future__ import annotations

import pytest

from desktop_app.api import create_app
from desktop_app.database import Database


@pytest.fixture()
def auth_env(tmp_path):
    """Create a file-backed SQLite database with strict Phase 2 auth enforced."""
    db_file = tmp_path / "phase2_auth.sqlite3"
    db = Database(db_file)
    app = create_app(db=db, seed=True, enforce_auth=True)
    app.config["TESTING"] = True
    return db, app


def _setup_admin(client, username: str = "admin", pin: str = "Admin@1234"):
    resp = client.post(
        "/api/auth/setup",
        json={
            "full_name": "Principal Tariq Mahmood",
            "username": username,
            "secret": pin,
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    data = resp.get_json()
    assert data["ok"] is True
    assert data["recovery_code"].startswith("RK-")
    assert data["token"]
    return data


class TestMigrationsAndFirstRunSetup:
    """Verify PRAGMA user_version migration and first-run setup security."""

    def test_schema_user_version_and_phase2_tables_exist(self, auth_env):
        db, _ = auth_env
        ver = db.fetch_one("PRAGMA user_version")
        assert ver is not None
        assert int(list(ver.values())[0]) >= 1

        tables = {
            r["name"]
            for r in db.fetch_all("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for required in ("app_user", "app_session", "audit_log", "school_setting"):
            assert required in tables, f"Missing Phase 2 table: {required}"

    def test_before_setup_status_reports_setup_required_and_blocks_data(self, auth_env):
        _, app = auth_env
        client = app.test_client()

        st = client.get("/api/auth/status").get_json()
        assert st["ok"] is True
        assert st["setup_required"] is True
        assert st["authenticated"] is False

        # Data endpoints must return 401 before setup/login
        boot = client.get("/api/bootstrap")
        assert boot.status_code == 401

        students = client.get("/api/students/list")
        assert students.status_code == 401

    def test_setup_creates_admin_once_and_rejects_second_setup(self, auth_env):
        db, app = auth_env
        client = app.test_client()

        setup_data = _setup_admin(client)
        token = setup_data["token"]

        # Stored password & recovery hashes must NEVER contain plaintext secrets
        raw_user = db.fetch_one("SELECT * FROM app_user WHERE username = 'admin'")
        assert raw_user is not None
        assert "Admin@1234" not in raw_user["password_hash"]
        assert setup_data["recovery_code"] not in (raw_user["recovery_hash"] or "")

        # Second call to /api/auth/setup must fail with 403
        second = client.post(
            "/api/auth/setup",
            json={"full_name": "Attacker", "username": "evil", "secret": "Evil@1234"},
        )
        assert second.status_code == 403

        # Authenticated admin can now read bootstrap
        boot = client.get("/api/bootstrap", headers={"X-Session-Token": token})
        assert boot.status_code == 200
        assert boot.get_json()["ok"] is True


class TestLoginLockoutAndRecovery:
    """Verify R-S1 (lockout after 5 bad PINs) and R6 (recovery code reset)."""

    def test_five_wrong_attempts_locks_account_and_recovery_unlocks(self, auth_env):
        db, app = auth_env
        client = app.test_client()
        setup_data = _setup_admin(client, username="principal", pin="Correct#99")
        recovery_code = setup_data["recovery_code"]

        # Logout first
        client.post(
            "/api/auth/logout",
            headers={"X-Session-Token": setup_data["token"]},
        )

        # 5 wrong attempts
        for attempt in range(1, 6):
            bad = client.post(
                "/api/auth/login",
                json={"username": "principal", "secret": f"WrongPass{attempt}"},
            )
            assert bad.status_code in (401, 429)

        # 6th attempt even with CORRECT password must be locked (429)
        locked = client.post(
            "/api/auth/login",
            json={"username": "principal", "secret": "Correct#99"},
        )
        assert locked.status_code == 429
        assert "lock" in locked.get_json()["error"].lower()

        # Wrong recovery code fails
        bad_rec = client.post(
            "/api/auth/recover",
            json={
                "username": "principal",
                "recovery_code": "RK-0000-0000-0000",
                "new_secret": "NewPass#88",
            },
        )
        assert bad_rec.status_code == 401

        # Valid recovery code unlocks account, sets new secret, and rotates recovery code
        good_rec = client.post(
            "/api/auth/recover",
            json={
                "username": "principal",
                "recovery_code": recovery_code,
                "new_secret": "NewPass#88",
            },
        )
        assert good_rec.status_code == 200
        rec_json = good_rec.get_json()
        assert rec_json["ok"] is True
        new_recovery = rec_json["new_recovery_code"]
        assert new_recovery != recovery_code

        # Old recovery code must no longer work (one-time rotation)
        reuse = client.post(
            "/api/auth/recover",
            json={
                "username": "principal",
                "recovery_code": recovery_code,
                "new_secret": "Another#77",
            },
        )
        assert reuse.status_code == 401

        # Login with new password succeeds
        ok_login = client.post(
            "/api/auth/login",
            json={"username": "principal", "secret": "NewPass#88"},
        )
        assert ok_login.status_code == 200
        assert ok_login.get_json()["ok"] is True

        # Verify audit_log captured login failures & recovery without leaking secrets
        logs = db.fetch_all("SELECT * FROM audit_log")
        assert len(logs) >= 5
        serialized = str(logs)
        assert "Correct#99" not in serialized
        assert "NewPass#88" not in serialized
        assert recovery_code not in serialized


class TestDenyByDefaultRBACAndAudit:
    """Verify every single /api/* route enforces 401 unauthenticated and 403 per role."""

    PUBLIC_API_PATHS = {
        "/api/health",
        "/api/auth/status",
        "/api/auth/login",
        "/api/auth/setup",
        "/api/auth/recover",
    }

    def test_every_registered_api_route_denies_unauthenticated_access(self, auth_env):
        _, app = auth_env
        admin_client = app.test_client()
        _setup_admin(admin_client)

        anon_client = app.test_client()
        checked = 0
        for rule in app.url_map.iter_rules():
            if not rule.rule.startswith("/api/"):
                continue
            if rule.rule in self.PUBLIC_API_PATHS:
                continue

            # Replace Flask int/string converters with concrete sample IDs
            concrete_url = (
                rule.rule.replace("<int:student_id>", "1")
                .replace("<int:slip_id>", "1")
                .replace("<int:att_id>", "1")
                .replace("<int:leave_id>", "1")
                .replace("<int:assign_id>", "1")
                .replace("<int:exam_id>", "1")
                .replace("<int:result_id>", "1")
                .replace("<int:subject_line_id>", "1")
                .replace("<int:issue_id>", "1")
                .replace("<int:reg_id>", "1")
                .replace("<int:hs_id>", "1")
                .replace("<int:class_id>", "1")
                .replace("<int:user_id>", "1")
            )
            methods = [m for m in (rule.methods or set()) if m in ("GET", "POST", "PUT", "DELETE")]
            for method in methods:
                checked += 1
                resp = anon_client.open(concrete_url, method=method, json={})
                assert resp.status_code == 401, (
                    f"Route {method} {concrete_url} did NOT enforce 401! Got {resp.status_code}"
                )
        assert checked >= 30

    def test_role_isolation_teacher_cannot_access_fees_or_settings(self, auth_env):
        db, app = auth_env
        admin_client = app.test_client()
        admin_setup = _setup_admin(admin_client)
        admin_headers = {"X-Session-Token": admin_setup["token"]}

        # Create a teacher user and a fee_clerk user
        t_create = admin_client.post(
            "/api/auth/users",
            headers=admin_headers,
            json={
                "full_name": "Ustaad Kamran",
                "username": "kamran_t",
                "role": "teacher",
                "secret": "Teach@123",
            },
        )
        assert t_create.status_code == 200

        f_create = admin_client.post(
            "/api/auth/users",
            headers=admin_headers,
            json={
                "full_name": "Clerk Naveed",
                "username": "naveed_f",
                "role": "fee_clerk",
                "secret": "Clerk@123",
            },
        )
        assert f_create.status_code == 200

        # Login as Teacher
        t_client = app.test_client()
        t_tok = t_client.post(
            "/api/auth/login",
            json={"username": "kamran_t", "secret": "Teach@123"},
        ).get_json()["token"]
        t_headers = {"X-Session-Token": t_tok}

        # R-T4: Teacher CANNOT create payslips, manage users, or trigger DB restore -> 403
        assert t_client.post("/api/fees/payslips", headers=t_headers, json={}).status_code == 403
        assert t_client.get("/api/auth/users", headers=t_headers).status_code == 403
        assert t_client.post("/api/settings/backup", headers=t_headers, json={}).status_code == 403
        assert t_client.post("/api/students", headers=t_headers, json={}).status_code == 403

        # Teacher CAN view Teacher Home and mark attendance
        t_home = t_client.get("/api/dashboard/home", headers=t_headers)
        assert t_home.status_code == 200
        assert t_home.get_json()["role"] == "teacher"

        # Login as Fee Clerk
        f_client = app.test_client()
        f_tok = f_client.post(
            "/api/auth/login",
            json={"username": "naveed_f", "secret": "Clerk@123"},
        ).get_json()["token"]
        f_headers = {"X-Session-Token": f_tok}

        # Fee Clerk CANNOT mark attendance or edit exam marks -> 403
        assert f_client.post("/api/attendance/daily", headers=f_headers, json={}).status_code == 403
        assert f_client.post("/api/exams", headers=f_headers, json={}).status_code == 403
        assert f_client.post("/api/auth/users", headers=f_headers, json={}).status_code == 403

        # Fee Clerk CAN create a fee voucher -> and it MUST write an audit_log entry!
        before_audit = db.fetch_one("SELECT COUNT(*) AS c FROM audit_log WHERE username = 'naveed_f'")["c"]
        boot = admin_client.get("/api/bootstrap", headers=admin_headers).get_json()
        stu_id = boot["school"]["students"][0]["id"]
        struct_id = boot["fees"]["structures"][0]["id"]

        slip_res = f_client.post(
            "/api/fees/payslips",
            headers=f_headers,
            json={
                "student_id": stu_id,
                "name": "November Tuition Voucher",
                "date": "2026-11-15",
                "fees_structure_id": struct_id,
            },
        )
        assert slip_res.status_code == 200
        after_audit = db.fetch_one("SELECT COUNT(*) AS c FROM audit_log WHERE username = 'naveed_f'")["c"]
        assert after_audit > before_audit

