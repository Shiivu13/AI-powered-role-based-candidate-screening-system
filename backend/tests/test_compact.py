"""The compact (NumPy-only) knowledge base must behave like the full one."""
import numpy as np
import pytest

from app.config import get_settings
from app.rag import compact
from app.rag.embeddings import get_embedder
from app.rag.vector_store import ChromaVectorStore, NumpyVectorStore


@pytest.fixture(scope="module")
def kb_dir(tmp_path_factory, knowledge_base):
    out = tmp_path_factory.mktemp("kb")
    compact.export(out)
    return out


def test_numpy_lsa_matches_sklearn(kb_dir):
    full = get_embedder()
    small = compact.NumpyLSAEmbedder(kb_dir)
    texts = ["Decision tree learning uses information gain and entropy.",
             "Gradient boosting fits trees to residual errors; bagging averages bootstrap models.",
             "zzz unknown words only"]
    a, b = full.embed(texts), small.embed(texts)
    # float16 storage of the SVD components costs a little precision, nothing more
    assert np.allclose(a[:2], b[:2], atol=2e-3)
    assert np.allclose(b[2], 0)


def test_numpy_store_ranks_like_chroma(kb_dir, monkeypatch):
    monkeypatch.setattr(get_settings(), "kb_dir", kb_dir)
    compact.load_role.cache_clear()
    query = get_embedder().embed_one("information gain entropy decision tree")
    chroma = [c.id for c, _ in ChromaVectorStore("ai_ml_engineer").query(query, 3)]
    numpy_ = [c.id for c, _ in NumpyVectorStore("ai_ml_engineer").query(query, 3)]
    assert chroma[0] == numpy_[0]
    assert len(set(chroma) & set(numpy_)) >= 2
    compact.load_role.cache_clear()
