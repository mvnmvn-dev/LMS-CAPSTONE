from flask import Blueprint, jsonify, redirect, request, url_for
from flask_login import current_user, login_required

from services.notification_service import (
    get_unread_count,
    get_user_notifications,
    mark_all_read,
    mark_read,
)
from services.rbac import api_response, require_permission

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/")
@login_required
@require_permission("notifications.view")
def index():
    notes = get_user_notifications(current_user.id, limit=50)
    return api_response({
        "notifications": notes,
        "unread_count": get_unread_count(current_user.id),
    })


@notifications_bp.route("/<int:note_id>/read", methods=["POST"])
@login_required
@require_permission("notifications.view")
def mark_read_route(note_id):
    mark_read(note_id, current_user.id)
    return api_response({"unread_count": get_unread_count(current_user.id)})


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
@require_permission("notifications.view")
def mark_all_read_route():
    mark_all_read(current_user.id)
    return api_response({"unread_count": 0})
