# Library Management System — Entire Workflow

## 1. System overview

The Library Management System (LMS) is a Flask-based web application backed by MySQL. It supports three roles: **Student/Patron**, **Librarian Staff**, and **Administrator**. The system manages the complete physical and digital library lifecycle: account access, library-card eligibility, catalog discovery, reservations, borrowing, returns, renewals, fines, e-book access, lost or damaged items, clearance, reporting, notifications, and administrative auditing.

The main application flow is:

> **Login → Role-based dashboard → Search or staff operation → Transaction/business-rule validation → Database update → Notification and audit log → Follow-up action or completion**

The web interface is available through Flask routes, while selected functions are also exposed through the REST gateway at `/api/v1/*`.

## 2. Actors and responsibilities

| Actor | Main responsibilities |
|---|---|
| **Student / Patron** | Search books, place or cancel reservations, view borrowing history, renew own loans, view and pay own fines, access e-books, report lost or damaged borrowed items, request clearance, manage own profile, and read notifications. |
| **Librarian Staff** | Perform checkout and check-in, manage books and copies, verify patron IDs, manage reservations, record fine payments, manage e-books, process lost/damaged reports, review clearance requests, and view reports. |
| **Administrator** | Perform all staff functions plus manage users and roles, change library-card status, waive fines with a reason, export reports, and inspect the activity/security log. |
| **System** | Enforce authentication and authorization, validate eligibility, update item and transaction states, calculate overdue fines, send notifications, and write audit events. |

## 3. Startup and system initialization workflow

1. The application starts through `app.py` and loads configuration from `config.py`.
2. Flask, Flask-Login, and CSRF protection are initialized.
3. A database schema-upgrade check runs inside the application context.
4. All web blueprints are registered, including authentication, dashboard, inventory, search, verification, borrowing, fines, reservations, e-books, lost/damaged reports, clearance, analytics, notifications, profile, users, activity, and API routes.
5. Flask-Login loads the current user from the session for each request.
6. The application connects to MySQL using the schema in `schema.sql`.
7. The system can be initialized with `python init_db.py` and started with `python app.py`.
8. The user opens `http://localhost:5000` and is redirected to the login page unless already authenticated.

## 4. Authentication and session workflow

### 4.1 Login

1. The user opens `/login`.
2. The user submits a username and password.
3. The system looks up the user account.
4. The system rejects the request if the account is temporarily locked because of repeated failed attempts.
5. The system rejects disabled accounts.
6. If the password is incorrect, the failed-login counter is updated. Five failed attempts cause a configurable five-minute lockout.
7. If credentials are valid, the failed-login counter is cleared and the user is logged in.
8. The session is marked permanent and stores the user’s session version.
9. If `must_change_password` is set, the user is redirected to `/change-password` before using the rest of the system.
10. Otherwise, the user is redirected to a safe requested page or to the role-appropriate dashboard.

### 4.2 Password change

1. The user supplies the current password, a new password, and confirmation.
2. The system checks the current password, requires at least eight characters, and checks that the two new passwords match.
3. The password hash is updated and `must_change_password` is cleared.
4. A `password_changed` audit event is recorded.

### 4.3 Request-level security checks

For every authenticated request, the system:

1. Reloads the user from the database.
2. Logs the user out if the account is no longer active.
3. Logs the user out if the stored session version has changed.
4. Redirects users who must change their password.
5. Checks the endpoint against the role-permission matrix.
6. Records a `permission_denied` event and returns HTTP 403 when access is not allowed.

Logout is available at `/logout` and ends the Flask-Login session.

## 5. Dashboard workflow

1. After login, the user opens `/dashboard/`.
2. The system updates overdue statuses for the current patron, or for all users when a staff member or administrator opens the dashboard.
3. It loads statistics based on the user’s role.
4. It loads role-specific chart data and dashboard reminders.
5. For patrons, it also loads due-soon loans, fine statistics, card-status information, and continue-reading information.
6. The dashboard may show a spotlight/book-of-the-week item, library tips, trivia, and recent activity.
7. Staff and administrators may set the library spotlight. The existing spotlight is deactivated and a new active spotlight record is created.

