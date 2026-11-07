"""
Phase 4 Admissions, Bulk CSV/Excel Import & Export, Student ID Cards, PTM 1-Pagers &
Library 1-Click Quick Issue Service (G6, G15, S7, R-D1, ADM-0..4, F4, F14, F15).

Strictly under 600 lines per anti-monolith budget (ADVANCEMENT_PLAN.md Section 10.1).
"""

from __future__ import annotations

import csv
from datetime import date
import io
import json
from typing import Any

from dateutil.relativedelta import relativedelta
import xlsxwriter

from desktop_app.database import Database
from desktop_app.exceptions import ValidationError, parse_date
from desktop_app.services.audit_service import AuditService
from desktop_app.services.family_service import FamilyService, _digits_only
from desktop_app.services.fee_engine_service import FeeEngineService
from desktop_app.services.library_service import LibraryService
from desktop_app.services.school_service import SchoolService
from desktop_app.services.settings_service import SettingsService
from desktop_app.services.student_prints_mixin import StudentPrintsAndCampusMixin


class AdmissionImportService(StudentPrintsAndCampusMixin):
    """3-Step Admission Wizard, 1000-Row Fast Bulk Importer, Excel Exporter & Print Aggregator."""

    def __init__(
        self,
        db: Database,
        school_svc: SchoolService | None = None,
        family_svc: FamilyService | None = None,
        fee_engine: FeeEngineService | None = None,
        lib_svc: LibraryService | None = None,
        settings: SettingsService | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.db = db
        self.audit = audit or AuditService(db)
        self.settings = settings or SettingsService(db, self.audit)
        self.school_svc = school_svc or SchoolService(db)
        self.fee_engine = fee_engine or FeeEngineService(db, self.audit, self.settings)
        self.family_svc = family_svc or FamilyService(db, self.fee_engine, self.audit, self.settings)
        self.lib_svc = lib_svc or LibraryService(db)

    # -------------------------------------------------------------------------
    # ADM-1 & ADM-2: Live Duplicate Check & Sibling Family Auto-Detection (R-D1)
    # -------------------------------------------------------------------------
    def check_duplicate_and_family(
        self,
        *,
        b_form_no: str = "",
        student_name: str = "",
        date_of_birth: str = "",
        guardian_phone: str = "",
        guardian_cnic: str = "",
    ) -> dict[str, Any]:
        bf = (b_form_no or "").strip()
        bf_digits = _digits_only(bf)
        sname = (student_name or "").strip().lower()
        dob = (date_of_birth or "").strip()[:10]
        gphone = (guardian_phone or "").strip()
        gphone_digits = _digits_only(gphone)
        gcnic = (guardian_cnic or "").strip()

        duplicates: dict[int, dict[str, Any]] = {}
        with self.db.connection() as conn:
            if bf and len(bf_digits) >= 5:
                rows = conn.execute(
                    """
                    SELECT s.id, s.pid, s.student_name, s.last, s.date_of_birth,
                           s.b_form_no, s.contact_mobile, ss.name AS class_name
                    FROM student_student s
                    LEFT JOIN school_standard ss ON ss.id = s.standard_id
                    WHERE s.active = 1 AND s.b_form_no != ''
                    """
                ).fetchall()
                for r in rows:
                    if _digits_only(r["b_form_no"]) == bf_digits or r["b_form_no"].strip().lower() == bf.lower():
                        d = dict(r)
                        d["match_reason"] = "Exact B-Form / Bay-Form match"
                        duplicates[int(r["id"])] = d

            if dob and (sname or len(gphone_digits) >= 7):
                rows = conn.execute(
                    """
                    SELECT s.id, s.pid, s.student_name, s.last, s.date_of_birth,
                           s.b_form_no, s.contact_mobile, ss.name AS class_name
                    FROM student_student s
                    LEFT JOIN school_standard ss ON ss.id = s.standard_id
                    WHERE s.active = 1 AND s.date_of_birth = ?
                    """,
                    (dob,),
                ).fetchall()
                for r in rows:
                    sid = int(r["id"])
                    if sid in duplicates:
                        continue
                    row_mob = _digits_only(r["contact_mobile"])
                    name_match = bool(sname and r["student_name"].strip().lower() == sname)
                    mob_match = bool(len(gphone_digits) >= 7 and row_mob == gphone_digits)
                    if name_match or mob_match:
                        d = dict(r)
                        d["match_reason"] = (
                            "Guardian mobile + Date of Birth match"
                            if mob_match
                            else "Student Name + Date of Birth match"
                        )
                        duplicates[sid] = d

        existing_family = None
        if len(gphone_digits) >= 7 or len(_digits_only(gcnic)) >= 7:
            fams = self.family_svc.list_families(q=gphone or gcnic)
            if fams:
                existing_family = fams[0]

        return {
            "duplicates": list(duplicates.values()),
            "has_duplicate": len(duplicates) > 0,
            "existing_family": existing_family,
        }

    # -------------------------------------------------------------------------
    # ADM-1..ADM-4: 3-Step Admission Wizard Enrollment (G6, F4, F15)
    # -------------------------------------------------------------------------
    def enroll_wizard(
        self,
        payload: dict[str, Any],
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        student_name = (payload.get("student_name") or "").strip()
        if not student_name:
            raise ValidationError("Student First Name is required.")
        dob_str = (payload.get("date_of_birth") or "").strip()
        if not dob_str:
            raise ValidationError("Student Date of Birth is required.")
        if not payload.get("standard_id"):
            raise ValidationError("Class selection is required.")

        b_form_no = (payload.get("b_form_no") or "").strip()[:30]
        g_name = (payload.get("guardian_name") or "").strip()
        g_phone = (payload.get("guardian_phone") or payload.get("contact_mobile") or "").strip()[:40]
        g_cnic = (payload.get("guardian_cnic") or "").strip()[:25]
        g_rel = (payload.get("guardian_relation") or "Father").strip()[:40]

        if not payload.get("allow_duplicate", False):
            dup_check = self.check_duplicate_and_family(
                b_form_no=b_form_no,
                student_name=student_name,
                date_of_birth=dob_str,
                guardian_phone=g_phone,
                guardian_cnic=g_cnic,
            )
            if dup_check["has_duplicate"]:
                first_dup = dup_check["duplicates"][0]
                raise ValidationError(
                    f"Duplicate admission detected: {first_dup['student_name']} "
                    f"({first_dup['pid']}) already exists ({first_dup['match_reason']})."
                )

        class_id = int(payload["standard_id"])
        cls = self.school_svc.recompute_school_standard(class_id)
        if int(cls["remaining_seats"]) <= 0:
            raise ValidationError(
                f"Seats of class {cls['name']} are full ({cls['capacity']}/{cls['capacity']})."
            )

        school_id = int(payload.get("school_id") or cls["school_id"])
        year_id = int(payload["year_id"]) if payload.get("year_id") else None

        stu = self.school_svc.create_student(
            student_name=student_name,
            middle=(payload.get("middle") or "").strip(),
            last=(payload.get("last") or "").strip(),
            date_of_birth=dob_str,
            school_id=school_id,
            standard_id=class_id,
            year_id=year_id,
            gender=(payload.get("gender") or "male").strip().lower(),
            email=(payload.get("email") or "").strip(),
            contact_mobile=g_phone,
            admission_date=payload.get("admission_date"),
        )
        stu_id = int(stu["id"])

        docs_dict = payload.get("documents") if isinstance(payload.get("documents"), dict) else {}
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE student_student SET b_form_no = ?, documents_json = ? WHERE id = ?",
                (b_form_no, json.dumps(docs_dict), stu_id),
            )

        if payload.get("auto_admit", True):
            self.school_svc.admission_done(stu_id)

        family_key = f"S-{stu_id}"
        if len(g_name) >= 2:
            fam_res = self.family_svc.upsert_guardian(
                {
                    "name": g_name,
                    "phone": g_phone,
                    "cnic": g_cnic,
                    "relation": g_rel,
                    "student_ids": [stu_id],
                },
                actor=None,
            )
            family_key = fam_res["family_key"]

        if payload.get("apply_sibling_concession") and payload.get("sibling_discount_pct"):
            self.fee_engine.create_concession(
                {
                    "student_id": stu_id,
                    "concession_type": "sibling",
                    "calc_mode": "percent",
                    "value": int(payload["sibling_discount_pct"]),
                    "reason": "Admission Wizard Sibling Concession",
                },
                actor=None,
            )

        first_voucher = None
        if payload.get("generate_first_voucher") and payload.get("fees_structure_id"):
            bmonth = (payload.get("billing_month") or date.today().strftime("%Y-%m")).strip()[:7]
            self.fee_engine.generate_bulk_vouchers(
                billing_month=bmonth,
                fees_structure_id=int(payload["fees_structure_id"]),
                due_date=payload.get("due_date"),
                class_id=class_id,
                include_arrears=False,
                apply_rules=True,
                actor=None,
            )
            v_list = self.fee_engine.list_vouchers_paginated(
                page=1, per_page=5, q=stu["pid"], billing_month=bmonth
            )["items"]
            first_voucher = next((v for v in v_list if int(v["student_id"]) == stu_id), None)

        fresh_stu = self.db.fetch_one(
            """
            SELECT s.*, ss.name AS class_name, ay.name AS year_name
            FROM student_student s
            LEFT JOIN school_standard ss ON ss.id = s.standard_id
            LEFT JOIN academic_year ay ON ay.id = s.year_id
            WHERE s.id = ?
            """,
            (stu_id,),
        )
        if actor:
            self.audit.record(
                user_id=actor.get("id"),
                username=actor.get("username") or "front_desk",
                role=actor.get("role") or "front_desk",
                action="admissions.enroll",
                entity_type="student_student",
                entity_id=stu_id,
                summary=f"Admitted '{student_name}' ({fresh_stu['pid']}) into {fresh_stu.get('class_name')}",
                ip_address=ip_address,
            )
        return {
            "student": fresh_stu,
            "family_key": family_key,
            "first_voucher": first_voucher,
        }

    # -------------------------------------------------------------------------
    # G15: Fast 1000-Row Bulk CSV Import Preview & Commit (< 60s) + XLSX Export
    # -------------------------------------------------------------------------
    def _parse_and_validate_import_csv(self, csv_text: str) -> dict[str, Any]:
        if not csv_text or not csv_text.strip():
            raise ValidationError("CSV content is empty.")

        reader = csv.DictReader(io.StringIO(csv_text.strip()))
        with self.db.connection() as conn:
            school = conn.execute("SELECT * FROM school_school ORDER BY id ASC LIMIT 1").fetchone()
            req_age = int(school["required_age"] or 6) if school else 6
            school_id = int(school["id"]) if school else 1
            yr = conn.execute("SELECT id FROM academic_year WHERE current = 1 LIMIT 1").fetchone()
            year_id = int(yr["id"]) if yr else 1
            classes = {
                r["name"].strip().lower(): dict(r)
                for r in conn.execute("SELECT * FROM school_standard").fetchall()
            }
            default_cls = next(iter(classes.values()), None)

        valid_rows: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        today = date.today()

        for row_idx, raw in enumerate(reader, start=2):
            norm = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
            fname = norm.get("first_name") or norm.get("student_name") or ""
            lname = norm.get("last_name") or norm.get("last") or ""
            gender = (norm.get("gender") or "male").lower()
            if gender not in ("male", "female"):
                gender = "male"
            dob_raw = norm.get("date_of_birth") or norm.get("dob") or ""
            cls_name = (norm.get("class_name") or norm.get("class") or "").lower()
            g_name = norm.get("guardian_name") or norm.get("father_name") or ""
            g_phone = norm.get("guardian_phone") or norm.get("contact_mobile") or norm.get("mobile") or ""
            b_form = norm.get("b_form_no") or norm.get("b_form") or ""

            if not fname:
                errors.append({"row": row_idx, "error": "Missing first_name / student_name"})
                continue
            try:
                dob_dt = parse_date(dob_raw, "date_of_birth")
            except Exception as exc:
                errors.append({"row": row_idx, "error": str(exc)})
                continue

            if not dob_dt or (dob_dt + relativedelta(years=req_age)) > today:
                errors.append(
                    {"row": row_idx, "error": f"Student age must be at least {req_age} years"}
                )
                continue

            matched_cls = classes.get(cls_name) or default_cls
            if not matched_cls:
                errors.append({"row": row_idx, "error": f"Class '{cls_name}' not found"})
                continue

            valid_rows.append(
                {
                    "row": row_idx,
                    "student_name": fname,
                    "last": lname,
                    "gender": gender,
                    "date_of_birth": dob_dt.isoformat(),
                    "age": SchoolService.compute_age(dob_dt, today),
                    "standard_id": int(matched_cls["id"]),
                    "division_id": matched_cls["division_id"],
                    "medium_id": matched_cls["medium_id"],
                    "class_name": matched_cls["name"],
                    "school_id": school_id,
                    "year_id": year_id,
                    "guardian_name": g_name,
                    "contact_mobile": g_phone,
                    "b_form_no": b_form,
                }
            )

        return {
            "valid_count": len(valid_rows),
            "error_count": len(errors),
            "errors": errors[:100],
            "preview_rows": valid_rows[:25],
            "_all_valid": valid_rows,
        }

    def preview_students_import(self, csv_text: str) -> dict[str, Any]:
        parsed = self._parse_and_validate_import_csv(csv_text)
        return {k: v for k, v in parsed.items() if k != "_all_valid"}

    def commit_students_import(
        self,
        csv_text: str,
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        parsed = self._parse_and_validate_import_csv(csv_text)
        valid_rows = parsed["_all_valid"]
        today_iso = date.today().isoformat()
        touched_classes: set[int] = set()

        with self.db.connection() as conn:
            seq_row = conn.execute(
                "SELECT prefix, padding, next_val FROM ir_sequence WHERE code = 'student.student'"
            ).fetchone()
            prefix = seq_row["prefix"] if seq_row else "PID/"
            padding = int(seq_row["padding"]) if seq_row else 4
            next_val = int(seq_row["next_val"]) if seq_row else 1

            # Ensure class capacity accommodates imported batch
            by_cls_cnt: dict[int, int] = {}
            for r in valid_rows:
                cid = int(r["standard_id"])
                by_cls_cnt[cid] = by_cls_cnt.get(cid, 0) + 1
                touched_classes.add(cid)

            for cid, add_cnt in by_cls_cnt.items():
                ss = conn.execute("SELECT capacity, total_students FROM school_standard WHERE id = ?", (cid,)).fetchone()
                if ss and int(ss["total_students"]) + add_cnt > int(ss["capacity"]):
                    new_cap = int(ss["total_students"]) + add_cnt + 20
                    conn.execute("UPDATE school_standard SET capacity = ? WHERE id = ?", (new_cap, cid))

            for r in valid_rows:
                pid_str = f"{prefix}{next_val:0{padding}d}"
                next_val += 1
                conn.execute(
                    """
                    INSERT INTO student_student
                        (pid, student_name, middle, last, contact_mobile, year_id, school_id,
                         standard_id, division_id, medium_id, admission_date, gender,
                         date_of_birth, age, b_form_no, state, active)
                    VALUES (?, ?, '', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'done', 1)
                    """,
                    (
                        pid_str,
                        r["student_name"],
                        r["last"],
                        r["contact_mobile"],
                        r["year_id"],
                        r["school_id"],
                        r["standard_id"],
                        r["division_id"],
                        r["medium_id"],
                        today_iso,
                        r["gender"],
                        r["date_of_birth"],
                        r["age"],
                        r["b_form_no"],
                    ),
                )

            conn.execute(
                "UPDATE ir_sequence SET next_val = ? WHERE code = 'student.student'",
                (next_val,),
            )

        for cid in touched_classes:
            self.school_svc.recompute_school_standard(cid)

        if actor and valid_rows:
            self.audit.record(
                user_id=actor.get("id"),
                username=actor.get("username") or "admin",
                role=actor.get("role") or "admin",
                action="import.students_commit",
                entity_type="student_student",
                summary=f"Bulk imported {len(valid_rows)} student(s) ({parsed['error_count']} error row(s) skipped)",
                ip_address=ip_address,
            )
        return {
            "imported_count": len(valid_rows),
            "skipped_errors": parsed["error_count"],
            "errors": parsed["errors"],
        }

    def export_students_xlsx(self, class_id: int | None = None) -> bytes:
        clauses = ["s.active = 1"]
        params: list[Any] = []
        if class_id:
            clauses.append("s.standard_id = ?")
            params.append(int(class_id))
        rows = self.db.fetch_all(
            f"""
            SELECT s.pid, s.roll_no, s.student_name, s.last, s.gender, s.date_of_birth,
                   s.b_form_no, s.contact_mobile, ss.name AS class_name, ay.name AS year_name, s.state
            FROM student_student s
            LEFT JOIN school_standard ss ON ss.id = s.standard_id
            LEFT JOIN academic_year ay ON ay.id = s.year_id
            WHERE {' AND '.join(clauses)}
            ORDER BY ss.name ASC, s.roll_no ASC, s.id ASC
            """,
            tuple(params),
        )
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        ws = wb.add_worksheet("Students")
        hdr_fmt = wb.add_format({"bold": True, "bg_color": "#EFECE6", "border": 1})
        headers = [
            "GR No", "Roll No", "First Name", "Last Name", "Gender",
            "Date of Birth", "B-Form No", "Mobile", "Class", "Session", "Status",
        ]
        for col, h in enumerate(headers):
            ws.write(0, col, h, hdr_fmt)
        for r_idx, r in enumerate(rows, start=1):
            vals = [
                r["pid"], r["roll_no"], r["student_name"], r["last"], r["gender"],
                r["date_of_birth"], r.get("b_form_no") or "", r.get("contact_mobile") or "",
                r.get("class_name") or "", r.get("year_name") or "", r["state"],
            ]
            for col, val in enumerate(vals):
                ws.write(r_idx, col, val)
        wb.close()
        return buf.getvalue()

    def export_vouchers_xlsx(self, billing_month: str = "") -> bytes:
        res = self.fee_engine.list_vouchers_paginated(
            page=1, per_page=5000, billing_month=billing_month
        )
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        ws = wb.add_worksheet("Fee Vouchers")
        hdr_fmt = wb.add_format({"bold": True, "bg_color": "#EFECE6", "border": 1})
        headers = [
            "Voucher #", "GR No", "Student Name", "Class", "Billing Month",
            "Due Date", "Total (PKR)", "Paid (PKR)", "Balance Due (PKR)", "Status",
        ]
        for col, h in enumerate(headers):
            ws.write(0, col, h, hdr_fmt)
        for r_idx, v in enumerate(res["items"], start=1):
            vals = [
                v["voucher_display"], v.get("pid") or "", v.get("student_name") or "",
                v.get("class_name") or "", v.get("billing_month") or "", v.get("due_date") or "",
                v["total"], v["paid_amount"], v["due_amount"], v["state"],
            ]
            for col, val in enumerate(vals):
                ws.write(r_idx, col, val)
        wb.close()
        return buf.getvalue()

