from datetime import datetime

from models.database import execute, query_all, query_one, transactional
from services.analytics_service import log_event
from services.fines_service import get_unpaid_balance
from services.notification_service import notify_patron, notify_staff
from services.verification_service import verify_user_eligibility


def run_clearance_audit(user_id):
    eligible, result = verify_user_eligibility(user_id)
    if not eligible:
        return {
            "cleared": False,
            "blocked_reason": result,
            "active_loans": 0,
            "pending_holds": 0,
            "unpaid_fines": 0,
        }

    active_loans = query_one(
        "SELECT COUNT(*) AS c FROM transactions WHERE user_id = %s AND status IN ('active', 'overdue')",
        (user_id,),
    )["c"]

    pending_holds = query_one(
        "SELECT COUNT(*) AS c FROM reservations WHERE user_id = %s AND status IN ('pending', 'ready')",
        (user_id,),
    )["c"]

    unpaid = get_unpaid_balance(user_id)

    cleared = active_loans == 0 and pending_holds == 0 and unpaid == 0
    return {
        "cleared": cleared,
        "active_loans": active_loans,
        "pending_holds": pending_holds,
        "unpaid_fines": unpaid,
        "blocked_reason": None if cleared else "Outstanding obligations found.",
    }


@transactional
def request_clearance(user_id):
    audit = run_clearance_audit(user_id)
    status = "cleared" if audit["cleared"] else "blocked"
    req_id = execute(
        """INSERT INTO clearance_requests
           (user_id, status, checked_loans, checked_fines, checked_holds, cleared_at, notes)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            user_id,
            status,
            1,
            1,
            1,
            datetime.now() if audit["cleared"] else None,
            audit.get("blocked_reason"),
        ),
    )[0]
    log_event("clearance_requested", user_id=user_id, entity_type="clearance", entity_id=req_id)
    if audit["cleared"]:
        notify_patron(user_id, "Clearance granted", "You have no outstanding library obligations.", "success", "/clearance/")
    else:
        notify_patron(user_id, "Clearance blocked", audit.get("blocked_reason", "Outstanding items found."), "danger", "/clearance/")
    notify_staff("Clearance request", f"User #{user_id} clearance: {status}", "info", "/clearance/")
    audit["request_id"] = req_id
    audit["status"] = status
    return audit


def list_clearance_requests(page=None, per_page=10):
    if page is not None:
        total = query_one("SELECT COUNT(*) AS c FROM clearance_requests")["c"]
        from services.pagination import sql_page_clause

        limit_sql, limit_params = sql_page_clause(page, per_page)
        return (
            query_all(
                f"""SELECT cr.*, u.full_name, u.library_id
                    FROM clearance_requests cr
                    JOIN users u ON u.id = cr.user_id
                    ORDER BY cr.requested_at DESC{limit_sql}""",
                limit_params,
            ),
            total,
        )

    return query_all(
        """SELECT cr.*, u.full_name, u.library_id
           FROM clearance_requests cr
           JOIN users u ON u.id = cr.user_id
           ORDER BY cr.requested_at DESC"""
    )


def get_clearance_stats():
    return {
        "total": query_one("SELECT COUNT(*) AS c FROM clearance_requests")["c"],
        "cleared": query_one(
            "SELECT COUNT(*) AS c FROM clearance_requests WHERE status = 'cleared'"
        )["c"],
        "blocked": query_one(
            "SELECT COUNT(*) AS c FROM clearance_requests WHERE status = 'blocked'"
        )["c"],
    }