## 6. Library ID verification and eligibility workflow

Library-card status and system-login status are separate controls.

- `card_status`: `active`, `expired`, `suspended`, or `inactive`.
- `account_status`: `active` or `disabled`.

### 6.1 Staff verification

1. Staff or an administrator opens `/verification/`.
2. The staff member searches by library ID or barcode.
3. The system displays the patron record and card information.
4. The system checks whether the card is active and whether its expiry date has passed.
5. If the expiry date has passed, the system changes the card status to `expired` and marks the patron ineligible.
6. Staff can view eligibility but cannot change card status.
7. An administrator may change card status and expiry date, but must provide a reason.
8. The change is stored and an audit event is written.

Eligibility is checked before checkout, reservation, e-book access, and clearance processing.

## 7. Book inventory workflow

Inventory is available to Staff and Administrators.

### 7.1 Add a book

1. Staff or an administrator opens the inventory module.
2. The user submits ISBN, title, publisher, genre, description, authors, and optional e-book flag.
3. The user may provide a comma-separated list of copy barcodes.
4. The system creates the book, creates or links authors, and creates the associated physical copies.
5. An optional cover image is saved.
6. The book appears in inventory and can be found through search.

### 7.2 Manage copies

1. Staff or an administrator opens a book’s inventory detail.
2. A new copy may be added with a unique barcode and optional RFID tag.
3. A copy begins with status `available`.
4. During its lifecycle, the copy may become `borrowed`, `reserved`, `lost`, `damaged`, or `under_repair`.
5. Staff may edit book metadata; administrators may also delete books.

### 7.3 Inventory availability

The catalog calculates availability from copy records. A book is considered in stock when an eligible available copy exists. Pending holds are also shown to staff so inventory activity can be coordinated with the reservation queue.

## 8. Online book search and discovery workflow

1. An authenticated user opens `/search/`.
2. The user searches by title, publisher, genre, or description.
3. The user can filter by genre, availability, and e-book availability.
4. The system performs full-text book search and returns paginated results.
5. The page may show trending books and the patron’s recently viewed books.
6. Opening a book detail records a book-view event.
7. If a physical copy is available, the user is directed to borrow it through the library’s checkout process.
8. If no copy is available, the patron may place a reservation.
9. Search results can also be requested dynamically through `/search/results` or the REST search endpoints.

## 9. Reservation workflow

### 9.1 Place a reservation

1. The patron selects an unavailable book and submits a reservation.
2. The system verifies the patron’s library-card eligibility.
3. The system checks that the patron has no unpaid balance.
4. The system rejects duplicate pending or ready reservations for the same book.
5. The system rejects the reservation when the book currently has an available copy, because the patron should borrow directly.
6. The system assigns the next queue position and creates a `pending` reservation.
7. The event is audited and the patron receives a notification with the queue position.

### 9.2 Reservation becomes ready

1. A borrowed copy is checked in.
2. The system advances the queue for that book.
3. The first pending reservation is changed to `ready`.
4. A hold-expiry timestamp is calculated using the configured reservation hold period.
5. An available copy is marked `reserved` when one is found.
6. The system records a `reservation_ready` event.
7. The patron receives a pickup notification with the expiration date.

### 9.3 Cancel or fulfill a reservation

- A patron may cancel their own reservation.
- Staff or an administrator may fulfill a ready reservation after pickup.
- Reservation statuses are stored as `pending`, `ready`, `fulfilled`, `expired`, or `cancelled`.

## 10. Physical borrowing workflow

### 10.1 Checkout

Checkout is performed by Staff or an Administrator, either through the web form or `POST /api/v1/borrow/checkout`.

1. Staff verifies the patron by user ID, library ID, or barcode.
2. The system checks library-card eligibility.
3. The system checks for unpaid fines. A patron with an unpaid balance cannot borrow.
4. The system checks the configured maximum active-loan limit.
5. Staff scans or enters the physical copy barcode.
6. The system verifies that the copy exists and has status `available`.
7. A transaction is created with status `active` and a due date equal to today plus the configured loan period.
8. The copy status changes to `borrowed`.
9. The due-date event is logged.
10. The patron receives a checkout notification containing the title and due date.
11. The checkout event is recorded with the staff member and barcode.

