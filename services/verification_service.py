from datetime import date, timedelta

from flask import current_app

from models.database import execute, query_all, query_one
from services.analytics_service import log_event


def verify_user_eligibility(user_id):
    user = query_one("SELECT * FROM users WHERE id = %s", (user_id,))
    if not user:
        return False, "User not found."
    if user["card_status"] != "active":
        return False, f"Library card is {user['card_status']}."
    if user["card_expiry"] and user["card_expiry"] < date.today():
        execute(
            "UPDATE users SET card_status = 'expired' WHERE id = %s",
            (user_id,),
        )
        return False, "Library card has expired."
    return True, user


def register_user(data):
    execute(
        """INSERT INTO users (username, password_hash, email, full_name, role, library_id, barcode, card_status, card_expiry)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            data["username"],
            data["password_hash"],
            data["email"],
            data["full_name"],
            data.get("role", "patron"),
            data["library_id"],
            data.get("barcode"),
            data.get("card_status", "active"),
            data.get("card_expiry"),
        ),
    )
    log_event("user_registered", entity_type="user", metadata={"library_id": data["library_id"]})


def lookup_by_barcode(barcode):
    return query_one("SELECT * FROM users WHERE barcode = %s OR library_id = %s", (barcode, barcode))


def get_all_users(page=None, per_page=10):
    if page is not None:
        total = query_one("SELECT COUNT(*) AS c FROM users")["c"]
        from services.pagination import sql_page_clause

        limit_sql, limit_params = sql_page_clause(page, per_page)
        return (
            query_all(
                f"""SELECT id, username, email, full_name, role, library_id, barcode, card_status, card_expiry
                    FROM users ORDER BY full_name{limit_sql}""",
                limit_params,
            ),
            total,
        )

    return query_all(
        """SELECT id, username, email, full_name, role, library_id, barcode, card_status, card_expiry
           FROM users ORDER BY full_name"""
    )


def update_card_status(user_id, status, expiry=None):
    execute(
        "UPDATE users SET card_status = %s, card_expiry = %s WHERE id = %s",
        (status, expiry, user_id),
    )
    log_event("card_status_updated", user_id=user_id, metadata={"status": status})
