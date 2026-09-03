from flask import Blueprint, flash, redirect, render_template, request, url_for

from flask_login import current_user, login_required



from services.pagination import get_page_from_request, make_pagination

from services.rbac import require_permission

from services.users_service import (

    create_user,

    get_user,

    list_users,

    reset_password,

    update_user,

)



users_bp = Blueprint("users", __name__, url_prefix="/admin/users")




def _users_index_redirect(**query):
    return redirect(url_for("users.index", **query))





@users_bp.route("/")

@login_required

@require_permission("users.manage")

def index():

    page = get_page_from_request()

    users, total = list_users(

        role=request.args.get("role") or None,

        card_status=request.args.get("card_status") or None,

        account_status=request.args.get("account_status") or None,

        search=request.args.get("q") or None,

        page=page,

    )

    pagination = make_pagination(total, page)

    return render_template(

        "users/index.html",

        users=users,

        pagination=pagination,

        filters={

            "role": request.args.get("role", ""),

            "card_status": request.args.get("card_status", ""),

            "account_status": request.args.get("account_status", ""),

            "q": request.args.get("q", ""),

        },

        breadcrumbs=[("Administration", None), ("Users", None)],

        page_title="User Management",

        staff_context="admin",

    )





@users_bp.route("/create", methods=["GET", "POST"])

@login_required

@require_permission("users.manage")

def create():

    if request.method == "POST":

        if not request.form.get("confirm_create"):

            flash("Please confirm user creation.", "error")

            return _users_index_redirect(modal="create")



        data = {

            "username": request.form.get("username", ""),

            "email": request.form.get("email", ""),

            "full_name": request.form.get("full_name", ""),

            "role": request.form.get("role", "patron"),

            "library_id": request.form.get("library_id", ""),

            "barcode": request.form.get("barcode", ""),

            "card_status": request.form.get("card_status", "active"),

            "must_change_password": True,

        }

        ok, result = create_user(data, current_user.id)

        if ok:

            flash(

                f"User created. Temporary password: {result['temp_password']} (user must change on first login).",

                "success",

            )

            return _users_index_redirect()

        flash(result, "error")

        return _users_index_redirect(modal="create")



    return _users_index_redirect(modal="create")





@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])

@login_required

@require_permission("users.manage")

def edit(user_id):

    user = get_user(user_id)

    if not user:

        flash("User not found.", "error")

        return redirect(url_for("users.index"))



    if request.method == "POST":

        new_role = request.form.get("role", user["role"])

        reason = request.form.get("reason", "").strip()



        if new_role != user["role"]:

            if not request.form.get("confirm_role_change"):

                flash("Please confirm the role change.", "error")

                return _users_index_redirect(modal="edit", user_id=user_id)

            if not reason:

                flash("A reason is required when changing a user's role.", "error")

                return _users_index_redirect(modal="edit", user_id=user_id)



        data = {

            "full_name": request.form.get("full_name", ""),

            "email": request.form.get("email", ""),

            "role": new_role,

            "card_status": request.form.get("card_status", user["card_status"]),

            "card_expiry": request.form.get("card_expiry") or None,

            "account_status": request.form.get("account_status", user.get("account_status", "active")),

        }

        ok, msg = update_user(user_id, data, current_user.id, reason=reason or None)

        flash(msg, "success" if ok else "error")

        if ok:

            return _users_index_redirect()

        return _users_index_redirect(modal="edit", user_id=user_id)



    return _users_index_redirect(modal="edit", user_id=user_id)





@users_bp.route("/<int:user_id>/toggle-status", methods=["POST"])

@login_required

@require_permission("users.manage")

def toggle_status(user_id):

    user = get_user(user_id)

    if not user:

        flash("User not found.", "error")

        return redirect(url_for("users.index"))



    reason = request.form.get("reason", "").strip()

    if not reason:

        flash("A reason is required to change account status.", "error")

        return _users_index_redirect(modal="edit", user_id=user_id)



    new_status = "disabled" if user.get("account_status", "active") == "active" else "active"

    ok, msg = update_user(

        user_id,

        {**user, "account_status": new_status},

        current_user.id,

        reason=reason,

    )

    flash(msg, "success" if ok else "error")

    if ok:

        return _users_index_redirect()

    return _users_index_redirect(modal="edit", user_id=user_id)





@users_bp.route("/<int:user_id>/reset-password", methods=["POST"])

@login_required

@require_permission("users.manage")

def reset_password_route(user_id):

    ok, result = reset_password(user_id, current_user.id)

    if ok:

        flash(f"Password reset. Temporary password: {result}", "success")

        return _users_index_redirect()

    flash(result, "error")

    return _users_index_redirect(modal="edit", user_id=user_id)

