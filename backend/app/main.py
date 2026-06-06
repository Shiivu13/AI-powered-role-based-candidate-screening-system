import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.api.routes import sessions, interview, knowledge


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    _bootstrap_knowledge()
    yield


def _bootstrap_knowledge():
    from app.ml.vector_store import collection_exists_with_data
    needs_ingest = any(
        not collection_exists_with_data(role) for role in ["ai_ml", "data_science", "backend"]
    )
    if needs_ingest:
        import threading
        def _run():
            import importlib.util, sys as _sys
            spec = importlib.util.spec_from_file_location(
                "ingest_knowledge",
                os.path.join(os.path.dirname(__file__), "..", "scripts", "ingest_knowledge.py")
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.ingest_all()
        t = threading.Thread(target=_run, daemon=True)
        t.start()


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered role-based candidate screening system",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"],
    # Allow any Vercel deployment of this project (prod + preview URLs)
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(interview.router)
app.include_router(knowledge.router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
