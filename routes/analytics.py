from datetime import datetime



from flask import Blueprint, Response, render_template, request

from flask_login import current_user, login_required



from services.analytics_service import get_dashboard_stats, log_event

from services.reports_service import (

    export_report_csv,

    export_report_html,

    get_reports_summary,

    serialize_for_json,

)

from services.rbac import api_response, require_permission, require_roles



analytics_bp = Blueprint("analytics", __name__, url_prefix="/reports")





@analytics_bp.route("/")

@login_required

@require_roles("staff", "admin")

def index():

    summary = get_reports_summary(role=current_user.role)

    return render_template(

        "reports/index.html",

        summary=summary,

        breadcrumbs=[("Reports", None)],

        page_title="Library Reports & Analytics",

        staff_context="staff",

    )





@analytics_bp.route("/api/data")

@login_required

@require_roles("staff", "admin")

def api_data():

    summary = get_reports_summary()

    return api_response(serialize_for_json(summary))





@analytics_bp.route("/export")

@login_required

@require_permission("reports.manage")

def export():

    summary = get_reports_summary(role=current_user.role)

    fmt = request.args.get("format", "csv").lower()



    log_event(

        "report_exported",

        user_id=current_user.id,

        metadata={"format": fmt},

    )



    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")



    if fmt == "html":

        content = export_report_html(summary)

        return Response(

            content,

            mimetype="text/html",

            headers={

                "Content-Disposition": f"attachment; filename=lms_report_{timestamp}.html"

            },

        )



    content = export_report_csv(summary)

    return Response(

        content,

        mimetype="text/csv",

        headers={

            "Content-Disposition": f"attachment; filename=lms_report_{timestamp}.csv"

        },

    )

