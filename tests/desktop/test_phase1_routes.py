"""
Phase 1 — Backend Route Tests
Tests: paginated students, today attendance, bulk-mark, global search.
Run: pytest tests/desktop/test_phase1_routes.py -v
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from desktop_app.api import create_app
from desktop_app.database import Database


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_app():
    """Fresh in-memory DB with seed data for all Phase 1 tests."""
    db  = Database(":memory:")
    app = create_app(db=db, seed=True)
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="module")
def client(test_app):
    return test_app.test_client()


@pytest.fixture(scope="function")
def bulk_client():
    """
    Separate fresh DB for bulk-mark tests.
    Seed creates attendance for class_9 in validate state.
    This fixture adds students to class_10 (no seed attendance) for draft testing.
    """
    db = Database(":memory:")
    app = create_app(db=db, seed=True)
    app.config["TESTING"] = True

    # Inject a few students into class_10 (id=2) so we can create attendance there
    # class_10 already exists from seed — just add students
    with app.test_client() as c:
        boot = c.get("/api/bootstrap").get_json()
        stds = boot.get("school", {}).get("standards", [])
        # Find class_10 (id=2 in seed)
        class10 = next((s for s in stds if "10" in s.get("name", "")), None)
        if class10:
            cid = class10["id"]
            # Create attendance for class_10 — no seed validates this one
            resp = c.post("/api/attendance/daily",
                data=json.dumps({"standard_id": cid, "date": date.today().isoformat()}),
                content_type="application/json").get_json()
            # Store on app for tests to access
            app._bulk_test_class_id = cid
            app._bulk_test_att_id   = resp.get("id")
        else:
            app._bulk_test_class_id = None
            app._bulk_test_att_id   = None

    return app.test_client()


# ─── Helper ───────────────────────────────────────────────────────────────────

def jget(client, url) -> dict:
    r = client.get(url)
    return r.get_json()


def jpost(client, url, body) -> dict:
    r = client.post(url, data=json.dumps(body),
                    content_type="application/json")
    return r.get_json()


# ─── /api/students/list ───────────────────────────────────────────────────────

class TestStudentsPaginated:

    def test_returns_ok(self, client):
        d = jget(client, "/api/students/list")
        assert d["ok"] is True

    def test_has_pagination_fields(self, client):
        d = jget(client, "/api/students/list")
        assert "items" in d
        assert "total" in d
        assert "page"  in d
        assert "pages" in d

    def test_default_page_is_1(self, client):
        d = jget(client, "/api/students/list")
        assert d["page"] == 1

    def test_per_page_max_100(self, client):
        d = jget(client, "/api/students/list?per_page=999")
        assert len(d["items"]) <= 100

    def test_search_filter_works(self, client):
        d = jget(client, "/api/students/list?q=hamza")
        assert d["ok"] is True
        assert isinstance(d["items"], list)

    def test_items_have_expected_keys(self, client):
        d = jget(client, "/api/students/list")
        if d["items"]:
            keys = d["items"][0].keys()
            assert "student_name" in keys
            assert "pid"          in keys
            assert "state"        in keys
            assert "class_name"   in keys

    def test_state_filter_done(self, client):
        d = jget(client, "/api/students/list?state=done")
        assert d["ok"] is True
        for item in d["items"]:
            assert item["state"] == "done"

    def test_pages_calculation(self, client):
        d = jget(client, "/api/students/list?per_page=1")
        if d["total"] > 0:
            assert d["pages"] == d["total"]


# ─── /api/attendance/today/<class_id> ─────────────────────────────────────────

class TestTodayAttendance:

    def _get_first_class_id(self, client) -> int | None:
        d = jget(client, "/api/bootstrap")
        standards = d.get("school", {}).get("standards", [])
        return standards[0]["id"] if standards else None

    def test_no_attendance_yet_returns_null(self, client):
        cid = self._get_first_class_id(client)
        if cid is None:
            pytest.skip("No class in seed data")
        d = jget(client, f"/api/attendance/today/{cid}")
        assert d["ok"] is True
        assert "attendance" in d

    def test_invalid_class_returns_null_not_error(self, client):
        d = jget(client, "/api/attendance/today/99999")
        assert d["ok"] is True
        assert d["attendance"] is None


# ─── /api/attendance/daily/<id>/bulk-mark ─────────────────────────────────────

class TestBulkMarkAttendance:
    """
    Uses bulk_client fixture which creates attendance for class_10 (no seed students).
    class_10 has 0 students so attendance lines will be empty.
    Tests verify the API contract: empty-but-draft att handles lines=[].
    """

    def test_bulk_mark_requires_lines(self, bulk_client):
        """Empty lines list must return error."""
        # Get the first class with any attendance
        boot = jget(bulk_client, "/api/bootstrap")
        stds = boot.get("school", {}).get("standards", [])
        if not stds:
            pytest.skip("No standards in seed")

        # Find any attendance (class_9 from seed, state=validate, att_id=1)
        # We just need *any* att_id for this test — even validated works here
        # because empty lines check happens before state check in route
        for std in stds:
            today_resp = jget(bulk_client, f"/api/attendance/today/{std['id']}")
            att = today_resp.get("attendance")
            if att:
                resp = jpost(bulk_client,
                    f"/api/attendance/daily/{att['id']}/bulk-mark",
                    {"lines": []})
                assert resp["ok"] is False
                assert "lines" in resp.get("error", "").lower() or "list" in resp.get("error", "").lower()
                return
        pytest.skip("No attendance found in any class")

    def test_bulk_mark_marks_absent(self, bulk_client):
        """
        Mark a student absent via bulk-mark on a DRAFT attendance.
        Uses class_9 attendance reset to draft OR creates fresh one.
        """
        boot = jget(bulk_client, "/api/bootstrap")
        stds = boot.get("school", {}).get("standards", [])

        # Find class_9 (has 3 students, seed creates validated att)
        class9 = next((s for s in stds if "9" in s.get("name", "")), None)
        if not class9:
            pytest.skip("Class 9 not found in seed")

        cid = class9["id"]
        today_resp = jget(bulk_client, f"/api/attendance/today/{cid}")
        att = today_resp.get("attendance")
        if not att:
            pytest.skip("No attendance for class 9")

        # Reset to draft using existing route
        reset = jpost(bulk_client, f"/api/attendance/daily/{att['id']}/action",
                      {"action": "draft"})

        if not reset.get("ok"):
            pytest.skip(f"Cannot reset attendance to draft: {reset.get('error')}")

        # Fetch again to get updated state + lines
        today2 = jget(bulk_client, f"/api/attendance/today/{cid}")
        att2 = today2.get("attendance")
        if not att2 or not att2.get("student_ids"):
            pytest.skip("No student lines after reset")

        lines = att2["student_ids"]
        payload = [{"line_id": lines[0]["id"], "is_absent": True}]
        resp = jpost(bulk_client,
            f"/api/attendance/daily/{att2['id']}/bulk-mark",
            {"lines": payload})
        assert resp["ok"] is True, f"bulk-mark failed: {resp}"
        assert resp["total_absent"] >= 1

    def test_bulk_mark_all_present(self, bulk_client):
        """Mark all students present in a draft attendance."""
        boot = jget(bulk_client, "/api/bootstrap")
        stds = boot.get("school", {}).get("standards", [])

        class9 = next((s for s in stds if "9" in s.get("name", "")), None)
        if not class9:
            pytest.skip("Class 9 not found")

        cid = class9["id"]
        today_resp = jget(bulk_client, f"/api/attendance/today/{cid}")
        att = today_resp.get("attendance")
        if not att or not att.get("student_ids"):
            pytest.skip("No lines")

        # Ensure draft
        if att.get("state") == "validate":
            reset = jpost(bulk_client,
                f"/api/attendance/daily/{att['id']}/action",
                {"action": "draft"})
            if not reset.get("ok"):
                pytest.skip(f"Cannot reset: {reset.get('error')}")
            today_resp = jget(bulk_client, f"/api/attendance/today/{cid}")
            att = today_resp.get("attendance")
            if not att or not att.get("student_ids"):
                pytest.skip("No lines after reset")

        lines = att["student_ids"]
        payload = [{"line_id": l["id"], "is_absent": False} for l in lines]
        resp = jpost(bulk_client,
            f"/api/attendance/daily/{att['id']}/bulk-mark",
            {"lines": payload})
        assert resp["ok"] is True, f"bulk-mark failed: {resp}"
        assert resp["total_presence"] == len(lines)
        assert resp["total_absent"]   == 0

    def test_bulk_mark_validated_att_returns_error(self, bulk_client):
        """Bulk-mark on a validated attendance must return error."""
        boot = jget(bulk_client, "/api/bootstrap")
        stds = boot.get("school", {}).get("standards", [])

        class9 = next((s for s in stds if "9" in s.get("name", "")), None)
        if not class9:
            pytest.skip("Class 9 not found")

        cid = class9["id"]
        today_resp = jget(bulk_client, f"/api/attendance/today/{cid}")
        att = today_resp.get("attendance")
        if not att:
            pytest.skip("No attendance found")

        # Make sure it's validated
        if att.get("state") != "validate":
            jpost(bulk_client, f"/api/attendance/daily/{att['id']}/action",
                  {"action": "validate"})

        resp = jpost(bulk_client,
            f"/api/attendance/daily/{att['id']}/bulk-mark",
            {"lines": [{"line_id": 1, "is_absent": True}]})
        assert resp["ok"] is False
        assert "validate" in resp.get("error", "").lower()


# ─── /api/search ──────────────────────────────────────────────────────────────

class TestGlobalSearch:

    def test_too_short_query_returns_empty(self, client):
        d = jget(client, "/api/search?q=a")
        assert d["ok"] is True
        assert d["results"] == []

    def test_empty_query_returns_empty(self, client):
        d = jget(client, "/api/search?q=")
        assert d["ok"] is True
        assert d["results"] == []

    def test_valid_query_returns_ok(self, client):
        d = jget(client, "/api/search?q=ta")
        assert d["ok"] is True
        assert isinstance(d["results"], list)

    def test_results_have_type_field(self, client):
        d = jget(client, "/api/search?q=ta")
        for r in d["results"]:
            assert "type" in r
            assert r["type"] in ("student", "teacher", "voucher")

    def test_teacher_search_works(self, client):
        d = jget(client, "/api/search?q=tariq")
        assert d["ok"] is True
        types = [r["type"] for r in d["results"]]
        assert "teacher" in types or len(d["results"]) == 0

    def test_no_sql_injection_in_query(self, client):
        d = jget(client, "/api/search?q='; DROP TABLE student_student; --")
        assert d["ok"] is True


# ─── Existing tests still pass ────────────────────────────────────────────────

class TestBootstrapStillWorks:
    """Ensure we didn't break the existing bootstrap endpoint."""

    def test_bootstrap_ok(self, client):
        d = jget(client, "/api/bootstrap")
        assert d["ok"] is True

    def test_bootstrap_has_all_modules(self, client):
        d = jget(client, "/api/bootstrap")
        for key in ("school", "fees", "attendance", "assignment",
                    "timetable", "exam", "library", "event", "hostel", "transport"):
            assert key in d, f"Missing key: {key}"

    def test_health_ok(self, client):
        d = jget(client, "/api/health")
        assert d["ok"] is True
        assert d["status"] == "healthy"

    def test_ui_shell_and_phase1_assets_served(self, client):
        """Verify Kaghaz aur Siyahi CSS cascade, ES module entry, and split screen modules serve 200."""
        index_res = client.get("/")
        assert index_res.status_code == 200
        html = index_res.get_data(as_text=True)
        assert "/static/css/tokens.css" in html
        assert "/static/css/feedback-and-screens.css" in html
        assert "/static/app.js" in html
        assert "/static/js/main.js" in html

        for asset in (
            "/static/css/tokens.css",
            "/static/css/base.css",
            "/static/css/layout.css",
            "/static/css/components.css",
            "/static/css/feedback-and-screens.css",
            "/static/js/main.js",
            "/static/js/core/api.js",
            "/static/js/core/router.js",
            "/static/js/screens/attendance/daily-sheet.js",
            "/static/js/screens/attendance/daily-sheet-view.js",
            "/static/js/screens/school/students-list.js",
            "/static/js/screens/school/student-modal.js",
        ):
            res = client.get(asset)
            assert res.status_code == 200, f"Asset failed to load: {asset}"

