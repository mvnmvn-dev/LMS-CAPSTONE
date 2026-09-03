import csv
import io
from datetime import date, datetime
from decimal import Decimal

from models.database import query_all, query_one
from services.analytics_service import get_dashboard_stats, log_event
from services.fines_service import update_overdue_status


def get_module_analytics():
  """Aggregate chart-ready data across all LMS modules."""
  return {
    "borrowing": {
      "by_status": query_all(
        "SELECT status, COUNT(*) AS count FROM transactions GROUP BY status"
      ),
      "monthly": list(
        reversed(
          query_all(
            """SELECT DATE_FORMAT(checkout_date, '%Y-%m') AS period,
                      COUNT(*) AS count
               FROM transactions
               GROUP BY period
               ORDER BY period DESC
               LIMIT 6"""
          )
        )
      ),
    },
    "reservations": {
      "by_status": query_all(
        "SELECT status, COUNT(*) AS count FROM reservations GROUP BY status"
      ),
    },
    "fines": {
      "by_status": query_all(
        """SELECT status, COUNT(*) AS count,
                  COALESCE(SUM(amount), 0) AS total
           FROM fines GROUP BY status"""
      ),
      "revenue_trend": list(
        reversed(
          query_all(
            """SELECT DATE(paid_at) AS day, SUM(amount) AS revenue
               FROM fines
               WHERE status = 'paid' AND paid_at IS NOT NULL
               GROUP BY DATE(paid_at)
               ORDER BY day DESC
               LIMIT 14"""
          )
        )
      ),
    },
    "ebooks": {
      "by_format": query_all(
        "SELECT format, COUNT(*) AS count FROM ebooks GROUP BY format"
      ),
      "active_access": query_one(
        "SELECT COUNT(*) AS c FROM ebook_access WHERE expires_at > NOW()"
      )["c"],
      "total_grants": query_one("SELECT COUNT(*) AS c FROM ebook_access")["c"],
    },
    "clearance": {
      "by_status": query_all(
        "SELECT status, COUNT(*) AS count FROM clearance_requests GROUP BY status"
      ),
    },
    "lost_damaged": {
      "by_type": query_all(
        """SELECT report_type, COUNT(*) AS count
           FROM lost_damaged_reports GROUP BY report_type"""
      ),
      "by_status": query_all(
        "SELECT status, COUNT(*) AS count FROM lost_damaged_reports GROUP BY status"
      ),
    },
    "inventory_status": query_all(
      "SELECT status, COUNT(*) AS count FROM copies GROUP BY status"
    ),
    "genre_distribution": query_all(
      "SELECT genre, COUNT(*) AS count FROM books GROUP BY genre ORDER BY count DESC"
    ),
    "peak_hours": query_all(
      """SELECT HOUR(created_at) AS hour, COUNT(*) AS events
         FROM analytics_log
         GROUP BY HOUR(created_at)
         ORDER BY hour ASC"""
    ),
    "module_events": query_all(
      """SELECT event_type, COUNT(*) AS count
         FROM analytics_log
         GROUP BY event_type
         ORDER BY count DESC
         LIMIT 12"""
    ),
    "users_by_role": query_all(
      "SELECT role, COUNT(*) AS count FROM users GROUP BY role"
    ),
  }


def get_personal_chart_data(user_id):
  """Chart data scoped to a single patron."""
  return {
    "borrowing": {
      "by_status": query_all(
        """SELECT status, COUNT(*) AS count
           FROM transactions WHERE user_id = %s GROUP BY status""",
        (user_id,),
      ),
    },
    "reservations": {
      "by_status": query_all(
        """SELECT status, COUNT(*) AS count
           FROM reservations WHERE user_id = %s GROUP BY status""",
        (user_id,),
      ),
    },
    "fines": {
      "by_status": query_all(
        """SELECT status, COUNT(*) AS count,
                  COALESCE(SUM(amount), 0) AS total
           FROM fines WHERE user_id = %s GROUP BY status""",
        (user_id,),
      ),
    },
  }


def get_reports_summary(role="staff"):
  update_overdue_status()
  modules = get_module_analytics()
  dashboard = get_dashboard_stats(role=role)
  return {
    "dashboard": dashboard,
    "modules": modules,
    "generated_at": datetime.now(),
    "fine_revenue": modules["fines"]["revenue_trend"],
    "peak_hours": modules["peak_hours"],
    "genre_distribution": modules["genre_distribution"],
    "inventory_status": modules["inventory_status"],
    "analysis": generate_analysis_narrative(dashboard, modules),
  }


