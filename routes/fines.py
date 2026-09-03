from flask import Blueprint, render_template, request, redirect, url_for, flash

from flask_login import current_user, login_required



from services.dashboard_extras import enrich_reservations, get_fine_stats, parse_fine_breakdown

from services.fines_service import list_fines, record_payment, update_overdue_status, waive_fine

from services.pagination import get_page_from_request, make_pagination

from services.rbac import require_permission



fines_bp = Blueprint("fines", __name__, url_prefix="/fines")





@fines_bp.route("/")

@login_required

def index():

    update_overdue_status()
    page = get_page_from_request()

    if current_user.role == "patron":

        fines, total = list_fines(user_id=current_user.id, page=page)

        fine_stats = get_fine_stats(current_user.id)

    else:

        fines, total = list_fines(status=request.args.get("status"), page=page)

        fine_stats = None

    for fine in fines:

        fine["breakdown"] = parse_fine_breakdown(fine.get("reason"), fine.get("amount", 0))

    pagination = make_pagination(total, page)

    return render_template(

        "fines/index.html",

        fines=fines,

        fine_stats=fine_stats,

        pagination=pagination,

        breadcrumbs=[("Fines", None)],

        page_title="Due Dates & Fines",

        staff_context="staff" if current_user.role == "staff" else None,

    )





@fines_bp.route("/pay/<int:fine_id>", methods=["POST"])

@login_required

@require_permission("fines.manage")

def pay(fine_id):

    ok, msg = record_payment(fine_id, staff_id=current_user.id)

    flash(msg, "success" if ok else "error")

    return redirect(url_for("fines.index"))





@fines_bp.route("/pay-online/<int:fine_id>", methods=["POST"])

@login_required

def pay_online(fine_id):

    from models.database import query_one

    fine = query_one("SELECT * FROM fines WHERE id = %s AND user_id = %s", (fine_id, current_user.id))

    if not fine:

        flash("Fine not found.", "error")

        return redirect(url_for("fines.index"))

    if fine["status"] != "unpaid":

        flash("Fine already settled.", "error")

        return redirect(url_for("fines.index"))

    ok, msg = record_payment(fine_id, staff_id=None)

    flash("Payment successful! (simulated online payment)" if ok else msg, "success" if ok else "error")

    return redirect(url_for("fines.index"))





@fines_bp.route("/waive/<int:fine_id>", methods=["POST"])

@login_required

@require_permission("fines.waive")

def waive(fine_id):

    reason = request.form.get("reason", "").strip()

    if not reason:

        flash("A reason is required to waive a fine.", "error")

        return redirect(url_for("fines.index"))

    ok, msg = waive_fine(fine_id, current_user.id, reason)

    flash(msg, "success" if ok else "error")

    return redirect(url_for("fines.index"))

