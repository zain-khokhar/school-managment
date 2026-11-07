"""
tests/desktop/test_phase5_outbox_messaging.py — Test Suite for Phase 5 Outbox & Rabta Messaging.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
from typing import Generator
import urllib.parse

import pytest

from desktop_app.api import create_app
from desktop_app.database import Database
from desktop_app.services.seed_service import ensure_seed_data
from desktop_app.services.outbox_service import (
    OutboxService,
    build_whatsapp_link,
    clean_pakistani_phone,
)


@pytest.fixture
def temp_db() -> Generator[Database, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_outbox.sqlite3"
        db = Database(str(db_path))
        ensure_seed_data(db)
        yield db


@pytest.fixture
def app_client(temp_db: Database):
    app = create_app(db=temp_db, seed=True, enforce_auth=False)
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestPhoneAndLinkUtils:
    def test_clean_pakistani_phone_formats(self) -> None:
        assert clean_pakistani_phone("03001234567") == "923001234567"
        assert clean_pakistani_phone("+92 300 1234567") == "923001234567"
        assert clean_pakistani_phone("0092-300-1234567") == "923001234567"
        assert clean_pakistani_phone("3001234567") == "923001234567"
        assert clean_pakistani_phone("923001234567") == "923001234567"
        assert clean_pakistani_phone("") == ""
        assert clean_pakistani_phone(None) == ""
        assert clean_pakistani_phone("123") == "123"

    def test_build_whatsapp_link(self) -> None:
        link = build_whatsapp_link("03001234567", "Hello Parent! Fee is due.")
        assert link.startswith("https://wa.me/923001234567?text=")
        assert "Hello%20Parent%21" in link or "Hello+Parent%21" in link or "Hello" in link

    def test_build_whatsapp_link_urdu_encoding(self) -> None:
        urdu_msg = "السلام علیکم، احمد آج غیر حاضر ہے۔"
        link = build_whatsapp_link("03219876543", urdu_msg)
        assert link.startswith("https://wa.me/923219876543?text=")
        quoted = urllib.parse.quote(urdu_msg)
        assert quoted in link


class TestOutboxServiceLogic:
    def test_templates_seeded_and_update(self, temp_db: Database) -> None:
        svc = OutboxService(temp_db)
        templates = svc.list_templates()
        assert len(templates) >= 4
        codes = [t["code"] for t in templates]
        assert "ABSENT_ALERT" in codes
        assert "FEE_REMINDER" in codes
        assert "PTM_CIRCULAR" in codes

        absent_tpl = svc.get_template("ABSENT_ALERT")
        assert absent_tpl is not None
        assert "{student_name}" in absent_tpl["body_template"]

        svc.update_template(absent_tpl["id"], "Custom Absent Title", "Updated notice for {student_name}")
        updated = svc.get_template("ABSENT_ALERT")
        assert updated["title"] == "Custom Absent Title"
        assert updated["body_template"] == "Updated notice for {student_name}"

    def test_enqueue_and_deduplication(self, temp_db: Database) -> None:
        svc = OutboxService(temp_db)
        msg_id1 = svc.enqueue_message(
            channel="whatsapp",
            to_name="Tariq Khan",
            to_phone="0300-1112233",
            template_code="ABSENT_ALERT",
            category="attendance",
            params={"guardian_name": "Tariq Khan", "student_name": "Hamza Tariq", "class_name": "Grade 5", "gr_no": "101"},
            student_id=1,
            dedupe_date="2026-11-07",
        )
        assert msg_id1 > 0

        # Duplicate enqueue on same student + template + date
        msg_id2 = svc.enqueue_message(
            channel="whatsapp",
            to_name="Tariq Khan",
            to_phone="0300-1112233",
            template_code="ABSENT_ALERT",
            category="attendance",
            params={"guardian_name": "Tariq Khan", "student_name": "Hamza Tariq"},
            student_id=1,
            dedupe_date="2026-11-07",
        )
        assert msg_id2 == msg_id1  # Returns existing message id

        listing = svc.list_messages(page=1, per_page=10)
        assert listing["total"] == 1
        item = listing["items"][0]
        assert item["to_phone"] == "923001112233"
        assert "Hamza Tariq" in item["body_text"]
        assert item["whatsapp_link"].startswith("https://wa.me/923001112233")

    def test_message_lifecycle_actions(self, temp_db: Database) -> None:
        svc = OutboxService(temp_db)
        mid = svc.enqueue_message(
            to_name="Test Parent",
            to_phone="03009998877",
            template_code="PTM_CIRCULAR",
            category="circular",
            subject="PTM on Monday",
            body_override="Dear Parent, PTM will be held on Monday.",
            student_id=2,
            dedupe_date="2026-11-10",
        )
        stats = svc.get_stats()
        assert stats["ready"] >= 1

        # Mark sent
        svc.mark_sent(mid, user="clerk")
        row = temp_db.fetch_all("SELECT * FROM outbox_message WHERE id = ?", (mid,))[0]
        assert row["status"] == "sent"
        assert row["sent_at"] is not None

        # Retry
        svc.retry_message(mid, user="clerk")
        row = temp_db.fetch_all("SELECT * FROM outbox_message WHERE id = ?", (mid,))[0]
        assert row["status"] == "ready"
        assert row["attempts"] == 1

        # Cancel
        svc.cancel_message(mid, user="clerk")
        row = temp_db.fetch_all("SELECT * FROM outbox_message WHERE id = ?", (mid,))[0]
        assert row["status"] == "cancelled"

        # Delete
        svc.delete_message(mid, user="admin")
        assert len(temp_db.fetch_all("SELECT * FROM outbox_message WHERE id = ?", (mid,))) == 0


class TestOutboxTriggers:
    def test_generate_circular(self, temp_db: Database) -> None:
        svc = OutboxService(temp_db)
        res = svc.generate_circular(
            title="Winter Uniform Notice",
            body_text="All students must wear winter sweaters starting next week.",
            target_type="all",
            user="principal",
        )
        assert res["enqueued"] >= 1
        listing = svc.list_messages(category="circular")
        assert listing["total"] >= 1
        assert "Winter Uniform Notice" in listing["items"][0]["body_text"]

    def test_generate_absent_alerts_trigger(self, temp_db: Database) -> None:
        # Seed an attendance record with absent
        students = temp_db.fetch_all("SELECT id, standard_id FROM student_student LIMIT 1")
        assert len(students) > 0
        sid = students[0]["id"]
        class_id = students[0]["standard_id"] or 1
        today = "2026-11-07"
        with temp_db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO daily_attendance (date, standard_id, user_id, state, total_student, total_presence, total_absent, is_generate)
                VALUES (?, ?, 1, 'draft', 1, 0, 1, 1)
                """,
                (today, class_id),
            )
            att_id = cur.lastrowid
            conn.execute(
                """
                INSERT INTO daily_attendance_line (standard_id, stud_id, roll_no, is_present, is_absent)
                VALUES (?, ?, '1', 0, 1)
                """,
                (att_id, sid),
            )

        svc = OutboxService(temp_db)
        res = svc.generate_absent_alerts(date_str=today, user="teacher")
        assert res["enqueued"] >= 1

        listing = svc.list_messages(category="attendance")
        assert listing["total"] >= 1
        assert "absent" in listing["items"][0]["body_text"].lower()


