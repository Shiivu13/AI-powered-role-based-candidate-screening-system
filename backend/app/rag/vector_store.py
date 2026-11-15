"""Vector database access (ChromaDB, persistent, embedded mode).

One collection per (role, embedding provider). Isolating roles keeps retrieval
scoped to the role's own books without metadata filters, and keying on the
provider means switching embedding models never mixes incompatible vectors.
Embeddings are always computed by our own :mod:`embeddings` module and passed
in explicitly, so Chroma never downloads its default model.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from app.config import get_settings
from app.rag.chunking import Chunk

logger = logging.getLogger(__name__)


@dataclass
class StoredChunk:
    id: str
    text: str
    metadata: dict
    embedding: np.ndarray | None = None


@lru_cache
def _client():
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    settings = get_settings()
    return chromadb.PersistentClient(
        path=str(settings.resolved_chroma_dir),
        settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
    )


def collection_name(role_id: str, provider: str | None = None) -> str:
    provider = provider or get_settings().embedding_provider
    return f"kb_{role_id}_{provider}".replace("-", "_")


class VectorStore:
    def __init__(self, role_id: str, provider: str | None = None):
        self.role_id = role_id
        self.name = collection_name(role_id, provider)
        self._collection = _client().get_or_create_collection(
            name=self.name,
            metadata={"hnsw:space": "cosine", "role_id": role_id},
            embedding_function=None,
        )

    # -- writes -------------------------------------------------------------
    def reset(self) -> None:
        _client().delete_collection(self.name)
        self._collection = _client().get_or_create_collection(
            name=self.name,
            metadata={"hnsw:space": "cosine", "role_id": self.role_id},
            embedding_function=None,
        )

    def delete_book(self, book_id: str) -> None:
        self._collection.delete(where={"book_id": book_id})

    def add(self, chunks: list[Chunk], embeddings: np.ndarray, batch_size: int = 500) -> None:
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            self._collection.upsert(
                ids=[c.id for c in batch],
                documents=[c.text for c in batch],
                embeddings=embeddings[start : start + batch_size].tolist(),
                metadatas=[
                    {
                        "book_id": c.book_id,
                        "book_title": c.book_title,
                        "section": c.section,
                        "page_start": c.page_start,
                        "page_end": c.page_end,
                        "position": c.position,
                    }
                    for c in batch
                ],
            )

    # -- reads --------------------------------------------------------------
    def count(self) -> int:
        return self._collection.count()

    def query(self, embedding: np.ndarray, n_results: int) -> list[tuple[StoredChunk, float]]:
        if self.count() == 0:
            return []
        result = self._collection.query(
            query_embeddings=[embedding.tolist()],
            n_results=min(n_results, self.count()),
            include=["documents", "metadatas", "distances", "embeddings"],
        )
        hits = []
        for i, chunk_id in enumerate(result["ids"][0]):
            similarity = 1.0 - float(result["distances"][0][i])  # cosine distance -> similarity
            hits.append(
                (
                    StoredChunk(
                        id=chunk_id,
                        text=result["documents"][0][i],
                        metadata=result["metadatas"][0][i],
                        embedding=np.asarray(result["embeddings"][0][i], dtype=np.float32),
                    ),
                    similarity,
                )
            )
        return hits

    def get_all(self, include_embeddings: bool = False) -> list[StoredChunk]:
        total = self.count()
        out: list[StoredChunk] = []
        include = ["documents", "metadatas"] + (["embeddings"] if include_embeddings else [])
        for offset in range(0, total, 5000):
            page = self._collection.get(include=include, limit=5000, offset=offset)
            for i, chunk_id in enumerate(page["ids"]):
                emb = None
                if include_embeddings:
                    emb = np.asarray(page["embeddings"][i], dtype=np.float32)
                out.append(StoredChunk(chunk_id, page["documents"][i], page["metadatas"][i], emb))
        return out

    def get_many(self, ids: list[str]) -> list[StoredChunk]:
        if not ids:
            return []
        page = self._collection.get(ids=ids, include=["documents", "metadatas", "embeddings"])
        return [
            StoredChunk(cid, page["documents"][i], page["metadatas"][i],
                        np.asarray(page["embeddings"][i], dtype=np.float32))
            for i, cid in enumerate(page["ids"])
        ]

    def book_stats(self) -> dict[str, int]:
        stats: dict[str, int] = {}
        for chunk in self.get_all():
            stats[chunk.metadata["book_id"]] = stats.get(chunk.metadata["book_id"], 0) + 1
        return stats
