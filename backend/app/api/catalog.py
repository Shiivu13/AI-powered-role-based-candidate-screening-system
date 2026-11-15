"""Roles, knowledge-base status and a retrieval playground."""
from __future__ import annotations

from fastapi import APIRouter

from app.ai.catalog import ROLES, role_books, role_topics
from app.config import get_settings
from app.errors import NotFound
from app.rag.ingest import read_manifest
from app.rag.retriever import HybridRetriever
from app.schemas import HealthOut, RoleOut, SearchIn, SearchOut

router = APIRouter(tags=["catalog"])


def _role_out(role_id: str, manifest: dict) -> dict:
    role = ROLES[role_id]
    books_dir = get_settings().resolved_books_dir
    role_manifest = manifest.get("roles", {}).get(role_id, {})
    ingested = set(role_manifest.get("books", []))
    chunks = role_manifest.get("chunks", 0)
    return {
        "id": role.id,
        "title": role.title,
        "description": role.description,
        "books": [
            {
                "id": b.id,
                "title": b.title,
                "author": b.author,
                "available": b.id in ingested or (books_dir / b.filename).exists(),
                "chunks": manifest.get("books", {}).get(b.id, {}).get("chunks", 0) if b.id in ingested else 0,
            }
            for b in role_books(role)
        ],
        "topics": [{"id": t.id, "name": t.name, "description": t.description} for t in role_topics(role)],
        "knowledge_base_ready": chunks > 0,
        "knowledge_base_chunks": chunks,
    }


@router.get("/roles", response_model=list[RoleOut])
def list_roles():
    manifest = read_manifest()
    return [_role_out(r, manifest) for r in ROLES]


@router.get("/roles/{role_id}", response_model=RoleOut)
def get_role(role_id: str):
    if role_id not in ROLES:
        raise NotFound(f"Unknown role '{role_id}'")
    return _role_out(role_id, read_manifest())


@router.post("/knowledge/search", response_model=SearchOut)
def search_knowledge(payload: SearchIn):
    """Inspect what the RAG retriever returns for an arbitrary query."""
    if payload.role_id not in ROLES:
        raise NotFound(f"Unknown role '{payload.role_id}'")
    result = HybridRetriever(payload.role_id).retrieve([payload.query], top_k=payload.top_k, mode=payload.mode)
    return {
        "role_id": payload.role_id,
        "mode": payload.mode,
        "queries": result.queries,
        "diagnostics": result.diagnostics,
        "chunks": [c.to_trace() for c in result.chunks],
    }


@router.get("/knowledge/benchmark")
def retrieval_benchmark():
    """Latest output of ``scripts/benchmark_retrieval.py`` (committed under docs/benchmarks)."""
    import json

    from app.config import BACKEND_DIR

    path = BACKEND_DIR.parent / "docs" / "benchmarks" / "retrieval.json"
    if not path.exists():
        raise NotFound("No benchmark has been run yet. Run `python -m scripts.benchmark_retrieval`.")
    return json.loads(path.read_text())


@router.get("/health", response_model=HealthOut)
def health():
    from app.ai.llm import get_llm

    settings = get_settings()
    llm = get_llm()
    manifest = read_manifest()
    return {
        "status": "ok",
        "llm_provider": llm.name,
        "llm_model": llm.model,
        "embedding_provider": settings.embedding_provider,
        "database": settings.resolved_database_url.split(":", 1)[0],
        "knowledge_base": {r: v.get("chunks", 0) for r, v in manifest.get("roles", {}).items()},
    }
