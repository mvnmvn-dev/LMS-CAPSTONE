from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required

from services.dashboard_extras import enrich_reservations
from services.pagination import get_page_from_request, make_pagination
from services.reservation_service import cancel_reservation, fulfill_reservation, list_reservations
from services.rbac import require_roles

reservations_bp = Blueprint("reservations", __name__, url_prefix="/reservations")


@reservations_bp.route("/")
@login_required
def index():
    page = get_page_from_request()
    if current_user.role == "patron":
        reservations, total = list_reservations(user_id=current_user.id, page=page)
    else:
        reservations, total = list_reservations(page=page)
    reservations = enrich_reservations(reservations)
    pagination = make_pagination(total, page)
    return render_template(
        "reservations/index.html",
        reservations=reservations,
        pagination=pagination,
        breadcrumbs=[("Reservations", None)],
        page_title="Book Reservations",
    )


@reservations_bp.route("/cancel/<int:res_id>", methods=["POST"])
@login_required
def cancel(res_id):
    ok, msg = cancel_reservation(res_id, current_user.id if current_user.role == "patron" else None)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("reservations.index"))


@reservations_bp.route("/fulfill/<int:res_id>", methods=["POST"])
@login_required
@require_roles("staff", "admin")
def fulfill(res_id):
    ok, msg = fulfill_reservation(res_id)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("reservations.index"))
