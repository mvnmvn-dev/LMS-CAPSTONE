from datetime import datetime



from flask import Flask, flash, redirect, render_template, request, session, url_for

from flask_login import LoginManager, current_user, logout_user

from flask_wtf.csrf import CSRFProtect



from config import Config

from models.database import close_db

from models.user import User

from routes.activity import activity_bp

from routes.analytics import analytics_bp

from routes.api_gateway import api_bp

from routes.auth import auth_bp

from routes.borrowing import borrowing_bp

from routes.clearance import clearance_bp

from routes.dashboard import dashboard_bp

from routes.ebooks import ebooks_bp

from routes.fines import fines_bp

from routes.inventory import inventory_bp

from routes.lost_damaged import reports_lost_bp

from routes.notifications import notifications_bp

from routes.profile import profile_bp

from routes.reservations import reservations_bp

from routes.search import search_bp

from routes.users import users_bp

from routes.verification import verification_bp

from services.analytics_service import log_event

from services.notification_service import get_unread_count, get_user_notifications

from services.rbac import (

    STAFF_TOOL_ENDPOINTS,

    check_endpoint_access,

    get_forbidden_context,

    get_nav_for_role,

    get_role_label,

    has_permission,

)



csrf = CSRFProtect()





def create_app():

    app = Flask(__name__)

    app.config.from_object(Config)

    app.config["WTF_CSRF_CHECK_DEFAULT"] = True



    with app.app_context():

        try:

            from services.db_upgrade import ensure_schema_upgrades

            ensure_schema_upgrades()

        except Exception:

            pass



    login_manager = LoginManager()

    login_manager.login_view = "auth.login"

    login_manager.init_app(app)

    csrf.init_app(app)



    @login_manager.user_loader

    def load_user(user_id):

        return User.get_by_id(int(user_id))



    app.teardown_appcontext(close_db)



    app.register_blueprint(auth_bp)

    app.register_blueprint(dashboard_bp)

    app.register_blueprint(inventory_bp)

    app.register_blueprint(search_bp)

    app.register_blueprint(verification_bp)

    app.register_blueprint(borrowing_bp)

    app.register_blueprint(fines_bp)

    app.register_blueprint(reservations_bp)

    app.register_blueprint(ebooks_bp)

    app.register_blueprint(reports_lost_bp)

    app.register_blueprint(clearance_bp)

    app.register_blueprint(analytics_bp)

    app.register_blueprint(notifications_bp)

    app.register_blueprint(profile_bp)

    app.register_blueprint(users_bp)

    app.register_blueprint(activity_bp)

    app.register_blueprint(api_bp)



    def _force_logout(message):
        logout_user()
        flash(message, "warning")
        return redirect(url_for("auth.login"))

    @app.before_request

    def enforce_rbac():

        if not current_user.is_authenticated:

            return

        fresh_user = User.get_by_id(current_user.id)
        if not fresh_user or fresh_user.account_status != "active":
            return _force_logout(
                "Your account has been disabled. Contact the library administrator."
            )

        stored_version = session.get("session_version")
        if stored_version is None:
            session["session_version"] = fresh_user.session_version
        elif stored_version != fresh_user.session_version:
            return _force_logout("Your session has expired. Please log in again.")

        if fresh_user.must_change_password and request.endpoint not in (
            "auth.change_password",
            "auth.logout",
            "static",
        ):

            return redirect(url_for("auth.change_password"))



        endpoint = request.endpoint

        if endpoint and not check_endpoint_access(endpoint):

            from flask import abort

            log_event(

                "permission_denied",

                user_id=current_user.id,

                metadata={"endpoint": endpoint, "path": request.path, "method": request.method},

            )

            abort(403)



    @app.context_processor

    def inject_globals():

        ctx = {"now": datetime.now()}

        if current_user.is_authenticated:

            ctx["nav_sections"] = get_nav_for_role(current_user.role)

            ctx["has_perm"] = lambda p: has_permission(current_user.role, p)

            ctx["user_role"] = current_user.role

            ctx["role_label"] = get_role_label(current_user.role)

            ctx["show_staff_banner"] = request.endpoint in STAFF_TOOL_ENDPOINTS and current_user.role in ("staff", "admin")

            ctx["notifications"] = get_user_notifications(current_user.id, limit=8)

            ctx["unread_count"] = get_unread_count(current_user.id)

        else:

            ctx["nav_sections"] = []

            ctx["has_perm"] = lambda p: False

            ctx["user_role"] = None

            ctx["role_label"] = None

            ctx["show_staff_banner"] = False

            ctx["notifications"] = []

            ctx["unread_count"] = 0

        return ctx



    @app.errorhandler(403)

    def forbidden(e):

        return render_template(

            "errors/403.html",

            forbidden_message=get_forbidden_context(),

            attempted_endpoint=request.endpoint,

        ), 403



    @app.errorhandler(404)

    def not_found(e):

        return render_template("errors/404.html"), 404



    @app.after_request

    def prevent_login_bg_cache(response):

        path = request.path.replace("\\", "/").lower()

        if "/static/images/" in path and "login" in path and "logo" not in path:

            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"

            response.headers["Pragma"] = "no-cache"

        if request.endpoint == "auth.login":

            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"

        return response



    return app





if __name__ == "__main__":

    application = create_app()

    application.run(debug=True, host="0.0.0.0", port=5000)

