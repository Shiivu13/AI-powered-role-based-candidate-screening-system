"""Encrypted session snapshots ("self-healing sessions").

On a serverless host each instance has its own SQLite file in /tmp, so a
request can land on an instance that has never seen the session. The browser
therefore keeps the latest snapshot of its session, and if the API answers 404
it sends the snapshot back (see ``app/middleware.py``). With a shared database
(``DATABASE_URL`` / ``POSTGRES_URL``) this path is simply never taken.

Snapshots are encrypted *and* authenticated with Fernet (AES-128-CBC +
HMAC-SHA256): a client can neither edit its scores nor read them, which matters
in assessment mode where results stay hidden until the report. A small,
unauthenticated ``summary`` travels alongside for the history page only.

Set ``SESSION_SECRET`` in production; without it a fixed development key is
used, which only protects against casual tampering because the code is public.
"""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import DateTime, inspect
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ValidationFailed
from app.models import Answer, InterviewSession, Question, Report

_DEV_KEY = "screenrag-development-session-key"


def _fernet() -> Fernet:
    secret = (get_settings().session_secret or _DEV_KEY).encode()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret).digest()))


def _row(obj) -> dict:
    out = {}
    for col in inspect(obj).mapper.column_attrs:
        value = getattr(obj, col.key)
        out[col.key] = value.isoformat() if isinstance(value, datetime) else value
    return out


def _build(model, data: dict):
    kwargs = {}
    for col in inspect(model).columns:
        if col.key not in data:
            continue
        value = data[col.key]
        if value is not None and isinstance(col.type, DateTime):
            value = datetime.fromisoformat(value)
        kwargs[col.key] = value
    return model(**kwargs)


def _version(questions: list[dict], has_report: bool) -> int:
    closed = sum(q["status"] != "asked" for q in questions)
    hints = sum(1 for q in questions if (q.get("trace") or {}).get("hint"))
    return 3 * len(questions) + 2 * closed + hints + (10_000 if has_report else 0)


def snapshot_version(session: InterviewSession) -> int:
    """Monotonic progress counter: grows with every question asked, answered,
    skipped or hinted, and when the report is created. Lets the client spot
    stale instances."""
    return _version([{"status": q.status, "trace": q.trace} for q in session.questions], session.report is not None)


def _summary(session: InterviewSession) -> dict:
    """Display-only data for the history page (never trusted by the server)."""
    qs = session.questions
    completed = session.status == "completed" and session.report is not None
    return {
        "id": session.id,
        "candidate_name": session.candidate_name,
        "role_id": session.role_id,
        "role_title": (session.role_spec or {}).get("title"),
        "status": session.status,
        "mode": session.mode,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "planned": len(session.plan),
        "primary_asked": sum(q.kind == "primary" for q in qs),
        "asked": len(qs),
        "answered": sum(q.status == "answered" for q in qs),
        "skipped": sum(q.status == "skipped" for q in qs),
        "follow_ups": sum(q.kind == "follow_up" for q in qs),
        "difficulty_offset": session.difficulty_offset,
        "overall_score": session.report.data.get("overall_score") if completed else None,
    }


def export_snapshot(session: InterviewSession) -> dict:
    data = {
        "session": _row(session),
        "questions": [_row(q) for q in session.questions],
        "answers": [_row(q.answer) for q in session.questions if q.answer],
        "report": _row(session.report) if session.report else None,
    }
    token = _fernet().encrypt(json.dumps(data, separators=(",", ":")).encode()).decode()
    return {"session_id": session.id, "version": snapshot_version(session), "body": token, "summary": _summary(session)}


def restore_snapshot(db: Session, snapshot: dict) -> InterviewSession:
    if not isinstance(snapshot, dict):
        raise ValidationFailed("Session snapshot is invalid or was tampered with")
    try:
        data = json.loads(_fernet().decrypt(str(snapshot.get("body", "")).encode()))
        if not isinstance(data, dict) or not isinstance(data.get("session"), dict):
            raise ValueError("unexpected snapshot shape")
    except (InvalidToken, ValueError) as exc:
        raise ValidationFailed("Session snapshot is invalid or was tampered with") from exc

    session_id = data["session"]["id"]
    existing = db.get(InterviewSession, session_id)
    if existing is not None:
        # Keep whichever copy has progressed further.
        if snapshot_version(existing) >= _version(data["questions"], bool(data["report"])):
            return existing
        db.delete(existing)
        db.flush()

    db.add(_build(InterviewSession, data["session"]))
    for q in data["questions"]:
        db.add(_build(Question, q))
    for a in data["answers"]:
        db.add(_build(Answer, a))
    if data["report"]:
        db.add(_build(Report, data["report"]))
    db.commit()
    db.expire_all()
    return db.get(InterviewSession, session_id)
