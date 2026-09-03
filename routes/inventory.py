from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required

from services.inventory_service import (
    create_book,
    delete_book,
    get_book,
    list_books,
    add_copy,
    update_book,
    list_genres,
    save_book_cover,
)
from services.pagination import get_page_from_request, make_pagination
from services.rbac import require_roles

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@inventory_bp.route("/")
@login_required
@require_roles("staff", "admin")
def index():
    page = get_page_from_request()
    books, total = list_books(search=request.args.get("q"), page=page)
    open_book_id = request.args.get("book_id", type=int)
    scan_code = request.args.get("scan", "")
    pagination = make_pagination(total, page)
    return render_template(
        "inventory/index.html",
        books=books,
        pagination=pagination,
        open_book_id=open_book_id,
        scan_code=scan_code,
        breadcrumbs=[("Inventory", None)],
        page_title="Book Inventory",
    )


@inventory_bp.route("/add", methods=["GET", "POST"])
@login_required
@require_roles("staff", "admin")
def add():
    if request.method == "GET":
        return redirect(url_for("inventory.index"))
    authors = [a.strip() for a in request.form.get("authors", "").split(",") if a.strip()]
    copies = []
    for bc in request.form.get("barcodes", "").split(","):
        bc = bc.strip()
        if bc:
            copies.append({"barcode": bc})
    book_id = create_book({
        "isbn": request.form.get("isbn"),
        "title": request.form.get("title"),
        "publisher": request.form.get("publisher"),
        "genre": request.form.get("genre"),
        "description": request.form.get("description"),
        "authors": authors,
        "copies": copies,
        "has_ebook": request.form.get("has_ebook") == "on",
    })
    cover_file = request.files.get("cover_image")
    if cover_file and cover_file.filename:
        ok, result = save_book_cover(book_id, cover_file)
        if not ok:
            flash(result, "warning")
    flash("Book added successfully.", "success")
    return redirect(url_for("inventory.index"))


@inventory_bp.route("/<int:book_id>")
@login_required
@require_roles("staff", "admin")
def detail(book_id):
    return redirect(url_for("inventory.index", book_id=book_id))


@inventory_bp.route("/<int:book_id>/edit", methods=["GET", "POST"])
@login_required
@require_roles("staff", "admin")
def edit(book_id):
    book = get_book(book_id)
    if not book:
        flash("Book not found.", "error")
        return redirect(url_for("inventory.index"))
    if request.method == "GET":
        return redirect(url_for("inventory.index", book_id=book_id))
    cover_url = book.get("cover_url")
    cover_file = request.files.get("cover_image")
    if cover_file and cover_file.filename:
        ok, result = save_book_cover(book_id, cover_file)
        if ok:
            cover_url = result
        else:
            flash(result, "warning")
    update_book(book_id, {
        "isbn": request.form.get("isbn"),
        "title": request.form.get("title"),
        "publisher": request.form.get("publisher"),
        "genre": request.form.get("genre"),
        "description": request.form.get("description"),
        "cover_url": cover_url,
        "has_ebook": request.form.get("has_ebook") == "on",
    })
    flash("Book updated.", "success")
    return redirect(url_for("inventory.index", book_id=book_id))


@inventory_bp.route("/<int:book_id>/delete", methods=["POST"])
@login_required
@require_roles("admin")
def remove(book_id):
    delete_book(book_id)
    flash("Book deleted.", "success")
    return redirect(url_for("inventory.index"))


@inventory_bp.route("/<int:book_id>/copy", methods=["POST"])
@login_required
@require_roles("staff", "admin")
def add_copy_route(book_id):
    barcode = request.form.get("barcode", "").strip()
    if barcode:
        rfid_tag = (request.form.get("rfid_tag") or "").strip() or None
        add_copy(book_id, barcode, rfid_tag)
        flash("Copy added.", "success")
    return redirect(url_for("inventory.index", book_id=book_id))
