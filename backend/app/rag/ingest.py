"""Knowledge ingestion: load -> clean -> chunk -> embed -> store.

Run via ``python -m scripts.ingest_kb`` (see README). Ingestion is offline and
idempotent: re-running replaces each role's collection.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.ai.catalog import BOOKS, ROLES, Book
from app.config import get_settings
from app.rag.chunking import Chunk, chunk_pages
from app.rag.embeddings import LSAEmbedder, get_embedder
from app.rag.loaders import load_document
from app.rag.retriever import HybridRetriever
from app.rag.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


@dataclass
class BookReport:
    book_id: str
    title: str
    pages: int
    chunks: int
    avg_chunk_chars: int
    seconds: float


def _manifest_path() -> Path:
    return get_settings().resolved_index_dir / "manifest.json"


def read_manifest() -> dict:
    settings = get_settings()
    path = settings.kb_dir / "manifest.json" if settings.effective_vector_backend == "numpy" else _manifest_path()
    if path.exists():
        return json.loads(path.read_text())
    return {"books": {}, "roles": {}}


def _write_manifest(manifest: dict) -> None:
    _manifest_path().write_text(json.dumps(manifest, indent=2))


def chunk_book(book: Book, path: Path) -> tuple[list[Chunk], BookReport]:
    settings = get_settings()
    start = time.time()
    pages = load_document(path)
    chunks = chunk_pages(
        pages,
        book_id=book.id,
        book_title=book.title,
        chunk_size=settings.chunk_size,
        overlap=settings.chunk_overlap,
        min_chars=settings.min_chunk_chars,
    )
    avg = int(sum(len(c.text) for c in chunks) / max(len(chunks), 1))
    report = BookReport(book.id, book.title, len(pages), len(chunks), avg, round(time.time() - start, 1))
    logger.info("Chunked %s: %d pages -> %d chunks (avg %d chars)", book.id, len(pages), len(chunks), avg)
    return chunks, report


def ingest_all(role_ids: list[str] | None = None, refit: bool = True) -> dict:
    """Ingest every available book for the given roles (default: all roles)."""
    settings = get_settings()
    role_ids = role_ids or list(ROLES)
    book_ids = sorted({b for r in role_ids for b in ROLES[r].book_ids})

    chunks_by_book: dict[str, list[Chunk]] = {}
    reports: dict[str, dict] = {}
    for book_id in book_ids:
        book = BOOKS[book_id]
        path = settings.resolved_books_dir / book.filename
        if not path.exists():
            logger.warning("Missing %s (expected at %s); skipping", book.title, path)
            continue
        chunks, report = chunk_book(book, path)
        chunks_by_book[book_id] = chunks
        reports[book_id] = asdict(report)

    if not chunks_by_book:
        raise RuntimeError(
            f"No books found in {settings.resolved_books_dir}. Run `python -m scripts.download_kb` first."
        )

    embedder = get_embedder(refresh=True)
    if isinstance(embedder, LSAEmbedder) and (refit or not embedder.is_ready):
        # The LSA space is fitted on the *whole* corpus so all roles share one
        # consistent vector space (needed for ad-hoc document additions later).
        corpus = [c.embedding_text for chunks in chunks_by_book.values() for c in chunks]
        embedder.fit(corpus)

    manifest = read_manifest()
    manifest["embedding_provider"] = settings.embedding_provider
    manifest["chunk_size"] = settings.chunk_size
    manifest["chunk_overlap"] = settings.chunk_overlap
    manifest["books"].update(reports)

    for role_id in role_ids:
        role = ROLES[role_id]
        store = ChromaVectorStore(role_id)
        store.reset()
        role_chunks = [c for b in role.book_ids for c in chunks_by_book.get(b, [])]
        if role_chunks:
            vectors = embedder.embed([c.embedding_text for c in role_chunks])
            store.add(role_chunks, vectors)
        manifest["roles"][role_id] = {
            "chunks": len(role_chunks),
            "books": [b for b in role.book_ids if b in chunks_by_book],
            "missing_books": [b for b in role.book_ids if b not in chunks_by_book],
            "ingested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        logger.info("Role %s: stored %d chunks in %s", role_id, len(role_chunks), store.name)
    HybridRetriever.invalidate()
    _write_manifest(manifest)
    return manifest


def ingest_extra_document(role_id: str, path: Path, title: str | None = None) -> dict:
    """Add a user-supplied document (PDF/TXT/MD) to a role's knowledge base
    using the already-fitted embedding space."""
    if role_id not in ROLES:
        raise ValueError(f"Unknown role: {role_id}")
    embedder = get_embedder()
    if not embedder.is_ready:
        raise RuntimeError("Run the main ingestion first so the embedding space exists.")
    slug = re.sub(r"[^a-z0-9]+", "_", (title or path.stem).lower()).strip("_")[:40]
    book = Book(f"custom_{slug}", title or path.stem, "uploaded", path.name, "")
    chunks, report = chunk_book(book, path)
    store = ChromaVectorStore(role_id)
    store.delete_book(book.id)
    if chunks:
        store.add(chunks, embedder.embed([c.embedding_text for c in chunks]))
    HybridRetriever.invalidate(role_id)
    manifest = read_manifest()
    manifest["books"][book.id] = asdict(report)
    role_entry = manifest["roles"].setdefault(role_id, {"chunks": 0, "books": [], "missing_books": []})
    if book.id not in role_entry["books"]:
        role_entry["books"].append(book.id)
    role_entry["chunks"] = store.count()
    _write_manifest(manifest)
    return asdict(report)
