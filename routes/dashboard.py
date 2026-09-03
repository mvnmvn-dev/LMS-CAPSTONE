from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required

from models.database import execute
from services.analytics_service import get_dashboard_stats, get_dashboard_reminder
from services.content_service import get_all_tips, get_spotlight_book, get_trivia_pool
from services.dashboard_extras import get_card_status_info, get_continue_reading, get_due_soon_loans, get_fine_stats
from services.fines_service import update_overdue_status
from services.reports_service import get_chart_data
from services.rbac import require_roles


def enrich_due_soon(loans):
    from services.dashboard_extras import enrich_due_urgency
    return [enrich_due_urgency(dict(loan)) for loan in loans]


dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


@dashboard_bp.route("/")
@login_required
def index():
    update_overdue_status(current_user.id if current_user.role == "patron" else None)
    stats = get_dashboard_stats(
        user_id=current_user.id,
        role=current_user.role,
    )
    chart_data = get_chart_data(role=current_user.role, user_id=current_user.id)
    extras = {
        "due_soon": enrich_due_soon(get_due_soon_loans(current_user.id)) if current_user.role == "patron" else [],
        "continue_reading": get_continue_reading(current_user.id) if current_user.role == "patron" else None,
        "spotlight": get_spotlight_book(),
        "library_tips": get_all_tips(current_user.role),
        "trivia_pool": get_trivia_pool(),
        "fine_stats": get_fine_stats(current_user.id) if current_user.role == "patron" else None,
        "card_info": get_card_status_info({
            "card_status": current_user.card_status,
            "card_expiry": current_user.card_expiry,
        }),
        "reminder_text": get_dashboard_reminder(current_user.role, current_user.id, stats),
    }
    return render_template(
        "dashboard/index.html",
        stats=stats,
        chart_data=chart_data,
        extras=extras,
        breadcrumbs=[("Dashboard", None)],
        page_title="Dashboard",
    )


@dashboard_bp.route("/spotlight", methods=["POST"])
@login_required
@require_roles("staff", "admin")
def set_spotlight():
    book_id = request.form.get("book_id", type=int)
    label = request.form.get("label", "Staff Pick").strip() or "Staff Pick"
    note = request.form.get("note", "").strip()
    if not book_id:
        flash("Book ID is required.", "error")
        return redirect(url_for("dashboard.index"))
    execute("UPDATE library_spotlight SET active = 0")
    execute(
        "INSERT INTO library_spotlight (book_id, label, note, set_by, active) VALUES (%s, %s, %s, %s, 1)",
        (book_id, label, note or None, current_user.id),
    )
    flash("Book of the Week updated!", "success")
    return redirect(url_for("dashboard.index"))
