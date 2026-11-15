"""Hybrid retrieval: dense (vector DB) + sparse (BM25), fused and diversified.

Pipeline for one interview question::

    multiple queries ──► dense top-N  (Chroma, cosine)  ─┐
                    └──► sparse top-N (BM25 in memory)  ─┴► Reciprocal Rank Fusion
                                                              │
                         drop chunks already used this session│
                                                              ▼
                                     Maximal Marginal Relevance (top-k, diverse)
                                                              ▼
                                        grounding diagnostics for the trace

Why this design:

* **Multi-query** – one query per angle (topic definition, candidate's own
  skills, applied use) recalls more relevant passages than one long query.
* **Hybrid** – dense vectors capture topical similarity, BM25 nails exact
  technical terms ("ID3", "EM algorithm") that embeddings can blur.
* **RRF** – fuses rankings without having to calibrate BM25 scores against
  cosine similarities.
* **MMR** – avoids handing the generator four near-identical overlapping
  chunks; diverse context produces better, less trivial questions.
* **Session de-duplication** – each question in an interview is grounded in
  fresh material.
"""
from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field

import numpy as np
from rank_bm25 import BM25Okapi
from app.rag.stopwords import ENGLISH_STOP_WORDS

from app.config import get_settings
from app.rag.embeddings import get_embedder
from app.rag.vector_store import StoredChunk, VectorStore

logger = logging.getLogger(__name__)

