"""Custom exceptions and validation helpers for School Management ERP."""

from __future__ import annotations

from datetime import date, datetime
import re

EMAIL_REGEX = re.compile(
    r"^[_a-zA-Z0-9-]+(\.[_a-zA-Z0-9-]+)*@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*(\.[a-zA-Z]{2,6})$"
)


class AppError(Exception):
    """Base application exception."""


SchoolERPError = AppError


class ValidationError(AppError):
    """Raised when domain or constraint validation fails (mirrors Odoo ValidationError)."""


class UserError(AppError):
    """Raised when user workflow action violates business rules (mirrors Odoo UserError)."""


class NotFoundError(AppError):
    """Raised when a requested record is not found."""


def validate_email(email: str | None) -> None:
    """Validate email format using the school module's regex rule."""
    if email:
        if not EMAIL_REGEX.match(email.strip()):
            raise ValidationError(
                "This seems not to be valid email. Please enter email in correct format!"
            )


def parse_date(
    val: str | date | datetime | None,
    field_name: str = "Date",
) -> date | None:
    """Parse ISO date string ('YYYY-MM-DD') or date/datetime into a date object."""
    if val is None or val == "":
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val).strip()[:10])
    except ValueError as exc:
        raise ValidationError(f"Invalid {field_name}: {val}") from exc
