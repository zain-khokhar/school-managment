"""
SQLite Online Backup, PRAGMA Integrity Check & Verified Restore Service (Phase 2 — G13, SET-5).

Uses ``sqlite3.Connection.backup()`` so backups and restores work safely
on Windows even while WAL mode connections are active.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
import tempfile
from typing import Any

from desktop_app.database import Database
from desktop_app.db.migrate import apply_migrations, get_schema_version
from desktop_app.exceptions import ValidationError
from desktop_app.services.audit_service import AuditService, utc_now_iso
from desktop_app.services.settings_service import SettingsService

SAFE_BACKUP_NAME_RE = re.compile(r"^school_erp_[0-9]{8}_[0-9]{6}(?:_[a-z0-9]+)?\.sqlite3$")


class BackupService:
    """Provides database health verification, atomic snapshots, and safe restores."""

    def __init__(
        self,
        db: Database,
        settings: SettingsService | None = None,
        audit: AuditService | None = None,
    ) -> None:
        self.db = db
        self.audit = audit or AuditService(db)
        self.settings = settings or SettingsService(db, self.audit)
        self._mem_backup_dir: Path | None = None

    def get_backup_dir(self) -> Path:
        """Resolve dedicated ``backups/`` folder adjacent to the SQLite database."""
        if self.db.db_path == ":memory:":
            if self._mem_backup_dir is None:
                self._mem_backup_dir = Path(tempfile.mkdtemp(prefix="school_erp_backups_"))
            return self._mem_backup_dir
        folder = Path(self.db.db_path).resolve().parent / "backups"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def check_health(self) -> dict[str, Any]:
        """Run ``PRAGMA integrity_check`` and return schema version, size, and backup status."""
        with self.db.connection() as conn:
            integ_row = conn.execute("PRAGMA integrity_check").fetchone()
            integrity_msg = str(integ_row[0]) if integ_row else "unknown"
            schema_ver = get_schema_version(conn)

        size_bytes = 0
        if self.db.db_path != ":memory:":
            p = Path(self.db.db_path)
            if p.exists():
                size_bytes = p.stat().st_size

        prefs = self.settings.get_preferences()
        last_backup = prefs.get("last_backup_at") or ""
        overdue = True
        if last_backup:
            try:
                dt = datetime.fromisoformat(last_backup)
                age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
                overdue = age_hours > 24.0
            except ValueError:
                overdue = True

        return {
            "integrity_ok": integrity_msg.lower() == "ok",
            "integrity_detail": integrity_msg,
            "schema_version": schema_ver,
            "db_size_bytes": size_bytes,
            "db_size_kb": round(size_bytes / 1024.0, 1),
            "last_backup_at": last_backup,
            "last_backup_file": prefs.get("last_backup_file") or "",
            "backup_overdue": overdue,
            "backup_stale": overdue,
            "backup_dir": str(self.get_backup_dir()),
        }

    def list_backups(self) -> list[dict[str, Any]]:
        """List verified ``.sqlite3`` snapshots in ``backups/`` newest-first."""
        bdir = self.get_backup_dir()
        items: list[dict[str, Any]] = []
        for f in sorted(bdir.glob("school_erp_*.sqlite3"), reverse=True):
            if not SAFE_BACKUP_NAME_RE.match(f.name):
                continue
            stat = f.stat()
            items.append(
                {
                    "filename": f.name,
                    "size_bytes": stat.st_size,
                    "size_kb": round(stat.st_size / 1024.0, 1),
                    "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                    .replace(microsecond=0)
                    .isoformat(),
                }
            )
        return items

    def create_backup(
        self,
        *,
        suffix: str = "manual",
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """Create an online SQLite snapshot and verify its integrity immediately."""
        clean_suffix = re.sub(r"[^a-z0-9]", "", (suffix or "manual").lower())[:12] or "manual"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"school_erp_{stamp}_{clean_suffix}.sqlite3"
        target_path = self.get_backup_dir() / filename

        # Perform online SQLite backup
        dest_conn = sqlite3.connect(str(target_path))
        try:
            with self.db.connection() as src_conn:
                src_conn.backup(dest_conn)
            chk = dest_conn.execute("PRAGMA integrity_check").fetchone()
            if not chk or str(chk[0]).lower() != "ok":
                raise ValidationError("Backup file failed post-copy integrity verification.")
        finally:
            dest_conn.close()

        now_iso = utc_now_iso()
        uname = actor["username"] if actor else "system"
        self.settings.set_value("last_backup_at", now_iso, updated_by=uname)
        self.settings.set_value("last_backup_file", filename, updated_by=uname)

        if actor:
            self.audit.record(
                user_id=actor["id"],
                username=actor["username"],
                role=actor["role"],
                action="backup.create",
                entity_type="database",
                entity_id=filename,
                summary=f"Created verified database backup '{filename}'",
                ip_address=ip_address,
            )

        sz = target_path.stat().st_size
        return {
            "filename": filename,
            "size_bytes": sz,
            "size_kb": round(sz / 1024.0, 1),
            "created_at": now_iso,
        }

    def restore_backup(
        self,
        *,
        filename: str,
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """Validate backup file strictly, snapshot current DB, and restore atomically."""
        clean_name = (filename or "").strip()
        if not SAFE_BACKUP_NAME_RE.match(clean_name):
            raise ValidationError("Invalid backup filename.")

        bdir = self.get_backup_dir().resolve()
        src_path = (bdir / clean_name).resolve()
        if src_path.parent != bdir or not src_path.is_file():
            raise ValidationError("Requested backup file was not found in backups folder.")

        # Validate backup integrity & required schema before touching live DB
        src_conn = sqlite3.connect(str(src_path))
        try:
            chk = src_conn.execute("PRAGMA integrity_check").fetchone()
            if not chk or str(chk[0]).lower() != "ok":
                raise ValidationError("Selected backup failed SQLite integrity check; restore aborted.")
            tbl = src_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='school_school'"
            ).fetchone()
            if not tbl:
                raise ValidationError("Selected file is not a valid School ERP database backup.")

            # Take pre-restore safety snapshot first
            self.create_backup(suffix="prerestore", actor=None)

            # Copy backup pages into live database and run any newer migrations
            if self.db._memory_conn is not None:
                src_conn.backup(self.db._memory_conn)
                apply_migrations(self.db._memory_conn)
                self.db._memory_conn.commit()
            else:
                dest_conn = sqlite3.connect(self.db.db_path, timeout=30.0)
                try:
                    src_conn.backup(dest_conn)
                    apply_migrations(dest_conn)
                    dest_conn.commit()
                finally:
                    dest_conn.close()
        finally:
            src_conn.close()

        now_iso = utc_now_iso()
        uname = actor["username"] if actor else "system"
        self.settings.set_value("last_backup_at", now_iso, updated_by=uname)
        self.settings.set_value("last_backup_file", clean_name, updated_by=uname)

        if actor:
            self.audit.record(
                user_id=actor["id"],
                username=actor["username"],
                role=actor["role"],
                action="backup.restore",
                entity_type="database",
                entity_id=clean_name,
                summary=f"Restored database from verified backup '{clean_name}'",
                ip_address=ip_address,
            )

        return {"restored_from": clean_name, "restored_at": now_iso}

