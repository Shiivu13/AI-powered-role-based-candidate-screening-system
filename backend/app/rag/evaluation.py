"""Offline retrieval evaluation.

There is no hand-labelled relevance data for these textbooks, so the
benchmark uses the books' own structure as weak supervision:

    query    = the title of a numbered section, e.g. "Bayes Theorem And Concept Learning"
    relevant = every chunk that belongs to that section

To stop the benchmark from trivially matching the title, the evaluation index
is rebuilt from the *chunk text only*: no section header in the BM25 document
and no contextual header in the embedded text. A retriever therefore only
scores well if the section's body text is what it finds for the title.

This is not a perfect proxy for "useful interview context", but it is cheap,
reproducible, and sensitive to the decisions that matter here: dense vs sparse
vs hybrid, the MMR trade-off, and chunk size.
"""
from __future__ import annotations

import math
import random
import re
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Callable

import numpy as np
from rank_bm25 import BM25Okapi

from app.rag.embeddings import Embedder, LSAEmbedder
from app.rag.retriever import mmr_select, tokenize

_NUMBERED = re.compile(r"^\d+(\.\d+)+\.?\s+")
_GENERIC = re.compile(r"summary|further reading|exercise|introduction|overview|references|bibliograph|conclusion|notes", re.I)


@dataclass
class Doc:
    id: str
    text: str
    book_id: str
    section: str


@dataclass
class EvalQuery:
    query: str
    relevant: set[str]
    section: str
    book_id: str


def build_eval_set(docs: list[Doc], *, max_queries: int = 150, min_chunks: int = 2, max_chunks: int = 25, seed: int = 13) -> list[EvalQuery]:
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for d in docs:
        groups[(d.book_id, d.section)].append(d.id)
    queries = []
    for (book_id, section), ids in groups.items():
        if not _NUMBERED.match(section) or _GENERIC.search(section):
            continue
        title = _NUMBERED.sub("", section).strip()
        if len(tokenize(title)) < 2 or not (min_chunks <= len(ids) <= max_chunks):
            continue
        queries.append(EvalQuery(title, set(ids), section, book_id))
    random.Random(seed).shuffle(queries)
    return sorted(queries[:max_queries], key=lambda q: (q.book_id, q.section))


class EvalIndex:
    """In-memory dense + BM25 index over chunk text only (no headers)."""

    def __init__(self, docs: list[Doc], embedder: Embedder):
        self.docs = docs
        self.ids = [d.id for d in docs]
        self.embedder = embedder
        self.matrix = embedder.embed([d.text for d in docs])
        self.vectors = {d.id: self.matrix[i] for i, d in enumerate(docs)}
        self.bm25 = BM25Okapi([tokenize(d.text) for d in docs])

    def dense(self, query: str, n: int) -> list[str]:
        scores = self.matrix @ self.embedder.embed_one(query)
        return [self.ids[i] for i in np.argsort(scores)[::-1][:n]]

    def sparse(self, query: str, n: int) -> list[str]:
        scores = self.bm25.get_scores(tokenize(query))
        return [self.ids[i] for i in np.argsort(scores)[::-1][:n] if scores[i] > 0]

    def rrf(self, query: str, n: int, k: int = 60, candidates: int = 25, sparse_weight: float = 1.0) -> dict[str, float]:
        fused: dict[str, float] = {}
        for weight, ranking in ((1.0, self.dense(query, candidates)), (sparse_weight, self.sparse(query, candidates))):
            for rank, cid in enumerate(ranking):
                fused[cid] = fused.get(cid, 0.0) + weight / (k + rank + 1)
        return dict(sorted(fused.items(), key=lambda x: x[1], reverse=True)[:n])

    def hybrid(self, query: str, n: int, sparse_weight: float = 1.0) -> list[str]:
        return list(self.rrf(query, n, sparse_weight=sparse_weight))

    def hybrid_mmr(self, query: str, n: int, lam: float, sparse_weight: float = 1.0) -> list[str]:
        fused = self.rrf(query, max(n * 3, 30), sparse_weight=sparse_weight)
        cands = list(fused)
        return mmr_select(cands, fused, {c: self.vectors[c] for c in cands}, n, lam)


