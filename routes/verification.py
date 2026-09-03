from flask import Blueprint, render_template, request, redirect, url_for, flash

from flask_login import current_user, login_required



from services.dashboard_extras import get_card_status_info

from services.pagination import get_page_from_request, make_pagination

from services.verification_service import get_all_users, lookup_by_barcode, update_card_status

from services.rbac import require_permission, require_roles



verification_bp = Blueprint("verification", __name__, url_prefix="/verification")





@verification_bp.route("/")

@login_required

@require_roles("staff", "admin")

def index():

    page = get_page_from_request()

    users, total = get_all_users(page=page)

    for u in users:

        u["card_info"] = get_card_status_info(u)

    pagination = make_pagination(total, page)

    lookup = None

    code = request.args.get("code", "").strip()

    if code:

        lookup = lookup_by_barcode(code)

        if lookup:

            lookup["card_info"] = get_card_status_info(lookup)

    return render_template(

        "verification/index.html",

        users=users,

        pagination=pagination,

        lookup=lookup,

        code=code,

        breadcrumbs=[("Library ID", None)],

        page_title="Library ID Verification",

        staff_context="staff",

    )





@verification_bp.route("/<int:user_id>/status", methods=["POST"])

@login_required

@require_permission("verification.manage")

def set_status(user_id):

    reason = request.form.get("reason", "").strip()

    if not reason:

        flash("A reason is required when changing card status.", "error")

        return redirect(url_for("verification.index"))



    status = request.form.get("card_status")

    expiry = request.form.get("card_expiry") or None

    update_card_status(user_id, status, expiry)



    from services.analytics_service import log_event

    log_event(

        "card_status_changed",

        user_id=current_user.id,

        entity_type="user",

        entity_id=user_id,

        metadata={"card_status": status, "reason": reason},

    )

    flash("Card status updated.", "success")

    return redirect(url_for("verification.index"))

