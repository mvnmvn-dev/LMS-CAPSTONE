from flask import Blueprint, render_template, redirect, url_for, flash, request

from flask_login import current_user, login_required



from services.clearance_service import (

    get_clearance_stats,

    list_clearance_requests,

    request_clearance,

    run_clearance_audit,

)

from services.pagination import get_page_from_request, make_pagination

from services.rbac import require_permission, require_roles

from services.verification_service import lookup_by_barcode



clearance_bp = Blueprint("clearance", __name__, url_prefix="/clearance")





def _audit_checklist(audit, user_id):

    from flask import url_for

    return [

        {

            "label": "No active loans",

            "ok": audit["active_loans"] == 0,

            "detail": f"{audit['active_loans']} active loan(s)" if audit["active_loans"] else "All clear",

            "link": url_for("borrowing.index") if audit["active_loans"] else None,

            "action": "Return books" if audit["active_loans"] else None,

        },

        {

            "label": "No pending holds",

            "ok": audit["pending_holds"] == 0,

            "detail": f"{audit['pending_holds']} pending hold(s)" if audit["pending_holds"] else "All clear",

            "link": url_for("reservations.index") if audit["pending_holds"] else None,

            "action": "View reservations" if audit["pending_holds"] else None,

        },

        {

            "label": "No unpaid fines",

            "ok": audit["unpaid_fines"] == 0,

            "detail": f"₱{audit['unpaid_fines']:.2f} outstanding" if audit["unpaid_fines"] else "All clear",

            "link": url_for("fines.index") if audit["unpaid_fines"] else None,

            "action": "Pay fines" if audit["unpaid_fines"] else None,

        },

    ]





@clearance_bp.route("/")

@login_required

def index():

    patron_lookup = None

    patron_audit = None

    patron_checklist = []



    if current_user.role == "patron":

        audit = run_clearance_audit(current_user.id)

        checklist = _audit_checklist(audit, current_user.id)

        requests = []

        stats = None

        pagination = None

    else:

        audit = None

        checklist = []

        page = get_page_from_request()

        requests, total = list_clearance_requests(page=page)

        pagination = make_pagination(total, page)

        stats = get_clearance_stats()



        code = request.args.get("code", "").strip()

        if code:

            patron_lookup = lookup_by_barcode(code)

            if patron_lookup:

                if patron_lookup["role"] != "patron":

                    flash("Clearance audits apply to patron accounts only.", "error")

                    patron_lookup = None

                else:

                    patron_audit = run_clearance_audit(patron_lookup["id"])

                    patron_checklist = _audit_checklist(patron_audit, patron_lookup["id"])

            else:

                flash("Patron not found. Check the Library ID or barcode.", "error")



    return render_template(

        "clearance/index.html",

        audit=audit,

        checklist=checklist,

        requests=requests,

        pagination=pagination,

        stats=stats,

        patron_lookup=patron_lookup,

        patron_audit=patron_audit,

        patron_checklist=patron_checklist,

        lookup_code=request.args.get("code", ""),

        breadcrumbs=[("Clearance", None)],

        page_title="Library Clearance",

    )





@clearance_bp.route("/request", methods=["POST"])

@login_required

@require_permission("clearance.request")

def request_clearance_route():

    result = request_clearance(current_user.id)

    if result["cleared"]:

        flash("Clearance granted! No outstanding obligations.", "success")

    else:

        flash(f"Clearance blocked: {result.get('blocked_reason', 'Outstanding items found.')}", "error")

    return redirect(url_for("clearance.index"))

