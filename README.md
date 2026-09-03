# Library Management System

A full-featured Library Management System built with **HTML, Python (Flask), JavaScript, Tailwind CSS, and MySQL**, styled after the Bestlink College portal templates.

## Modules Included

| # | Module | Description |
|---|--------|-------------|
| — | **Dashboard** | Overview stats, recent activity, role-based summaries |
| 1 | **Book Inventory** | CRUD for books, authors, copies, barcodes/RFID |
| 2 | **Library ID Verification** | User lookup, card status, expiration handling |
| 3 | **Online Book Search** | Full-text search, filters, availability, reserve actions |
| 4 | **Borrowing Logs** | Check-out/in, renewals, lending limits |
| 5 | **Due Dates & Fines** | Overdue tracking, fine calculation, payments |
| 6 | **Book Reservations** | Hold queue, ready notifications, expiration |
| 7 | **E-Book Integration** | Digital access grants, time-bound reader |
| 8 | **Lost/Damaged Reports** | Report intake, status updates, replacement fines |
| 9 | **Library Clearance** | Automated audit for loans, holds, fines |
| 10 | **Reports & Analytics** | Borrowing stats, genre distribution, peak hours |

## Tech Stack

- **Backend:** Python 3 + Flask
- **Frontend:** HTML + Tailwind CSS (CDN) + JavaScript
- **Database:** MySQL 8.0+ (normalized schema)
- **Authentication:** Flask-Login with role-based access control (Patron, Staff, Admin)
- **API:** REST gateway at `/api/v1/*`

# Installation on Another Device

This section describes how to install and run the system on a new Windows, macOS, or Linux device. These instructions create a new database containing the sample data and demo accounts.

> **For an existing installation:** These steps do not transfer existing library records. Export and restore the old MySQL database before running the application if existing data must be preserved.

## 1. Install the prerequisites

Install the following software on the new device:

| Software | Required version | Purpose |
|---|---:|---|
| Python | 3.10 or newer | Runs the Flask application |
| MySQL Server | 8.0 or newer | Stores application data |
| Git | Optional | Downloads the project from a repository |

During MySQL installation, remember the password for the MySQL account that will be used by the application. The default configuration uses the `root` account on `localhost` and port `3306`.

### Installing Python

