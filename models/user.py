from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from models.database import query_one


class User(UserMixin):
    def __init__(self, row):
        self.id = row["id"]
        self.username = row["username"]
        self.email = row["email"]
        self.full_name = row["full_name"]
        self.role = row["role"]
        self.library_id = row["library_id"]
        self.barcode = row.get("barcode")
        self.card_status = row["card_status"]
        self.card_expiry = row.get("card_expiry")
        self.account_status = row.get("account_status", "active")
        self.session_version = row.get("session_version", 0)
        self.must_change_password = bool(row.get("must_change_password"))
        self.failed_login_attempts = row.get("failed_login_attempts", 0)
        self.locked_until = row.get("locked_until")
        self.profile_image = row.get("profile_image")
        self.password_hash = row.get("password_hash")

    @property
    def is_active(self):
        return self.account_status == "active"

    @staticmethod
    def get_by_id(user_id):
        row = query_one("SELECT * FROM users WHERE id = %s", (user_id,))
        return User(row) if row else None

    @staticmethod
    def get_by_username(username):
        row = query_one("SELECT * FROM users WHERE username = %s", (username,))
        return User(row) if row else None

    @staticmethod
    def get_by_library_id(library_id):
        row = query_one("SELECT * FROM users WHERE library_id = %s", (library_id,))
        return User(row) if row else None

    @staticmethod
    def get_by_barcode(barcode):
        row = query_one("SELECT * FROM users WHERE barcode = %s", (barcode,))
        return User(row) if row else None

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @staticmethod
    def hash_password(password):
        return generate_password_hash(password)

    def initials(self):
        parts = self.full_name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return self.full_name[:2].upper()

    def has_profile_image(self):
        return bool(self.profile_image)