def serialize_for_json(obj):
  if isinstance(obj, (datetime, date)):
    return obj.isoformat()
  if isinstance(obj, Decimal):
    return float(obj)
  if isinstance(obj, dict):
    return {k: serialize_for_json(v) for k, v in obj.items()}
  if isinstance(obj, (list, tuple)):
    return [serialize_for_json(i) for i in obj]
  return obj


def _sum_counts(rows, key="count"):
  return sum(int(r.get(key) or 0) for r in rows)


def _pct(part, whole):
  if not whole:
    return 0
  return round(part / whole * 100, 1)


def generate_analysis_narrative(dashboard, modules):
  """Build human-readable insights for reports and exports."""
  insights = []
  total_copies = dashboard.get("total_copies") or 0
  available = dashboard.get("available_copies") or 0
  total_books = dashboard.get("total_books") or 0

  insights.append(
    {
      "module": "Inventory",
      "title": "Collection overview",
      "text": (
        f"The library catalog contains {total_books} unique titles and "
        f"{total_copies} physical copies, with {available} currently available "
        f"({_pct(available, total_copies)}% of stock)."
      ),
    }
  )

  inv_rows = modules.get("inventory_status") or []
  borrowed = next(
    (int(r["count"]) for r in inv_rows if r.get("status") == "borrowed"), 0
  )
  insights.append(
    {
      "module": "Borrowing",
      "title": "Circulation activity",
      "text": (
        f"There are {dashboard.get('active_loans', 0)} active loans and "
        f"{dashboard.get('overdue_loans', 0)} overdue items. "
        f"{borrowed} copies are currently marked as borrowed."
      ),
    }
  )

  overdue = dashboard.get("overdue_loans") or 0
  if overdue:
    insights.append(
      {
        "module": "Fines",
        "title": "Overdue attention needed",
        "text": (
          f"{overdue} loan(s) are overdue. Unpaid fines total "
          f"₱{dashboard.get('unpaid_fines_total', 0):.2f}."
        ),
      }
    )
  else:
    insights.append(
      {
        "module": "Fines",
        "title": "Fine collection status",
        "text": (
          f"No overdue loans detected. Outstanding unpaid fines total "
          f"₱{dashboard.get('unpaid_fines_total', 0):.2f}."
        ),
      }
    )

  res_rows = modules.get("reservations", {}).get("by_status") or []
  pending_holds = sum(
    int(r["count"])
    for r in res_rows
    if r.get("status") in ("pending", "ready")
  )
  insights.append(
    {
      "module": "Reservations",
      "title": "Hold queue",
      "text": (
        f"{pending_holds} reservation(s) are pending or ready for pickup, "
        f"indicating current demand for unavailable titles."
      ),
    }
  )

  ebook = modules.get("ebooks") or {}
  insights.append(
    {
      "module": "E-Books",
      "title": "Digital lending",
      "text": (
        f"{ebook.get('total_grants', 0)} e-book access grant(s) have been issued, "
        f"with {ebook.get('active_access', 0)} currently active."
      ),
    }
  )

  clearance_rows = modules.get("clearance", {}).get("by_status") or []
  blocked = next(
    (int(r["count"]) for r in clearance_rows if r.get("status") == "blocked"), 0
  )
  insights.append(
    {
      "module": "Clearance",
      "title": "Graduation clearance",
      "text": (
        f"{_sum_counts(clearance_rows)} clearance request(s) on record"
        + (f", including {blocked} blocked." if blocked else ".")
      ),
    }
  )

  ld_rows = modules.get("lost_damaged", {}).get("by_type") or []
  if ld_rows:
    lost = next(
      (int(r["count"]) for r in ld_rows if r.get("report_type") == "lost"), 0
    )
    damaged = next(
      (int(r["count"]) for r in ld_rows if r.get("report_type") == "damaged"), 0
    )
    insights.append(
      {
        "module": "Lost / Damaged",
        "title": "Asset incidents",
        "text": (
          f"{lost} lost and {damaged} damaged item report(s) have been filed."
        ),
      }
    )

  genres = modules.get("genre_distribution") or []
  if genres:
    top = genres[0]
    genre_name = top.get("genre") or "Uncategorized"
    genre_count = int(top.get("count") or 0)
    insights.append(
      {
        "module": "Search & Catalog",
        "title": "Genre distribution",
        "text": (
          f'"{genre_name}" is the largest genre with {genre_count} title(s) '
          f"({_pct(genre_count, total_books)}% of the catalog)."
        ),
      }
    )

  peak = modules.get("peak_hours") or []
  if peak:
    busiest = max(peak, key=lambda r: int(r.get("events") or 0))
    hour = int(busiest.get("hour") or 0)
    insights.append(
      {
        "module": "Analytics",
        "title": "Peak usage",
        "text": (
          f"Peak system activity occurs around {hour:02d}:00 with "
          f"{busiest.get('events', 0)} logged event(s)."
        ),
      }
    )

  most_borrowed = dashboard.get("most_borrowed") or []
  if most_borrowed:
    top_book = most_borrowed[0]
    insights.append(
      {
        "module": "Borrowing",
        "title": "Most popular title",
        "text": (
          f'"{top_book["title"]}" leads borrowing with '
          f'{top_book["borrow_count"]} checkout(s).'
        ),
      }
    )

  return insights


