from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import current_user, login_required
import os

from services.ebook_service import get_user_access, grant_access, list_ebooks, save_reading_progress
from services.pagination import get_page_from_request, make_pagination
from services.rbac import require_roles

ebooks_bp = Blueprint("ebooks", __name__, url_prefix="/ebooks")


@ebooks_bp.route("/")
@login_required
def index():
    page = get_page_from_request()
    if current_user.role == "patron":
        access = get_user_access(current_user.id)
    else:
        access = []
    catalog, total = list_ebooks(page=page)
    pagination = make_pagination(total, page)
    return render_template(
        "ebooks/index.html",
        access=access,
        catalog=catalog,
        pagination=pagination,
        breadcrumbs=[("E-Books", None)],
        page_title="E-Book Integration",
    )


@ebooks_bp.route("/access/<int:ebook_id>", methods=["POST"])
@login_required
def access(ebook_id):
    ok, result = grant_access(current_user.id, ebook_id)
    flash(result if isinstance(result, str) else "Access granted!", "success" if ok else "error")
    return redirect(url_for("ebooks.index"))


@ebooks_bp.route("/reader/<int:access_id>")
@login_required
def reader(access_id):
    from models.database import query_one
    row = query_one(
        """SELECT ea.*, e.file_path, e.format, b.title
           FROM ebook_access ea
           JOIN ebooks e ON e.id = ea.ebook_id
           JOIN books b ON b.id = e.book_id
           WHERE ea.id = %s AND ea.user_id = %s AND ea.expires_at > NOW()""",
        (access_id, current_user.id),
    )
    if not row:
        flash("Access expired or not found.", "error")
        return redirect(url_for("ebooks.index"))
    save_reading_progress(current_user.id, access_id, row.get("progress_pct") or 5)
    return render_template(
        "ebooks/reader.html",
        ebook=row,
        breadcrumbs=[("E-Books", url_for("ebooks.index")), ("Reader", None)],
        page_title=row["title"],
    )


@ebooks_bp.route("/reader/<int:access_id>/progress", methods=["POST"])
@login_required
def save_progress(access_id):
    from flask import jsonify
    data = request.get_json(silent=True) or {}
    progress = data.get("progress_pct", 0)
    last_page = data.get("last_page", 0)
    save_reading_progress(current_user.id, access_id, progress, last_page)
    return jsonify({"success": True})
