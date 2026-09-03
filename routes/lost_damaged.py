from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required

from models.database import query_all
from services.lost_damaged_service import create_report, list_reports, resolve_report
from services.pagination import get_page_from_request, make_pagination
from services.rbac import require_permission, require_roles

reports_lost_bp = Blueprint("lost_damaged", __name__, url_prefix="/lost-damaged")


@reports_lost_bp.route("/")
@login_required
@require_permission("lost_damaged.report")
def index():
    page = get_page_from_request()
    if current_user.role == "patron":
        reports, total = list_reports(user_id=current_user.id, page=page)
        copies = query_all(
            """SELECT c.id, c.barcode, b.title FROM copies c
               JOIN books b ON b.id = c.book_id
               JOIN transactions t ON t.copy_id = c.id
               WHERE t.user_id = %s AND t.status IN ('active', 'overdue')
               ORDER BY b.title""",
            (current_user.id,),
        )
    else:
        reports, total = list_reports(status=request.args.get("status"), page=page)
        copies = query_all(
            """SELECT c.id, c.barcode, b.title FROM copies c
               JOIN books b ON b.id = c.book_id
               WHERE c.status NOT IN ('lost') ORDER BY b.title"""
        )
    pagination = make_pagination(total, page)
    return render_template(
        "lost_damaged/index.html",
        reports=reports,
        copies=copies,
        pagination=pagination,
        breadcrumbs=[("Lost/Damaged", None)],
        page_title="Lost & Damaged Reports",
    )


@reports_lost_bp.route("/report", methods=["POST"])
@login_required
@require_permission("lost_damaged.report")
def report():
    copy_id = int(request.form.get("copy_id"))
    report_type = request.form.get("report_type", "damaged")
    user_id = request.form.get("user_id")
    user_id = int(user_id) if user_id else (current_user.id if current_user.role == "patron" else None)
    cost = float(request.form.get("replacement_cost") or 0)
    ok, result = create_report(
        copy_id, current_user.id, report_type, user_id,
        notes=request.form.get("notes"), replacement_cost=cost,
    )
    flash(result if isinstance(result, str) else "Report submitted.", "success" if ok else "error")
    return redirect(url_for("lost_damaged.index"))


@reports_lost_bp.route("/resolve/<int:report_id>", methods=["POST"])
@login_required
@require_roles("staff", "admin")
def resolve(report_id):
    resolve_report(report_id)
    flash("Report resolved.", "success")
    return redirect(url_for("lost_damaged.index"))
