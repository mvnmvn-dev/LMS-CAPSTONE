"""RBAC route protection tests — ensures every endpoint is registered or whitelisted."""

import pytest

from app import create_app
from services.rbac import ENDPOINT_PERMISSIONS, PUBLIC_ENDPOINTS


@pytest.fixture
def app():
    application = create_app()
    application.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret",
    })
    return application


def _collect_endpoints(app):
    endpoints = set()
    for rule in app.url_map.iter_rules():
        if rule.endpoint:
            endpoints.add(rule.endpoint)
    return endpoints


def test_every_route_has_permission_or_is_public(app):
    """Catch forgotten route protection before deployment."""
    endpoints = _collect_endpoints(app)
    unregistered = []
    for endpoint in sorted(endpoints):
        if endpoint in PUBLIC_ENDPOINTS:
            continue
        if endpoint in ENDPOINT_PERMISSIONS:
            continue
        unregistered.append(endpoint)

    assert not unregistered, (
        "Routes missing from ENDPOINT_PERMISSIONS or PUBLIC_ENDPOINTS:\n"
        + "\n".join(f"  - {ep}" for ep in unregistered)
    )


def test_patron_cannot_access_staff_routes(client, app):
    """Student role should get 403 on staff-only pages."""
    with app.app_context():
        from models.database import execute
        from models.user import User
        try:
            execute(
                """INSERT INTO users (username, password_hash, email, full_name, role, library_id, account_status)
                   VALUES ('test_patron', %s, 'tp@test.edu', 'Test Patron', 'patron', 'LIB-TEST-001', 'active')
                   ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash)""",
                (User.hash_password("password123"),),
            )
        except Exception:
            pytest.skip("Database not available for integration test")

    client.post("/login", data={"username": "test_patron", "password": "password123"})
    staff_only_paths = [
        "/inventory/",
        "/verification/",
        "/reports/",
        "/admin/users/",
        "/admin/activity/",
    ]
    for path in staff_only_paths:
        response = client.get(path)
        assert response.status_code == 403, f"Expected 403 for patron at {path}, got {response.status_code}"


def test_staff_cannot_access_admin_users(client, app):
    with app.app_context():
        from models.database import execute
        from models.user import User
        try:
            execute(
                """INSERT INTO users (username, password_hash, email, full_name, role, library_id, account_status)
                   VALUES ('test_staff', %s, 'ts@test.edu', 'Test Staff', 'staff', 'LIB-TEST-002', 'active')
                   ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash)""",
                (User.hash_password("password123"),),
            )
        except Exception:
            pytest.skip("Database not available for integration test")

    client.post("/login", data={"username": "test_staff", "password": "password123"})
    assert client.get("/admin/users/").status_code == 403
    assert client.get("/admin/activity/").status_code == 403


def test_role_permissions_split():
    from services.rbac import ROLE_PERMISSIONS

    staff = ROLE_PERMISSIONS["staff"]
    admin = ROLE_PERMISSIONS["admin"]

    assert "users.manage" not in staff
    assert "audit.view" not in staff
    assert "fines.waive" not in staff
    assert "verification.manage" not in staff
    assert "reports.manage" not in staff

    assert "users.manage" in admin
    assert "audit.view" in admin
    assert "fines.waive" in admin
    assert "verification.manage" in admin
    assert "reports.manage" in admin


def test_disabled_account_invalidates_session(client, app):
    """A disabled user is logged out on their next request."""
    with app.app_context():
        from models.database import execute, query_one
        from models.user import User
        from services.users_service import update_user
        try:
            execute(
                """INSERT INTO users (username, password_hash, email, full_name, role, library_id, account_status)
                   VALUES ('test_disable_patron', %s, 'tdp@test.edu', 'Disable Patron', 'patron', 'LIB-TEST-003', 'active')
                   ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash), account_status = 'active'""",
                (User.hash_password("password123"),),
            )
            patron = query_one("SELECT id FROM users WHERE username = 'test_disable_patron'")
            execute(
                """INSERT INTO users (username, password_hash, email, full_name, role, library_id, account_status)
                   VALUES ('test_disable_admin', %s, 'tda@test.edu', 'Disable Admin', 'admin', 'LIB-TEST-004', 'active')
                   ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash)""",
                (User.hash_password("password123"),),
            )
            admin = query_one("SELECT id FROM users WHERE username = 'test_disable_admin'")
        except Exception:
            pytest.skip("Database not available for integration test")

    client.post("/login", data={"username": "test_disable_patron", "password": "password123"})
    assert client.get("/dashboard/").status_code == 200

    with app.app_context():
        update_user(patron["id"], {"account_status": "disabled"}, admin["id"])

    response = client.get("/dashboard/")
    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")


def test_password_reset_invalidates_session(client, app):
    """An admin password reset invalidates the user's existing session."""
    with app.app_context():
        from models.database import execute, query_one
        from models.user import User
        from services.users_service import reset_password
        try:
            execute(
                """INSERT INTO users (username, password_hash, email, full_name, role, library_id, account_status)
                   VALUES ('test_reset_patron', %s, 'trp@test.edu', 'Reset Patron', 'patron', 'LIB-TEST-005', 'active')
                   ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash), account_status = 'active'""",
                (User.hash_password("password123"),),
            )
            patron = query_one("SELECT id FROM users WHERE username = 'test_reset_patron'")
            execute(
                """INSERT INTO users (username, password_hash, email, full_name, role, library_id, account_status)
                   VALUES ('test_reset_admin', %s, 'tra@test.edu', 'Reset Admin', 'admin', 'LIB-TEST-006', 'active')
                   ON DUPLICATE KEY UPDATE password_hash = VALUES(password_hash)""",
                (User.hash_password("password123"),),
            )
            admin = query_one("SELECT id FROM users WHERE username = 'test_reset_admin'")
        except Exception:
            pytest.skip("Database not available for integration test")

    client.post("/login", data={"username": "test_reset_patron", "password": "password123"})
    assert client.get("/dashboard/").status_code == 200

    with app.app_context():
        reset_password(patron["id"], admin["id"])

    response = client.get("/dashboard/")
    assert response.status_code == 302
    assert "/login" in response.headers.get("Location", "")
