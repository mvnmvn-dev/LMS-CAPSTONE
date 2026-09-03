from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user, login_required

from models.database import query_one
from services.borrowing_service import checkout, checkin, list_transactions, renew
from services.dashboard_extras import enrich_transactions
from services.pagination import get_page_from_request, make_pagination
from services.rbac import require_roles

borrowing_bp = Blueprint("borrowing", __name__, url_prefix="/borrowing")


@borrowing_bp.route("/")
@login_required
def index():
    page = get_page_from_request()
    if current_user.role == "patron":
        transactions, total = list_transactions(user_id=current_user.id, page=page)
    else:
        transactions, total = list_transactions(status=request.args.get("status"), page=page)
    transactions = enrich_transactions(transactions)
    pagination = make_pagination(total, page)
    return render_template(
        "borrowing/index.html",
        transactions=transactions,
        pagination=pagination,
        breadcrumbs=[("Borrowing", None)],
        page_title="Borrowing Logs",
    )


@borrowing_bp.route("/checkout", methods=["POST"])
@login_required
@require_roles("staff", "admin")
def checkout_route():
    user_id = int(request.form.get("user_id"))
    barcode = request.form.get("barcode", "").strip()
    ok, result = checkout(user_id, barcode, staff_id=current_user.id)
    flash(result if isinstance(result, str) else f"Checked out. Due: {result['due_date']}", "success" if ok else "error")
    return redirect(url_for("borrowing.index"))


@borrowing_bp.route("/checkin", methods=["POST"])
@login_required
@require_roles("staff", "admin")
def checkin_route():
    barcode = request.form.get("barcode", "").strip()
    ok, result = checkin(barcode, staff_id=current_user.id)
    flash(result if isinstance(result, str) else "Book returned.", "success" if ok else "error")
    return redirect(url_for("borrowing.index"))


@borrowing_bp.route("/renew/<int:tx_id>", methods=["POST"])
@login_required
def renew_route(tx_id):
    tx = query_one("SELECT user_id FROM transactions WHERE id = %s", (tx_id,))
    if not tx:
        flash("Transaction not found.", "error")
        return redirect(url_for("borrowing.index"))
    if current_user.role == "patron" and tx["user_id"] != current_user.id:
        abort(403)
    ok, result = renew(tx_id, tx["user_id"])
    flash(result if isinstance(result, str) else f"Renewed. New due date: {result['due_date']}", "success" if ok else "error")
    return redirect(url_for("borrowing.index"))
