from models.database import execute, query_all, query_one, transactional
from services.analytics_service import log_event
from services.fines_service import create_replacement_fine
from services.inventory_service import update_copy_status
from services.notification_service import notify_patron, notify_staff


@transactional
def create_report(copy_id, reported_by, report_type, user_id=None, notes=None, replacement_cost=0):
    copy = query_one(
        """SELECT c.*, b.title FROM copies c JOIN books b ON b.id = c.book_id WHERE c.id = %s""",
        (copy_id,),
    )
    if not copy:
        return False, "Copy not found."

    status = "lost" if report_type == "lost" else "under_repair"
    report_id = execute(
        """INSERT INTO lost_damaged_reports (copy_id, user_id, reported_by, report_type, replacement_cost, notes)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (copy_id, user_id, reported_by, report_type, replacement_cost, notes),
    )[0]

    update_copy_status(copy_id, status)

    if replacement_cost > 0 and user_id:
        create_replacement_fine(
            user_id,
            replacement_cost,
            f"{report_type.title()} book: {copy['title']}",
            report_id,
        )

    log_event(
        f"book_{report_type}",
        user_id=reported_by,
        entity_type="report",
        entity_id=report_id,
        metadata={"copy_id": copy_id},
    )
    notify_staff(
        f"New {report_type} report",
        f"{copy['title']} ({copy['barcode']}) reported as {report_type}.",
        "warning",
        "/lost-damaged/",
    )
    if user_id:
        notify_patron(user_id, "Book report filed", f"A {report_type} report was filed for {copy['title']}.", "warning")
    return True, {"report_id": report_id}


def list_reports(status=None, user_id=None, page=None, per_page=10):
    where = " WHERE 1=1"
    params = []
    if user_id:
        where += " AND (r.reported_by = %s OR r.user_id = %s)"
        params.extend([user_id, user_id])
    if status:
        where += " AND r.status = %s"
        params.append(status)

    if page is not None:
        total = query_one(
            f"""SELECT COUNT(*) AS c
                FROM lost_damaged_reports r
                JOIN copies c ON c.id = r.copy_id
                JOIN books b ON b.id = c.book_id
                JOIN users u ON u.id = r.reported_by{where}""",
            params,
        )["c"]
        from services.pagination import sql_page_clause

        limit_sql, limit_params = sql_page_clause(page, per_page)
        sql = f"""
            SELECT r.*, c.barcode, b.title, u.full_name AS reporter_name
            FROM lost_damaged_reports r
            JOIN copies c ON c.id = r.copy_id
            JOIN books b ON b.id = c.book_id
            JOIN users u ON u.id = r.reported_by{where}
            ORDER BY r.created_at DESC{limit_sql}
        """
        return query_all(sql, params + limit_params), total

    sql = f"""
        SELECT r.*, c.barcode, b.title, u.full_name AS reporter_name
        FROM lost_damaged_reports r
        JOIN copies c ON c.id = r.copy_id
        JOIN books b ON b.id = c.book_id
        JOIN users u ON u.id = r.reported_by{where}
        ORDER BY r.created_at DESC
    """
    return query_all(sql, params)


@transactional
def resolve_report(report_id, status="resolved"):
    execute("UPDATE lost_damaged_reports SET status = %s WHERE id = %s", (status, report_id))
    log_event("report_resolved", entity_type="report", entity_id=report_id)