### 10.2 View borrowing logs

- A patron sees only their own transactions.
- Staff and administrators can view all transactions and filter them by status.
- Transaction statuses are `active`, `returned`, or `overdue`.

### 10.3 Renewal

1. A patron submits a renewal for one of their own active or overdue transactions.
2. The system verifies that the transaction belongs to that patron.
3. The system rejects missing or inactive loans.
4. The system rejects the renewal when the maximum of two renewals has been reached.
5. The due date is reset to today plus the configured loan period.
6. The renewal count increases and the transaction is set to `active`.
7. A renewal event and notification are generated.

### 10.4 Check-in / return

1. Staff scans or enters the copy barcode.
2. The system finds the latest active or overdue transaction for that copy.
3. The transaction is marked `returned` and the return timestamp is stored.
4. The copy status changes to `available`.
5. The system updates overdue information for the borrower.
6. The reservation queue is advanced for the book.
7. The patron receives a return notification.
8. A check-in audit event is written.

## 11. Due-date and fine workflow

### 11.1 Overdue assessment

1. The dashboard and fines page run the overdue-status update routine.
2. The system finds active loans whose due date is before today.
3. Each matching transaction is changed to `overdue`.
4. The fine is calculated as overdue days multiplied by the configured daily fine rate.
5. If an unpaid fine already exists for the transaction, its amount is updated.
6. Otherwise, a new unpaid fine is created.
7. The patron receives an overdue notification.

### 11.2 Payment

- Patrons can view their own fines and use the simulated online-payment action.
- Staff and administrators can record payments for fines.
- The system rejects payments for missing or already paid fines.
- A successful payment changes the fine status to `paid`, stores the payment time, records a `fine_paid` event, and notifies the patron.

### 11.3 Fine waiver

1. Only an administrator can waive a fine.
2. The administrator must enter a reason.
3. The system only waives unpaid fines.
4. The fine status changes to `waived` and the timestamp is stored.
5. A `fine_waived` audit event records the administrator, patron, amount, and reason.
6. The patron receives a waiver notification.

Unpaid fines block new physical borrowing and reservations until settled or waived.

## 12. E-book workflow

### 12.1 E-book catalog and access

1. An authenticated user opens `/ebooks/`.
2. The system lists available e-book records and their formats.
3. Patrons see their active access grants.
4. Staff and administrators manage the e-book catalog and access-related operations.
5. When access is requested, the system validates the user’s card eligibility and verifies that the e-book exists.
6. An `ebook_access` record is created with a time-limited expiration based on the e-book or system access period.
7. An `ebook_access_granted` event is logged.

### 12.2 Reader and progress

1. The patron opens an active access grant.
2. The system confirms that the grant belongs to the current patron and has not expired.
3. The reader opens the configured file path and displays the book title and format.
4. Opening the reader saves initial reading progress.
5. The reader submits progress percentage and last page updates.
6. Progress is clamped between 0 and 100 and saved in `reading_progress`.
7. An `ebook_progress` event is recorded.
8. Expired or unauthorized access is rejected and the user is returned to the e-book catalog.

## 13. Lost and damaged item workflow

1. A patron opens the Lost/Damaged module and selects one of their active or overdue borrowed copies.
2. Staff can report an item for any applicable copy and may associate it with a patron.
3. The reporter selects `lost` or `damaged`, enters notes, and may enter a replacement cost.
4. The system creates a report with status `open`.
5. The physical copy status changes to `lost` for a lost report or `under_repair` for a damaged report.
6. If a replacement cost and patron are provided, an unpaid replacement fine is created.
7. The system notifies staff and, when associated, the patron.
8. Staff or an administrator reviews the report and marks it `resolved`.
9. The report lifecycle is `open` → `under_review`/processing → `resolved`, with the exact intermediate transition controlled by the report-management implementation.

## 14. Library clearance workflow

### 14.1 Audit

