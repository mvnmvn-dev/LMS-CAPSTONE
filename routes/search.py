from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash
from flask_login import current_user, login_required

from services.dashboard_extras import get_recently_viewed_books, get_trending_books
from services.inventory_service import list_genres
from services.pagination import get_page_from_request, make_pagination
from services.search_service import get_book_details, log_book_view, search_books
from services.reservation_service import place_hold

search_bp = Blueprint("search", __name__, url_prefix="/search")


def _search_context():
    query = request.args.get("q", "")
    genre = request.args.get("genre", "")
    available_only = request.args.get("available") == "1"
    ebook_only = request.args.get("ebook") == "1"
    page = get_page_from_request()
    books, total = search_books(
        query=query or None,
        genre=genre or None,
        available_only=available_only,
        ebook_only=ebook_only,
        page=page,
    )
    pagination = make_pagination(total, page)
    return {
        "books": books,
        "pagination": pagination,
        "query": query,
        "genre": genre,
        "available_only": available_only,
        "ebook_only": ebook_only,
        "genres": list_genres(),
        "has_filters": bool(query or genre or available_only or ebook_only),
    }


@search_bp.route("/")
@login_required
def index():
    ctx = _search_context()
    trending = get_trending_books(5)
    recently_viewed = get_recently_viewed_books(current_user.id, 5)
    return render_template(
        "search/index.html",
        **ctx,
        trending=trending,
        recently_viewed=recently_viewed,
        breadcrumbs=[("Search", None)],
        page_title="Online Book Search",
    )


@search_bp.route("/results")
@login_required
def results_fragment():
    ctx = _search_context()
    return jsonify(
        {
            "filters_html": render_template("search/_filters.html", **ctx),
            "results_html": render_template("search/_results.html", **ctx),
            "modals_html": render_template("search/_reserve_modals.html", **ctx),
            "total": ctx["pagination"]["total"],
            "query": ctx["query"],
            "has_filters": ctx["has_filters"],
        }
    )


@search_bp.route("/<int:book_id>")
@login_required
def detail(book_id):
    book = get_book_details(book_id)
    if not book:
        flash("Book not found.", "error")
        return redirect(url_for("search.index"))
    log_book_view(current_user.id, book_id)
    return redirect(url_for("search.index", book=book_id))


@search_bp.route("/<int:book_id>/reserve", methods=["POST"])
@login_required
def reserve(book_id):
    ok, result = place_hold(current_user.id, book_id)
    flash(result if isinstance(result, str) else f"Reserved! Queue position: {result['queue_position']}", "success" if ok else "error")
    return redirect(request.referrer or url_for("search.index"))
