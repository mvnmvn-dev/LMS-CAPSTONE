from flask import Blueprint, render_template, request

from flask_login import login_required

from services.pagination import get_page_from_request, make_pagination
from services.rbac import require_permission
from services.users_service import get_activity_event_types, list_activity_log


activity_bp = Blueprint("activity", __name__, url_prefix="/admin/activity")


@activity_bp.route("/")
@login_required
@require_permission("audit.view")
def index():
    event_type = (request.args.get("event_type") or "").strip() or None
    actor = (request.args.get("actor") or "").strip() or None
    page = get_page_from_request()
    logs, total = list_activity_log(event_type=event_type, actor=actor, page=page)
    pagination = make_pagination(total, page)
    return render_template(
        "activity/index.html",
        logs=logs,
        pagination=pagination,
        event_types=get_activity_event_types(),
        selected_event=event_type or "",
        selected_actor=actor or "",
        breadcrumbs=[("Administration", None), ("Activity Log", None)],
        page_title="Activity Log",
        staff_context="admin",
    )
