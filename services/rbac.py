from functools import wraps

from flask import abort, jsonify, request
from flask_login import current_user

ROLE_PERMISSIONS = {
    "patron": {
        "dashboard.view",
        "search.view",
        "reservations.manage_own",
        "borrowing.view_own",
        "fines.view_own",
        "ebooks.view_own",
        "clearance.request",
        "lost_damaged.report",
        "notifications.view",
        "profile.manage_own",
    },
    "staff": {
        "dashboard.view",
        "inventory.view",
        "inventory.manage",
        "search.view",
        "verification.view",
        "borrowing.manage",
        "fines.manage",
        "reservations.manage",
        "ebooks.manage",
        "lost_damaged.manage",
        "clearance.manage",
        "reports.view",
        "notifications.view",
        "profile.manage_own",
    },
    "admin": {
        "dashboard.view",
        "inventory.view",
        "inventory.manage",
        "search.view",
        "verification.view",
        "verification.manage",
        "borrowing.manage",
        "fines.manage",
        "fines.waive",
        "reservations.manage",
        "ebooks.manage",
        "lost_damaged.manage",
        "clearance.manage",
        "reports.view",
        "reports.manage",
        "users.manage",
        "audit.view",
        "notifications.view",
        "profile.manage_own",
    },
}

ROLE_LABELS = {
    "patron": "Student",
    "staff": "Librarian Staff",
    "admin": "Admin",
}

PUBLIC_ENDPOINTS = frozenset({
    "auth.login",
    "auth.logout",
    "auth.index",
    "auth.change_password",
    "static",
    "api.health",
})

ENDPOINT_PERMISSIONS = {
    "dashboard.index": "dashboard.view",
    "dashboard.set_spotlight": "inventory.manage",
    "search.index": "search.view",
    "search.results_fragment": "search.view",
    "search.detail": "search.view",
    "search.reserve": "reservations.manage_own",
    "reservations.index": "reservations.manage_own",
    "reservations.cancel": "reservations.manage_own",
    "reservations.fulfill": "reservations.manage",
    "borrowing.index": "borrowing.view_own",
    "borrowing.checkout_route": "borrowing.manage",
    "borrowing.checkin_route": "borrowing.manage",
    "borrowing.renew_route": "borrowing.view_own",
    "fines.index": "fines.view_own",
    "fines.pay": "fines.manage",
    "fines.pay_online": "fines.view_own",
    "fines.waive": "fines.waive",
    "ebooks.index": "ebooks.view_own",
    "ebooks.access": "ebooks.view_own",
    "ebooks.reader": "ebooks.view_own",
    "ebooks.save_progress": "ebooks.view_own",
    "clearance.index": "clearance.request",
    "clearance.request_clearance_route": "clearance.request",
    "lost_damaged.index": "lost_damaged.report",
    "lost_damaged.report": "lost_damaged.report",
    "lost_damaged.resolve": "lost_damaged.manage",
    "inventory.index": "inventory.view",
    "inventory.add": "inventory.manage",
    "inventory.detail": "inventory.view",
    "inventory.edit": "inventory.manage",
    "inventory.remove": "inventory.manage",
    "inventory.add_copy_route": "inventory.manage",
    "verification.index": "verification.view",
    "verification.set_status": "verification.manage",
    "analytics.index": "reports.view",
    "analytics.api_data": "reports.view",
    "analytics.export": "reports.manage",
    "notifications.index": "notifications.view",
    "notifications.mark_read_route": "notifications.view",
    "notifications.mark_all_read_route": "notifications.view",
    "users.index": "users.manage",
    "users.create": "users.manage",
    "users.edit": "users.manage",
    "users.toggle_status": "users.manage",
    "users.reset_password_route": "users.manage",
    "activity.index": "audit.view",
    "profile.index": "profile.manage_own",
    "profile.update": "profile.manage_own",
    "profile.upload_photo": "profile.manage_own",
    "profile.remove_photo": "profile.manage_own",
    "api.health": None,
    "api.api_dashboard": "dashboard.view",
    "api.api_books": "search.view",
    "api.api_book": "search.view",
    "api.api_search_suggest": "search.view",
    "api.api_search": "search.view",
    "api.api_verify": "verification.view",
    "api.api_checkout": "borrowing.manage",
    "api.api_checkin": "borrowing.manage",
    "api.api_transactions": "borrowing.view_own",
    "api.api_fines": "fines.view_own",
    "api.api_reservations": "reservations.manage_own",
    "api.api_clearance": "clearance.request",
}