def get_chart_data(role="patron", user_id=None):
  """Return chart-ready data for dashboard visualizations."""
  if role in ("staff", "admin"):
    return {"scope": "system", "modules": get_module_analytics()}
  return {"scope": "personal", "modules": get_personal_chart_data(user_id)}


def export_report_csv(summary):
  """Generate a multi-section CSV report."""
  output = io.StringIO()
  writer = csv.writer(output)
  generated = summary["generated_at"].strftime("%Y-%m-%d %H:%M:%S")

  writer.writerow(["Library Management System — Analytics Report"])
  writer.writerow(["Generated", generated])
  writer.writerow([])

  writer.writerow(["EXECUTIVE SUMMARY"])
  for item in summary.get("analysis", []):
    writer.writerow([item["module"], item["title"], item["text"]])
  writer.writerow([])

  d = summary["dashboard"]
  writer.writerow(["KEY METRICS"])
  writer.writerow(["Total Books", d.get("total_books", 0)])
  writer.writerow(["Total Copies", d.get("total_copies", 0)])
  writer.writerow(["Available Copies", d.get("available_copies", 0)])
  writer.writerow(["Active Loans", d.get("active_loans", 0)])
  writer.writerow(["Overdue Loans", d.get("overdue_loans", 0)])
  writer.writerow(["Pending Reservations", d.get("pending_reservations", 0)])
  writer.writerow(["Unpaid Fines (PHP)", f"{d.get('unpaid_fines_total', 0):.2f}"])
  writer.writerow([])

  modules = summary.get("modules") or {}
  sections = [
    ("BORROWING BY STATUS", modules.get("borrowing", {}).get("by_status"), ["status", "count"]),
    ("RESERVATIONS BY STATUS", modules.get("reservations", {}).get("by_status"), ["status", "count"]),
    ("FINES BY STATUS", modules.get("fines", {}).get("by_status"), ["status", "count", "total"]),
    ("INVENTORY BY STATUS", modules.get("inventory_status"), ["status", "count"]),
    ("GENRE DISTRIBUTION", modules.get("genre_distribution"), ["genre", "count"]),
    ("E-BOOK FORMATS", modules.get("ebooks", {}).get("by_format"), ["format", "count"]),
    ("CLEARANCE REQUESTS", modules.get("clearance", {}).get("by_status"), ["status", "count"]),
    ("LOST/DAMAGED BY TYPE", modules.get("lost_damaged", {}).get("by_type"), ["report_type", "count"]),
    ("USERS BY ROLE", modules.get("users_by_role"), ["role", "count"]),
    ("MODULE EVENTS", modules.get("module_events"), ["event_type", "count"]),
  ]

  for title, rows, cols in sections:
    writer.writerow([title])
    writer.writerow(cols)
    for row in rows or []:
      writer.writerow([row.get(c, "") for c in cols])
    writer.writerow([])

  writer.writerow(["MOST BORROWED TITLES"])
  writer.writerow(["title", "borrow_count"])
  for item in d.get("most_borrowed") or []:
    writer.writerow([item.get("title"), item.get("borrow_count")])

  return output.getvalue()