_TOKEN = re.compile(r"[a-z][a-z0-9\-]+")
_LOW_VALUE_SECTION = re.compile(r"exercises?|further reading|bibliograph|references", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    tokens = []
    for tok in _TOKEN.findall(text.lower()):
        if tok in ENGLISH_STOP_WORDS or len(tok) < 2:
            continue
        # very light stemming keeps "trees"/"tree", "networks"/"network" together
        if len(tok) > 4 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        tokens.append(tok)
    return tokens


@dataclass
class RetrievedChunk:
    id: str
    text: str
    book_id: str
    book_title: str
    section: str
    page_start: int
    page_end: int
    rrf_score: float
    dense_score: float | None
    bm25_rank: int | None
    dense_rank: int | None
    matched_queries: list[int] = field(default_factory=list)

    def citation(self) -> str:
        pages = (
            f"p.{self.page_start}"
            if self.page_start == self.page_end
            else f"pp.{self.page_start}-{self.page_end}"
        )
        section = f", {self.section}" if self.section else ""
        return f"{self.book_title}{section} ({pages})"

    def to_trace(self, snippet_chars: int = 600) -> dict:
        return {
            "chunk_id": self.id,
            "book_id": self.book_id,
            "book_title": self.book_title,
            "section": self.section,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "citation": self.citation(),
            "rrf_score": round(self.rrf_score, 5),
            "dense_score": None if self.dense_score is None else round(self.dense_score, 4),
            "dense_rank": self.dense_rank,
            "bm25_rank": self.bm25_rank,
            "matched_queries": self.matched_queries,
            "snippet": self.text[:snippet_chars],
        }


@dataclass
class RetrievalResult:
    queries: list[str]
    chunks: list[RetrievedChunk]
    diagnostics: dict

    def context_block(self) -> str:
        parts = []
        for i, c in enumerate(self.chunks, start=1):
            parts.append(f"[S{i}] {c.citation()}\n{c.text}")
        return "\n\n".join(parts)


def mmr_select(
    candidates: list[str],
    relevance: dict[str, float],
    vectors: dict[str, np.ndarray],
    top_k: int,
    lam: float,
) -> list[str]:
    """Maximal Marginal Relevance. ``relevance`` is normalised to [0, 1] here so
    that RRF scores and cosine similarities live on comparable scales.
    ``lam=1`` is pure relevance ranking; lower values trade relevance for diversity."""
    if not candidates:
        return []
    top = max(relevance[c] for c in candidates) or 1.0
    rel = {c: relevance[c] / top for c in candidates}
    selected: list[str] = []
    remaining = list(candidates)
    while remaining and len(selected) < top_k:
        best, best_score = remaining[0], -1e9
        for c in remaining:
            redundancy = max((float(vectors[c] @ vectors[s]) for s in selected), default=0.0)
            score = lam * rel[c] - (1 - lam) * redundancy
            if score > best_score:
                best, best_score = c, score
        selected.append(best)
        remaining.remove(best)
    return selected


class _BM25Index:
    def __init__(self, chunks: list[StoredChunk]):
        self.ids = [c.id for c in chunks]
        self.by_id = {c.id: c for c in chunks}
        self.bm25 = BM25Okapi([tokenize(c.text + " " + c.metadata.get("section", "")) for c in chunks])

    def search(self, query: str, n: int) -> list[str]:
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        top = np.argsort(scores)[::-1][:n]
        return [self.ids[i] for i in top if scores[i] > 0]


class HybridRetriever:
    _bm25_cache: dict[str, _BM25Index] = {}
    _lock = threading.Lock()

    def __init__(self, role_id: str):
        self.role_id = role_id
        self.settings = get_settings()
        self.store = VectorStore(role_id)
        self.embedder = get_embedder()

    @classmethod
    def invalidate(cls, role_id: str | None = None) -> None:
        with cls._lock:
            if role_id is None:
                cls._bm25_cache.clear()
            else:
                cls._bm25_cache.pop(role_id, None)

    def _bm25(self) -> _BM25Index:
        with self._lock:
            index = self._bm25_cache.get(self.role_id)
            if index is None:
                logger.info("Building BM25 index for role %s", self.role_id)
                index = _BM25Index(self.store.get_all())
                self._bm25_cache[self.role_id] = index
            return index

    def is_ready(self) -> bool:
        return self.embedder.is_ready and self.store.count() > 0

    def retrieve(
        self,
        queries: list[str],
        *,
        top_k: int | None = None,
        exclude_ids: set[str] | None = None,
        focus_terms: list[str] | None = None,
        mode: str = "hybrid",
        mmr_lambda: float | None = None,
    ) -> RetrievalResult:
        """``mode`` is "hybrid" (default), "dense" or "bm25"; the single-retriever
        modes exist for the retrieval explorer and the benchmark."""
        s = self.settings
        if mode not in {"hybrid", "dense", "bm25"}:
            raise ValueError(f"unknown retrieval mode: {mode}")
        top_k = top_k or s.retrieval_top_k
        exclude_ids = exclude_ids or set()
        queries = [q for q in dict.fromkeys(q.strip() for q in queries) if q]
        if not queries or not self.is_ready():
            return RetrievalResult(queries, [], {"status": "knowledge_base_empty"})

        query_vecs = self.embedder.embed(queries)
        bm25 = self._bm25()

        rrf: dict[str, float] = {}
        dense_best: dict[str, float] = {}
        dense_rank: dict[str, int] = {}
        bm25_rank: dict[str, int] = {}
        matched: dict[str, set[int]] = {}
        pool: dict[str, StoredChunk] = {}

        for qi, (query, qvec) in enumerate(zip(queries, query_vecs)):
            dense_hits = self.store.query(qvec, s.retrieval_candidates) if mode != "bm25" else []
            for rank, (chunk, sim) in enumerate(dense_hits):
                pool[chunk.id] = chunk
                rrf[chunk.id] = rrf.get(chunk.id, 0.0) + 1.0 / (s.rrf_k + rank + 1)
                dense_best[chunk.id] = max(dense_best.get(chunk.id, -1.0), sim)
                dense_rank[chunk.id] = min(dense_rank.get(chunk.id, 10**6), rank + 1)
                matched.setdefault(chunk.id, set()).add(qi)
            sparse_hits = bm25.search(query, s.retrieval_candidates) if mode != "dense" else []
            for rank, chunk_id in enumerate(sparse_hits):
                rrf[chunk_id] = rrf.get(chunk_id, 0.0) + s.bm25_weight / (s.rrf_k + rank + 1)
                bm25_rank[chunk_id] = min(bm25_rank.get(chunk_id, 10**6), rank + 1)
                matched.setdefault(chunk_id, set()).add(qi)

        # Exercise lists and reading lists mention many topics but explain none.
        for cid in rrf:
            section = bm25.by_id[cid].metadata.get("section", "") if cid in bm25.by_id else ""
            if _LOW_VALUE_SECTION.search(section):
                rrf[cid] *= 0.75

        candidates = [cid for cid in rrf if cid not in exclude_ids]
        if len(candidates) < top_k:  # small corpus: allow reuse rather than starve
            candidates = list(rrf)
        candidates.sort(key=lambda cid: rrf[cid], reverse=True)
        candidates = candidates[: max(top_k * 6, 20)]

        missing = [cid for cid in candidates if cid not in pool or pool[cid].embedding is None]
        for chunk in self.store.get_many(missing):
            pool[chunk.id] = chunk

        usable = [c for c in candidates if c in pool and pool[c].embedding is not None]
        selected = mmr_select(
            usable,
            {c: rrf[c] for c in usable},
            {c: pool[c].embedding for c in usable},
            top_k,
            s.mmr_lambda if mmr_lambda is None else mmr_lambda,
        )

        chunks = []
        for cid in selected:
            c = pool[cid]
            m = c.metadata
            chunks.append(
                RetrievedChunk(
                    id=cid,
                    text=c.text,
                    book_id=m.get("book_id", ""),
                    book_title=m.get("book_title", ""),
                    section=m.get("section", ""),
                    page_start=int(m.get("page_start", 0)),
                    page_end=int(m.get("page_end", 0)),
                    rrf_score=rrf[cid],
                    dense_score=dense_best.get(cid),
                    dense_rank=dense_rank.get(cid),
                    bm25_rank=bm25_rank.get(cid),
                    matched_queries=sorted(matched.get(cid, set())),
                )
            )
        return RetrievalResult(queries, chunks, self._diagnostics(chunks, focus_terms, len(rrf)))

    @staticmethod
    def _diagnostics(chunks: list[RetrievedChunk], focus_terms: list[str] | None, pool_size: int) -> dict:
        if not chunks:
            return {"status": "no_results", "candidate_pool": pool_size}
        text = " ".join(c.text.lower() for c in chunks)
        coverage = None
        hit_terms: list[str] = []
        if focus_terms:
            hit_terms = [t for t in focus_terms if t.lower() in text]
            coverage = round(len(hit_terms) / len(focus_terms), 3)
        dense = [c.dense_score for c in chunks if c.dense_score is not None]
        mean_dense = round(float(np.mean(dense)), 4) if dense else None
        both = sum(1 for c in chunks if c.dense_rank and c.bm25_rank)
        grounded = (coverage is None or coverage > 0) and (mean_dense is None or mean_dense > 0.15)
        return {
            "status": "ok" if grounded else "weak_grounding",
            "candidate_pool": pool_size,
            "mean_dense_similarity": mean_dense,
            "focus_term_coverage": coverage,
            "focus_terms_found": hit_terms,
            "chunks_agreed_by_both_retrievers": both,
            "books": sorted({c.book_title for c in chunks}),
        }