The clearance audit checks three obligations:

1. Active or overdue loans.
2. Pending or ready reservations.
3. Unpaid fines.

A patron is cleared only when all three counts are zero and the card is eligible.

### 14.2 Patron request

1. The patron opens `/clearance/`.
2. The system runs the audit and displays a checklist.
3. If active loans, holds, or unpaid fines exist, the checklist provides the relevant corrective action.
4. The patron submits a clearance request.
5. The system stores the request as `cleared` when no obligations exist, otherwise as `blocked`.
6. A cleared request receives a timestamp.
7. The patron and staff receive notifications.
8. The event is logged.

### 14.3 Staff/admin review

1. Staff or an administrator views the clearance request list and statistics.
2. Staff may search for a patron by library ID or barcode.
3. The system runs the same audit for the selected patron.
4. Staff can use the audit results to direct the patron to return books, cancel holds, or settle fines.

## 15. Notifications workflow

Notifications are generated by important system events, including checkout, return, renewal, reservation placement, reservation readiness, overdue fines, payments, waivers, replacement fines, e-book access, and clearance results.

1. A business operation calls the notification service.
2. The notification is stored for the target user with a type, title, message, link, and read flag.
3. The unread count appears in the authenticated application context.
4. The user opens `/notifications/` to view up to 50 notifications.
5. The user can mark one notification or all notifications as read.
6. Users can only access their own notifications.

## 16. Reports, analytics, and audit workflow

### 16.1 Reports

1. Staff or an administrator opens `/reports/`.
2. The system builds a summary for library activity, including borrowing statistics, genre distribution, and usage patterns supported by the reporting service.
3. Chart data can be loaded through `/reports/api/data`.
4. Only an administrator can export reports.
5. Export format can be CSV or HTML.
6. Each export records a `report_exported` event and includes a timestamped filename.

### 16.2 Activity log

1. The system records important events in `analytics_log`.
2. Examples include login failures, permission denials, password changes, checkouts, check-ins, renewals, reservation events, payment, fine waiver, card-status changes, user changes, and report exports.
3. Only administrators can view the activity log.
4. The audit trail supports accountability for sensitive actions.

## 17. Administrator user-management workflow

1. The administrator opens `/admin/users/`.
2. Users can be filtered by role, card status, account status, or search text.
3. To create a user, the administrator enters account, identity, library-card, and role information.
4. The system generates a temporary password and sets `must_change_password`.
5. The administrator gives the temporary password to the user securely; the user must change it at first login.
6. To edit a user, the administrator can update profile fields, role, card status, card expiry, and account status.
7. Role changes require explicit confirmation and a reason.
8. Account-status changes require a reason and may disable or re-enable login access.
9. Disabling an account blocks future login but preserves historical transactions and records.
10. The administrator can reset a user password, which produces a new temporary password and requires a password change.
11. Sensitive account actions generate audit events.

## 18. API workflow

The API is available under `/api/v1/`. It uses JSON responses in the form:

```json
{
  "success": true,
  "message": "OK",
  "data": {}
}
```

| Method | Endpoint | Workflow purpose |
|---|---|---|
| GET | `/api/v1/health` | Public health check. |
| GET | `/api/v1/dashboard` | Authenticated role-aware dashboard statistics. |
| GET | `/api/v1/books` | List books, optionally filtered, with availability. |
| GET | `/api/v1/books/<book_id>` | Retrieve one book’s details. |
| GET | `/api/v1/search/suggest` | Search suggestions. |
| GET | `/api/v1/search` | Search books with filters. |
| GET | `/api/v1/verify/<code>` | Staff/admin lookup and eligibility verification. |
| POST | `/api/v1/borrow/checkout` | Staff/admin checkout using user ID and copy barcode. |
| POST | `/api/v1/borrow/checkin` | Staff/admin return using copy barcode. |
| GET | `/api/v1/borrow/transactions` | Patron’s own or staff/admin transaction list. |
| GET | `/api/v1/fines` | Patron’s own or staff/admin fine list. |
| GET/POST | `/api/v1/reservations` | List reservations or place a reservation. |
| GET | `/api/v1/clearance/<user_id>` | Run an authorized clearance audit. |

