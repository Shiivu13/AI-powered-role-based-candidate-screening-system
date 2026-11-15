"""Application configuration.

All runtime configuration is read from environment variables (optionally via a
``.env`` file in the ``backend/`` directory). Nothing in the codebase reads
``os.environ`` directly; everything goes through :func:`get_settings`.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ON_VERCEL = bool(os.environ.get("VERCEL"))


def _default_data_dir() -> Path:
    # Serverless functions can only write to /tmp.
    return Path("/tmp/screenrag") if ON_VERCEL else BACKEND_DIR / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General -----------------------------------------------------------
    app_name: str = "AI Candidate Screening Platform"
    environment: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )
    # Optional regex for deployed frontends, e.g. r"https://.*\.vercel\.app"
    cors_origin_regex: str | None = None

    # --- Storage -----------------------------------------------------------
    data_dir: Path = Field(default_factory=_default_data_dir)
    database_url: str = ""  # defaults to sqlite file inside data_dir
    postgres_url: str = ""  # set automatically by Vercel/Neon Postgres integrations
    # Vector store: "chroma" (full pipeline, writable) or "numpy" (the compact,
    # read-only export in backend/kb used for serverless). "auto" uses Chroma
    # when it is installed and has been ingested, otherwise the compact export.
    vector_backend: Literal["auto", "chroma", "numpy"] = "auto"
    kb_dir: Path = BACKEND_DIR / "kb"
    session_secret: str = ""  # HMAC key for session snapshots (see services/snapshot.py)
    books_dir: Path | None = None  # defaults to data_dir / "books"
    chroma_dir: Path | None = None  # defaults to data_dir / "chroma"
    index_dir: Path | None = None  # defaults to data_dir / "index"

    # --- LLM -----------------------------------------------------------------
    # "auto" => use Gemini when GEMINI_API_KEY is set, otherwise offline mode.
    llm_provider: Literal["auto", "gemini", "offline"] = "auto"
    gemini_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.4
    llm_timeout_seconds: int = 60

    # --- Embeddings / retrieval ----------------------------------------------
    # "lsa" is fully local (TF-IDF + truncated SVD fitted on the corpus).
    # "gemini" uses the Gemini embedding API. "sentence-transformers" needs the
    # optional dependency and a downloadable model.
    embedding_provider: Literal["lsa", "gemini", "sentence-transformers"] = "lsa"
    # 256 dims over a 20k-term vocabulary keeps the shipped model at ~10 MB
    # (float16), small enough for a serverless function; see docs/benchmarks.
    embedding_dim: int = 256
    lsa_max_features: int = 20_000
    gemini_embedding_model: str = "gemini-embedding-001"
    st_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    chunk_size: int = 1000  # characters
    chunk_overlap: int = 200  # characters
    min_chunk_chars: int = 200

    retrieval_candidates: int = 25  # per query, per retriever
    retrieval_top_k: int = 4  # chunks handed to the generator
    # Defaults chosen from docs/benchmarks/retrieval.md (scripts/benchmark_retrieval.py):
    # BM25 at half weight was the most consistent fusion across the three roles.
    # MMR at 0.9 cuts top-4 redundancy by 15-20% for a similar drop in
    # precision@4, with hit@4 and MRR flat. That trade is deliberate: four
    # overlapping excerpts of one paragraph make worse question context than
    # four related ones. MMR at 0.7 cost 30-40% of precision@4, too much.
    mmr_lambda: float = 0.9  # relevance vs diversity trade-off
    bm25_weight: float = 0.5  # weight of the sparse ranking inside RRF
    rrf_k: int = 60

    # --- Interview -------------------------------------------------------------
    default_num_questions: int = 6
    min_num_questions: int = 3
    max_num_questions: int = 10
    max_follow_ups: int = 2
    max_resume_bytes: int = 4 * 1024 * 1024  # Vercel caps request bodies at 4.5 MB
    min_resume_chars: int = 80

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        if self.postgres_url:
            url = self.postgres_url
            for prefix in ("postgres://", "postgresql://"):
                if url.startswith(prefix):
                    return "postgresql+psycopg://" + url[len(prefix):]
            return url
        return f"sqlite:///{(self.data_dir / 'screening.db').as_posix()}"

    @property
    def resolved_books_dir(self) -> Path:
        return self.books_dir or self.data_dir / "books"

    @property
    def resolved_chroma_dir(self) -> Path:
        return self.chroma_dir or self.data_dir / "chroma"

    @property
    def resolved_index_dir(self) -> Path:
        return self.index_dir or self.data_dir / "index"

    @property
    def effective_vector_backend(self) -> Literal["chroma", "numpy"]:
        if self.vector_backend != "auto":
            return self.vector_backend
        try:
            import chromadb  # noqa: F401
        except ImportError:
            return "numpy"
        ingested = (self.resolved_chroma_dir / "chroma.sqlite3").exists()
        if not ingested and (self.kb_dir / "manifest.json").exists():
            return "numpy"
        return "chroma"

    @property
    def effective_llm_provider(self) -> Literal["gemini", "offline"]:
        if self.llm_provider == "auto":
            return "gemini" if self.gemini_api_key else "offline"
        return self.llm_provider


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    for path in (
        settings.data_dir,
        settings.resolved_books_dir,
        settings.resolved_chroma_dir,
        settings.resolved_index_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)
    return settings
