"""Services for `school_event`, `school_hostel`, and `school_transport` modules."""

from __future__ import annotations

from datetime import date
import sqlite3
from typing import Any

from dateutil.relativedelta import relativedelta

from desktop_app.database import Database
from desktop_app.exceptions import NotFoundError, UserError, ValidationError, parse_date


class EventService:
    """Service layer for `school_event`."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_event(
        self,
        name: str,
        start_date: str,
        end_date: str,
        event_type: str = "intra",
        contact_teacher_id: int | None = None,
        standard_ids: list[int] | None = None,
        pipe_end: bool = False,
    ) -> int:
        if not name or not name.strip():
            raise ValidationError("Event Name is required!")
        d_start = parse_date(start_date, "Start Date")
        d_end = parse_date(end_date, "End Date")
        if d_end < d_start:
            raise ValidationError("Event End Date must be greater than or equal to Start Date!")

        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO school_event
                    (name, event_type, start_date, end_date, contact_teacher_id, pipe_end)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    name.strip(),
                    event_type,
                    d_start.isoformat(),
                    d_end.isoformat(),
                    contact_teacher_id,
                    1 if pipe_end else 0,
                ),
            )
            event_id = int(cur.lastrowid)
            for std_id in standard_ids or []:
                conn.execute(
                    "INSERT OR IGNORE INTO school_event_standard_rel (event_id, standard_id) VALUES (?, ?)",
                    (event_id, std_id),
                )
            return event_id

    def set_event_ended(self, event_id: int, ended: bool = True) -> None:
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE school_event SET pipe_end = ? WHERE id = ?",
                (1 if ended else 0, event_id),
            )

    def create_registration(self, event_id: int, part_name_id: int) -> int:
        """Create event registration and auto-populate `student_standard_id` (`onchange_student_standard`)."""
        with self.db.connection() as conn:
            ev = conn.execute("SELECT id FROM school_event WHERE id = ?", (event_id,)).fetchone()
            if not ev:
                raise NotFoundError(f"Event {event_id} not found.")
            stu = conn.execute(
                "SELECT id, standard_id FROM student_student WHERE id = ?",
                (part_name_id,),
            ).fetchone()
            if not stu:
                raise NotFoundError(f"Student {part_name_id} not found.")

            cur = conn.execute(
                """
                INSERT INTO event_registration (event_id, part_name_id, student_standard_id, state)
                VALUES (?, ?, ?, 'draft')
                """,
                (event_id, part_name_id, stu["standard_id"]),
            )
            return int(cur.lastrowid)

    def confirm_registration(self, reg_id: int) -> None:
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE event_registration SET state = 'confirm' WHERE id = ?",
                (reg_id,),
            )

    def cancel_registration(self, reg_id: int) -> None:
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE event_registration SET state = 'cancel' WHERE id = ?",
                (reg_id,),
            )

    def set_registration_draft(self, reg_id: int) -> None:
        """Mirror `action_set_draft`: block resetting to draft if event `pipe_end` is True."""
        with self.db.connection() as conn:
            reg = conn.execute(
                """
                SELECT er.id, se.pipe_end
                FROM event_registration er
                JOIN school_event se ON se.id = er.event_id
                WHERE er.id = ?
                """,
                (reg_id,),
            ).fetchone()
            if not reg:
                raise NotFoundError(f"Event Registration {reg_id} not found.")
            if reg["pipe_end"]:
                raise ValidationError(
                    "You can not set registration to Draft stage due to event is ended!"
                )
            conn.execute(
                "UPDATE event_registration SET state = 'draft' WHERE id = ?",
                (reg_id,),
            )

    def list_events(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT se.*, t.name AS teacher_name,
                   (SELECT COUNT(*) FROM event_registration er WHERE er.event_id = se.id) AS registration_count
            FROM school_event se
            LEFT JOIN school_teacher t ON t.id = se.contact_teacher_id
            ORDER BY se.start_date DESC, se.id DESC
            """
        )

    def list_registrations(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT er.*, se.name AS event_name, se.pipe_end,
                   s.student_name, s.pid, ss.name AS standard_name
            FROM event_registration er
            JOIN school_event se ON se.id = er.event_id
            JOIN student_student s ON s.id = er.part_name_id
            LEFT JOIN school_standard ss ON ss.id = er.student_standard_id
            ORDER BY er.id DESC
            """
        )


class HostelService:
    """Service layer for `school_hostel`."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_hostel_type(
        self,
        name: str,
        hostel_type: str = "common",
        rector_name: str = "",
        city: str = "",
        other_info: str = "",
    ) -> int:
        if not name or not name.strip():
            raise ValidationError("Hostel Name is required!")
        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO hostel_type (name, type, rector_name, city, other_info)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name.strip(), hostel_type, rector_name, city, other_info),
            )
            return int(cur.lastrowid)

    def create_hostel_room(
        self,
        hostel_id: int,
        room_no: str,
        floor_no: int = 1,
        student_per_room: int = 2,
        rent_amount: float = 1000.0,
    ) -> int:
        """Create hostel room with floor, capacity, rent, and unique `(room_no, hostel_id)` checks."""
        if not room_no or not room_no.strip():
            raise ValidationError("Room No. is required!")
        if floor_no >= 99:
            raise ValidationError("Error ! Floor per HOSTEL should be less than 99.")
        if student_per_room <= 0:
            raise ValidationError("Student per room must be greater than zero!")
        if student_per_room >= 10:
            raise ValidationError("Error ! Student per room should be less than 10.")
        if rent_amount < 0:
            raise ValidationError("Room Rent Amount cannot be negative!")

        with self.db.connection() as conn:
            dup = conn.execute(
                "SELECT id FROM hostel_room WHERE room_no = ? AND hostel_id = ?",
                (room_no.strip(), hostel_id),
            ).fetchone()
            if dup:
                raise ValidationError("Room number must be unique per hostel!")

            cur = conn.execute(
                """
                INSERT INTO hostel_room
                    (hostel_id, floor_no, room_no, student_per_room, availability, rent_amount)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    hostel_id,
                    floor_no,
                    room_no.strip(),
                    student_per_room,
                    float(student_per_room),
                    rent_amount,
                ),
            )
            return int(cur.lastrowid)

    def _recompute_room_availability_conn(self, conn: sqlite3.Connection, room_id: int) -> float:
        """Mirror `_compute_check_availability`."""
        room = conn.execute("SELECT * FROM hostel_room WHERE id = ?", (room_id,)).fetchone()
        if not room:
            return 0.0
        occupied = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM hostel_student
            WHERE room_id = ?
              AND status NOT IN ('cancel', 'discharge')
              AND active = 1
            """,
            (room_id,),
        ).fetchone()["cnt"]
        avail = float(int(room["student_per_room"]) - int(occupied))
        conn.execute(
            "UPDATE hostel_room SET availability = ? WHERE id = ?",
            (avail, room_id),
        )
        return avail

    def create_hostel_student(
        self,
        student_id: int,
        hostel_info_id: int,
        room_id: int,
        duration: int,
        admission_date: str | None = None,
        tax_amount: float = 0.0,
        allow_past_dates: bool = False,
    ) -> int:
        """Register student in hostel with gender, duplicate, date, duration, and room availability checks."""
        if duration <= 0:
            raise ValidationError("Duration (in months) must be greater than 0!")

        d_adm = parse_date(admission_date or date.today().isoformat(), "Admission Date")
        if not allow_past_dates and d_adm < date.today():
            raise ValidationError("Your admission date should be greater than current date!")
        d_dis = d_adm + relativedelta(months=duration)

        with self.db.connection() as conn:
            stu = conn.execute(
                "SELECT * FROM student_student WHERE id = ?",
                (student_id,),
            ).fetchone()
            if not stu:
                raise NotFoundError(f"Student {student_id} not found.")

            hostel = conn.execute(
                "SELECT * FROM hostel_type WHERE id = ?",
                (hostel_info_id,),
            ).fetchone()
            if not hostel:
                raise NotFoundError(f"Hostel {hostel_info_id} not found.")

            if hostel["type"] not in ("common", stu["gender"]):
                raise ValidationError(
                    f"Hostel type ({hostel['type']}) does not match student gender ({stu['gender']})!"
                )

            dup = conn.execute(
                """
                SELECT id FROM hostel_student
                WHERE student_id = ?
                  AND status NOT IN ('cancel', 'discharge')
                  AND active = 1
                """,
                (student_id,),
            ).fetchone()
            if dup:
                raise ValidationError("This student is already registered in the hostel!")

            room = conn.execute(
                "SELECT * FROM hostel_room WHERE id = ? AND hostel_id = ?",
                (room_id, hostel_info_id),
            ).fetchone()
            if not room:
                raise ValidationError("Selected room does not belong to the chosen hostel!")

            avail = self._recompute_room_availability_conn(conn, room_id)
            if avail <= 0:
                raise ValidationError("There is no availability in the room!")

            room_rent = round(duration * float(room["rent_amount"]), 2)
            remaining = round(room_rent + float(tax_amount), 2)

            cur = conn.execute(
                """
                INSERT INTO hostel_student
                    (hostel_id, student_id, school_id, hostel_info_id, room_id, duration,
                     admission_date, discharge_date, room_rent, tax_amount, paid_amount,
                     remaining_amount, status, hostel_types, stud_gender, active)
                VALUES ('New', ?, ?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, 'draft', ?, ?, 1)
                """,
                (
                    student_id,
                    stu["school_id"],
                    hostel_info_id,
                    room_id,
                    duration,
                    d_adm.isoformat(),
                    d_dis.isoformat(),
                    room_rent,
                    tax_amount,
                    remaining,
                    hostel["type"],
                    stu["gender"],
                ),
            )
            hs_id = int(cur.lastrowid)
            self._recompute_room_availability_conn(conn, room_id)
            return hs_id

    def reservation_state(self, hostel_student_id: int) -> str:
        """Confirm reservation (`reservation_state`) and allocate `HST/` sequence."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM hostel_student WHERE id = ?",
                (hostel_student_id,),
            ).fetchone()
            if not row:
                raise NotFoundError(f"Hostel Student {hostel_student_id} not found.")
            code = (
                row["hostel_id"]
                if row["hostel_id"] and row["hostel_id"] != "New"
                else self.db.next_by_code("hostel.student", conn)
            )
            conn.execute(
                "UPDATE hostel_student SET hostel_id = ?, status = 'reservation' WHERE id = ?",
                (code, hostel_student_id),
            )
            self._recompute_room_availability_conn(conn, row["room_id"])
            return code

    def pay_hostel_fees(
        self,
        hostel_student_id: int,
        payment_amount: float | None = None,
    ) -> dict[str, Any]:
        """Pay hostel fees (`pay_fees`) and update `paid_amount`, `remaining_amount`, and `status`."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT * FROM hostel_student WHERE id = ?",
                (hostel_student_id,),
            ).fetchone()
            if not row:
                raise NotFoundError(f"Hostel Student {hostel_student_id} not found.")
            total_due = float(row["room_rent"]) + float(row["tax_amount"])
            already_paid = float(row["paid_amount"])
            pay_now = (
                float(payment_amount)
                if payment_amount is not None
                else max(0.0, total_due - already_paid)
            )
            new_paid = round(already_paid + pay_now, 2)
            new_rem = round(max(0.0, total_due - new_paid), 2)
            new_status = "paid" if new_rem <= 0.0 else "pending"

            conn.execute(
                """
                UPDATE hostel_student
                SET paid_amount = ?, remaining_amount = ?, status = ?
                WHERE id = ?
                """,
                (new_paid, new_rem, new_status, hostel_student_id),
            )
            updated = conn.execute(
                "SELECT * FROM hostel_student WHERE id = ?",
                (hostel_student_id,),
            ).fetchone()
            return dict(updated)

    def discharge_student(
        self,
        hostel_student_id: int,
        actual_discharge_date: str | None = None,
    ) -> None:
        """Discharge student (`discharge_state`) and free room seat."""
        d_act = parse_date(actual_discharge_date or date.today().isoformat(), "Discharge Date")
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT room_id FROM hostel_student WHERE id = ?",
                (hostel_student_id,),
            ).fetchone()
            if not row:
                raise NotFoundError(f"Hostel Student {hostel_student_id} not found.")
            conn.execute(
                """
                UPDATE hostel_student
                SET status = 'discharge', acutal_discharge_date = ?
                WHERE id = ?
                """,
                (d_act.isoformat(), hostel_student_id),
            )
            self._recompute_room_availability_conn(conn, row["room_id"])

    def cancel_hostel_student(self, hostel_student_id: int) -> None:
        """Cancel hostel registration (`cancel_state`) and free room capacity."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT room_id FROM hostel_student WHERE id = ?",
                (hostel_student_id,),
            ).fetchone()
            if not row:
                raise NotFoundError(f"Hostel Student {hostel_student_id} not found.")
            conn.execute(
                "UPDATE hostel_student SET status = 'cancel' WHERE id = ?",
                (hostel_student_id,),
            )
            self._recompute_room_availability_conn(conn, row["room_id"])

    def delete_hostel_student(self, hostel_student_id: int) -> None:
        """Disallow deleting in `reservation`, `pending`, or `paid` status."""
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT status, room_id FROM hostel_student WHERE id = ?",
                (hostel_student_id,),
            ).fetchone()
            if not row:
                raise NotFoundError(f"Hostel Student {hostel_student_id} not found.")
            if row["status"] in ("reservation", "pending", "paid"):
                raise ValidationError(
                    "You can not delete record in Confirmed, Pending or Paid state!"
                )
            conn.execute("DELETE FROM hostel_student WHERE id = ?", (hostel_student_id,))
            self._recompute_room_availability_conn(conn, row["room_id"])

    def list_hostels(self) -> list[dict[str, Any]]:
        return self.db.fetch_all("SELECT * FROM hostel_type ORDER BY name")

    def list_rooms(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT r.*, h.name AS hostel_name, h.type AS hostel_type
            FROM hostel_room r
            JOIN hostel_type h ON h.id = r.hostel_id
            ORDER BY h.name, r.room_no
            """
        )

    def list_hostel_students(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT hs.*, s.student_name, s.pid, h.name AS hostel_name, r.room_no
            FROM hostel_student hs
            JOIN student_student s ON s.id = hs.student_id
            JOIN hostel_type h ON h.id = hs.hostel_info_id
            JOIN hostel_room r ON r.id = hs.room_id
            ORDER BY hs.id DESC
            """
        )


class TransportService:
    """Service layer for `school_transport`."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def create_vehicle(
        self,
        license_plate: str,
        model_name: str,
        driver_name: str = "",
        driver_licence_no: str | None = None,
        seats: int = 30,
    ) -> int:
        if not license_plate or not license_plate.strip():
            raise ValidationError("Vehicle License Plate is required!")
        if seats <= 0:
            raise ValidationError("Vehicle seats must be greater than zero!")

        with self.db.connection() as conn:
            if driver_licence_no and driver_licence_no.strip():
                dup = conn.execute(
                    "SELECT id FROM fleet_vehicle WHERE driver_licence_no = ?",
                    (driver_licence_no.strip(),),
                ).fetchone()
                if dup:
                    raise ValidationError("Driver Licence Number must be unique!")

            cur = conn.execute(
                """
                INSERT INTO fleet_vehicle
                    (license_plate, model_name, driver_name, driver_licence_no, seats)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    license_plate.strip(),
                    model_name.strip(),
                    driver_name.strip(),
                    driver_licence_no.strip() if driver_licence_no else None,
                    seats,
                ),
            )
            return int(cur.lastrowid)

    def _get_vehicle_participant_count_conn(
        self,
        conn: sqlite3.Connection,
        vehicle_id: int,
    ) -> int:
        row = conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM transport_participant
            WHERE vehicle_id = ? AND state != 'over' AND active = 1
            """,
            (vehicle_id,),
        ).fetchone()
        return int(row["cnt"])

    def create_transport_route(
        self,
        name: str,
        start_date: str,
        end_date: str,
        amount: float,
        contact_person: str = "",
        vehicle_ids: list[int] | None = None,
        allow_past_dates: bool = False,
    ) -> int:
        """Create transport route with `_check_transport_date` and 30-day minimum duration checks."""
        if not name or not name.strip():
            raise ValidationError("Transport Route Name is required!")
        d_start = parse_date(start_date, "Start Date")
        d_end = parse_date(end_date, "End Date")

        if not allow_past_dates and d_start < date.today():
            raise ValidationError("Start date should be greater than or equal to current date!")
        if d_start > d_end:
            raise ValidationError("Start date must be less than or equal to end date!")
        if (d_end - d_start).days < 30:
            raise ValidationError(
                "Transport root duration must be greater than or equal to 1 month!"
            )

        with self.db.connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO student_transport
                    (name, start_date, end_date, contact_person, amount, state)
                VALUES (?, ?, ?, ?, ?, 'draft')
                """,
                (name.strip(), d_start.isoformat(), d_end.isoformat(), contact_person, amount),
            )
            route_id = int(cur.lastrowid)
            for vid in vehicle_ids or []:
                conn.execute(
                    "INSERT OR IGNORE INTO transport_vehicle_rel (transport_id, vehicle_id) VALUES (?, ?)",
                    (route_id, vid),
                )
            return route_id

    def transport_open(self, route_id: int) -> None:
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE student_transport SET state = 'open' WHERE id = ?",
                (route_id,),
            )

    def transport_close(self, route_id: int) -> None:
        """Close route and transition all active participants to `over` and `active = False`."""
        with self.db.connection() as conn:
            conn.execute(
                "UPDATE student_transport SET state = 'close' WHERE id = ?",
                (route_id,),
            )
            conn.execute(
                """
                UPDATE transport_participant
                SET state = 'over', active = 0
                WHERE transport_id = ?
                """,
                (route_id,),
            )

    def delete_transport_route(self, route_id: int) -> None:
        with self.db.connection() as conn:
            row = conn.execute(
                "SELECT state FROM student_transport WHERE id = ?",
                (route_id,),
            ).fetchone()
            if not row:
                raise NotFoundError(f"Transport Route {route_id} not found.")
            if row["state"] == "open":
                raise ValidationError("You cannot delete record in open state!")
            conn.execute("DELETE FROM student_transport WHERE id = ?", (route_id,))

    def create_transport_registration(
        self,
        route_id: int,
        student_id: int,
        vehicle_id: int,
        registration_month: int,
        reg_date: str | None = None,
        tax_amount: float = 0.0,
    ) -> int:
        """Create transport registration with `_check_registration_month` and `_check_transport_Order`."""
        if registration_month < 1:
            raise ValidationError("Registration Month must be 1 or more than 1 month!")

        d_reg = parse_date(reg_date or date.today().isoformat(), "Registration Date")
        d_end = d_reg + relativedelta(months=registration_month)

        with self.db.connection() as conn:
            route = conn.execute(
                "SELECT * FROM student_transport WHERE id = ?",
                (route_id,),
            ).fetchone()
            if not route:
                raise NotFoundError(f"Transport Route {route_id} not found.")

            dup = conn.execute(
                """
                SELECT id FROM transport_registration
                WHERE student_id = ? AND name = ? AND reg_date = ?
                  AND state NOT IN ('cancel', 'paid')
                """,
                (student_id, route_id, d_reg.isoformat()),
            ).fetchone()
            if dup:
                raise ValidationError(
                    "Creation of multiple registration for same route on same registration date is not allowed!"
                )

            r_end = parse_date(route["end_date"], "Route End Date")
            if d_end > r_end:
                raise UserError(
                    "Registration end date should not be greater than transport route end date!"
                )

            monthly = float(route["amount"] or 0.0)
            fees = round(monthly * registration_month, 2)
            remain = round(fees + float(tax_amount), 2)

            cur = conn.execute(
                """
                INSERT INTO transport_registration
                    (name, student_id, vehicle_id, reg_date, reg_end_date,
                     registration_month, monthly_amount, transport_fees,
                     paid_amount, tax_amount, remain_amt, state)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0.0, ?, ?, 'draft')
                """,
                (
                    route_id,
                    student_id,
                    vehicle_id,
                    d_reg.isoformat(),
                    d_end.isoformat(),
                    registration_month,
                    monthly,
                    fees,
                    tax_amount,
                    remain,
                ),
            )
            return int(cur.lastrowid)

    def trans_regi_confirm(self, reg_id: int) -> int:
        """Confirm transport registration (`trans_regi_confirm`), checking seat vacancy and creating participant."""
        with self.db.connection() as conn:
            reg = conn.execute(
                "SELECT * FROM transport_registration WHERE id = ?",
                (reg_id,),
            ).fetchone()
            if not reg:
                raise NotFoundError(f"Transport Registration {reg_id} not found.")

            route = conn.execute(
                "SELECT * FROM student_transport WHERE id = ?",
                (reg["name"],),
            ).fetchone()
            if not route or route["state"] != "open":
                raise UserError("First Open Transport Route!")

            veh = conn.execute(
                "SELECT * FROM fleet_vehicle WHERE id = ?",
                (reg["vehicle_id"],),
            ).fetchone()
            if not veh:
                raise NotFoundError(f"Vehicle {reg['vehicle_id']} not found.")

            stu = conn.execute(
                "SELECT * FROM student_student WHERE id = ?",
                (reg["student_id"],),
            ).fetchone()
            if not stu:
                raise NotFoundError(f"Student {reg['student_id']} not found.")

            current_participants = self._get_vehicle_participant_count_conn(conn, veh["id"])
            if current_participants + 1 > int(veh["seats"]):
                raise UserError("There is No More vacancy on this vehicle!")

            if parse_date(reg["reg_end_date"], "Registration End Date") > parse_date(
                route["end_date"], "Route End Date"
            ):
                raise UserError(
                    "Registration end date should not be greater than transport route end date!"
                )

            cur = conn.execute(
                """
                INSERT INTO transport_participant
                    (name, amount, transport_id, stu_pid_id, tr_reg_date,
                     tr_end_date, months, vehicle_id, state, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'running', 1)
                """,
                (
                    stu["id"],
                    reg["transport_fees"],
                    route["id"],
                    stu["pid"],
                    reg["reg_date"],
                    reg["reg_end_date"],
                    reg["registration_month"],
                    veh["id"],
                ),
            )
            part_id = int(cur.lastrowid)
            new_state = "paid" if float(reg["transport_fees"]) <= 0 else "confirm"
            conn.execute(
                "UPDATE transport_registration SET state = ? WHERE id = ?",
                (new_state, reg_id),
            )
            return part_id

    def pay_transport_fees(
        self,
        reg_id: int,
        payment_amount: float | None = None,
    ) -> dict[str, Any]:
        """Process transport fee payment (`transport_fees_pay`)."""
        with self.db.connection() as conn:
            reg = conn.execute(
                "SELECT * FROM transport_registration WHERE id = ?",
                (reg_id,),
            ).fetchone()
            if not reg:
                raise NotFoundError(f"Transport Registration {reg_id} not found.")
            total_due = float(reg["transport_fees"]) + float(reg["tax_amount"])
            already_paid = float(reg["paid_amount"])
            pay_now = (
                float(payment_amount)
                if payment_amount is not None
                else max(0.0, total_due - already_paid)
            )
            new_paid = round(already_paid + pay_now, 2)
            new_rem = round(max(0.0, total_due - new_paid), 2)
            new_state = "paid" if new_rem <= 0.0 else "pending"

            conn.execute(
                """
                UPDATE transport_registration
                SET paid_amount = ?, remain_amt = ?, state = ?
                WHERE id = ?
                """,
                (new_paid, new_rem, new_state, reg_id),
            )
            updated = conn.execute(
                "SELECT * FROM transport_registration WHERE id = ?",
                (reg_id,),
            ).fetchone()
            return dict(updated)

    def delete_transport_registration(self, reg_id: int) -> None:
        with self.db.connection() as conn:
            reg = conn.execute(
                "SELECT state FROM transport_registration WHERE id = ?",
                (reg_id,),
            ).fetchone()
            if not reg:
                raise NotFoundError(f"Transport Registration {reg_id} not found.")
            if reg["state"] in ("confirm", "pending", "paid"):
                raise ValidationError(
                    "You cannot delete record in Confirm, Pending or Paid state!"
                )
            conn.execute("DELETE FROM transport_registration WHERE id = ?", (reg_id,))

    def transfer_vehicle(self, participant_id: int, new_vehicle_id: int) -> dict[str, Any]:
        """Wizard `transfer.vehicle`: move participant to a new vehicle after checking capacity."""
        with self.db.connection() as conn:
            part = conn.execute(
                "SELECT * FROM transport_participant WHERE id = ?",
                (participant_id,),
            ).fetchone()
            if not part:
                raise NotFoundError(f"Transport Participant {participant_id} not found.")

            if int(part["vehicle_id"]) == int(new_vehicle_id):
                raise UserError("Sorry you can not transfer in same vehicle.")

            new_veh = conn.execute(
                "SELECT * FROM fleet_vehicle WHERE id = ?",
                (new_vehicle_id,),
            ).fetchone()
            if not new_veh:
                raise NotFoundError(f"Vehicle {new_vehicle_id} not found.")

            cnt = self._get_vehicle_participant_count_conn(conn, new_vehicle_id)
            if cnt + 1 > int(new_veh["seats"]):
                raise UserError("There is No More vacancy on this vehicle!")

            conn.execute(
                "UPDATE transport_participant SET vehicle_id = ? WHERE id = ?",
                (new_vehicle_id, participant_id),
            )
            updated = conn.execute(
                "SELECT * FROM transport_participant WHERE id = ?",
                (participant_id,),
            ).fetchone()
            return dict(updated)

    def list_vehicles(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT v.*,
                   (SELECT COUNT(*) FROM transport_participant tp
                    WHERE tp.vehicle_id = v.id AND tp.state != 'over' AND tp.active = 1) AS participant_count
            FROM fleet_vehicle v
            ORDER BY v.license_plate
            """
        )

    def list_routes(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT r.*,
                   (SELECT COUNT(*) FROM transport_participant tp
                    WHERE tp.transport_id = r.id AND tp.state != 'over' AND tp.active = 1) AS active_participants
            FROM student_transport r
            ORDER BY r.id DESC
            """
        )

    def list_registrations(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT tr.*, r.name AS route_name, s.student_name, s.pid,
                   v.license_plate, v.model_name
            FROM transport_registration tr
            JOIN student_transport r ON r.id = tr.name
            JOIN student_student s ON s.id = tr.student_id
            JOIN fleet_vehicle v ON v.id = tr.vehicle_id
            ORDER BY tr.id DESC
            """
        )

    def list_participants(self) -> list[dict[str, Any]]:
        return self.db.fetch_all(
            """
            SELECT tp.*, s.student_name, r.name AS route_name,
                   v.license_plate, v.model_name
            FROM transport_participant tp
            JOIN student_student s ON s.id = tp.name
            JOIN student_transport r ON r.id = tp.transport_id
            JOIN fleet_vehicle v ON v.id = tp.vehicle_id
            WHERE tp.active = 1
            ORDER BY tp.id DESC
            """
        )

