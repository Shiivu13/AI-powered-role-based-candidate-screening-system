"""Restore-and-replay in a single request.

When an API instance does not know a session (404), the client retries the
same URL as::

    POST <original path>
    X-Session-Restore: 1
    X-Original-Method: GET | POST | ...
    {"snapshot": {...}, "body": "<base64 original body or null>", "content_type": "..."}

This middleware restores the snapshot into the local database and then hands
the *original* request to the app, all on the instance that received it. A
separate "restore" call followed by a retry would not work on serverless,
because the two calls can land on different instances.
"""
from __future__ import annotations

import base64
import json

from app.db import SessionLocal, init_db
from app.errors import AppError
from app.services.snapshot import restore_snapshot


class SessionRestoreMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not any(k == b"x-session-restore" for k, _ in scope["headers"]):
            return await self.app(scope, receive, send)

        raw = b""
        more = True
        while more:
            message = await receive()
            raw += message.get("body", b"")
            more = message.get("more_body", False)

        try:
            envelope = json.loads(raw or b"{}")
            init_db()
            with SessionLocal() as db:
                restore_snapshot(db, envelope.get("snapshot") or {})
        except AppError as exc:
            return await _json(send, exc.status_code, {"error": {"code": exc.code, "message": exc.message, "details": exc.details}})
        except (ValueError, KeyError, TypeError):
            return await _json(send, 422, {"error": {"code": "validation_failed", "message": "Invalid restore envelope", "details": {}}})

        body = base64.b64decode(envelope["body"]) if envelope.get("body") else b""
        headers = {k: v for k, v in scope["headers"]}
        method = headers.get(b"x-original-method", b"GET").decode().upper()
        new_headers = [(k, v) for k, v in scope["headers"] if k not in (b"content-length", b"content-type", b"x-session-restore")]
        new_headers.append((b"content-length", str(len(body)).encode()))
        if envelope.get("content_type"):
            new_headers.append((b"content-type", envelope["content_type"].encode()))

        sent = False

        async def replay_receive():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        return await self.app({**scope, "method": method, "headers": new_headers}, replay_receive, send)


async def _json(send, status: int, payload: dict) -> None:
    data = json.dumps(payload).encode()
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(data)).encode())]})
    await send({"type": "http.response.body", "body": data})
