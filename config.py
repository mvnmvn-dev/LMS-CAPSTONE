import os

from datetime import timedelta



from dotenv import load_dotenv



load_dotenv()





class Config:

    FLASK_ENV = os.getenv("FLASK_ENV", "development")

    SECRET_KEY = os.getenv("SECRET_KEY")

    if not SECRET_KEY:

        if FLASK_ENV == "production":

            raise RuntimeError("SECRET_KEY environment variable must be set in production.")

        SECRET_KEY = "lms-capstone-dev-secret-key-change-in-production"



    PERMANENT_SESSION_LIFETIME = timedelta(minutes=int(os.getenv("SESSION_LIFETIME_MINUTES", "45")))

    MAX_LOGIN_ATTEMPTS = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))

    LOGIN_LOCKOUT_MINUTES = int(os.getenv("LOGIN_LOCKOUT_MINUTES", "5"))

    WTF_CSRF_TIME_LIMIT = None



    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")

    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))

    MYSQL_USER = os.getenv("MYSQL_USER", "root")

    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")

    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "library_management")



    LOAN_PERIOD_DAYS = int(os.getenv("LOAN_PERIOD_DAYS", "14"))

    MAX_ACTIVE_LOANS = int(os.getenv("MAX_ACTIVE_LOANS", "5"))

    FINE_PER_DAY = float(os.getenv("FINE_PER_DAY", "10.00"))

    RESERVATION_HOLD_DAYS = int(os.getenv("RESERVATION_HOLD_DAYS", "3"))

    EBOOK_ACCESS_HOURS = int(os.getenv("EBOOK_ACCESS_HOURS", "72"))
    MAX_PROFILE_IMAGE_MB = int(os.getenv("MAX_PROFILE_IMAGE_MB", "2"))

