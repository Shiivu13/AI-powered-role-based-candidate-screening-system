"""Download the knowledge-base books listed in the assignment.

Usage (from ``backend/``)::

    python -m scripts.download_kb            # all books
    python -m scripts.download_kb mitchell   # specific book ids

Books are written to ``data/books/`` (git-ignored). TLS certificates are always
verified; a host with a broken certificate is reported and skipped, and you can
place that PDF in ``data/books/`` manually under the expected file name.
"""
from __future__ import annotations

import sys
import urllib.request

from app.ai.catalog import BOOKS
from app.config import get_settings


def download(book_ids: list[str]) -> int:
    books_dir = get_settings().resolved_books_dir
    failures = 0
    for book_id in book_ids:
        book = BOOKS[book_id]
        target = books_dir / book.filename
        if target.exists() and target.stat().st_size > 10_000:
            print(f"[skip] {book.title} already at {target}")
            continue
        print(f"[get ] {book.title} <- {book.url}")
        try:
            request = urllib.request.Request(book.url, headers={"User-Agent": "kb-downloader/1.0"})
            with urllib.request.urlopen(request, timeout=300) as response:
                data = response.read()
            if not data.startswith(b"%PDF"):
                raise ValueError("response is not a PDF")
            target.write_bytes(data)
            print(f"[ ok ] {target} ({len(data) / 1e6:.1f} MB)")
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            print(f"[fail] {book.title}: {exc}\n       Download it manually to {target}")
    return failures


if __name__ == "__main__":
    ids = sys.argv[1:] or list(BOOKS)
    unknown = [i for i in ids if i not in BOOKS]
    if unknown:
        sys.exit(f"Unknown book ids: {unknown}. Known: {list(BOOKS)}")
    sys.exit(1 if download(ids) == len(ids) else 0)
