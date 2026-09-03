"""Create any tables or columns added after initial deployment."""

from models.database import get_db


USER_COLUMN_UPGRADES = [
    ("account_status", "ENUM('active', 'disabled') NOT NULL DEFAULT 'active'"),
    ("must_change_password", "TINYINT(1) NOT NULL DEFAULT 0"),
    ("failed_login_attempts", "INT NOT NULL DEFAULT 0"),
    ("locked_until", "DATETIME NULL"),
    ("profile_image", "VARCHAR(500) NULL"),
    ("session_version", "INT NOT NULL DEFAULT 0"),
]

UPGRADE_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS reading_progress (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        ebook_access_id INT NOT NULL,
        progress_pct INT NOT NULL DEFAULT 0,
        last_page INT DEFAULT 0,
        last_opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uk_user_access (user_id, ebook_access_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (ebook_access_id) REFERENCES ebook_access(id) ON DELETE CASCADE
    )""",
    """CREATE TABLE IF NOT EXISTS library_spotlight (
        id INT AUTO_INCREMENT PRIMARY KEY,
        book_id INT NOT NULL,
        label VARCHAR(100) DEFAULT 'Staff Pick',
        note TEXT,
        set_by INT NULL,
        active TINYINT(1) DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE,
        FOREIGN KEY (set_by) REFERENCES users(id) ON DELETE SET NULL
    )""",
]


def _column_exists(cursor, column_name):
    cursor.execute(
        """SELECT COUNT(*) FROM information_schema.COLUMNS
           WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'users' AND COLUMN_NAME = %s""",
        (column_name,),
    )
    return cursor.fetchone()[0] > 0


def ensure_schema_upgrades():
    db = get_db()
    cursor = db.cursor()
    for column_name, column_def in USER_COLUMN_UPGRADES:
        if not _column_exists(cursor, column_name):
            cursor.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_def}")
    for stmt in UPGRADE_STATEMENTS:
        cursor.execute(stmt)
    cursor.execute("UPDATE copies SET rfid_tag = NULL WHERE rfid_tag = ''")
    db.commit()
    cursor.close()
