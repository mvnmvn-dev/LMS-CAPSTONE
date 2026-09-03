from datetime import date, timedelta

from models.database import query_all, query_one


def get_due_soon_loans(user_id, limit=3):
    return query_all(
        """SELECT t.id, t.due_date, t.status, b.title, c.barcode
           FROM transactions t
           JOIN copies c ON c.id = t.copy_id
           JOIN books b ON b.id = c.book_id
           WHERE t.user_id = %s AND t.status IN ('active', 'overdue')
           ORDER BY t.due_date ASC
           LIMIT %s""",
        (user_id, limit),
    )


def enrich_due_urgency(tx):
    if not tx.get("due_date") or tx.get("status") not in ("active", "overdue"):
        tx["due_urgency"] = None
        tx["days_remaining"] = None
        return tx

    due = tx["due_date"]
    if not isinstance(due, date):
        due = date.fromisoformat(str(due))
    days = (due - date.today()).days
    tx["days_remaining"] = days

    if tx["status"] == "overdue" or days < 0:
        tx["due_urgency"] = "overdue"
    elif days <= 2:
        tx["due_urgency"] = "soon"
    elif days <= 7:
        tx["due_urgency"] = "warning"
    else:
        tx["due_urgency"] = "ok"
    return tx


def enrich_transactions(transactions):
    return [enrich_due_urgency(dict(tx)) for tx in transactions]


def get_continue_reading(user_id):
    try:
        return query_one(
            """SELECT rp.*, ea.expires_at, e.format, b.title, b.id AS book_id, ea.id AS access_id
               FROM reading_progress rp
               JOIN ebook_access ea ON ea.id = rp.ebook_access_id
               JOIN ebooks e ON e.id = ea.ebook_id
               JOIN books b ON b.id = e.book_id
               WHERE rp.user_id = %s AND ea.expires_at > NOW() AND rp.progress_pct < 100
               ORDER BY rp.last_opened_at DESC
               LIMIT 1""",
            (user_id,),
        )
    except Exception:
        return None


def get_trending_books(limit=5):
    return query_all(
        """SELECT b.id, b.title, b.genre, b.cover_url, b.isbn, COUNT(t.id) AS borrow_count
           FROM books b
           JOIN copies c ON c.book_id = b.id
           JOIN transactions t ON t.copy_id = c.id
           GROUP BY b.id, b.title, b.genre, b.cover_url, b.isbn
           ORDER BY borrow_count DESC
           LIMIT %s""",
        (limit,),
    )


def get_recently_viewed_books(user_id, limit=5):
    return query_all(
        """SELECT b.id, b.title, b.genre, b.cover_url, b.isbn, MAX(al.created_at) AS viewed_at
           FROM analytics_log al
           JOIN books b ON b.id = al.entity_id
           WHERE al.user_id = %s AND al.event_type = 'book_viewed' AND al.entity_type = 'book'
           GROUP BY b.id, b.title, b.genre, b.cover_url, b.isbn
           ORDER BY viewed_at DESC
           LIMIT %s""",
        (user_id, limit),
    )


def get_fine_stats(user_id):
    unpaid = float(
        query_one(
            "SELECT COALESCE(SUM(amount), 0) AS t FROM fines WHERE user_id = %s AND status = 'unpaid'",
            (user_id,),
        )["t"]
    )
    semester_start = date.today().replace(day=1)
    if date.today().month <= 6:
        semester_start = date(date.today().year, 1, 1)
    else:
        semester_start = date(date.today().year, 7, 1)

    paid_semester = float(
        query_one(
            """SELECT COALESCE(SUM(amount), 0) AS t FROM fines
               WHERE user_id = %s AND status = 'paid' AND paid_at >= %s""",
            (user_id, semester_start),
        )["t"]
    )

    on_time_returns = query_one(
        """SELECT COUNT(*) AS c FROM transactions
           WHERE user_id = %s AND status = 'returned' AND return_date <= due_date""",
        (user_id,),
    )["c"]

    return {
        "unpaid": unpaid,
        "paid_semester": paid_semester,
        "on_time_returns": on_time_returns,
    }


def parse_fine_breakdown(reason, amount):
    days = None
    rate = 10.0
    if reason and "days" in reason.lower():
        import re
        m = re.search(r"(\d+)\s*days?", reason, re.I)
        if m:
            days = int(m.group(1))
            if days:
                rate = round(float(amount) / days, 2)
    return {"days": days, "rate": rate, "amount": float(amount)}


def get_card_status_info(user_row):
    status = user_row.get("card_status", "inactive")
    expiry = user_row.get("card_expiry")
    if status != "active":
        return {
            "level": "danger",
            "label": status.replace("_", " ").title(),
            "message": f"Card is {status}",
        }
    if expiry:
        if not isinstance(expiry, date):
            expiry = date.fromisoformat(str(expiry))
        days = (expiry - date.today()).days
        if days < 0:
            return {"level": "danger", "label": "Expired", "message": f"Expired on {expiry}"}
        if days <= 14:
            return {
                "level": "warning",
                "label": f"Expiring in {days} day{'s' if days != 1 else ''}",
                "message": f"Renew before {expiry}",
            }
    return {"level": "success", "label": "Active", "message": "Card is valid for borrowing"}


def get_reservation_eta(book_id):
    row = query_one(
        """SELECT MIN(t.due_date) AS earliest_due
           FROM transactions t
           JOIN copies c ON c.id = t.copy_id
           WHERE c.book_id = %s AND t.status IN ('active', 'overdue')""",
        (book_id,),
    )
    return row["earliest_due"] if row else None


def enrich_reservations(reservations):
    enriched = []
    for res in reservations:
        r = dict(res)
        eta = get_reservation_eta(res["book_id"])
        r["eta_date"] = eta
        if eta and hasattr(eta, "strftime"):
            r["eta_display"] = eta.strftime("%b %d, %Y")
        elif eta:
            r["eta_display"] = str(eta)
        else:
            r["eta_display"] = None
        r["queue_label"] = f"You are #{res['queue_position']} in line"
        enriched.append(r)
    return enriched
