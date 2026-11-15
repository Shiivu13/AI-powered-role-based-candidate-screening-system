"""Database engine and session management (SQLAlchemy 2.0).

SQLite by default; set ``DATABASE_URL`` (e.g. ``postgresql+psycopg://...``) to
use another database. Tables are created on startup.
"""
from __future__ import annotations

import threading
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str) -> Engine:
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, pool_pre_ping=True, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _):  # pragma: no cover - trivial
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

    return engine


engine = _make_engine(get_settings().resolved_database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


_init_lock = threading.Lock()
_initialized = False


def init_db() -> None:
    global _initialized
    with _init_lock:
        if _initialized:
            return
        from app import models  # noqa: F401 - register models

        Base.metadata.create_all(engine)
        _migrate()
        _initialized = True


def _migrate() -> None:
    """Additive, idempotent column migrations for databases created by older versions."""
    from sqlalchemy import inspect, text

    columns = {c["name"] for c in inspect(engine).get_columns("interview_sessions")}
    added = {
        "mode": "ALTER TABLE interview_sessions ADD COLUMN mode VARCHAR(20) DEFAULT 'practice'",
        "role_spec": "ALTER TABLE interview_sessions ADD COLUMN role_spec JSON",
    }
    for column, ddl in added.items():
        if column not in columns:
            with engine.begin() as conn:
                conn.execute(text(ddl))


def get_db() -> Iterator[Session]:
    # Also called lazily here: serverless runtimes (Vercel) do not send the
    # ASGI lifespan event, so the startup hook alone is not enough.
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
