"""Compact, read-only knowledge base for serverless deployments.

The full pipeline (scikit-learn LSA + ChromaDB) is ~300 MB of dependencies and
needs the books on disk. For a serverless function that is too heavy, so the
ingested knowledge base can be exported to a small set of files that only need
NumPy at runtime:

    kb/
      manifest.json            ingestion stats (same format as data/index/manifest.json)
      lsa_vocab.json.gz        vocabulary in column order
      lsa.npz                  idf (float32) + SVD components (float16)
      roles/<role>.npz         chunk embeddings (float16), row order = chunk order
      roles/<role>.jsonl.gz    chunk ids, text and metadata

``NumpyLSAEmbedder`` re-implements exactly the TF-IDF transform used at fit time
(lower-casing, token pattern, stop words, uni+bi-grams, sublinear tf, idf, L2),
followed by the SVD projection. ``tests/test_compact.py`` checks it against
scikit-learn.

Export with ``python -m scripts.export_kb`` after ``python -m scripts.ingest_kb``.
"""
from __future__ import annotations

import gzip
import json
import re
import shutil
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.rag.stopwords import ENGLISH_STOP_WORDS

_TOKEN = re.compile(r"(?u)\b[a-zA-Z][a-zA-Z0-9\-]{1,}\b")


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


# --------------------------------------------------------------------------- export
def export(out_dir: Path) -> dict:
    """Write the compact KB from the fitted LSA model and the Chroma collections."""
    import joblib

    from app.ai.catalog import ROLES
    from app.config import get_settings
    from app.rag.ingest import read_manifest
    from app.rag.vector_store import ChromaVectorStore

    settings = get_settings()
    bundle = joblib.load(settings.resolved_index_dir / "lsa.joblib")
    vectorizer, svd = bundle["vectorizer"], bundle["svd"]
    if vectorizer.ngram_range != (1, 2) or not vectorizer.sublinear_tf or vectorizer.norm != "l2":
        raise ValueError("compact export assumes the TF-IDF settings in embeddings.LSAEmbedder")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    (out_dir / "roles").mkdir(parents=True)

    vocab = sorted(vectorizer.vocabulary_, key=vectorizer.vocabulary_.get)
    with gzip.open(out_dir / "lsa_vocab.json.gz", "wt", encoding="utf-8") as fh:
        json.dump(vocab, fh)
    np.savez(out_dir / "lsa.npz", idf=vectorizer.idf_.astype(np.float32), components=svd.components_.astype(np.float16))

    stats = {}
    for role_id in ROLES:
        chunks = ChromaVectorStore(role_id).get_all(include_embeddings=True)
        if not chunks:
            continue
        np.savez(out_dir / "roles" / f"{role_id}.npz", embeddings=np.stack([c.embedding for c in chunks]).astype(np.float16))
        with gzip.open(out_dir / "roles" / f"{role_id}.jsonl.gz", "wt", encoding="utf-8") as fh:
            for c in chunks:
                fh.write(json.dumps({"id": c.id, "text": c.text, "metadata": c.metadata}) + "\n")
        stats[role_id] = len(chunks)
    manifest = read_manifest()
    manifest["compact"] = {"dims": int(svd.components_.shape[0]), "vocab": len(vocab), "roles": stats}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


# --------------------------------------------------------------------------- runtime
class NumpyLSAEmbedder:
    """Query-time LSA embedder that needs only NumPy."""

    name = "lsa"

    def __init__(self, kb_dir: Path):
        with gzip.open(kb_dir / "lsa_vocab.json.gz", "rt", encoding="utf-8") as fh:
            self.vocab = {term: i for i, term in enumerate(json.load(fh))}
        data = np.load(kb_dir / "lsa.npz")
        self.idf = data["idf"].astype(np.float32)
        self.components_t = data["components"].astype(np.float32).T  # (vocab, dims)

    @property
    def is_ready(self) -> bool:
        return True

    def _tfidf_rows(self, text: str) -> tuple[np.ndarray, np.ndarray]:
        words = [w for w in _TOKEN.findall(text.lower()) if w not in ENGLISH_STOP_WORDS]
        counts: dict[int, int] = {}
        grams = words + [f"{a} {b}" for a, b in zip(words, words[1:])]
        for g in grams:
            idx = self.vocab.get(g)
            if idx is not None:
                counts[idx] = counts.get(idx, 0) + 1
        if not counts:
            return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.float32)
        cols = np.fromiter(counts.keys(), dtype=np.int64)
        tf = np.fromiter(counts.values(), dtype=np.float32)
        weights = (np.log(tf) + 1.0) * self.idf[cols]
        weights /= np.linalg.norm(weights)
        return cols, weights

    def embed(self, texts) -> np.ndarray:
        out = np.zeros((len(texts), self.components_t.shape[1]), dtype=np.float32)
        for i, text in enumerate(texts):
            cols, weights = self._tfidf_rows(text)
            if len(cols):
                out[i] = weights @ self.components_t[cols]
        return _normalize(out)

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]

    def fit(self, texts) -> None:  # pragma: no cover - read-only by design
        raise RuntimeError("The compact knowledge base is read-only; re-run ingestion to refit.")


@lru_cache
def load_role(kb_dir: Path, role_id: str) -> tuple[list[dict], np.ndarray]:
    path = kb_dir / "roles" / f"{role_id}.jsonl.gz"
    if not path.exists():
        return [], np.zeros((0, 1), dtype=np.float32)
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        records = [json.loads(line) for line in fh]
    embeddings = np.load(kb_dir / "roles" / f"{role_id}.npz")["embeddings"].astype(np.float32)
    return records, embeddings