def _metrics(ranked: list[str], relevant: set[str], vectors: dict[str, np.ndarray]) -> dict[str, float]:
    hits = [1 if cid in relevant else 0 for cid in ranked[:10]]
    rr = next((1.0 / (i + 1) for i, h in enumerate(hits) if h), 0.0)
    dcg = sum(h / math.log2(i + 2) for i, h in enumerate(hits))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(relevant), 10)))
    top4 = ranked[:4]
    pairs = [(a, b) for i, a in enumerate(top4) for b in top4[i + 1 :]]
    redundancy = mean(float(vectors[a] @ vectors[b]) for a, b in pairs) if pairs else 0.0
    return {
        "hit@1": float(hits[0]) if hits else 0.0,
        "hit@4": float(any(hits[:4])),
        "precision@4": sum(hits[:4]) / 4,
        "mrr@10": rr,
        "ndcg@10": dcg / ideal if ideal else 0.0,
        "redundancy@4": redundancy,
    }


def evaluate(index: EvalIndex, queries: list[EvalQuery], methods: dict[str, Callable[[str, int], list[str]]]) -> dict[str, dict[str, float]]:
    results: dict[str, dict[str, float]] = {}
    for name, fn in methods.items():
        per_query = [_metrics(fn(q.query, 10), q.relevant, index.vectors) for q in queries]
        results[name] = {k: round(mean(m[k] for m in per_query), 3) for k in per_query[0]}
    return results


def standard_methods(index: EvalIndex, lambdas=(0.9, 0.7), sparse_weights=(0.5, 0.3)) -> dict[str, Callable[[str, int], list[str]]]:
    methods: dict[str, Callable[[str, int], list[str]]] = {
        "dense (LSA)": index.dense,
        "sparse (BM25)": index.sparse,
        "hybrid RRF, equal weights": index.hybrid,
    }
    for w in sparse_weights:
        methods[f"hybrid RRF, BM25 weight {w}"] = lambda q, n, w=w: index.hybrid(q, n, w)
    # MMR on top of the fusion used in production (BM25 weight 0.5, see config.py)
    for lam in lambdas:
        methods[f"hybrid (BM25 0.5) + MMR λ={lam}"] = lambda q, n, lam=lam: index.hybrid_mmr(q, n, lam, 0.5)
    return methods


def fit_text_only_lsa(docs: list[Doc], dim: int = 384) -> LSAEmbedder:
    """A fresh LSA space fitted on chunk bodies only, so section titles cannot
    leak into the evaluation through the embedding model."""
    tmp = tempfile.mkdtemp()
    embedder = LSAEmbedder(Path(tmp) / "lsa.joblib", dim)
    embedder.fit([d.text for d in docs])
    return embedder


def chunk_size_ablation(pages_by_book: dict[str, tuple[str, list]], sizes: list[int], *, overlap_ratio: float = 0.2,
                        dim: int = 256, max_queries: int = 150) -> dict[int, dict]:
    """Re-chunk the same books at several sizes, fit a fresh LSA space for each,
    and score hybrid retrieval. Relevance labels come from section membership,
    so they stay comparable across chunkings."""
    from app.rag.chunking import chunk_pages

    corpora: dict[int, list[Doc]] = {}
    for size in sizes:
        corpora[size] = [
            Doc(c.id, c.text, c.book_id, c.section)
            for book_id, (title, pages) in pages_by_book.items()
            for c in chunk_pages(pages, book_id=book_id, book_title=title, chunk_size=size,
                                 overlap=int(size * overlap_ratio), min_chars=min(200, size // 3))
        ]
    # One fixed query set: sections evaluable at *every* size (>=2 chunks even
    # at the largest size), so the comparison is not biased by which sections
    # happen to qualify.
    per_size = {size: {(q.book_id, q.section): q for q in build_eval_set(docs, max_queries=10_000)} for size, docs in corpora.items()}
    common = set.intersection(*(set(v) for v in per_size.values()))
    keys = sorted(common)
    random.Random(13).shuffle(keys)
    keys = keys[:max_queries]

    out: dict[int, dict] = {}
    for size, docs in corpora.items():
        index = EvalIndex(docs, fit_text_only_lsa(docs, dim))
        queries = [per_size[size][k] for k in keys]
        scores = evaluate(index, queries, {"hybrid": lambda q, n: index.hybrid(q, n, 0.5)})["hybrid"]
        out[size] = {"chunks": len(docs), "avg_chars": int(mean(len(d.text) for d in docs)), "queries": len(queries), **scores}
    return out