Although API routes are exempt from form CSRF validation, authentication, RBAC, and patron ownership checks still apply.

## 19. End-to-end example: normal physical-book lifecycle

> **Catalog → Search → Eligibility → Checkout → Borrowed → Due-date monitoring → Return → Available or Reserved → Notification → Audit**

1. Staff adds a book and one or more barcoded copies.
2. A patron searches for the title.
3. The patron requests the book at the circulation desk.
4. Staff verifies the patron’s ID and card status.
5. The system checks fines and the lending limit.
6. Staff scans the copy and completes checkout.
7. The copy becomes `borrowed`; the transaction becomes `active`.
8. The system sends the due date to the patron.
9. If the book passes its due date, the transaction becomes `overdue` and an unpaid fine is created or updated.
10. The patron either renews the loan, pays any fine, or returns the book.
11. On return, the copy becomes `available`.
12. If another patron is waiting, the first reservation is advanced to `ready`, the copy becomes `reserved`, and a pickup notification is sent.
13. Staff fulfills the reservation after pickup, or the reservation is later cancelled/expired according to the reservation process.

## 20. Role-based workflow summary

| Function | Patron | Staff | Admin |
|---|---:|---:|---:|
| Dashboard | Own view | Full view | Full view |
| Search and book details | Yes | Yes | Yes |
| Reserve/cancel own hold | Yes | Yes | Yes |
| Checkout/check-in | No | Yes | Yes |
| Renew own loan | Yes | Yes as permitted | Yes as permitted |
| View/pay own fines | Yes | Yes | Yes |
| Record payments | No | Yes | Yes |
| Waive fines | No | No | Yes, with reason |
| E-book access | Own access | Manage | Manage |
| Report lost/damaged | Own report | Manage all | Manage all |
| Inventory | No | Manage | Manage/delete |
| ID lookup | No | View | View/manage status |
| Clearance | Request own | Review/manage | Review/manage |
| Reports | No | View | View/export |
| User management | No | No | Yes |
| Activity log | No | No | Yes |

## 21. Important implementation notes

1. **Patron self-checkout is not implemented as a web action.** Physical checkout is a staff/admin operation; patrons can view and renew their own loans.
2. **Online payment is simulated.** The current route marks a valid unpaid fine as paid and displays a simulated-success message; no external payment gateway is connected.
3. **Overdue processing is request-triggered.** The overdue routine runs when dashboard/fines workflows are opened rather than through a separate scheduled worker.
4. **Reservation expiry is represented in the data model.** Ready reservations receive an expiry timestamp; a separate automatic expiry job is not evident in the current route/service flow.
5. **Clearance is obligation-based.** Clearance requires no active/overdue loans, no pending/ready holds, no unpaid balance, and an eligible card.
6. **Physical card and login access are intentionally independent.** Disabling an account does not erase its circulation history, and changing card status does not necessarily disable login.
7. **Sensitive operations are audited.** Role changes, account status changes, card-status decisions, fine waivers, permission denials, login failures, and report exports are especially important audit events.

## 22. Core data lifecycle

| Entity | Main states or lifecycle |
|---|---|
| User account | `active` ↔ `disabled` |
| Library card | `active`, `expired`, `suspended`, `inactive` |
| Book copy | `available` → `borrowed` → `available`; may become `reserved`, `lost`, `damaged`, or `under_repair` |
| Transaction | `active` → `returned`; `active` → `overdue` → `returned` |
| Reservation | `pending` → `ready` → `fulfilled`; may become `cancelled` or `expired` |
| Fine | `unpaid` → `paid` or `waived` |
| Lost/damaged report | `open` → review/processing → `resolved` |
| Clearance request | `pending`, `cleared`, or `blocked` |
| E-book access | Granted until `expires_at`; reader access is rejected after expiration |
| Notification | Unread → read |

This represents the implemented end-to-end workflow of the current LMS codebase as identified from `app.py`, the route modules, service modules, `schema.sql`, and `docs/RBAC_ROLE_MATRIX.md`.
