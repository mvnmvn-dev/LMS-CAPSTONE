from datetime import datetime, timedelta

from flask import current_app

from models.database import execute, query_all, query_one, transactional
from services.analytics_service import log_event
from services.fines_service import can_use_services, get_unpaid_balance
from services.inventory_service import get_availability, update_copy_status
from services.notification_service import notify_patron
from services.verification_service import verify_user_eligibility


def _next_queue_position(book_id):
    # Lock the parent book row so concurrent reservations for this book cannot
    # compute the same next position.
    query_one("SELECT id FROM books WHERE id = %s FOR UPDATE", (book_id,))
    row = query_one(
        "SELECT COALESCE(MAX(queue_position), 0) + 1 AS pos FROM reservations WHERE book_id = %s AND status = 'pending'",
        (book_id,),
    )
    return row["pos"]


@transactional
def place_hold(user_id, book_id):
    eligible, result = verify_user_eligibility(user_id)
    if not eligible:
        return False, result
    if not can_use_services(user_id):
        return False, "Cannot reserve with unpaid fines."

    existing = query_one(
        """SELECT id FROM reservations
           WHERE user_id = %s AND book_id = %s AND status IN ('pending', 'ready')""",
        (user_id, book_id),
    )
    if existing:
        return False, "You already have a reservation for this book."

    avail = get_availability(book_id)
    if avail["in_stock"]:
        return False, "Book is currently available. Please borrow directly."

    pos = _next_queue_position(book_id)
    res_id = execute(
        """INSERT INTO reservations (user_id, book_id, queue_position, status)
           VALUES (%s, %s, %s, 'pending')""",
        (user_id, book_id, pos),
    )[0]
    log_event("reservation_placed", user_id=user_id, entity_type="reservation", entity_id=res_id)
    book = query_one("SELECT title FROM books WHERE id = %s", (book_id,))
    notify_patron(user_id, "Reservation placed", f'You are #{pos} in queue for "{book["title"]}".', "info", "/reservations/")
    return True, {"reservation_id": res_id, "queue_position": pos}


def advance_queue_on_return(book_id):
    pending = query_one(
        """SELECT * FROM reservations WHERE book_id = %s AND status = 'pending'
           ORDER BY queue_position ASC LIMIT 1""",
        (book_id,),
    )
    if not pending:
        return

    hold_days = current_app.config["RESERVATION_HOLD_DAYS"]
    expires = datetime.now() + timedelta(days=hold_days)
    execute(
        """UPDATE reservations SET status = 'ready', ready_at = %s, expires_at = %s
           WHERE id = %s""",
        (datetime.now(), expires, pending["id"]),
    )

    copy = query_one(
        "SELECT id FROM copies WHERE book_id = %s AND status = 'available' LIMIT 1",
        (book_id,),
    )
    if copy:
        update_copy_status(copy["id"], "reserved")

    log_event(
        "reservation_ready",
        user_id=pending["user_id"],
        entity_type="reservation",
        entity_id=pending["id"],
    )
    book = query_one("SELECT title FROM books WHERE id = %s", (book_id,))
    notify_patron(
        pending["user_id"],
        "Reservation ready!",
        f'"{book["title"]}" is ready for pickup. Expires {expires.strftime("%b %d")}.',
        "success",
        "/reservations/",
    )


def list_reservations(user_id=None, page=None, per_page=10):
    where = " WHERE r.status IN ('pending', 'ready')"
    params = []
    if user_id:
        where += " AND r.user_id = %s"
        params.append(user_id)

    if page is not None:
        total = query_one(
            f"""SELECT COUNT(*) AS c
                FROM reservations r
                JOIN books b ON b.id = r.book_id
                JOIN users u ON u.id = r.user_id{where}""",
            params,
        )["c"]
        from services.pagination import sql_page_clause

        limit_sql, limit_params = sql_page_clause(page, per_page)
        sql = f"""
            SELECT r.*, b.title, u.full_name, u.library_id
            FROM reservations r
            JOIN books b ON b.id = r.book_id
            JOIN users u ON u.id = r.user_id{where}
            ORDER BY r.created_at DESC{limit_sql}
        """
        return query_all(sql, params + limit_params), total

    sql = f"""
        SELECT r.*, b.title, u.full_name, u.library_id
        FROM reservations r
        JOIN books b ON b.id = r.book_id
        JOIN users u ON u.id = r.user_id{where}
        ORDER BY r.created_at DESC
    """
    return query_all(sql, params)


def cancel_reservation(reservation_id, user_id=None):
    res = query_one("SELECT * FROM reservations WHERE id = %s", (reservation_id,))
    if not res:
        return False, "Reservation not found."
    if user_id and res["user_id"] != user_id:
        return False, "Not authorized."
    execute(
        "UPDATE reservations SET status = 'cancelled' WHERE id = %s",
        (reservation_id,),
    )
    log_event("reservation_cancelled", user_id=res["user_id"], entity_type="reservation", entity_id=reservation_id)
    return True, "Reservation cancelled."


@transactional
def fulfill_reservation(reservation_id):
    res = query_one("SELECT * FROM reservations WHERE status = 'ready' AND id = %s", (reservation_id,))
    if not res:
        return False, "Ready reservation not found."
    execute("UPDATE reservations SET status = 'fulfilled' WHERE id = %s", (reservation_id,))
    return True, "Reservation marked fulfilled."
