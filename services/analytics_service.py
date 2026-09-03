import json
from datetime import date, datetime

from models.database import execute, query_all, query_one


def log_event(event_type, user_id=None, entity_type=None, entity_id=None, metadata=None):
    execute(
        """INSERT INTO analytics_log (event_type, user_id, entity_type, entity_id, metadata)
           VALUES (%s, %s, %s, %s, %s)""",
        (
            event_type,
            user_id,
            entity_type,
            entity_id,
            json.dumps(metadata or {}),
        ),
    )


def _system_totals():
    row = query_one("""
        SELECT
            (SELECT COUNT(*) FROM books) AS total_books,
            (SELECT COUNT(*) FROM copies) AS total_copies,
            (SELECT COUNT(*) FROM copies WHERE status = 'available') AS available_copies,
            (SELECT COUNT(*) FROM transactions WHERE status IN ('active', 'overdue')) AS active_loans,
            (SELECT COUNT(*) FROM reservations WHERE status IN ('pending', 'ready')) AS pending_reservations,
            (SELECT COALESCE(SUM(amount), 0) FROM fines WHERE status = 'unpaid') AS unpaid_fines_total,
            (SELECT COUNT(*) FROM transactions WHERE status = 'overdue') AS overdue_loans,
            (SELECT COUNT(*) FROM users) AS registered_users
    """)
    row["unpaid_fines_total"] = float(row["unpaid_fines_total"] or 0)
    return row


def _patron_stats(user_id):
    row = query_one("""
        SELECT
            (SELECT COUNT(*) FROM transactions WHERE user_id = %s AND status IN ('active', 'overdue')) AS my_active_loans,
            (SELECT COUNT(*) FROM transactions WHERE user_id = %s AND status = 'overdue') AS my_overdue_loans,
            (SELECT COUNT(*) FROM reservations WHERE user_id = %s AND status IN ('pending', 'ready')) AS my_reservations,
            (SELECT COALESCE(SUM(amount), 0) FROM fines WHERE user_id = %s AND status = 'unpaid') AS my_unpaid_fines,
            (SELECT COUNT(*) FROM transactions WHERE user_id = %s) AS my_total_borrows,
            (SELECT COUNT(*) FROM ebook_access WHERE user_id = %s AND expires_at > NOW()) AS my_ebooks
    """, (user_id,) * 6)
    row["my_unpaid_fines"] = float(row["my_unpaid_fines"] or 0)
    return row


def _kpi_cards_for_role(role, user_id, stats):
    if role == "patron":
        return [
            {
                "label": "My Active Loans",
                "value": stats["my_active_loans"],
                "count": stats["my_active_loans"],
                "theme": "amber",
                "icon": "fa-right-left",
            },
            {
                "label": "My Reservations",
                "value": stats["my_reservations"],
                "count": stats["my_reservations"],
                "theme": "indigo",
                "icon": "fa-bookmark",
            },
            {
                "label": "Unpaid Fines",
                "value": stats["my_unpaid_fines"],
                "count": stats["my_unpaid_fines"],
                "theme": "red",
                "format": "currency",
                "icon": "fa-coins",
            },
            {
                "label": "Overdue Items",
                "value": stats["my_overdue_loans"],
                "count": stats["my_overdue_loans"],
                "theme": "red",
                "icon": "fa-exclamation-circle",
            },
        ]

    cards = [
        {
            "label": "Active Loans",
            "value": stats["active_loans"],
            "count": stats["active_loans"],
            "theme": "amber",
            "icon": "fa-right-left",
            "hint": "Library-wide",
        },
        {
            "label": "Pending Holds",
            "value": stats["pending_reservations"],
            "count": stats["pending_reservations"],
            "theme": "indigo",
            "icon": "fa-bookmark",
            "hint": "Library-wide",
        },
        {
            "label": "Overdue Loans",
            "value": stats["overdue_loans"],
            "count": stats["overdue_loans"],
            "theme": "red",
            "icon": "fa-exclamation-circle",
            "hint": "Library-wide",
        },
        {
            "label": "Available Copies",
            "value": stats["available_copies"],
            "count": stats["available_copies"],
            "theme": "emerald",
            "icon": "fa-check-circle",
            "hint": "Library-wide",
        },
    ]
    if role == "admin":
        cards[3] = {
            "label": "Registered Users",
            "value": stats["registered_users"],
            "count": stats["registered_users"],
            "theme": "emerald",
            "icon": "fa-users",
            "hint": "All accounts",
        }
    return cards


