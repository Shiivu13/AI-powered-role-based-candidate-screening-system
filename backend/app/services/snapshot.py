"""Signed session snapshots ("self-healing sessions").

On a serverless host each instance has its own SQLite file in /tmp, so a
request can land on an instance that has never seen the session. The browser
therefore keeps the latest signed snapshot of its session, and if the API
answers 404 it posts the snapshot back to ``/api/sessions/restore`` and
retries. With a shared database (``DATABASE_URL`` / ``POSTGRES_URL``) this
path is simply never taken.

Snapshots are HMAC-SHA256 signed so a client cannot edit its own scores.
Set ``SESSION_SECRET`` in production; without it a fixed development key is
used, which only protects against casual tampering because the code is public.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime

from sqlalchemy import DateTime, inspect
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import ValidationFailed
from app.models import Answer, InterviewSession, Question, Report

_DEV_KEY = "screenrag-development-session-key"


def _key() -> bytes:
    return (get_settings().session_secret or _DEV_KEY).encode()


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


def snapshot_version(session: InterviewSession) -> int:
    """Monotonic progress counter: grows with every question asked or closed
    and when the report is created. Lets the client spot stale instances."""
    closed = sum(q.status != "asked" for q in session.questions)
    return 2 * len(session.questions) + closed + (1000 if session.report else 0)


def export_snapshot(session: InterviewSession) -> dict:
    data = {
        "session": _row(session),
        "questions": [_row(q) for q in session.questions],
        "answers": [_row(q.answer) for q in session.questions if q.answer],
        "report": _row(session.report) if session.report else None,
    }
    body = base64.urlsafe_b64encode(json.dumps(data, separators=(",", ":"), sort_keys=True).encode()).decode()
    sig = hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()
    return {"session_id": session.id, "version": snapshot_version(session), "body": body, "sig": sig}


def restore_snapshot(db: Session, snapshot: dict) -> InterviewSession:
    body, sig = snapshot.get("body", ""), snapshot.get("sig", "")
    expected = hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise ValidationFailed("Session snapshot signature is invalid")
    data = json.loads(base64.urlsafe_b64decode(body.encode()))

    session_id = data["session"]["id"]
    existing = db.get(InterviewSession, session_id)
    if existing is not None:
        # Keep whichever copy has progressed further.
        closed = sum(q["status"] != "asked" for q in data["questions"])
        incoming = 2 * len(data["questions"]) + closed + (1000 if data["report"] else 0)
        if snapshot_version(existing) >= incoming:
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
