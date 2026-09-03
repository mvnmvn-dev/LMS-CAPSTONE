from contextlib import contextmanager
from functools import wraps

import mysql.connector
from flask import current_app, g


def get_db():
    if "db" not in g:
        g.db = mysql.connector.connect(
            host=current_app.config["MYSQL_HOST"],
            port=current_app.config["MYSQL_PORT"],
            user=current_app.config["MYSQL_USER"],
            password=current_app.config["MYSQL_PASSWORD"],
            database=current_app.config["MYSQL_DATABASE"],
            autocommit=False,
        )
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        # Never leave an open transaction attached to a request connection.
        if getattr(db, "in_transaction", False):
            db.rollback()
        db.close()


@contextmanager
def transaction():
    """Run a business operation atomically.

    Existing service functions share this connection, so every execute() call
    made inside this context participates in the same commit/rollback unit.
    Nested transaction blocks reuse the outer transaction.
    """
    db = get_db()
    depth = getattr(g, "db_transaction_depth", 0)
    g.db_transaction_depth = depth + 1
    try:
        yield db
        if depth == 0:
            db.commit()
    except Exception:
        if depth == 0:
            db.rollback()
        raise
    finally:
        g.db_transaction_depth = depth


def transactional(fn):
    """Wrap a service operation in one commit/rollback boundary."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        with transaction():
            return fn(*args, **kwargs)
    return wrapper


def query_all(sql, params=None):
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(sql, params or ())
        return cursor.fetchall()
    finally:
        cursor.close()


def query_one(sql, params=None):
    """Fetch one row without materializing all matching rows."""
    db = get_db()
    cursor = db.cursor(dictionary=True)
    try:
        cursor.execute(sql, params or ())
        return cursor.fetchone()
    finally:
        cursor.close()


def execute(sql, params=None):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute(sql, params or ())
        # Preserve legacy auto-commit behavior for standalone writes, while
        # allowing transaction() to group related writes atomically.
        if getattr(g, "db_transaction_depth", 0) == 0:
            db.commit()
        return cursor.lastrowid, cursor.rowcount
    except Exception:
        if getattr(g, "db_transaction_depth", 0) == 0:
            db.rollback()
        raise
    finally:
        cursor.close()


def execute_many(sql, params_list):
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.executemany(sql, params_list)
        if getattr(g, "db_transaction_depth", 0) == 0:
            db.commit()
    except Exception:
        if getattr(g, "db_transaction_depth", 0) == 0:
            db.rollback()
        raise
    finally:
        cursor.close()