def get_dashboard_stats(user_id=None, role="patron"):
    if role == "patron" and not user_id:
        role = "staff"
    # Patrons only consume personal KPIs; avoid eight system-wide scans for
    # every student dashboard request.
    stats = _system_totals() if role != "patron" else {}
    stats["role"] = role
    stats["scope"] = "personal" if role == "patron" else "system"

    if role == "patron" and user_id:
        stats.update(_patron_stats(user_id))
        stats["kpi_cards"] = _kpi_cards_for_role(role, user_id, stats)
        stats["most_borrowed"] = query_all(
            """SELECT b.title, COUNT(t.id) AS borrow_count
               FROM transactions t
               JOIN copies c ON c.id = t.copy_id
               JOIN books b ON b.id = c.book_id
               WHERE t.user_id = %s
               GROUP BY b.id, b.title
               ORDER BY borrow_count DESC
               LIMIT 5""",
            (user_id,),
        )
        stats["recent_activity"] = query_all(
            """SELECT event_type, entity_type, created_at, metadata
               FROM analytics_log
               WHERE user_id = %s
               ORDER BY created_at DESC
               LIMIT 10""",
            (user_id,),
        )
        stats["my_loans"] = query_all(
            """SELECT t.id, t.status, t.due_date, b.title
               FROM transactions t
               JOIN copies c ON c.id = t.copy_id
               JOIN books b ON b.id = c.book_id
               WHERE t.user_id = %s AND t.status IN ('active', 'overdue')
               ORDER BY t.due_date ASC
               LIMIT 5""",
            (user_id,),
        )
    else:
        stats["kpi_cards"] = _kpi_cards_for_role(role, user_id, stats)
        stats["most_borrowed"] = query_all(
            """SELECT b.title, COUNT(t.id) AS borrow_count
               FROM transactions t
               JOIN copies c ON c.id = t.copy_id
               JOIN books b ON b.id = c.book_id
               GROUP BY b.id, b.title
               ORDER BY borrow_count DESC
               LIMIT 5"""
        )
        if user_id:
            stats["recent_activity"] = query_all(
                """SELECT event_type, entity_type, created_at, metadata
                   FROM analytics_log
                   WHERE user_id = %s
                   ORDER BY created_at DESC
                   LIMIT 10""",
                (user_id,),
            )
            stats["staff_actions_today"] = query_one(
                """SELECT COUNT(*) AS c FROM analytics_log
                   WHERE user_id = %s AND DATE(created_at) = CURDATE()""",
                (user_id,),
            )["c"]
        else:
            stats["recent_activity"] = []
            stats["staff_actions_today"] = 0

    return stats


def get_dashboard_reminder(role, user_id, stats):
    if role == "patron":
        parts = []
        if stats.get("my_overdue_loans", 0) > 0:
            parts.append(
                f"You have {stats['my_overdue_loans']} overdue item(s). Return them soon to avoid additional fines."
            )
        if stats.get("my_unpaid_fines", 0) > 0:
            parts.append(f"Outstanding balance: ₱{stats['my_unpaid_fines']:.2f}.")
        if stats.get("my_reservations", 0) > 0:
            parts.append(f"You have {stats['my_reservations']} active reservation(s) waiting.")
        if parts:
            return " ".join(parts)
        return "You're all caught up! Browse the catalog or check your borrowing history below."

    if role == "admin":
        return (
            f"Library overview: {stats['active_loans']} active loans, "
            f"{stats['overdue_loans']} overdue, and {stats['registered_users']} registered users."
        )
    return (
        f"Operations snapshot: {stats['active_loans']} active loans, "
        f"{stats['pending_reservations']} pending holds, and {stats['overdue_loans']} overdue items system-wide."
    )
