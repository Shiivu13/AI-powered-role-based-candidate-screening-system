"""Embedding providers.

``LSAEmbedder`` (default) is fully local: a TF-IDF model (uni+bi-grams,
sublinear tf) fitted on the whole knowledge corpus, projected to a dense
space with truncated SVD (Latent Semantic Analysis) and L2-normalised. It needs
no model download or API key, is fast on CPU, and because it is fitted on the
textbooks themselves it captures the domain's co-occurrence structure (e.g.
"entropy" ~ "information gain"). Its weakness (exact term matching across
paraphrases) is compensated for by hybrid retrieval with BM25 in
``retriever.py``.

``GeminiEmbedder`` and ``SentenceTransformerEmbedder`` are drop-in neural
alternatives selected with ``EMBEDDING_PROVIDER``.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Sequence

import numpy as np

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class Embedder(ABC):
    name: str

    @abstractmethod
    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Return an (n, d) float32 array of L2-normalised embeddings."""

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]

    def fit(self, texts: Sequence[str]) -> None:  # pragma: no cover - default no-op
        """Providers that learn from the corpus override this."""

    @property
    def is_ready(self) -> bool:
        return True


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (matrix / norms).astype(np.float32)


class LSAEmbedder(Embedder):
    name = "lsa"

    def __init__(self, model_path: Path, dim: int = 256, max_features: int = 20_000):
        self.model_path = model_path
        self.dim = dim
        self.max_features = max_features
        self._vectorizer = None
        self._svd = None
        if model_path.exists():
            self._load()

    def _load(self) -> None:
        import joblib

        bundle = joblib.load(self.model_path)
        self._vectorizer = bundle["vectorizer"]
        self._svd = bundle["svd"]

    @property
    def is_ready(self) -> bool:
        return self._vectorizer is not None

    def fit(self, texts: Sequence[str]) -> None:
        import joblib
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer

        logger.info("Fitting LSA embedder on %d texts", len(texts))
        vectorizer = TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.5,
            max_features=self.max_features,
            sublinear_tf=True,
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9\-]{1,}\b",
        )
        tfidf = vectorizer.fit_transform(texts)
        n_components = min(self.dim, tfidf.shape[1] - 1, max(len(texts) - 1, 1))
        svd = TruncatedSVD(n_components=n_components, random_state=42, n_iter=7)
        svd.fit(tfidf)
        self._vectorizer, self._svd = vectorizer, svd
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"vectorizer": vectorizer, "svd": svd}, self.model_path)
        logger.info(
            "LSA fitted: vocab=%d dims=%d explained_var=%.2f",
            len(vectorizer.vocabulary_), n_components, svd.explained_variance_ratio_.sum(),
        )

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        if not self.is_ready:
            raise RuntimeError(
                "LSA embedder is not fitted. Run `python -m scripts.ingest_kb` first."
            )
        return _normalize(self._svd.transform(self._vectorizer.transform(list(texts))))


class GeminiEmbedder(Embedder):
    name = "gemini"

    def __init__(self, api_key: str, model: str, dim: int):
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is required for EMBEDDING_PROVIDER=gemini")
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.dim = dim

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        from google.genai import types

        vectors: list[list[float]] = []
        for start in range(0, len(texts), 100):
            batch = list(texts[start : start + 100])
            result = self._client.models.embed_content(
                model=self.model,
                contents=batch,
                config=types.EmbedContentConfig(output_dimensionality=self.dim),
            )
            vectors.extend(e.values for e in result.embeddings)
        return _normalize(np.asarray(vectors, dtype=np.float32))


class SentenceTransformerEmbedder(Embedder):
    name = "sentence-transformers"

    def __init__(self, model_name: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Install `sentence-transformers` to use EMBEDDING_PROVIDER=sentence-transformers"
            ) from exc
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        return _normalize(np.asarray(self._model.encode(list(texts), batch_size=64)))


_EMBEDDER: Embedder | None = None


def get_embedder(settings: Settings | None = None, *, refresh: bool = False) -> Embedder:
    global _EMBEDDER
    if _EMBEDDER is not None and not refresh:
        return _EMBEDDER
    settings = settings or get_settings()
    if settings.embedding_provider == "gemini":
        _EMBEDDER = GeminiEmbedder(
            settings.gemini_api_key, settings.gemini_embedding_model, settings.embedding_dim
        )
    elif settings.embedding_provider == "sentence-transformers":
        _EMBEDDER = SentenceTransformerEmbedder(settings.st_model_name)
    elif settings.effective_vector_backend == "numpy":
        from app.rag.compact import NumpyLSAEmbedder

        _EMBEDDER = NumpyLSAEmbedder(settings.kb_dir)
    else:
        _EMBEDDER = LSAEmbedder(
            settings.resolved_index_dir / "lsa.joblib", settings.embedding_dim, settings.lsa_max_features
        )
    return _EMBEDDER
