import os
import secrets
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from models.database import execute, query_all, query_one
from services.analytics_service import log_event

ALLOWED_COVER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def _normalize_rfid_tag(rfid_tag):
    if rfid_tag is None:
        return None
    value = str(rfid_tag).strip()
    return value or None


def _book_select():
    return """
        SELECT b.*,
               GROUP_CONCAT(DISTINCT a.name ORDER BY a.name SEPARATOR ', ') AS authors,
               COUNT(DISTINCT c.id) AS total_copies,
               SUM(CASE WHEN c.status = 'available' THEN 1 ELSE 0 END) AS available_copies,
               (
                   SELECT COUNT(*)
                   FROM reservations r
                   WHERE r.book_id = b.id
                     AND r.status IN ('pending', 'ready')
               ) AS pending_holds
        FROM books b
        LEFT JOIN book_authors ba ON ba.book_id = b.id
        LEFT JOIN authors a ON a.id = ba.author_id
        LEFT JOIN copies c ON c.book_id = b.id AND c.status NOT IN ('lost', 'damaged', 'under_repair')
    """


def _book_from_clause():
    return """
        FROM books b
        LEFT JOIN book_authors ba ON ba.book_id = b.id
        LEFT JOIN authors a ON a.id = ba.author_id
        LEFT JOIN copies c ON c.book_id = b.id AND c.status NOT IN ('lost', 'damaged', 'under_repair')
    """


def _book_filters(genre=None, search=None, available_only=False, ebook_only=False):
    where = " WHERE 1=1"
    params = []
    if genre:
        where += " AND b.genre = %s"
        params.append(genre)
    if search:
        where += " AND (b.title LIKE %s OR b.isbn LIKE %s OR a.name LIKE %s OR b.publisher LIKE %s)"
        term = f"%{search}%"
        params.extend([term, term, term, term])
    if ebook_only:
        where += " AND b.has_ebook = 1"
    having = ""
    if available_only:
        having = " HAVING SUM(CASE WHEN c.status = 'available' THEN 1 ELSE 0 END) > 0"
    return where, params, having


def list_books(genre=None, search=None, available_only=False, ebook_only=False, page=None, per_page=10):
    where, params, having = _book_filters(genre, search, available_only, ebook_only)
    select = _book_select() + where + " GROUP BY b.id" + having + " ORDER BY b.title"

    if page is not None:
        count_sql = f"""
            SELECT COUNT(*) AS c FROM (
                SELECT b.id{_book_from_clause()}{where}
                GROUP BY b.id{having}
            ) counted
        """
        total = query_one(count_sql, params)["c"]
        from services.pagination import sql_page_clause

        limit_sql, limit_params = sql_page_clause(page, per_page)
        return query_all(select + limit_sql, params + limit_params), total

    return query_all(select, params)


def list_genres():
    rows = query_all(
        "SELECT DISTINCT genre FROM books WHERE genre IS NOT NULL AND genre != '' ORDER BY genre"
    )
    return [row["genre"] for row in rows]


def get_book(book_id):
    book = query_one(
        _book_select() + " WHERE b.id = %s GROUP BY b.id",
        (book_id,),
    )
    if not book:
        return None
    book["copies"] = query_all(
        "SELECT * FROM copies WHERE book_id = %s ORDER BY barcode",
        (book_id,),
    )
    book["ebooks"] = query_all(
        "SELECT id, format, access_hours FROM ebooks WHERE book_id = %s",
        (book_id,),
    )
    return book


def _covers_dir():
    path = Path(current_app.static_folder) / "uploads" / "covers"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _delete_cover_file(relative_path):
    if not relative_path or not str(relative_path).startswith("uploads/covers/"):
        return
    filepath = Path(current_app.static_folder) / relative_path.replace("\\", "/")
    if filepath.is_file():
        try:
            filepath.unlink()
        except OSError:
            pass


