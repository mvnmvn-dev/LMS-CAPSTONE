import json
import os
import random

from flask import current_app

from models.database import query_one


def _load_content():
    path = os.path.join(current_app.static_folder, "data", "library_content.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_tips_for_role(role):
    data = _load_content()
    tips = list(data["tips"].get("all", []))
    tips.extend(data["tips"].get(role, []))
    return tips


def get_random_tip(role):
    tips = get_tips_for_role(role)
    return random.choice(tips) if tips else ""


def get_all_tips(role):
    return get_tips_for_role(role)


def get_trivia_pool():
    return _load_content().get("trivia", [])


def get_random_trivia():
    pool = get_trivia_pool()
    return random.choice(pool) if pool else ""


def get_spotlight_book():
    try:
        row = query_one(
            """SELECT ls.label, ls.note, b.id AS book_id, b.title, b.genre, b.description, b.cover_url, b.isbn,
                      (SELECT GROUP_CONCAT(a.name SEPARATOR ', ')
                       FROM book_authors ba JOIN authors a ON a.id = ba.author_id
                       WHERE ba.book_id = b.id) AS authors
               FROM library_spotlight ls
               JOIN books b ON b.id = ls.book_id
               WHERE ls.active = 1
               ORDER BY ls.created_at DESC
               LIMIT 1"""
        )
        if row:
            return row
    except Exception:
        pass
    return query_one(
        """SELECT b.id AS book_id, b.title, b.genre, b.description, b.cover_url, b.isbn,
                  'Book of the Week' AS label, NULL AS note,
                  (SELECT GROUP_CONCAT(a.name SEPARATOR ', ')
                   FROM book_authors ba JOIN authors a ON a.id = ba.author_id
                   WHERE ba.book_id = b.id) AS authors
           FROM books b
           ORDER BY b.id ASC
           LIMIT 1"""
    )
