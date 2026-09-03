from models.database import query_all, query_one
from services.analytics_service import log_event
from services.inventory_service import get_availability, list_books


def search_books(query=None, genre=None, available_only=False, ebook_only=False, page=None, per_page=10):
    if page is not None:
        books, total = list_books(
            genre=genre,
            search=query,
            available_only=available_only,
            ebook_only=ebook_only,
            page=page,
            per_page=per_page,
        )
    else:
        books = list_books(
            genre=genre,
            search=query,
            available_only=available_only,
            ebook_only=ebook_only,
        )
        total = len(books)
    results = []
    for book in books:
        avail = get_availability(book["id"])
        book["availability"] = avail
        book["ebook_formats"] = [
            e["format"]
            for e in query_all("SELECT format FROM ebooks WHERE book_id = %s", (book["id"],))
        ]
        results.append(book)
    if page is not None:
        return results, total
    return results


def get_book_details(book_id):
    from services.inventory_service import get_book

    book = get_book(book_id)
    if not book:
        return None
    book["availability"] = get_availability(book_id)
    book["similar"] = get_similar_books(book_id)
    return book


def log_book_view(user_id, book_id):
    log_event("book_viewed", user_id=user_id, entity_type="book", entity_id=book_id)


def search_suggest(query, limit=8):
    if not query or len(query.strip()) < 2:
        return []
    term = f"%{query.strip()}%"
    return query_all(
        """SELECT DISTINCT b.id, b.title, b.isbn, b.genre,
                  GROUP_CONCAT(DISTINCT a.name SEPARATOR ', ') AS authors
           FROM books b
           LEFT JOIN book_authors ba ON ba.book_id = b.id
           LEFT JOIN authors a ON a.id = ba.author_id
           WHERE b.title LIKE %s OR b.isbn LIKE %s OR a.name LIKE %s
           GROUP BY b.id, b.title, b.isbn, b.genre
           ORDER BY b.title
           LIMIT %s""",
        (term, term, term, limit),
    )


def get_similar_books(book_id, limit=4):
    book = query_one("SELECT genre FROM books WHERE id = %s", (book_id,))
    if not book or not book.get("genre"):
        return []
    return query_all(
        """SELECT b.id, b.title, b.genre, b.isbn, b.cover_url,
                  GROUP_CONCAT(DISTINCT a.name SEPARATOR ', ') AS authors
           FROM books b
           LEFT JOIN book_authors ba ON ba.book_id = b.id
           LEFT JOIN authors a ON a.id = ba.author_id
           WHERE b.genre = %s AND b.id != %s
           GROUP BY b.id, b.title, b.genre, b.isbn, b.cover_url
           ORDER BY b.title
           LIMIT %s""",
        (book["genre"], book_id, limit),
    )
