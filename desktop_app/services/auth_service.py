"""
Authentication, Role Management, Account Lockout & Recovery Code Service (Phase 2 — G3).

Security guarantees:
  - Passwords/PINs & recovery codes hashed with PBKDF2-HMAC-SHA256 (260,000 iterations) + random 16-byte salt
  - Constant-time verification via ``hmac.compare_digest``
  - Session tokens are 256-bit random strings; only SHA-256 hashes are stored in SQLite
  - 5 consecutive failed logins trigger a 15-minute account lockout (R-S1)
  - One-time Recovery Code rotates automatically whenever used (Risk R6)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re
import secrets
from typing import Any

from desktop_app.database import Database
from desktop_app.exceptions import SchoolERPError, ValidationError
from desktop_app.services.audit_service import AuditService, utc_now_iso

VALID_ROLES = ("admin", "principal", "teacher", "fee_clerk", "front_desk", "exam_incharge")
ADMIN_ROLES = frozenset({"admin", "principal"})

PBKDF2_ITERATIONS = 260_000
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
SESSION_HOURS = 24
RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")


class AuthError(SchoolERPError):
    """Authentication or authorization failure carrying an explicit HTTP status code."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.status_code = status_code


def _hash_secret(secret: str, salt_hex: str | None = None) -> tuple[str, str]:
    salt_bytes = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt_bytes,
        PBKDF2_ITERATIONS,
    )
    return digest.hex(), salt_bytes.hex()


def _verify_secret(secret: str, expected_hex: str | None, salt_hex: str | None) -> bool:
    if not expected_hex or not salt_hex:
        return False
    candidate_hex, _ = _hash_secret(secret, salt_hex)
    return hmac.compare_digest(candidate_hex, expected_hex)


def _normalize_recovery(code: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (code or "").upper())


def _generate_recovery_code() -> str:
    groups = [
        "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(4))
        for _ in range(3)
    ]
    return f"RK-{'-'.join(groups)}"


def _hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _public_user(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "username": row["username"],
        "full_name": row["full_name"],
        "role": row["role"],
        "teacher_id": row.get("teacher_id"),
        "teacher_name": row.get("teacher_name"),
        "active": bool(row.get("active", 1)),
        "failed_attempts": int(row.get("failed_attempts") or 0),
        "locked_until": row.get("locked_until"),
        "last_login_at": row.get("last_login_at"),
        "created_at": row.get("created_at"),
    }