NAV_SECTIONS = [
    {
        "label": "Main",
        "items": [
            {"label": "Dashboard", "endpoint": "dashboard.index", "icon": "fa-gauge-high", "permission": "dashboard.view"},
        ],
    },
    {
        "label": "Library Services",
        "items": [
            {"label": "Book Search", "endpoint": "search.index", "icon": "fa-magnifying-glass", "permission": "search.view"},
            {"label": "Reservations", "endpoint": "reservations.index", "icon": "fa-bookmark", "permission": "reservations.manage_own"},
            {"label": "Borrowing Logs", "endpoint": "borrowing.index", "icon": "fa-right-left", "permission": "borrowing.view_own"},
            {"label": "Due Dates & Fines", "endpoint": "fines.index", "icon": "fa-clock", "permission": "fines.view_own"},
            {"label": "E-Books", "endpoint": "ebooks.index", "icon": "fa-tablet-screen-button", "permission": "ebooks.view_own"},
            {"label": "Library Clearance", "endpoint": "clearance.index", "icon": "fa-clipboard-check", "permission": "clearance.request"},
            {"label": "Lost / Damaged", "endpoint": "lost_damaged.index", "icon": "fa-triangle-exclamation", "permission": "lost_damaged.report"},
        ],
    },
    {
        "label": "Staff Tools",
        "items": [
            {"label": "Book Inventory", "endpoint": "inventory.index", "icon": "fa-book-open", "permission": "inventory.view"},
            {"label": "ID Verification", "endpoint": "verification.index", "icon": "fa-id-card", "permission": "verification.view"},
            {"label": "Reports & Analytics", "endpoint": "analytics.index", "icon": "fa-chart-line", "permission": "reports.view"},
        ],
    },
    {
        "label": "Administration",
        "items": [
            {"label": "User Management", "endpoint": "users.index", "icon": "fa-users-gear", "permission": "users.manage"},
            {"label": "Activity Log", "endpoint": "activity.index", "icon": "fa-shield-halved", "permission": "audit.view"},
        ],
    },
]

STAFF_TOOL_ENDPOINTS = frozenset({
    "inventory.index", "inventory.add", "inventory.detail", "inventory.edit",
    "verification.index", "analytics.index", "borrowing.index", "fines.index",
    "reservations.index", "lost_damaged.index", "ebooks.index",
})


def has_permission(role, permission):
    if not permission:
        return True
    perms = ROLE_PERMISSIONS.get(role, set())
    if permission in perms:
        return True
    aliases = {
        "reservations.manage_own": "reservations.manage",
        "borrowing.view_own": "borrowing.manage",
        "fines.view_own": "fines.manage",
        "ebooks.view_own": "ebooks.manage",
        "clearance.request": "clearance.manage",
        "lost_damaged.report": "lost_damaged.manage",
    }
    mapped = aliases.get(permission)
    return mapped in perms if mapped else False


def can_access_endpoint(endpoint, role=None):
    role = role or (current_user.role if current_user.is_authenticated else None)
    if not role:
        return False
    if endpoint in PUBLIC_ENDPOINTS:
        return True
    if endpoint not in ENDPOINT_PERMISSIONS:
        return False
    permission = ENDPOINT_PERMISSIONS[endpoint]
    if permission is None:
        return True
    return has_permission(role, permission)


def get_nav_for_role(role):
    sections = []
    for section in NAV_SECTIONS:
        items = [item for item in section["items"] if has_permission(role, item["permission"])]
        if items:
            sections.append({"label": section["label"], "nav_items": items})
    return sections


def get_role_label(role):
    return ROLE_LABELS.get(role, role or "Unknown")


def get_forbidden_context(endpoint=None):
    endpoint = endpoint or request.endpoint
    permission = ENDPOINT_PERMISSIONS.get(endpoint)
    hints = {
        "users.manage": "User and role management is restricted to Administrators.",
        "audit.view": "The activity log is available to Administrators only.",
        "verification.manage": "Changing library card status requires Administrator approval.",
        "reports.manage": "Exporting system reports is an Administrator-only action.",
        "fines.waive": "Fine waivers can only be issued by an Administrator.",
        "inventory.manage": "Inventory changes require Staff or Administrator access.",
        "inventory.view": "Inventory is visible to Staff and Administrators only.",
    }
    if permission and permission in hints:
        return hints[permission]
    if endpoint and endpoint.startswith("users."):
        return "User management is restricted to Administrators."
    if endpoint and endpoint.startswith("analytics."):
        return "Reports and analytics require Staff or Administrator access."
    return "This page requires permissions your role does not have. Contact an Administrator if you need access."


def check_endpoint_access(endpoint):
    if not current_user.is_authenticated:
        return True
    if endpoint in PUBLIC_ENDPOINTS:
        return True
    if endpoint not in ENDPOINT_PERMISSIONS:
        return False
    permission = ENDPOINT_PERMISSIONS[endpoint]
    if permission is None:
        return True
    return has_permission(current_user.role, permission)


def require_permission(permission):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not has_permission(current_user.role, permission):
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def require_roles(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def api_response(data=None, message="OK", status=200):
    return jsonify({"success": status < 400, "message": message, "data": data}), status


def api_error(message, status=400):
    return api_response(None, message, status)


def get_json():
    return request.get_json(silent=True) or {}