If Python is not installed, use one of the following options. The official installer is available from the [Python downloads page](https://www.python.org/downloads/).

| Operating system | Installation command |
|---|---|
| Windows 10/11 | `winget install --id Python.Python.3.12 -e` |
| macOS with Homebrew | `brew install python` |
| Ubuntu/Debian Linux | `sudo apt update && sudo apt install -y python3 python3-venv python3-pip` |

On Windows, the `winget` command is included with current versions of Windows 10 and Windows 11. If `winget` is unavailable, download the Windows installer from the official Python website and select **Add Python to PATH** during installation.

After installation, close and reopen the terminal, then verify Python:

```bash
# Windows
python --version

# macOS or Linux
python3 --version
```

Verify the installations by opening a terminal or command prompt and running:

```text
python --version
mysql --version
```

On some Linux and macOS installations, use `python3` instead of `python`.

## 2. Copy or download the project

Copy the complete `LMS CAPSTONE` project folder to the new device. If the project is stored in Git, clone it instead:

```bash
git clone <repository-url>
cd "LMS CAPSTONE"
```

If the project was copied using a ZIP file, extract it first and then open a terminal **inside the folder that contains `app.py`**. The project must retain its folder structure, including `models/`, `routes/`, `services/`, `templates/`, and `static/`.

The `static/` folder contains application assets, e-books, images, and uploads. Copy this folder as part of the complete project; do not copy only the Python files.

## 3. Create and activate a virtual environment

A virtual environment keeps this application's Python packages separate from other projects on the device.

### Windows PowerShell

```powershell
cd "C:\path\to\LMS CAPSTONE"
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run PowerShell as the current user and execute:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Then activate the environment again.

### Windows Command Prompt

```bat
cd /d "C:\path\to\LMS CAPSTONE"
py -3 -m venv .venv
.venv\Scripts\activate.bat
```

### macOS or Linux

```bash
cd "/path/to/LMS CAPSTONE"
python3 -m venv .venv
source .venv/bin/activate
```

After activation, install the required packages:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4. Configure the application

Create a file named `.env` in the same folder as `app.py` by copying `.env.example`.

### Windows Command Prompt

```bat
copy .env.example .env
```

### Windows PowerShell, macOS, or Linux

```bash
cp .env.example .env
```

Open `.env` and set the MySQL credentials. For a standard local MySQL installation, the values may look like this:

```dotenv
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=library_management
SECRET_KEY=replace-with-a-long-random-secret
FLASK_ENV=development
```

Replace `your_mysql_password` with the actual MySQL password. Keep `.env` private and do not commit it to Git because it contains credentials and the Flask secret key.

The remaining settings control library rules such as loan duration, active-loan limits, fines, reservation holds, and e-book access. The defaults in `.env.example` can be used for a standard installation.

## 5. Start MySQL

Make sure the MySQL server is running before initializing the database.

- **Windows:** Start the MySQL service from the Services application or MySQL Installer.
- **macOS:** Start MySQL from MySQL System Settings, MySQL Installer, or the service manager used during installation.
- **Linux:** Start the service with `sudo systemctl start mysql` or the command provided by the Linux distribution.

You can test the connection with:

```bash
mysql -h localhost -P 3306 -u root -p
```

Enter the MySQL password when prompted. Type `exit` to leave the MySQL prompt.

## 6. Create and initialize the database

From the project folder, with the virtual environment active, run:

```bash
python init_db.py
```

On macOS or Linux, use `python3 init_db.py` if `python` is not mapped to Python 3.

This command:

1. Connects to the MySQL server using `.env`.
2. Creates the `library_management` database if it does not exist.
3. Creates the tables from `schema.sql`.
4. Inserts the sample books, users, copies, e-books, and notifications.
5. Creates the demo accounts listed below.

The script uses `INSERT IGNORE`, so running it again does not normally duplicate the seeded records. Do not use it as a replacement for restoring a production database backup.

## 7. Start the application

With the virtual environment active, run:

```bash
python app.py
```

On macOS or Linux, use `python3 app.py` if necessary. When the server starts successfully, open the following address in a browser:

**http://localhost:5000**

To stop the development server, press `Ctrl+C` in the terminal.

## 8. Sign in and verify the installation

Use one of the seeded demo accounts:

| Role | Username | Password |
|---|---|---|
| Admin | `admin` | `password123` |
| Staff | `staff01` | `password123` |
| Patron | `s230117154` | `password123` |

After signing in, verify that:

1. The dashboard loads without a database error.
2. Book search displays the sample books.
3. Staff can open inventory and borrowing functions.
4. The admin account can open user management and reports.
5. The patron account can view borrowing history and reservations.
6. E-book files and images load if they were included in the copied project folder.
7. The API health endpoint responds at `http://localhost:5000/api/v1/health`.

For security, change the demo passwords before using the system beyond testing.

## Troubleshooting

### `python` or `python3` is not recognized

Python is not installed or is not available in the system PATH. Install Python 3.10 or newer, enable the option to add Python to PATH on Windows, reopen the terminal, and verify with `python --version` or `python3 --version`.

### `No module named ...`

The virtual environment may not be active, or the dependencies may not be installed. Activate `.venv` and run:

```bash
python -m pip install -r requirements.txt
```

### MySQL connection refused or access denied

Confirm that MySQL is running, that `.env` contains the correct host, port, username, and password, and that the MySQL account can connect locally. Test independently with:

```bash
mysql -h localhost -P 3306 -u root -p
```

### `Unknown database 'library_management'`

Run `python init_db.py` from the project folder. The initialization script creates the database from `schema.sql` before inserting the sample data.

### Port 5000 is already in use

Stop the other process using port 5000, or update the Flask startup configuration and open the new port in the browser. Make sure any firewall rule allows local access to the selected port.

### E-books, uploads, or images are missing

Confirm that the complete `static/` directory was copied, including `static/ebooks/`, `static/uploads/`, and `static/images/`. Confirm that any database paths still point to files that exist on the new device.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/health` | Health check |
| GET | `/api/v1/dashboard` | Dashboard stats |
| GET | `/api/v1/books` | List books with availability |
| GET | `/api/v1/search?q=` | Search books |
| GET | `/api/v1/verify/<code>` | Verify library ID/barcode |
| POST | `/api/v1/borrow/checkout` | Check out a book |
| POST | `/api/v1/borrow/checkin` | Check in a book |
| GET | `/api/v1/borrow/transactions` | List transactions |
| GET | `/api/v1/fines` | List fines |
| GET/POST | `/api/v1/reservations` | List or place reservations |
| GET | `/api/v1/clearance/<user_id>` | Run clearance audit |

## Project Structure

```text
LMS CAPSTONE/
├── app.py                  # Flask application entry point
├── config.py               # Configuration loaded from .env
├── init_db.py              # Database setup and sample-data seeding
├── schema.sql              # MySQL schema
├── requirements.txt        # Python dependencies
├── .env.example            # Configuration template
├── models/                 # Database and user models
├── services/               # Business logic per module
├── routes/                 # Web and API route handlers
├── templates/              # Jinja2 HTML templates
└── static/                 # CSS, JavaScript, images, e-books, and uploads
```

## License

Educational capstone project.

## References

[1]: schema.sql "Library Management System database schema"
[2]: .env.example "Library Management System environment configuration template"
[3]: requirements.txt "Library Management System Python dependencies"
[4]: init_db.py "Library Management System database initialization script"

The installation instructions above are based on the project files referenced in [1], [2], [3], and [4].
