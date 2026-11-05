"""Library module service preserving all Odoo constraints, stock/availability tracking, and fine logic."""

from __future__ import annotations

from datetime import date
import sqlite3
from typing import Any

from dateutil.relativedelta import relativedelta

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, UserError, ValidationError, parse_date


class LibraryService:
    """Service layer for the `library` module."""

    def __init__(self, db: Database) -> None:
        self.db = db

    # -------------------------------------------------------------------------
    # Racks, Authors & Books
    # -------------------------------------------------------------------------
    def create_rack(self, name: str, code: str = "") -> int:
        if not name or not name.strip():
            raise ValidationError("Rack Name is required!")
        with self.db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO library_rack (name, code, active) VALUES (?, ?, 1)",
                (name.strip(), code.strip()),
            )
            return int(cur.lastrowid)

    def create_author(
        self,
        name: str,
        birth_date: str | None = None,
        death_date: str | None = None,
        biography: str = "",
        note: str = "",
    ) -> int:
        if not name or not name.strip():
            raise ValidationError("Author Name is required!")
        if birth_date and death_date:
            d_birth = parse_date(birth_date, "Birth Date")
            d_death = parse_date(death_date, "Death Date")
            if d_death < d_birth:
                raise ValidationError("Error! Death date is smaller than Birth Date!")

        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO library_author (name, birth_date, death_date, biography, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name.strip(), birth_date, death_date, biography, note),
            )
            return int(cur.lastrowid)

    def create_book(
        self,
        name: str,
        isbn: str | None = None,
        code: str | None = None,
        barcode: str | None = None,
        author_id: int | None = None,
        rack_id: int | None = None,
        qty_available: int = 1,
        day_to_return_book: int = 14,
        fine_late_return: float = 10.0,
        fine_lost: float = 500.0,
        is_ebook: bool = False,
        is_subscription: bool = False,
        subscrption_amt: float = 0.0,
        attach_ebook: str | None = None,
        back: str = "paper",
        nbpage: int = 200,
    ) -> int:
        """Create a library book (`product.product` extension) with ISBN/barcode uniqueness."""
        if not name or not name.strip():
            raise ValidationError("Book Title is required!")
        if day_to_return_book < 0:
            raise ValidationError("Error! Day to Return Must be Positive")
        if fine_late_return < 0:
            raise ValidationError("Error! Late Return Penalty Must be Positive")
        if fine_lost < 0:
            raise ValidationError("Error! Fine Lost Must be Positive")
        if nbpage < 0:
            raise ValidationError("Number of pages must be positive!")

        with self.db.connection() as conn:
            if isbn and isbn.strip():
                dup_isbn = conn.execute(
                    "SELECT id FROM library_book WHERE LOWER(isbn) = LOWER(?)",
                    (isbn.strip(),),
                ).fetchone()
                if dup_isbn:
                    raise ValidationError("ISBN number must be unique!")

            if barcode and code:
                dup_bc = conn.execute(
                    "SELECT id FROM library_book WHERE barcode = ? AND code = ?",
                    (barcode.strip(), code.strip()),
                ).fetchone()
                if dup_bc:
                    raise ValidationError("Same Book Barcode and Code already exist!")

            avail = (
                "available"
                if (qty_available >= 1 or (is_ebook and bool(attach_ebook)))
                else "notavailable"
            )
            cur = conn.execute(
                """
                INSERT INTO library_book
                    (name, isbn, code, barcode, author_id, rack_id, qty_available,
                     books_available, availability, day_to_return_book, fine_late_return,
                     fine_lost, is_ebook, is_subscription, subscrption_amt, attach_ebook,
                     back, nbpage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    isbn.strip() if isbn else None,
                    code.strip() if code else None,
                    barcode.strip() if barcode else None,
                    author_id,
                    rack_id,
                    qty_available,
                    qty_available,
                    avail,
                    day_to_return_book,
                    fine_late_return,
                    fine_lost,
                    1 if is_ebook else 0,
                    1 if is_subscription else 0,
                    subscrption_amt,
                    attach_ebook,
                    back,
                    nbpage,
                ),
            )
            book_id = int(cur.lastrowid)
            self._recompute_book_availability_conn(conn, book_id)
            return book_id

    def _recompute_book_availability_conn(self, conn: sqlite3.Connection, book_id: int) -> None:
        """Mirror `_compute_books_available` and `_compute_books_availablity`."""
        book = conn.execute("SELECT * FROM library_book WHERE id = ?", (book_id,)).fetchone()
        if not book:
            return
        issued_count = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM library_book_issue
            WHERE book_id = ? AND state IN ('issue', 'reissue')
            """,
            (book_id,),
        ).fetchone()["cnt"]
        books_avail = max(0, int(book["qty_available"]) - int(issued_count))
        is_avail = books_avail >= 1 or (bool(book["is_ebook"]) and bool(book["attach_ebook"]))
        availability = "available" if is_avail else "notavailable"
        conn.execute(
            """
            UPDATE library_book
            SET books_available = ?, availability = ?
            WHERE id = ?
            """,
            (books_avail, availability, book_id),
        )

    # -------------------------------------------------------------------------
    # Library Cards (library.card)
    # -------------------------------------------------------------------------
    def create_library_card(
        self,
        user: str = "student",
        student_id: int | None = None,
        teacher_id: int | None = None,
        book_limit: int = 3,
        start_date: str | None = None,
        duration: int = 12,
        allow_past_dates: bool = False,
    ) -> int:
        """Create a library card with `check_member_card`, `_check_date`, and `end_date` compute."""
        if duration < 0:
            raise ValidationError("Duration (in months) Must be Positive!")
        if book_limit <= 0:
            raise ValidationError("Book limit must be greater than zero!")

        d_start = parse_date(start_date or date.today().isoformat(), "Start Date")
        if not allow_past_dates and d_start < date.today():
            raise ValidationError("Start date must be greater than or equal to current date!")

        d_end = d_start + relativedelta(months=duration)

        with self.db.connection() as conn:
            standard_id = None
            roll_no = None
            card_name = ""

            if user == "student":
                if not student_id:
                    raise ValidationError("Student is required for a student library card!")
                existing = conn.execute(
                    """
                    SELECT id FROM library_card
                    WHERE student_id = ? AND state != 'expire' AND active = 1
                    """,
                    (student_id,),
                ).fetchone()
                if existing:
                    raise ValidationError("Library card already assigned to this student!")

                stu = conn.execute(
                    "SELECT student_name, standard_id, roll_no FROM student_student WHERE id = ?",
                    (student_id,),
                ).fetchone()
                if not stu:
                    raise NotFoundError(f"Student {student_id} not found.")
                standard_id = stu["standard_id"]
                roll_no = stu["roll_no"]
                card_name = stu["student_name"]
            else:
                if not teacher_id:
                    raise ValidationError("Teacher is required for a teacher library card!")
                existing = conn.execute(
                    """
                    SELECT id FROM library_card
                    WHERE teacher_id = ? AND state != 'expire' AND active = 1
                    """,
                    (teacher_id,),
                ).fetchone()
                if existing:
                    raise ValidationError("Library card already assigned to this teacher!")

                tch = conn.execute(
                    "SELECT name FROM school_teacher WHERE id = ?",
                    (teacher_id,),
                ).fetchone()
                if not tch:
                    raise NotFoundError(f"Teacher {teacher_id} not found.")
                card_name = tch["name"]

            cur = conn.execute(
                """
                INSERT INTO library_card
                    (code, book_limit, user, student_id, teacher_id, standard_id, roll_no,
                     card_name, start_date, duration, end_date, state, active)
                VALUES ('New', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', 1)
                """,
                (
                    book_limit,
                    user,
                    student_id,
                    teacher_id,
                    standard_id,
                    roll_no,
                    card_name,
                    d_start.isoformat(),
                    duration,
                    d_end.isoformat(),
                ),
            )
            return int(cur.lastrowid)

    def running_state_card(self, card_id: int) -> str:
        """Transition card to `running` state and assign `LCARD/` sequence."""
        with self.db.connection() as conn:
            card = conn.execute(
                "SELECT code FROM library_card WHERE id = ?",
                (card_id,),
            ).fetchone()
            if not card:
                raise NotFoundError(f"Library Card {card_id} not found.")
            code = (
                card["code"]
                if card["code"] and card["code"] != "New"
                else self.db.next_by_code("library.card", conn)
            )
            conn.execute(
                "UPDATE library_card SET code = ?, state = 'running' WHERE id = ?",
                (code, card_id),
            )
            return code

    def expire_overdue_cards(self, as_of_date: str | None = None) -> int:
        """Cron equivalent `librarycard_expire`: expire cards whose `end_date < current_date`."""
        ref_date = parse_date(as_of_date or date.today().isoformat(), "Reference Date")
        with self.db.connection() as conn:
            cur = conn.execute(
                """
                UPDATE library_card
                SET state = 'expire'
                WHERE end_date < ? AND state != 'expire'
                """,
                (ref_date.isoformat(),),
            )
            return int(cur.rowcount)

    def delete_library_card(self, card_id: int) -> None:
        """Disallow deleting confirmed/running library cards."""
        with self.db.connection() as conn:
            card = conn.execute(
                "SELECT state FROM library_card WHERE id = ?",
                (card_id,),
            ).fetchone()
            if not card:
                raise NotFoundError(f"Library Card {card_id} not found.")
            if card["state"] == "running":
                raise ValidationError("You cannot delete a confirmed library card!")
            conn.execute("DELETE FROM library_card WHERE id = ?", (card_id,))

    # -------------------------------------------------------------------------
    # Book Requests (library.book.request)
    # -------------------------------------------------------------------------
    def create_book_request(
        self,
        card_id: int,
        req_type: str = "existing",
        book_id: int | None = None,
        ebook_id: int | None = None,
        new_book: str | None = None,
    ) -> int:
        """Create a book request with `_check_ request` duplicate check."""
        with self.db.connection() as conn:
            card = conn.execute(
                "SELECT * FROM library_card WHERE id = ?",
                (card_id,),
            ).fetchone()
            if not card:
                raise NotFoundError(f"Library Card {card_id} not found.")

            book_name = new_book or ""
            if req_type == "existing":
                if not book_id:
                    raise ValidationError("Book is required for existing book request!")
                dup = conn.execute(
                    """
                    SELECT id FROM library_book_request
                    WHERE card_id = ? AND book_id = ? AND type = 'existing' AND state != 'cancel'
                    """,
                    (card_id, book_id),
                ).fetchone()
                if dup:
                    raise ValidationError("You can't request same book at the same time!")
                bk = conn.execute("SELECT name FROM library_book WHERE id = ?", (book_id,)).fetchone()
                if bk:
                    book_name = bk["name"]
            elif req_type == "ebook" and ebook_id:
                bk = conn.execute("SELECT name FROM library_book WHERE id = ?", (ebook_id,)).fetchone()
                if bk:
                    book_name = bk["name"]

            req_code = self.db.next_by_code("library.book.request", conn)
            cur = conn.execute(
                """
                INSERT INTO library_book_request
                    (req_id, card_id, type, book_id, ebook_id, new_book, book_name, state, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', 1)
                """,
                (req_code, card_id, req_type, book_id, ebook_id, new_book, book_name),
            )
            return int(cur.lastrowid)

    def confirm_book_request(self, request_id: int) -> int:
        """Confirm book request and generate corresponding `library.book.issue` record."""
        with self.db.connection() as conn:
            req = conn.execute(
                "SELECT * FROM library_book_request WHERE id = ?",
                (request_id,),
            ).fetchone()
            if not req:
                raise NotFoundError(f"Book Request {request_id} not found.")

            card = conn.execute(
                "SELECT * FROM library_card WHERE id = ?",
                (req["card_id"],),
            ).fetchone()
            if not card or card["state"] == "expire" or card["end_date"] < date.today().isoformat():
                raise UserError("Member's Card is Expired!")

            target_book_id = req["ebook_id"] if req["type"] == "ebook" else req["book_id"]
            if not target_book_id:
                raise UserError("Cannot issue a non-cataloged book request without a book record!")

            book = conn.execute(
                "SELECT * FROM library_book WHERE id = ?",
                (target_book_id,),
            ).fetchone()
            if not book:
                raise NotFoundError(f"Book {target_book_id} not found.")

            initial_state = "draft"
            sub_amt = 0.0
            if req["type"] == "ebook":
                if book["is_subscription"]:
                    initial_state = "subscribe"
                    sub_amt = float(book["subscrption_amt"] or 0.0)
                else:
                    initial_state = "paid"

            cur = conn.execute(
                """
                INSERT INTO library_book_issue
                    (book_id, issue_code, book_request_id, card_id, user, student_id,
                     teacher_id, standard_id, roll_no, card_name, date_issue,
                     day_to_return_book, subscription_amt, ebook_download, state)
                VALUES (?, 'New', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    target_book_id,
                    request_id,
                    card["id"],
                    card["user"],
                    card["student_id"],
                    card["teacher_id"],
                    card["standard_id"],
                    card["roll_no"],
                    card["card_name"],
                    date.today().isoformat(),
                    book["day_to_return_book"],
                    sub_amt,
                    book["attach_ebook"],
                    initial_state,
                ),
            )
            issue_id = int(cur.lastrowid)
            conn.execute(
                "UPDATE library_book_request SET state = 'confirm', book_issue_id = ? WHERE id = ?",
                (issue_id, request_id),
            )
            return issue_id

    def delete_book_request(self, request_id: int) -> None:
        with self.db.connection() as conn:
            req = conn.execute(
                "SELECT state FROM library_book_request WHERE id = ?",
                (request_id,),
            ).fetchone()
            if not req:
                raise NotFoundError(f"Book Request {request_id} not found.")
            if req["state"] == "confirm":
                raise ValidationError("You cannot delete a confirmed book request!")
            conn.execute("DELETE FROM library_book_request WHERE id = ?", (request_id,))

    # -------------------------------------------------------------------------
    # Book Issues (library.book.issue)
    # -------------------------------------------------------------------------
    def create_book_issue(
        self,
        book_id: int,
        card_id: int,
        date_issue: str | None = None,
    ) -> int:
        """Create a book issue record and validate card limits and duplicate issues."""
        d_issue = parse_date(date_issue or date.today().isoformat(), "Issue Date")
        with self.db.connection() as conn:
            card = conn.execute("SELECT * FROM library_card WHERE id = ?", (card_id,)).fetchone()
            if not card:
                raise NotFoundError(f"Library Card {card_id} not found.")
            book = conn.execute("SELECT * FROM library_book WHERE id = ?", (book_id,)).fetchone()
            if not book:
                raise NotFoundError(f"Book {book_id} not found.")

            self._validate_issue_constraints_conn(conn, card, book_id, exclude_issue_id=None)

            cur = conn.execute(
                """
                INSERT INTO library_book_issue
                    (book_id, issue_code, card_id, user, student_id, teacher_id,
                     standard_id, roll_no, card_name, date_issue, day_to_return_book, state)
                VALUES (?, 'New', ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft')
                """,
                (
                    book_id,
                    card_id,
                    card["user"],
                    card["student_id"],
                    card["teacher_id"],
                    card["standard_id"],
                    card["roll_no"],
                    card["card_name"],
                    d_issue.isoformat(),
                    book["day_to_return_book"],
                ),
            )
            return int(cur.lastrowid)

    def _validate_issue_constraints_conn(
        self,
        conn: sqlite3.Connection,
        card: sqlite3.Row,
        book_id: int,
        exclude_issue_id: int | None,
    ) -> None:
        """Enforce `check_book_issue` and `_check_issue_book_limit`."""
        dup_query = """
            SELECT id FROM library_book_issue
            WHERE card_id = ? AND book_id = ?
              AND state NOT IN ('draft', 'cancel', 'return', 'paid')
        """
        params: list[Any] = [card["id"], book_id]
        if exclude_issue_id is not None:
            dup_query += " AND id != ?"
            params.append(exclude_issue_id)
        if conn.execute(dup_query, tuple(params)).fetchone():
            raise ValidationError("This book is already issued on this card!")

        limit_query = """
            SELECT COUNT(*) AS cnt FROM library_book_issue
            WHERE card_id = ? AND state IN ('issue', 'reissue')
        """
        l_params: list[Any] = [card["id"]]
        if exclude_issue_id is not None:
            limit_query += " AND id != ?"
            l_params.append(exclude_issue_id)
        active_cnt = conn.execute(limit_query, tuple(l_params)).fetchone()["cnt"]
        if active_cnt >= int(card["book_limit"]):
            raise ValidationError("Book issue limit is over on this card!")

    def issue_book(self, issue_id: int) -> dict[str, Any]:
        """Issue book (`issue_book`), checking card expiration, unpaid fines, and stock availability."""
        with self.db.connection() as conn:
            issue = conn.execute(
                "SELECT * FROM library_book_issue WHERE id = ?",
                (issue_id,),
            ).fetchone()
            if not issue:
                raise NotFoundError(f"Book Issue {issue_id} not found.")

            card = conn.execute(
                "SELECT * FROM library_card WHERE id = ?",
                (issue["card_id"],),
            ).fetchone()
            if not card or card["state"] != "running" or card["end_date"] < date.today().isoformat():
                raise UserError("Member's Card is Expired or Not Running!")

            unpaid_fine = conn.execute(
                """
                SELECT id FROM library_book_issue
                WHERE card_id = ? AND state = 'fine' AND id != ?
                """,
                (card["id"], issue_id),
            ).fetchone()
            if unpaid_fine:
                raise UserError("You cannot issue book until previous fine is paid!")

            book = conn.execute(
                "SELECT * FROM library_book WHERE id = ?",
                (issue["book_id"],),
            ).fetchone()
            if not book:
                raise NotFoundError(f"Book {issue['book_id']} not found.")
            self._recompute_book_availability_conn(conn, book["id"])
            book = conn.execute("SELECT * FROM library_book WHERE id = ?", (book["id"],)).fetchone()
            if book["availability"] == "notavailable":
                raise UserError("The Book You are Trying to Issue is not Available!")

            self._validate_issue_constraints_conn(conn, card, book["id"], exclude_issue_id=issue_id)

            code = (
                issue["issue_code"]
                if issue["issue_code"] and issue["issue_code"] != "New"
                else self.db.next_by_code("library.book.issue", conn)
            )
            d_issue = parse_date(issue["date_issue"], "Issue Date")
            days_ret = int(book["day_to_return_book"] or 14)
            d_return = d_issue + relativedelta(days=days_ret)

            conn.execute(
                """
                UPDATE library_book_issue
                SET issue_code = ?, day_to_return_book = ?, date_return = ?, state = 'issue'
                WHERE id = ?
                """,
                (code, days_ret, d_return.isoformat(), issue_id),
            )
            self._recompute_book_availability_conn(conn, book["id"])
            updated = conn.execute(
                "SELECT * FROM library_book_issue WHERE id = ?",
                (issue_id,),
            ).fetchone()
            return dict(updated)

    def reissue_book(self, issue_id: int, reissue_date: str | None = None) -> dict[str, Any]:
        """Reissue book (`reissue_book`), blocking if return date has already expired with penalty."""
        d_now = parse_date(reissue_date or date.today().isoformat(), "Reissue Date")
        with self.db.connection() as conn:
            issue = conn.execute(
                "SELECT * FROM library_book_issue WHERE id = ?",
                (issue_id,),
            ).fetchone()
            if not issue:
                raise NotFoundError(f"Book Issue {issue_id} not found.")
            book = conn.execute(
                "SELECT * FROM library_book WHERE id = ?",
                (issue["book_id"],),
            ).fetchone()

            if issue["date_return"]:
                d_ret = parse_date(issue["date_return"], "Return Date")
                late_days = (d_now - d_ret).days
                if late_days > 0 and float(book["fine_late_return"]) > 0:
                    raise UserError("Return date is expired, Please return your book!")

            days_ret = int(issue["day_to_return_book"] or book["day_to_return_book"] or 14)
            new_ret = d_now + relativedelta(days=days_ret)
            conn.execute(
                """
                UPDATE library_book_issue
                SET date_issue = ?, date_return = ?, state = 'reissue'
                WHERE id = ?
                """,
                (d_now.isoformat(), new_ret.isoformat(), issue_id),
            )
            updated = conn.execute(
                "SELECT * FROM library_book_issue WHERE id = ?",
                (issue_id,),
            ).fetchone()
            return dict(updated)

    def return_book(self, issue_id: int, actual_return_date: str | None = None) -> dict[str, Any]:
        """Return book (`return_book`), computing late penalty and restoring book availability."""
        d_actual = parse_date(actual_return_date or date.today().isoformat(), "Actual Return Date")
        with self.db.connection() as conn:
            issue = conn.execute(
                "SELECT * FROM library_book_issue WHERE id = ?",
                (issue_id,),
            ).fetchone()
            if not issue:
                raise NotFoundError(f"Book Issue {issue_id} not found.")
            book = conn.execute(
                "SELECT * FROM library_book WHERE id = ?",
                (issue["book_id"],),
            ).fetchone()

            penalty = 0.0
            if issue["date_return"]:
                d_ret = parse_date(issue["date_return"], "Return Date")
                diff_days = (d_actual - d_ret).days
                if diff_days > 0:
                    penalty = round(diff_days * float(book["fine_late_return"] or 0.0), 2)

            new_state = "fine" if penalty > 0 else "return"
            conn.execute(
                """
                UPDATE library_book_issue
                SET actual_return_date = ?, penalty = ?, state = ?
                WHERE id = ?
                """,
                (d_actual.isoformat(), penalty, new_state, issue_id),
            )
            self._recompute_book_availability_conn(conn, issue["book_id"])
            updated = conn.execute(
                "SELECT * FROM library_book_issue WHERE id = ?",
                (issue_id,),
            ).fetchone()
            return dict(updated)

    def lost_book(self, issue_id: int) -> dict[str, Any]:
        """Mark book as lost (`lost_book`), charge `fine_lost`, and scrap 1 unit from `qty_available`."""
        with self.db.connection() as conn:
            issue = conn.execute(
                "SELECT * FROM library_book_issue WHERE id = ?",
                (issue_id,),
            ).fetchone()
            if not issue:
                raise NotFoundError(f"Book Issue {issue_id} not found.")
            book = conn.execute(
                "SELECT * FROM library_book WHERE id = ?",
                (issue["book_id"],),
            ).fetchone()
            lost_fine = float(book["fine_lost"] or 0.0)
            new_qty = max(0, int(book["qty_available"]) - 1)

            conn.execute(
                "UPDATE library_book SET qty_available = ? WHERE id = ?",
                (new_qty, book["id"]),
            )
            conn.execute(
                """
                UPDATE library_book_issue
                SET lost_penalty = ?, state = 'fine'
                WHERE id = ?
                """,
                (lost_fine, issue_id),
            )
            self._recompute_book_availability_conn(conn, book["id"])
            updated = conn.execute(
                "SELECT * FROM library_book_issue WHERE id = ?",
                (issue_id,),
            ).fetchone()
            return dict(updated)

    def pay_fine(self, issue_id: int) -> dict[str, Any]:
        """Pay fine (`user_fine` / invoice payment), marking issue `paid`."""
        with self.db.connection() as conn:
            issue = conn.execute(
                "SELECT * FROM library_book_issue WHERE id = ?",
                (issue_id,),
            ).fetchone()
            if not issue:
                raise NotFoundError(f"Book Issue {issue_id} not found.")
            conn.execute(
                """
                UPDATE library_book_issue
                SET state = 'paid'
                WHERE id = ?
                """,
                (issue_id,),
            )
            self._recompute_book_availability_conn(conn, issue["book_id"])
            updated = conn.execute(
                "SELECT * FROM library_book_issue WHERE id = ?",
                (issue_id,),
            ).fetchone()
            return dict(updated)

    # -------------------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------------------
    def list_books(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT b.*, a.name AS author_name, r.name AS rack_name
            FROM library_book b
            LEFT JOIN library_author a ON a.id = b.author_id
            LEFT JOIN library_rack r ON r.id = b.rack_id
            ORDER BY b.name
            """
        )

    def list_cards(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT c.*, ss.name AS standard_name
            FROM library_card c
            LEFT JOIN school_standard ss ON ss.id = c.standard_id
            WHERE c.active = 1
            ORDER BY c.id DESC
            """
        )

    def list_book_issues(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT bi.*, b.name AS book_name, b.isbn, c.code AS card_code
            FROM library_book_issue bi
            JOIN library_book b ON b.id = bi.book_id
            JOIN library_card c ON c.id = bi.card_id
            ORDER BY bi.id DESC
            """
        )

