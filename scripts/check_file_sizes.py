"""
scripts/check_file_sizes.py — Enforce Phase 1 Anti-Monolith File Size Rules

Budgets (from ADVANCEMENT_PLAN.md Section 10.1):
  - New JS modules (`desktop_app/ui/js/**/*.js`): target <= 200 lines, hard ceiling <= 300 lines
  - New CSS files (`desktop_app/ui/css/*.css`): hard ceiling <= 600 lines
  - New Python routes (`desktop_app/routes/*.py`): target <= 250 lines, hard ceiling <= 400 lines
"""

from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent


def check_files() -> int:
    violations: list[str] = []
    checked = 0

    print("=== Anti-Monolith File Size & Modularity Check (Phases 1-4) ===")

    for js_file in sorted((ROOT / "desktop_app" / "ui" / "js").rglob("*.js")):
        lines = len(js_file.read_text(encoding="utf-8").splitlines())
        rel = js_file.relative_to(ROOT)
        checked += 1
        status = "OK" if lines <= 300 else "VIOLATION (>300)"
        print(f"  [JS]  {str(rel):48s} : {lines:4d} lines  [{status}]")
        if lines > 300:
            violations.append(f"{rel} has {lines} lines (max 300)")

    for css_file in sorted((ROOT / "desktop_app" / "ui" / "css").rglob("*.css")):
        lines = len(css_file.read_text(encoding="utf-8").splitlines())
        rel = css_file.relative_to(ROOT)
        checked += 1
        status = "OK" if lines <= 600 else "VIOLATION (>600)"
        print(f"  [CSS] {str(rel):48s} : {lines:4d} lines  [{status}]")
        if lines > 600:
            violations.append(f"{rel} has {lines} lines (max 600)")

    for py_file in sorted((ROOT / "desktop_app" / "routes").rglob("*.py")):
        lines = len(py_file.read_text(encoding="utf-8").splitlines())
        rel = py_file.relative_to(ROOT)
        checked += 1
        status = "OK" if lines <= 400 else "VIOLATION (>400)"
        print(f"  [PY]  {str(rel):48s} : {lines:4d} lines  [{status}]")
        if lines > 400:
            violations.append(f"{rel} has {lines} lines (max 400)")

    phase_services = [
        "audit_service.py",
        "auth_service.py",
        "backup_service.py",
        "dashboard_service.py",
        "settings_service.py",
        "student360_service.py",
        "fee_engine_service.py",
        "fee_rules_and_print.py",
        "family_service.py",
        "academic_engine_service.py",
        "calendar_timetable_mixin.py",
        "admission_import_service.py",
        "student_prints_mixin.py",
        "outbox_service.py",
        "outbox_triggers_mixin.py",
    ]
    for svc_name in phase_services:
        svc_file = ROOT / "desktop_app" / "services" / svc_name
        if not svc_file.exists():
            continue
        lines = len(svc_file.read_text(encoding="utf-8").splitlines())
        rel = svc_file.relative_to(ROOT)
        checked += 1
        status = "OK" if lines <= 600 else "VIOLATION (>600)"
        print(f"  [SVC] {str(rel):48s} : {lines:4d} lines  [{status}]")
        if lines > 600:
            violations.append(f"{rel} has {lines} lines (max 600)")

    print(f"\nChecked {checked} modular files.")
    if violations:
        print("FAILED violations:")
        for v in violations:
            print(f"  - {v}")
        return 1

    print("ALL MODULAR FILES WITHIN STRICT ANTI-MONOLITH BUDGET!")
    return 0


if __name__ == "__main__":
    sys.exit(check_files())