class AuthService:
    """Local staff authentication, RBAC user management, and recovery service."""

    def __init__(self, db: Database, audit: AuditService | None = None) -> None:
        self.db = db
        self.audit = audit or AuditService(db)

    def has_any_users(self) -> bool:
        row = self.db.fetch_one("SELECT COUNT(*) AS c FROM app_user")
        return bool(row and int(row["c"]) > 0)

    def _validate_credentials(self, username: str, secret: str) -> str:
        uname = (username or "").strip().lower()
        if not USERNAME_RE.match(uname):
            raise ValidationError("Username must be 3-32 letters, digits, dots, hyphens, or underscores.")
        if not secret or len(secret.strip()) < 6:
            raise ValidationError("PIN / Password must be at least 6 characters long.")
        return uname

    def _issue_session_conn(self, conn: Any, user_id: int, ip_address: str) -> str:
        raw_token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).replace(microsecond=0)
        expires = (now + timedelta(hours=SESSION_HOURS)).isoformat()
        conn.execute(
            "DELETE FROM app_session WHERE expires_at <= ?",
            (now.isoformat(),),
        )
        conn.execute(
            """
            INSERT INTO app_session (token_hash, user_id, created_at, expires_at, ip_address)
            VALUES (?, ?, ?, ?, ?)
            """,
            (_hash_session_token(raw_token), user_id, now.isoformat(), expires, ip_address),
        )
        return raw_token

    def setup_initial_admin(
        self,
        *,
        full_name: str,
        username: str,
        secret: str,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """Create the initial Principal/Admin account only when zero users exist."""
        clean_name = (full_name or "").strip()
        if len(clean_name) < 2:
            raise ValidationError("Administrator full name is required.")
        uname = self._validate_credentials(username, secret)

        pw_hash, pw_salt = _hash_secret(secret.strip())
        raw_recovery = _generate_recovery_code()
        rec_hash, rec_salt = _hash_secret(_normalize_recovery(raw_recovery))
        now = utc_now_iso()

        with self.db.connection() as conn:
            existing = conn.execute("SELECT COUNT(*) AS c FROM app_user").fetchone()["c"]
            if int(existing) > 0:
                raise AuthError("Initial administrator setup has already been completed.", status_code=403)

            cur = conn.execute(
                """
                INSERT INTO app_user (
                    username, full_name, role, password_hash, password_salt,
                    recovery_hash, recovery_salt, active, last_login_at, created_at
                )
                VALUES (?, ?, 'principal', ?, ?, ?, ?, 1, ?, ?)
                """,
                (uname, clean_name, pw_hash, pw_salt, rec_hash, rec_salt, now, now),
            )
            user_id = int(cur.lastrowid)
            token = self._issue_session_conn(conn, user_id, ip_address)
            user_row = dict(conn.execute("SELECT * FROM app_user WHERE id = ?", (user_id,)).fetchone())

        self.audit.record(
            user_id=user_id,
            username=uname,
            role="principal",
            action="auth.setup",
            entity_type="app_user",
            entity_id=user_id,
            summary=f"Initialized administrator account '{uname}'",
            ip_address=ip_address,
        )
        return {
            "user": _public_user(user_row),
            "token": token,
            "recovery_code": raw_recovery,
        }

    def login(
        self,
        *,
        username: str,
        secret: str,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """Verify staff credentials, enforce 5-attempt lockout, and create a session."""
        uname = (username or "").strip().lower()
        if not uname or not secret:
            raise AuthError("Username and PIN/password are required.", status_code=401)

        row = self.db.fetch_one("SELECT * FROM app_user WHERE username = ?", (uname,))
        if not row or not row.get("active"):
            # Perform dummy hash work to prevent username enumeration timing leaks
            _hash_secret(secret, "00" * 16)
            self.audit.record(
                user_id=None,
                username=uname,
                role="unauthenticated",
                action="auth.login_failed",
                entity_type="app_user",
                summary=f"Failed sign-in for '{uname}'",
                ip_address=ip_address,
            )
            raise AuthError("Invalid username or PIN/password.", status_code=401)

        now_dt = datetime.now(timezone.utc).replace(microsecond=0)
        locked_until = row.get("locked_until")
        if locked_until:
            try:
                lock_dt = datetime.fromisoformat(locked_until)
                if lock_dt > now_dt:
                    mins = max(1, int((lock_dt - now_dt).total_seconds() // 60) + 1)
                    raise AuthError(
                        f"Account temporarily locked after failed attempts. Try again in {mins} min or use Recovery Code.",
                        status_code=429,
                    )
            except ValueError:
                pass

        if not _verify_secret(secret.strip(), row["password_hash"], row["password_salt"]):
            attempts = int(row.get("failed_attempts") or 0) + 1
            new_lock = (
                (now_dt + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
                if attempts >= MAX_FAILED_ATTEMPTS
                else None
            )
            with self.db.connection() as conn:
                conn.execute(
                    "UPDATE app_user SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                    (attempts, new_lock, row["id"]),
                )
            self.audit.record(
                user_id=int(row["id"]),
                username=row["username"],
                role=row["role"],
                action="auth.lockout" if new_lock else "auth.login_failed",
                entity_type="app_user",
                entity_id=row["id"],
                summary=(
                    f"Account locked after {attempts} failed attempts"
                    if new_lock
                    else f"Failed sign-in attempt ({attempts}/{MAX_FAILED_ATTEMPTS})"
                ),
                ip_address=ip_address,
            )
            if new_lock:
                raise AuthError(
                    f"Account locked for {LOCKOUT_MINUTES} minutes after {MAX_FAILED_ATTEMPTS} failed attempts.",
                    status_code=429,
                )
            raise AuthError("Invalid username or PIN/password.", status_code=401)

        now_iso = now_dt.isoformat()
        with self.db.connection() as conn:
            conn.execute(
                """
                UPDATE app_user
                SET failed_attempts = 0, locked_until = NULL, last_login_at = ?
                WHERE id = ?
                """,
                (now_iso, row["id"]),
            )
            token = self._issue_session_conn(conn, int(row["id"]), ip_address)
            updated = dict(conn.execute("SELECT * FROM app_user WHERE id = ?", (row["id"],)).fetchone())

        self.audit.record(
            user_id=int(row["id"]),
            username=row["username"],
            role=row["role"],
            action="auth.login",
            entity_type="app_user",
            entity_id=row["id"],
            summary=f"Signed in as {row['role']}",
            ip_address=ip_address,
        )
        return {"user": _public_user(updated), "token": token}

    def recover_account(
        self,
        *,
        username: str,
        recovery_code: str,
        new_secret: str,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """Reset administrator PIN/password using the one-time Recovery Code and rotate it."""
        uname = self._validate_credentials(username, new_secret)
        norm_code = _normalize_recovery(recovery_code)
        row = self.db.fetch_one("SELECT * FROM app_user WHERE username = ?", (uname,))

        if not row or row["role"] not in ADMIN_ROLES or not _verify_secret(
            norm_code, row.get("recovery_hash"), row.get("recovery_salt")
        ):
            self.audit.record(
                user_id=row["id"] if row else None,
                username=uname,
                role=row["role"] if row else "unauthenticated",
                action="auth.recover_failed",
                entity_type="app_user",
                summary=f"Invalid recovery code attempt for '{uname}'",
                ip_address=ip_address,
            )
            raise AuthError("Invalid username or Recovery Code.", status_code=401)

        pw_hash, pw_salt = _hash_secret(new_secret.strip())
        next_recovery = _generate_recovery_code()
        rec_hash, rec_salt = _hash_secret(_normalize_recovery(next_recovery))

        with self.db.connection() as conn:
            conn.execute(
                """
                UPDATE app_user
                SET password_hash = ?, password_salt = ?,
                    recovery_hash = ?, recovery_salt = ?,
                    failed_attempts = 0, locked_until = NULL, active = 1
                WHERE id = ?
                """,
                (pw_hash, pw_salt, rec_hash, rec_salt, row["id"]),
            )
            conn.execute("DELETE FROM app_session WHERE user_id = ?", (row["id"],))

        self.audit.record(
            user_id=int(row["id"]),
            username=row["username"],
            role=row["role"],
            action="auth.recover",
            entity_type="app_user",
            entity_id=row["id"],
            summary="Account recovered via one-time Recovery Code; code rotated",
            ip_address=ip_address,
        )
        return {"new_recovery_code": next_recovery}

    def regenerate_recovery_code(
        self,
        *,
        user_id: int,
        current_secret: str,
        ip_address: str = "127.0.0.1",
    ) -> str:
        """Issue a fresh one-time Recovery Code for an authenticated administrator."""
        row = self.db.fetch_one("SELECT * FROM app_user WHERE id = ?", (user_id,))
        if not row or row["role"] not in ADMIN_ROLES:
            raise AuthError("Only Principal/Admin accounts hold a Recovery Code.", status_code=403)
        if not _verify_secret((current_secret or "").strip(), row["password_hash"], row["password_salt"]):
            raise AuthError("Current PIN/password verification failed.", status_code=401)

        next_recovery = _generate_recovery_code()
        rec_hash, rec_salt = _hash_secret(_normalize_recovery(next_recovery))
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE app_user SET recovery_hash = ?, recovery_salt = ? WHERE id = ?",
                (rec_hash, rec_salt, user_id),
            )
        self.audit.record(
            user_id=user_id,
            username=row["username"],
            role=row["role"],
            action="auth.recovery_rotated",
            entity_type="app_user",
            entity_id=user_id,
            summary="Regenerated administrator Recovery Code",
            ip_address=ip_address,
        )
        return next_recovery

    def resolve_session(self, raw_token: str | None) -> dict[str, Any] | None:
        """Return public user dict if ``raw_token`` maps to an active, unexpired session."""
        if not raw_token:
            return None
        now_iso = utc_now_iso()
        row = self.db.fetch_one(
            """
            SELECT u.*
            FROM app_session s
            JOIN app_user u ON u.id = s.user_id
            WHERE s.token_hash = ? AND s.expires_at > ? AND u.active = 1
            """,
            (_hash_session_token(raw_token), now_iso),
        )
        return _public_user(row) if row else None

    def logout(self, raw_token: str | None, ip_address: str = "127.0.0.1") -> None:
        """Invalidate a session token."""
        if not raw_token:
            return
        user = self.resolve_session(raw_token)
        with self.db.connection() as conn:
            conn.execute("DELETE FROM app_session WHERE token_hash = ?", (_hash_session_token(raw_token),))
        if user:
            self.audit.record(
                user_id=user["id"],
                username=user["username"],
                role=user["role"],
                action="auth.logout",
                entity_type="app_user",
                entity_id=user["id"],
                summary="Signed out",
                ip_address=ip_address,
            )

    def list_users(self) -> list[dict[str, Any]]:
        """List all staff accounts without any password or recovery hashes."""
        rows = self.db.fetch_all(
            """
            SELECT u.*, t.name AS teacher_name
            FROM app_user u
            LEFT JOIN school_teacher t ON t.id = u.teacher_id
            ORDER BY u.active DESC, u.id ASC
            """
        )
        return [_public_user(r) for r in rows]

    def create_user(
        self,
        *,
        full_name: str,
        username: str,
        role: str,
        secret: str,
        teacher_id: int | None = None,
        actor: dict[str, Any] | None = None,
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """Create a staff account with an explicit role."""
        clean_name = (full_name or "").strip()
        if len(clean_name) < 2:
            raise ValidationError("Full name is required.")
        if role not in VALID_ROLES:
            raise ValidationError(f"Invalid role '{role}'. Must be one of: {', '.join(VALID_ROLES)}")
        uname = self._validate_credentials(username, secret)
        if self.db.fetch_one("SELECT id FROM app_user WHERE username = ?", (uname,)):
            raise ValidationError(f"Username '{uname}' already exists.")

        pw_hash, pw_salt = _hash_secret(secret.strip())
        now = utc_now_iso()
        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO app_user (
                    username, full_name, role, password_hash, password_salt,
                    teacher_id, active, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (uname, clean_name, role, pw_hash, pw_salt, teacher_id, now),
            )
            uid = int(cur.lastrowid)
            row = dict(conn.execute("SELECT * FROM app_user WHERE id = ?", (uid,)).fetchone())

        self.audit.record(
            user_id=actor["id"] if actor else None,
            username=actor["username"] if actor else "system",
            role=actor["role"] if actor else "admin",
            action="user.create",
            entity_type="app_user",
            entity_id=uid,
            summary=f"Created staff account '{uname}' with role '{role}'",
            ip_address=ip_address,
        )
        return _public_user(row)

    def manage_user(
        self,
        *,
        user_id: int,
        action: str,
        payload: dict[str, Any],
        actor: dict[str, Any],
        ip_address: str = "127.0.0.1",
    ) -> dict[str, Any]:
        """Reset PIN, unlock, activate/deactivate, or update role of a staff user."""
        target = self.db.fetch_one("SELECT * FROM app_user WHERE id = ?", (user_id,))
        if not target:
            raise ValidationError("Staff user not found.")

        norm_action = {"disable": "deactivate", "enable": "activate"}.get(action, action)
        if norm_action in ("deactivate", "change_role") and target["role"] in ADMIN_ROLES:
            admins = self.db.fetch_one(
                "SELECT COUNT(*) AS c FROM app_user WHERE role IN ('admin', 'principal') AND active = 1"
            )["c"]
            new_role = payload.get("role", target["role"])
            if int(admins) <= 1 and (norm_action == "deactivate" or new_role not in ADMIN_ROLES):
                raise ValidationError("Cannot deactivate or demote the last active Principal/Admin account.")

        with self.db.connection() as conn:
            if norm_action == "unlock":
                conn.execute(
                    "UPDATE app_user SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
                    (user_id,),
                )
            elif norm_action == "reset_secret":
                new_secret = (payload.get("new_secret") or payload.get("secret") or "").strip()
                if len(new_secret) < 6:
                    raise ValidationError("New PIN / Password must be at least 6 characters.")
                pw_hash, pw_salt = _hash_secret(new_secret)
                conn.execute(
                    """
                    UPDATE app_user
                    SET password_hash = ?, password_salt = ?, failed_attempts = 0, locked_until = NULL
                    WHERE id = ?
                    """,
                    (pw_hash, pw_salt, user_id),
                )
                conn.execute("DELETE FROM app_session WHERE user_id = ?", (user_id,))
            elif norm_action == "deactivate":
                conn.execute("UPDATE app_user SET active = 0 WHERE id = ?", (user_id,))
                conn.execute("DELETE FROM app_session WHERE user_id = ?", (user_id,))
            elif norm_action == "activate":
                conn.execute("UPDATE app_user SET active = 1 WHERE id = ?", (user_id,))
            elif norm_action == "change_role":
                new_role = payload.get("role", "")
                if new_role not in VALID_ROLES:
                    raise ValidationError(f"Invalid role: {new_role}")
                conn.execute("UPDATE app_user SET role = ? WHERE id = ?", (new_role, user_id))
            else:
                raise ValidationError(f"Unknown user management action: {action}")

            updated = dict(conn.execute("SELECT * FROM app_user WHERE id = ?", (user_id,)).fetchone())

        self.audit.record(
            user_id=actor["id"],
            username=actor["username"],
            role=actor["role"],
            action=f"user.{action}",
            entity_type="app_user",
            entity_id=user_id,
            summary=f"User '{target['username']}' action: {action}",
            ip_address=ip_address,
        )
        return _public_user(updated)