def export_report_html(summary):
  """Generate a printable HTML analysis report."""
  generated = summary["generated_at"].strftime("%B %d, %Y at %I:%M %p")
  d = summary["dashboard"]
  modules = summary.get("modules") or {}

  def table_rows(rows, cols):
    if not rows:
      return "<tr><td colspan='99'>No data</td></tr>"
    body = ""
    for row in rows:
      body += "<tr>" + "".join(f"<td>{row.get(c, '')}</td>" for c in cols) + "</tr>"
    return body

  insights_html = "".join(
    f"""<div class="insight">
      <span class="insight-module">{i['module']}</span>
      <h3>{i['title']}</h3>
      <p>{i['text']}</p>
    </div>"""
    for i in summary.get("analysis", [])
  )

  return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>LMS Analytics Report — {generated}</title>
  <style>
    body {{ font-family: Inter, system-ui, sans-serif; color: #0f172a; margin: 2rem; line-height: 1.5; }}
    h1 {{ font-size: 1.5rem; margin-bottom: 0.25rem; }}
    .meta {{ color: #64748b; font-size: 0.875rem; margin-bottom: 2rem; }}
    .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }}
    .metric {{ border: 1px solid #e2e8f0; border-radius: 0.5rem; padding: 1rem; }}
    .metric-label {{ font-size: 0.75rem; color: #64748b; text-transform: uppercase; }}
    .metric-value {{ font-size: 1.5rem; font-weight: 700; }}
    .insights {{ margin-bottom: 2rem; }}
    .insight {{ border-left: 3px solid #6366f1; padding: 0.75rem 1rem; margin-bottom: 0.75rem; background: #f8fafc; }}
    .insight-module {{ font-size: 0.6875rem; font-weight: 700; color: #6366f1; text-transform: uppercase; }}
    .insight h3 {{ margin: 0.25rem 0; font-size: 0.9375rem; }}
    .insight p {{ margin: 0; font-size: 0.8125rem; color: #475569; }}
    h2 {{ font-size: 1rem; margin: 1.5rem 0 0.75rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.35rem; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.8125rem; margin-bottom: 1rem; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 0.5rem 0.75rem; text-align: left; }}
    th {{ background: #f8fafc; font-weight: 600; }}
    @media print {{ body {{ margin: 1rem; }} }}
  </style>
</head>
<body>
  <h1>Library Management System — Analytics Report</h1>
  <p class="meta">Generated {generated}</p>

  <div class="metrics">
    <div class="metric"><div class="metric-label">Total Books</div><div class="metric-value">{d.get('total_books', 0)}</div></div>
    <div class="metric"><div class="metric-label">Active Loans</div><div class="metric-value">{d.get('active_loans', 0)}</div></div>
    <div class="metric"><div class="metric-label">Overdue</div><div class="metric-value">{d.get('overdue_loans', 0)}</div></div>
    <div class="metric"><div class="metric-label">Unpaid Fines</div><div class="metric-value">₱{d.get('unpaid_fines_total', 0):.2f}</div></div>
  </div>

  <h2>Analysis &amp; Insights</h2>
  <div class="insights">{insights_html}</div>

  <h2>Borrowing by Status</h2>
  <table><thead><tr><th>Status</th><th>Count</th></tr></thead>
  <tbody>{table_rows(modules.get('borrowing', {}).get('by_status'), ['status', 'count'])}</tbody></table>

  <h2>Reservations by Status</h2>
  <table><thead><tr><th>Status</th><th>Count</th></tr></thead>
  <tbody>{table_rows(modules.get('reservations', {}).get('by_status'), ['status', 'count'])}</tbody></table>

  <h2>Fines by Status</h2>
  <table><thead><tr><th>Status</th><th>Count</th><th>Total (PHP)</th></tr></thead>
  <tbody>{table_rows(modules.get('fines', {}).get('by_status'), ['status', 'count', 'total'])}</tbody></table>

  <h2>Inventory by Status</h2>
  <table><thead><tr><th>Status</th><th>Copies</th></tr></thead>
  <tbody>{table_rows(modules.get('inventory_status'), ['status', 'count'])}</tbody></table>

  <h2>Genre Distribution</h2>
  <table><thead><tr><th>Genre</th><th>Books</th></tr></thead>
  <tbody>{table_rows(modules.get('genre_distribution'), ['genre', 'count'])}</tbody></table>

  <h2>E-Book Formats</h2>
  <table><thead><tr><th>Format</th><th>Count</th></tr></thead>
  <tbody>{table_rows(modules.get('ebooks', {}).get('by_format'), ['format', 'count'])}</tbody></table>

  <h2>Clearance Requests</h2>
  <table><thead><tr><th>Status</th><th>Count</th></tr></thead>
  <tbody>{table_rows(modules.get('clearance', {}).get('by_status'), ['status', 'count'])}</tbody></table>

  <h2>Lost / Damaged Reports</h2>
  <table><thead><tr><th>Type</th><th>Count</th></tr></thead>
  <tbody>{table_rows(modules.get('lost_damaged', {}).get('by_type'), ['report_type', 'count'])}</tbody></table>

  <h2>Most Borrowed Titles</h2>
  <table><thead><tr><th>Title</th><th>Borrows</th></tr></thead>
  <tbody>{table_rows(d.get('most_borrowed'), ['title', 'borrow_count'])}</tbody></table>
</body>
</html>"""
