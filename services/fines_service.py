from datetime import date, datetime, timedelta

from flask import current_app

from models.database import execute, query_all, query_one, transactional
from services.analytics_service import log_event
from services.notification_service import notify_patron


def get_unpaid_balance(user_id):
    row = query_one(
        "SELECT COALESCE(SUM(amount), 0) AS total FROM fines WHERE user_id = %s AND status = 'unpaid'",
        (user_id,),
    )
    return float(row["total"])


def create_fine_from_checkout(transaction_id, user_id, due_date):
    log_event(
        "due_date_set",
        user_id=user_id,
        entity_type="transaction",
        entity_id=transaction_id,
        metadata={"due_date": str(due_date)},
    )


def update_overdue_status(user_id=None):
    today = date.today()
    fine_rate = current_app.config["FINE_PER_DAY"]

    sql = "SELECT * FROM transactions WHERE status IN ('active', 'overdue') AND due_date < %s"
    params = [today]
    if user_id:
        sql += " AND user_id = %s"
        params.append(user_id)

    overdue = query_all(sql, params)
    for tx in overdue:
        execute("UPDATE transactions SET status = 'overdue' WHERE id = %s", (tx["id"],))
        days_overdue = (today - tx["due_date"]).days
        amount = round(days_overdue * fine_rate, 2)
        existing = query_one(
            "SELECT id FROM fines WHERE transaction_id = %s AND status = 'unpaid'",
            (tx["id"],),
        )
        if existing:
            execute("UPDATE fines SET amount = %s WHERE id = %s", (amount, existing["id"]))
        else:
            execute(
                """INSERT INTO fines (user_id, transaction_id, amount, reason, status)
                   VALUES (%s, %s, %s, %s, 'unpaid')""",
                (tx["user_id"], tx["id"], amount, f"Overdue fine ({days_overdue} days)"),
            )
            notify_patron(
                tx["user_id"],
                "Overdue fine assessed",
                f"₱{amount:.2f} fine for overdue book. Please settle to continue borrowing.",
                "danger",
                "/fines/",
            )


def list_fines(user_id=None, status=None, page=None, per_page=10):
    where = " WHERE 1=1"
    params = []
    if user_id:
        where += " AND f.user_id = %s"
        params.append(user_id)
    if status:
        where += " AND f.status = %s"
        params.append(status)

    if page is not None:
        total = query_one(
            f"""SELECT COUNT(*) AS c
                FROM fines f
                JOIN users u ON u.id = f.user_id{where}""",
            params,
        )["c"]
        from services.pagination import sql_page_clause

        limit_sql, limit_params = sql_page_clause(page, per_page)
        sql = f"""
            SELECT f.*, u.full_name, u.library_id
            FROM fines f
            JOIN users u ON u.id = f.user_id{where}
            ORDER BY f.created_at DESC{limit_sql}
        """
        return query_all(sql, params + limit_params), total

    sql = f"""
        SELECT f.*, u.full_name, u.library_id
        FROM fines f
        JOIN users u ON u.id = f.user_id{where}
        ORDER BY f.created_at DESC
    """
    return query_all(sql, params)


@transactional
def record_payment(fine_id, staff_id=None):
    fine = query_one("SELECT * FROM fines WHERE id = %s", (fine_id,))
    if not fine:
        return False, "Fine not found."
    if fine["status"] == "paid":
        return False, "Fine already paid."

    execute(
        "UPDATE fines SET status = 'paid', paid_at = %s WHERE id = %s",
        (datetime.now(), fine_id),
    )
    log_event(
        "fine_paid",
        user_id=fine["user_id"],
        entity_type="fine",
        entity_id=fine_id,
        metadata={"staff_id": staff_id, "amount": float(fine["amount"])},
    )
    notify_patron(fine["user_id"], "Payment recorded", f"₱{float(fine['amount']):.2f} fine payment received.", "success", "/fines/")
    return True, "Payment recorded."


def create_replacement_fine(user_id, amount, reason, report_id=None):
    fine_id = execute(
        """INSERT INTO fines (user_id, report_id, amount, reason, status)
           VALUES (%s, %s, %s, %s, 'unpaid')""",
        (user_id, report_id, amount, reason),
    )[0]
    log_event("replacement_fine", user_id=user_id, entity_type="fine", entity_id=fine_id)
    notify_patron(user_id, "Replacement fine", f"₱{amount:.2f} — {reason}", "warning", "/fines/")
    return fine_id


def can_use_services(user_id):
    return get_unpaid_balance(user_id) <= 0


@transactional
def waive_fine(fine_id, staff_id, reason):
    fine = query_one("SELECT * FROM fines WHERE id = %s", (fine_id,))
    if not fine:
        return False, "Fine not found."
    if fine["status"] != "unpaid":
        return False, "Only unpaid fines can be waived."

    execute(
        "UPDATE fines SET status = 'waived', paid_at = %s WHERE id = %s",
        (datetime.now(), fine_id),
    )
    log_event(
        "fine_waived",
        user_id=staff_id,
        entity_type="fine",
        entity_id=fine_id,
        metadata={
            "patron_id": fine["user_id"],
            "amount": float(fine["amount"]),
            "reason": reason,
        },
    )
    notify_patron(
        fine["user_id"],
        "Fine waived",
        f"₱{float(fine['amount']):.2f} fine waived — {reason}",
        "success",
        "/fines/",
    )
    return True, "Fine waived."