class TestOutboxApiRoutes:
    def test_outbox_messages_and_stats_api(self, app_client) -> None:
        res = app_client.get("/api/outbox/messages")
        assert res.status_code == 200
        data = res.get_json()
        assert data["ok"] is True
        assert "items" in data
        assert "stats" in data

    def test_outbox_templates_api(self, app_client) -> None:
        res = app_client.get("/api/outbox/templates")
        assert res.status_code == 200
        data = res.get_json()
        assert data["ok"] is True
        assert len(data["templates"]) >= 4

    def test_generate_circular_api(self, app_client) -> None:
        res = app_client.post(
            "/api/outbox/generate/circular",
            data=json.dumps({
                "title": "Eid Milan Party",
                "body": "Eid Milan Party will be arranged on Friday.",
                "target_type": "all",
            }),
            content_type="application/json",
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["ok"] is True
        assert data["enqueued"] >= 1

    def test_outbox_message_action_api(self, app_client, temp_db: Database) -> None:
        svc = OutboxService(temp_db)
        mid = svc.enqueue_message(
            to_name="Parent Api Test",
            to_phone="03331122334",
            template_code="PTM_CIRCULAR",
            category="circular",
            body_override="Test Body",
            student_id=1,
            dedupe_date="2026-11-12",
        )

        res = app_client.post(
            f"/api/outbox/messages/{mid}/action",
            data=json.dumps({"action": "mark_sent"}),
            content_type="application/json",
        )
        assert res.status_code == 200
        assert res.get_json()["ok"] is True

        row = temp_db.fetch_all("SELECT status FROM outbox_message WHERE id = ?", (mid,))[0]
        assert row["status"] == "sent"