def save_book_cover(book_id, file_storage):
    if not file_storage or not file_storage.filename:
        return False, "No image selected."

    filename = secure_filename(file_storage.filename)
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_COVER_EXTENSIONS:
        return False, "Use JPG, PNG, WEBP, or GIF images only."

    max_bytes = current_app.config.get("MAX_BOOK_COVER_MB", 2) * 1024 * 1024
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > max_bytes:
        return False, f"Cover image must be under {current_app.config.get('MAX_BOOK_COVER_MB', 2)} MB."

    row = query_one("SELECT cover_url FROM books WHERE id = %s", (book_id,))
    if row and row.get("cover_url"):
        _delete_cover_file(row["cover_url"])

    token = secrets.token_hex(4)
    stored_name = f"{book_id}_{token}{ext}"
    filepath = _covers_dir() / stored_name
    file_storage.save(filepath)

    relative = f"uploads/covers/{stored_name}"
    execute("UPDATE books SET cover_url = %s WHERE id = %s", (relative, book_id))
    return True, relative


def _ensure_author(name):
    existing = query_one("SELECT id FROM authors WHERE name = %s", (name,))
    if existing:
        return existing["id"]
    return execute("INSERT INTO authors (name) VALUES (%s)", (name,))[0]


def create_book(data):
    book_id = execute(
        """INSERT INTO books (isbn, title, publisher, genre, description, cover_url, has_ebook)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (
            data.get("isbn"), data["title"], data.get("publisher"), data.get("genre"),
            data.get("description"), data.get("cover_url"), 1 if data.get("has_ebook") else 0,
        ),
    )[0]

    for author in data.get("authors", []):
        author_id = _ensure_author(author.strip())
        execute("INSERT IGNORE INTO book_authors (book_id, author_id) VALUES (%s, %s)", (book_id, author_id))

    for copy_data in data.get("copies", []):
        execute(
            """INSERT INTO copies (book_id, barcode, rfid_tag, status, condition_note)
               VALUES (%s, %s, %s, %s, %s)""",
            (book_id, copy_data["barcode"], _normalize_rfid_tag(copy_data.get("rfid_tag")),
             copy_data.get("status", "available"), copy_data.get("condition_note", "Good")),
        )

    log_event("book_created", entity_type="book", entity_id=book_id)
    return book_id


def update_book(book_id, data):
    execute(
        """UPDATE books SET isbn=%s, title=%s, publisher=%s, genre=%s, description=%s,
           cover_url=%s, has_ebook=%s WHERE id=%s""",
        (data.get("isbn"), data["title"], data.get("publisher"), data.get("genre"),
         data.get("description"), data.get("cover_url"), 1 if data.get("has_ebook") else 0, book_id),
    )
    log_event("book_updated", entity_type="book", entity_id=book_id)


def delete_book(book_id):
    row = query_one("SELECT cover_url FROM books WHERE id = %s", (book_id,))
    if row and row.get("cover_url"):
        _delete_cover_file(row["cover_url"])
    execute("DELETE FROM books WHERE id = %s", (book_id,))
    log_event("book_deleted", entity_type="book", entity_id=book_id)


def add_copy(book_id, barcode, rfid_tag=None):
    copy_id = execute(
        "INSERT INTO copies (book_id, barcode, rfid_tag) VALUES (%s, %s, %s)",
        (book_id, barcode, _normalize_rfid_tag(rfid_tag)),
    )[0]
    log_event("copy_added", entity_type="copy", entity_id=copy_id)
    return copy_id


def update_copy_status(copy_id, status):
    execute("UPDATE copies SET status = %s WHERE id = %s", (status, copy_id))


def get_availability(book_id):
    row = query_one(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN status = 'available' THEN 1 ELSE 0 END) AS available
           FROM copies WHERE book_id = %s AND status NOT IN ('lost', 'damaged', 'under_repair')""",
        (book_id,),
    )
    return {"book_id": book_id, "total": row["total"] or 0, "available": row["available"] or 0,
            "in_stock": (row["available"] or 0) > 0}
