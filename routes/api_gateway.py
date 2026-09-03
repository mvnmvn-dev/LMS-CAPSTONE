from flask import Blueprint, request
from flask_login import current_user, login_required

from services.analytics_service import get_dashboard_stats
from services.borrowing_service import checkout, checkin, list_transactions
from services.clearance_service import run_clearance_audit
from services.fines_service import list_fines
from services.inventory_service import get_availability, get_book, list_books
from services.rbac import api_error, api_response, get_json, has_permission, require_roles
from services.reservation_service import list_reservations, place_hold
from services.search_service import get_book_details, search_books, search_suggest
from services.verification_service import lookup_by_barcode, verify_user_eligibility

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


@api_bp.route("/health")
def health():
    return api_response({"status": "ok"})


@api_bp.route("/dashboard")
@login_required
def api_dashboard():
    stats = get_dashboard_stats(current_user.id, current_user.role)
    return api_response(stats)


@api_bp.route("/books")
@login_required
def api_books():
    genre = request.args.get("genre")
    search = request.args.get("q")
    books = list_books(genre=genre, search=search)
    for b in books:
        b["availability"] = get_availability(b["id"])
    return api_response(books)


@api_bp.route("/books/<int:book_id>")
@login_required
def api_book(book_id):
    book = get_book_details(book_id)
    if not book:
        return api_error("Book not found", 404)
    return api_response(book)


@api_bp.route("/search/suggest")
@login_required
def api_search_suggest():
    q = request.args.get("q", "")
    return api_response(search_suggest(q))


@api_bp.route("/search")
@login_required
def api_search():
    results = search_books(
        query=request.args.get("q"),
        genre=request.args.get("genre"),
        available_only=request.args.get("available") == "1",
    )
    return api_response(results)


@api_bp.route("/verify/<code>")
@login_required
@require_roles("staff", "admin")
def api_verify(code):
    user = lookup_by_barcode(code)
    if not user:
        return api_error("Not found", 404)
    eligible, msg = verify_user_eligibility(user["id"])
    return api_response({"user": user, "eligible": eligible, "message": msg})


@api_bp.route("/borrow/checkout", methods=["POST"])
@login_required
@require_roles("staff", "admin")
def api_checkout():
    data = get_json()
    ok, result = checkout(data.get("user_id"), data.get("barcode"), staff_id=current_user.id)
    return api_response(result, "OK" if ok else result, 200 if ok else 400)


@api_bp.route("/borrow/checkin", methods=["POST"])
@login_required
@require_roles("staff", "admin")
def api_checkin():
    data = get_json()
    ok, result = checkin(data.get("barcode"), staff_id=current_user.id)
    return api_response(result, "OK" if ok else result, 200 if ok else 400)


@api_bp.route("/borrow/transactions")
@login_required
def api_transactions():
    if current_user.role == "patron":
        uid = current_user.id
    else:
        uid = request.args.get("user_id")
    txs = list_transactions(user_id=int(uid) if uid else None, status=request.args.get("status"))
    return api_response(txs)


@api_bp.route("/fines")
@login_required
def api_fines():
    if current_user.role == "patron":
        uid = current_user.id
    else:
        uid = request.args.get("user_id")
    fines = list_fines(user_id=int(uid) if uid else None, status=request.args.get("status"))
    return api_response(fines)


@api_bp.route("/reservations", methods=["GET", "POST"])
@login_required
def api_reservations():
    if request.method == "POST":
        data = get_json()
        user_id = int(data.get("user_id", current_user.id))
        if current_user.role == "patron" and user_id != current_user.id:
            return api_error("Not authorized", 403)
        ok, result = place_hold(user_id, data.get("book_id"))
        return api_response(result, "OK" if ok else result, 200 if ok else 400)
    uid = current_user.id if current_user.role == "patron" else None
    return api_response(list_reservations(user_id=uid))


@api_bp.route("/clearance/<int:user_id>")
@login_required
def api_clearance(user_id):
    if current_user.role == "patron" and user_id != current_user.id:
        return api_error("Not authorized", 403)
    if current_user.role == "patron" and not has_permission(current_user.role, "clearance.request"):
        return api_error("Not authorized", 403)
    return api_response(run_clearance_audit(user_id))
