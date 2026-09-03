from datetime import date, datetime, timedelta

from flask import current_app

from models.database import execute, query_all, query_one, transactional
from services.analytics_service import log_event
from services.fines_service import create_fine_from_checkout, get_unpaid_balance, update_overdue_status
from services.inventory_service import update_copy_status
from services.reservation_service import advance_queue_on_return
from services.notification_service import notify_patron
from services.verification_service import verify_user_eligibility


def get_active_loan_count(user_id):
    return query_one(
        "SELECT COUNT(*) AS c FROM transactions WHERE user_id = %s AND status IN ('active', 'overdue')",
        (user_id,),
    )["c"]


@transactional
def checkout(user_id, copy_barcode, staff_id=None):
    eligible, result = verify_user_eligibility(user_id)
    if not eligible:
        return False, result

    # Serialize loan-limit checks for the patron in this transaction.
    query_one("SELECT id FROM users WHERE id = %s FOR UPDATE", (user_id,))

    if get_unpaid_balance(user_id) > 0:
        return False, "Cannot borrow with unpaid fines."

    max_loans = current_app.config["MAX_ACTIVE_LOANS"]
    if get_active_loan_count(user_id) >= max_loans:
        return False, f"Lending limit of {max_loans} books reached."

    copy = query_one(
        """SELECT c.*, b.title FROM copies c JOIN books b ON b.id = c.book_id
           WHERE c.barcode = %s FOR UPDATE""",
        (copy_barcode,),
    )
    if not copy:
        return False, "Copy not found."
    if copy["status"] != "available":
        return False, f"Copy is currently {copy['status']}."

    loan_days = current_app.config["LOAN_PERIOD_DAYS"]
    due_date = date.today() + timedelta(days=loan_days)

    tx_id = execute(
        """INSERT INTO transactions (user_id, copy_id, due_date, status)
           VALUES (%s, %s, %s, 'active')""",
        (user_id, copy["id"], due_date),
    )[0]

    update_copy_status(copy["id"], "borrowed")
    create_fine_from_checkout(tx_id, user_id, due_date)

    log_event(
        "checkout",
        user_id=user_id,
        entity_type="transaction",
        entity_id=tx_id,
        metadata={"copy_barcode": copy_barcode, "staff_id": staff_id},
    )
    notify_patron(
        user_id,
        "Book checked out",
        f'"{copy["title"]}" is due on {due_date}.',
        "success",
        "/borrowing/",
    )
    return True, {"transaction_id": tx_id, "due_date": str(due_date), "title": copy["title"]}


@transactional
def checkin(copy_barcode, staff_id=None):
    copy = query_one("SELECT * FROM copies WHERE barcode = %s FOR UPDATE", (copy_barcode,))
    if not copy:
        return False, "Copy not found."

    tx = query_one(
        """SELECT * FROM transactions WHERE copy_id = %s AND status IN ('active', 'overdue')
           ORDER BY id DESC LIMIT 1""",
        (copy["id"],),
    )
    if not tx:
        return False, "No active loan for this copy."

    execute(
        "UPDATE transactions SET return_date = %s, status = 'returned' WHERE id = %s",
        (datetime.now(), tx["id"]),
    )
    update_copy_status(copy["id"], "available")
    update_overdue_status(tx["user_id"])
    advance_queue_on_return(copy["book_id"])

    log_event(
        "checkin",
        user_id=tx["user_id"],
        entity_type="transaction",
        entity_id=tx["id"],
        metadata={"copy_barcode": copy_barcode, "staff_id": staff_id},
    )
    notify_patron(tx["user_id"], "Book returned", "Your borrowed item has been checked in.", "success", "/borrowing/")
    return True, {"transaction_id": tx["id"]}


@transactional
def renew(transaction_id, user_id):
    tx = query_one(
        "SELECT * FROM transactions WHERE id = %s AND user_id = %s AND status IN ('active', 'overdue')",
        (transaction_id, user_id),
    )
    if not tx:
        return False, "Active loan not found."
    if tx["renewal_count"] >= 2:
        return False, "Maximum renewals reached."

    loan_days = current_app.config["LOAN_PERIOD_DAYS"]
    new_due = date.today() + timedelta(days=loan_days)
    execute(
        "UPDATE transactions SET due_date = %s, renewal_count = renewal_count + 1, status = 'active' WHERE id = %s",
        (new_due, transaction_id),
    )
    log_event("renewal", user_id=user_id, entity_type="transaction", entity_id=transaction_id)
    notify_patron(user_id, "Loan renewed", f"New due date: {new_due}", "info", "/borrowing/")
    return True, {"due_date": str(new_due)}


def list_transactions(user_id=None, status=None, page=None, per_page=10):
    where = " WHERE 1=1"
    params = []
    if user_id:
        where += " AND t.user_id = %s"
        params.append(user_id)
    if status:
        where += " AND t.status = %s"
        params.append(status)

    if page is not None:
        total = query_one(
            f"""SELECT COUNT(*) AS c
                FROM transactions t
                JOIN users u ON u.id = t.user_id
                JOIN copies c ON c.id = t.copy_id
                JOIN books b ON b.id = c.book_id{where}""",
            params,
        )["c"]
        from services.pagination import sql_page_clause

        limit_sql, limit_params = sql_page_clause(page, per_page)
        sql = f"""
            SELECT t.*, u.full_name, u.library_id, b.title, c.barcode
            FROM transactions t
            JOIN users u ON u.id = t.user_id
            JOIN copies c ON c.id = t.copy_id
            JOIN books b ON b.id = c.book_id{where}
            ORDER BY t.checkout_date DESC{limit_sql}
        """
        return query_all(sql, params + limit_params), total

    sql = f"""
        SELECT t.*, u.full_name, u.library_id, b.title, c.barcode
        FROM transactions t
        JOIN users u ON u.id = t.user_id
        JOIN copies c ON c.id = t.copy_id
        JOIN books b ON b.id = c.book_id{where}
        ORDER BY t.checkout_date DESC
    """
    return query_all(sql, params)
