"""FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import catalog, sessions
from app.config import get_settings
from app.db import init_db
from app.errors import AppError

logger = logging.getLogger("app")


def _error(status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details or {}}})


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    from app.ai.llm import get_llm

    llm = get_llm()
    logger.info("Startup complete (LLM=%s, embeddings=%s)", llm.name, get_settings().embedding_provider)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("pypdf").setLevel(logging.ERROR)

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Role-based candidate screening with Retrieval-Augmented question generation.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        return _error(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        details = {"fields": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]}
        return _error(422, "validation_failed", "Request validation failed", details)

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception):  # pragma: no cover - safety net
        logger.exception("Unhandled error: %s", exc)
        return _error(500, "internal_error", "An unexpected error occurred")

    app.include_router(catalog.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    return app


app = create_app()
