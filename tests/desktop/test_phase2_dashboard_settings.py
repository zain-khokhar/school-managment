"""
Phase 2 — Role Dashboards ("Aaj Ka Din" x5), Student 360°, Settings, Backup Drill & UI Polish Gate.

Covers ADVANCEMENT_PLAN.md Phase 2 DoD & Section 12 scenarios:
  - R-P1: Principal Home answers today's collection, attendance %, and fee dues in < 500 ms
  - All 5 role homes: principal, teacher, fee_clerk, front_desk, exam_incharge
  - F10 / S360-1..8: Student 360° smart-button summary + tabs + audit_log activity timeline
  - SET-1..6 / R-A1: Settings, First-Run Checklist, SQLite backup, integrity check & restore drill
  - Enterprise UI Quality Gate: ZERO pictographic emojis across all HTML/JS/CSS UI files
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest

from desktop_app.api import create_app
from desktop_app.database import Database


@pytest.fixture()
def phase2_app(tmp_path):
    db_file = tmp_path / "phase2_erp.sqlite3"
    db = Database(db_file)
    app = create_app(db=db, seed=True, enforce_auth=True)
    app.config["TESTING"] = True
    return db, app, tmp_path


def _login_as(app, admin_headers, username: str, role: str):
    admin_client = app.test_client()
    res = admin_client.post(
        "/api/auth/users",
        headers=admin_headers,
        json={
            "full_name": f"Staff {role}",
            "username": username,
            "role": role,
            "secret": "RolePass#123",
        },
    )
    assert res.status_code == 200, res.get_data(as_text=True)

    c = app.test_client()
    tok = c.post(
        "/api/auth/login",
        json={"username": username, "secret": "RolePass#123"},
    ).get_json()["token"]
    return c, {"X-Session-Token": tok}


class TestRoleDashboardsAndStudent360:
    """Verify all 5 role 'Aaj Ka Din' dashboards and Student 360° profile."""

    def test_all_five_role_dashboards_and_budget(self, phase2_app):
        _, app, _ = phase2_app
        admin_client = app.test_client()
        setup = admin_client.post(
            "/api/auth/setup",
            json={
                "full_name": "Principal Ayesha",
                "username": "principal_a",
                "secret": "PrinPass#123",
            },
        ).get_json()
        admin_headers = {"X-Session-Token": setup["token"]}

        # 1. Principal Home (R-P1: today's collection, attendance %, fee dues, exceptions, < 500ms)
        p_res = admin_client.get("/api/dashboard/home", headers=admin_headers)
        assert p_res.status_code == 200
        assert p_res.headers.get("X-Content-Type-Options") == "nosniff"
        assert p_res.headers.get("X-Frame-Options") == "DENY"
        p_data = p_res.get_json()
        assert p_data["ok"] is True
        assert p_data["effective_role"] == "principal"
        assert p_data["elapsed_ms"] < 500.0
        assert "today_collection" in p_data["cards"]
        assert "today_attendance" in p_data["cards"]
        assert "fee_dues" in p_data["cards"]
        assert "attention_items" in p_data
        assert "pending_leaves" in p_data
        assert "recent_activity" in p_data
        assert "class_strip" in p_data
        assert "upcoming_7d" in p_data

        # 2. Teacher Home
        t_client, t_headers = _login_as(app, admin_headers, "teacher_u", "teacher")
        t_data = t_client.get("/api/dashboard/home", headers=t_headers).get_json()
        assert t_data["ok"] is True
        assert t_data["role"] == "teacher"
        assert t_data["effective_role"] == "teacher"
        assert "weekday" in t_data
        assert "classes_status" in t_data
        assert "today_periods" in t_data
        assert "absent_today" in t_data

        # 3. Fee Clerk Home
        f_client, f_headers = _login_as(app, admin_headers, "clerk_u", "fee_clerk")
        f_data = f_client.get("/api/dashboard/home", headers=f_headers).get_json()
        assert f_data["ok"] is True
        assert f_data["role"] == "fee_clerk"
        assert f_data["effective_role"] == "fee_clerk"
        assert "today_tally" in f_data
        assert "yesterday_amount" in f_data["today_tally"]
        assert "defaulters" in f_data

        # 4. Front Desk Home
        fd_client, fd_headers = _login_as(app, admin_headers, "desk_u", "front_desk")
        fd_data = fd_client.get("/api/dashboard/home", headers=fd_headers).get_json()
        assert fd_data["ok"] is True
        assert fd_data["role"] == "front_desk"
        assert "seat_meter" in fd_data
        assert "incomplete_admissions" in fd_data

        # 5. Exam In-Charge Home
        ex_client, ex_headers = _login_as(app, admin_headers, "exam_u", "exam_incharge")
        ex_data = ex_client.get("/api/dashboard/home", headers=ex_headers).get_json()
        assert ex_data["ok"] is True
        assert ex_data["role"] == "exam_incharge"
        assert "marks_matrix" in ex_data
        assert "exam_kpis" in ex_data

    def test_student_360_profile_and_activity_timeline(self, phase2_app):
        _, app, _ = phase2_app
        client = app.test_client()
        setup = client.post(
            "/api/auth/setup",
            json={"full_name": "Admin", "username": "admin360", "secret": "Admin360#1"},
        ).get_json()
        headers = {"X-Session-Token": setup["token"]}

        students = client.get("/api/students/list", headers=headers).get_json()["items"]
        assert len(students) >= 1
        sid = students[0]["id"]

        res = client.get(f"/api/students/{sid}/360", headers=headers)
        assert res.status_code == 200
        d = res.get_json()
        assert d["ok"] is True
        assert d["student"]["id"] == sid
        for smart_key in (
            "attendance_pct",
            "fee_due",
            "last_exam",
            "library_issued",
            "transport_route",
            "hostel_room",
        ):
            assert smart_key in d["smart_buttons"], f"Missing smart button: {smart_key}"
        assert "payslips" in d
        assert "attendance" in d
        assert "exam_results" in d
        assert "audit_timeline" in d


class TestSettingsBackupAndRestoreDrill:
    """Verify Settings (SET-1..6) and Backup/Restore drill (R-A1)."""

    def test_settings_checklist_backup_and_restore_drill(self, phase2_app):
        db, app, _ = phase2_app
        client = app.test_client()
        setup = client.post(
            "/api/auth/setup",
            json={"full_name": "Owner", "username": "owner", "secret": "OwnerPass#1"},
        ).get_json()
        headers = {"X-Session-Token": setup["token"]}

        # Initial settings + checklist + years + size_kb
        st = client.get("/api/settings", headers=headers).get_json()
        assert st["ok"] is True
        assert "checklist" in st
        assert "completed_count" in st["checklist"]
        assert len(st.get("years") or []) >= 1
        assert st["health"]["integrity_ok"] is True
        assert "db_size_kb" in st["health"]
        assert "backup_stale" in st["health"]

        # Update preferences (D3 bilingual prints + module toggles)
        pref_res = client.post(
            "/api/settings/preferences",
            headers=headers,
            json={
                "bilingual_prints": True,
                "enable_hostel": False,
                "enable_transport": True,
                "ramazan_mode": True,
            },
        )
        assert pref_res.status_code == 200
        updated_st = client.get("/api/settings", headers=headers).get_json()
        assert updated_st["preferences"]["bilingual_prints"] is True
        assert updated_st["preferences"]["enable_hostel"] is False

        # Create backup (SET-5)
        bk_res = client.post("/api/settings/backup", headers=headers, json={"note": "Phase 2 test"})
        assert bk_res.status_code == 200
        bk_data = bk_res.get_json()
        assert bk_data["ok"] is True
        backup_filename = bk_data["backup"]["filename"]

        # Mutate DB AFTER backup (add a teacher), then restore backup and confirm rollback!
        before_teachers = db.fetch_one("SELECT COUNT(*) AS c FROM school_teacher")["c"]
        client.post(
            "/api/teachers",
            headers=headers,
            json={"name": "Temporary Post-Backup Teacher", "department": "Temp"},
        )
        assert db.fetch_one("SELECT COUNT(*) AS c FROM school_teacher")["c"] == before_teachers + 1

        # Path traversal attempt must fail with 400
        trav = client.post(
            "/api/settings/restore",
            headers=headers,
            json={"filename": "../../evil.sqlite3"},
        )
        assert trav.status_code == 400

        # Valid restore brings teacher count back to exact pre-backup state
        rest = client.post(
            "/api/settings/restore",
            headers=headers,
            json={"filename": backup_filename},
        )
        assert rest.status_code == 200
        assert db.fetch_one("SELECT COUNT(*) AS c FROM school_teacher")["c"] == before_teachers

    def test_profile_audit_log_user_lifecycle_and_recovery_rotation(self, phase2_app):
        _, app, _ = phase2_app
        client = app.test_client()
        setup = client.post(
            "/api/auth/setup",
            json={"full_name": "Admin One", "username": "admin1", "secret": "AdminPass#1"},
        ).get_json()
        headers = {"X-Session-Token": setup["token"]}

        # Update school profile (SET-2) + health check
        prof = client.post(
            "/api/settings/profile",
            headers=headers,
            json={"name": "Al-Noor Model School", "code": "ANMS", "city": "Lahore", "phone": "042-111222"},
        )
        assert prof.status_code == 200
        hlth = client.get("/api/settings/health", headers=headers).get_json()
        assert hlth["ok"] is True and hlth["health"]["integrity_ok"] is True

        # Rotate recovery key (SET-5) — requires current_secret step-up check
        rk_denied = client.post("/api/settings/recovery-code", headers=headers, json={})
        assert rk_denied.status_code in (400, 401)
        rk = client.post(
            "/api/settings/recovery-code",
            headers=headers,
            json={"current_secret": "AdminPass#1"},
        ).get_json()
        assert rk["ok"] is True and rk["recovery_code"].startswith("RK-")

        # Create staff user + lifecycle actions (reset_secret, disable, enable, unlock)
        usr = client.post(
            "/api/auth/users",
            headers=headers,
            json={"full_name": "Clerk", "username": "clerk1", "role": "fee_clerk", "secret": "Clerk#12"},
        ).get_json()["user"]
        uid = usr["id"]

        for payload in (
            {"action": "reset_secret", "secret": "Clerk#34"},
            {"action": "disable"},
            {"action": "enable"},
            {"action": "unlock"},
        ):
            r = client.post(f"/api/auth/users/{uid}/action", headers=headers, json=payload)
            assert r.status_code == 200

        # Cannot disable the last active admin
        bad = client.post(f"/api/auth/users/{setup['user']['id']}/action", headers=headers, json={"action": "disable"})
        assert bad.status_code == 400

        # Paginated audit logs endpoint
        logs = client.get("/api/audit/logs?per_page=20&username=admin1", headers=headers).get_json()
        assert logs["ok"] is True and logs["total"] >= 4


class TestEnterpriseUIQualityGate:
    """Enforce zero pictographic emojis across the entire desktop UI codebase."""

    EMOJI_RE = re.compile(
        "[\U0001F300-\U0001FAFF\u2600-\u27BF\u23F0-\u23FA\uFE0F]"
    )

    def test_zero_emojis_in_ui_html_js_css(self):
        ui_root = Path(__file__).resolve().parents[2] / "desktop_app" / "ui"
        offenders: list[str] = []
        for path in sorted(ui_root.rglob("*")):
            if path.suffix not in {".html", ".js", ".css"}:
                continue
            text = path.read_text(encoding="utf-8")
            for line_no, line in enumerate(text.splitlines(), 1):
                found = self.EMOJI_RE.findall(line)
                if found:
                    offenders.append(
                        f"{path.relative_to(ui_root)}:{line_no}: {''.join(found)}"
                    )
        assert not offenders, f"Found forbidden emojis in UI:\n" + "\n".join(offenders[:25])

    def test_all_ui_api_endpoints_match_registered_flask_routes(self, phase2_app):
        """Ensure every `/api/...` literal in UI JS resolves to a real Flask route."""
        _, app, _ = phase2_app
        adapter = app.url_map.bind("127.0.0.1")
        ui_root = Path(__file__).resolve().parents[2] / "desktop_app" / "ui"
        call_re = re.compile(r"['\"`](/api/[^'\"`\s?]+)")
        interp_re = re.compile(r"\$\{[^}]+\}")

        missing: list[str] = []
        for js_file in sorted(ui_root.rglob("*.js")):
            text = js_file.read_text(encoding="utf-8")
            for m in call_re.finditer(text):
                raw_path = m.group(1)
                if raw_path.endswith("/"):
                    continue
                concrete = interp_re.sub("1", raw_path)
                matched = False
                for method in ("GET", "POST"):
                    try:
                        adapter.match(concrete, method=method)
                        matched = True
                        break
                    except Exception:
                        continue
                if not matched:
                    missing.append(f"{js_file.relative_to(ui_root)} -> {raw_path} (tested {concrete})")

        assert not missing, "UI calls unregistered Flask endpoints:\n" + "\n".join(missing)
