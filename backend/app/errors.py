"""Domain exceptions. The API layer maps them to HTTP responses with a stable
``{"error": {"code", "message", "details"}}`` envelope."""
from __future__ import annotations


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class InvalidState(AppError):
    """The requested action is not allowed in the session's current lifecycle stage."""

    status_code = 409
    code = "invalid_state"


class KnowledgeBaseUnavailable(AppError):
    status_code = 503
    code = "knowledge_base_unavailable"
