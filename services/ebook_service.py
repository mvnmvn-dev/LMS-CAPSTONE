from datetime import datetime, timedelta

from flask import current_app

from models.database import execute, query_all, query_one
from services.analytics_service import log_event
from services.verification_service import verify_user_eligibility


def list_ebooks(book_id=None, page=None, per_page=10):
    where = " WHERE 1=1"
    params = []
    if book_id:
        where += " AND e.book_id = %s"
        params.append(book_id)

    if page is not None:
        total = query_one(
            f"""SELECT COUNT(*) AS c
                FROM ebooks e
                JOIN books b ON b.id = e.book_id{where}""",
            params,
        )["c"]
        from services.pagination import sql_page_clause

        limit_sql, limit_params = sql_page_clause(page, per_page)
        sql = f"""
            SELECT e.*, b.title, b.isbn
            FROM ebooks e
            JOIN books b ON b.id = e.book_id{where}
            ORDER BY b.title, e.format{limit_sql}
        """
        return query_all(sql, params + limit_params), total

    sql = f"""
        SELECT e.*, b.title, b.isbn
        FROM ebooks e
        JOIN books b ON b.id = e.book_id{where}
        ORDER BY b.title, e.format
    """
    return query_all(sql, params)


def grant_access(user_id, ebook_id):
    eligible, result = verify_user_eligibility(user_id)
    if not eligible:
        return False, result

    ebook = query_one("SELECT * FROM ebooks WHERE id = %s", (ebook_id,))
    if not ebook:
        return False, "E-book not found."

    hours = ebook["access_hours"] or current_app.config["EBOOK_ACCESS_HOURS"]
    expires = datetime.now() + timedelta(hours=hours)

    access_id = execute(
        "INSERT INTO ebook_access (user_id, ebook_id, expires_at) VALUES (%s, %s, %s)",
        (user_id, ebook_id, expires),
    )[0]

    log_event("ebook_access_granted", user_id=user_id, entity_type="ebook", entity_id=ebook_id)
    return True, {"access_id": access_id, "expires_at": str(expires), "file_path": ebook["file_path"]}


def get_user_access(user_id):
    return query_all(
        """SELECT ea.*, e.format, e.file_path, b.title, e.id AS ebook_id,
                  COALESCE(rp.progress_pct, 0) AS progress_pct
           FROM ebook_access ea
           JOIN ebooks e ON e.id = ea.ebook_id
           JOIN books b ON b.id = e.book_id
           LEFT JOIN reading_progress rp ON rp.ebook_access_id = ea.id AND rp.user_id = ea.user_id
           WHERE ea.user_id = %s AND ea.expires_at > NOW()
           ORDER BY ea.granted_at DESC""",
        (user_id,),
    )


def save_reading_progress(user_id, access_id, progress_pct, last_page=0):
    existing = query_one(
        "SELECT id FROM reading_progress WHERE user_id = %s AND ebook_access_id = %s",
        (user_id, access_id),
    )
    progress_pct = max(0, min(100, int(progress_pct)))
    if existing:
        execute(
            """UPDATE reading_progress SET progress_pct = %s, last_page = %s, last_opened_at = NOW()
               WHERE id = %s""",
            (progress_pct, last_page, existing["id"]),
        )
    else:
        execute(
            """INSERT INTO reading_progress (user_id, ebook_access_id, progress_pct, last_page)
               VALUES (%s, %s, %s, %s)""",
            (user_id, access_id, progress_pct, last_page),
        )
    log_event("ebook_progress", user_id=user_id, entity_type="ebook_access", entity_id=access_id,
              metadata={"progress_pct": progress_pct})
    return True


def create_ebook(book_id, format_type, file_path, access_hours=None, drm_key=None):
    ebook_id = execute(
        """INSERT INTO ebooks (book_id, format, file_path, access_hours, drm_key)
           VALUES (%s, %s, %s, %s, %s)""",
        (book_id, format_type, file_path, access_hours or current_app.config["EBOOK_ACCESS_HOURS"], drm_key),
    )[0]
    execute("UPDATE books SET has_ebook = 1 WHERE id = %s", (book_id,))
    return ebook_id
