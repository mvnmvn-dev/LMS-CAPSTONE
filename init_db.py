#!/usr/bin/env python3
"""Initialize database schema and seed sample data."""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from werkzeug.security import generate_password_hash

from config import Config

try:
    import mysql.connector
except ImportError:
    print("Install dependencies: pip install -r requirements.txt")
    sys.exit(1)


def run_sql_file(cursor, path):
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    for statement in sql.split(";"):
        stmt = statement.strip()
        if stmt:
            cursor.execute(stmt)


def seed(cursor):
    password = generate_password_hash("password123")

    users = [
        ("admin", password, "admin@library.edu", "System Administrator", "admin", "LIB-ADMIN-001", "BC-ADMIN-001", "active", date.today() + timedelta(days=365)),
        ("staff01", password, "staff@library.edu", "Maria Santos", "staff", "LIB-STAFF-001", "BC-STAFF-001", "active", date.today() + timedelta(days=365)),
        ("s230117154", password, "john.agno@student.edu", "John Mervin Agno", "patron", "LIB-PAT-001", "BC-PAT-001", "active", date.today() + timedelta(days=180)),
        ("s230117155", password, "jane.doe@student.edu", "Jane Doe", "patron", "LIB-PAT-002", "BC-PAT-002", "active", date.today() + timedelta(days=180)),
    ]
    cursor.executemany(
        """INSERT IGNORE INTO users (username, password_hash, email, full_name, role, library_id, barcode, card_status, card_expiry)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        users,
    )

    books = [
        ("978-0134685991", "Effective Java", "Addison-Wesley", "Technology", "Best practices for Java programming.", 0),
        ("978-0596007126", "Head First Design Patterns", "O'Reilly", "Technology", "A brain-friendly guide to design patterns.", 1),
        ("978-0132350884", "Clean Code", "Prentice Hall", "Technology", "A handbook of agile software craftsmanship.", 0),
        ("978-0061120084", "To Kill a Mockingbird", "Harper", "Fiction", "Classic American novel.", 0),
        ("978-0743273565", "The Great Gatsby", "Scribner", "Fiction", "American classic set in the Jazz Age.", 1),
    ]
    cursor.executemany(
        "INSERT IGNORE INTO books (isbn, title, publisher, genre, description, has_ebook) VALUES (%s,%s,%s,%s,%s,%s)",
        books,
    )

    authors = [
        ("Joshua Bloch", 1), ("Eric Freeman", 2), ("Robert C. Martin", 3),
        ("Harper Lee", 4), ("F. Scott Fitzgerald", 5),
    ]
    for name, book_id in authors:
        cursor.execute("INSERT IGNORE INTO authors (name) VALUES (%s)", (name,))
        cursor.execute("SELECT id FROM authors WHERE name = %s", (name,))
        author_id = cursor.fetchone()[0]
        cursor.execute("INSERT IGNORE INTO book_authors (book_id, author_id) VALUES (%s, %s)", (book_id, author_id))

    copies = [
        (1, "CPY-001", "RFID-001", "available"),
        (1, "CPY-002", "RFID-002", "available"),
        (2, "CPY-003", "RFID-003", "available"),
        (2, "CPY-004", "RFID-004", "borrowed"),
        (3, "CPY-005", "RFID-005", "available"),
        (4, "CPY-006", "RFID-006", "available"),
        (5, "CPY-007", "RFID-007", "available"),
    ]
    cursor.executemany(
        "INSERT IGNORE INTO copies (book_id, barcode, rfid_tag, status) VALUES (%s,%s,%s,%s)",
        copies,
    )

    cursor.execute(
        """INSERT IGNORE INTO transactions (user_id, copy_id, due_date, status)
           SELECT 3, c.id, DATE_ADD(CURDATE(), INTERVAL 7 DAY), 'active'
           FROM copies c WHERE c.barcode = 'CPY-004'"""
    )

    cursor.executemany(
        "INSERT IGNORE INTO ebooks (book_id, format, file_path, access_hours) VALUES (%s,%s,%s,%s)",
        [
            (2, "PDF", "static/ebooks/head-first-design-patterns.pdf", 72),
            (5, "EPUB", "static/ebooks/great-gatsby.epub", 48),
        ],
    )

    cursor.executemany(
        """INSERT IGNORE INTO notifications (user_id, title, message, ntype, link, is_read)
           VALUES (%s,%s,%s,%s,%s,%s)""",
        [
            (3, "Welcome to the Library", "Your patron account is active. Browse and reserve books anytime.", "info", "/search/", 0),
            (3, "Book checked out", "Head First Design Patterns is due in 7 days.", "success", "/borrowing/", 0),
            (2, "New clearance request", "A patron has submitted a clearance audit request.", "info", "/clearance/", 0),
            (1, "System update", "Library Management System is now running with role-based access.", "info", "/dashboard/", 1),
        ],
    )

    cursor.execute(
        """INSERT IGNORE INTO library_spotlight (id, book_id, label, note, active)
           VALUES (1, 2, 'Staff Pick', 'A must-read for anyone learning software design patterns!', 1)"""
    )

    print("Seed data inserted successfully.")
    print("\nDemo accounts (password: password123):")
    print("  Admin:  admin")
    print("  Staff:  staff01")
    print("  Patron: s230117154")


def main():
    conn = mysql.connector.connect(
        host=Config.MYSQL_HOST,
        port=Config.MYSQL_PORT,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
    )
    cursor = conn.cursor()
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    run_sql_file(cursor, schema_path)
    conn.commit()

    cursor.execute(f"USE {Config.MYSQL_DATABASE}")
    seed(cursor)
    conn.commit()
    cursor.close()
    conn.close()
    print("\nDatabase initialized.")


if __name__ == "__main__":
    main()
