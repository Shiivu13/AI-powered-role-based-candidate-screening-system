"""Test fixtures: isolated data dir, synthetic knowledge base, fake LLM."""
from __future__ import annotations

import os
import tempfile

# Configure the app *before* it is imported anywhere.
_TMP = tempfile.mkdtemp(prefix="screening-tests-")
os.environ.update(
    {
        "DATA_DIR": _TMP,
        "LLM_PROVIDER": "offline",
        "GEMINI_API_KEY": "",
        "EMBEDDING_PROVIDER": "lsa",
        "EMBEDDING_DIM": "64",
        "CHUNK_SIZE": "450",
        "CHUNK_OVERLAP": "100",
        "MIN_CHUNK_CHARS": "120",
        "ENVIRONMENT": "test",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.ai import llm as llm_module  # noqa: E402
from app.ai.catalog import ROLES  # noqa: E402
from app.ai.llm import LLMClient  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.rag.chunking import chunk_pages  # noqa: E402
from app.rag.embeddings import get_embedder  # noqa: E402
from app.rag.retriever import HybridRetriever  # noqa: E402
from app.rag.vector_store import VectorStore  # noqa: E402
from tests.corpus import corpus_pages  # noqa: E402

RESUME = """Priya Sharma
Machine Learning Engineer

EXPERIENCE
ML Engineer, PayWise Fintech            Jan 2022 - Present
- Built credit-risk models with XGBoost, random forest and gradient boosting.
- Ran cross-validation and tracked precision and recall; deployed with FastAPI and Docker.
Data Science Intern, RetailCo           Jun 2021 - Dec 2021
- Customer segmentation with k-means clustering and PCA using pandas.

SKILLS: Python, SQL, scikit-learn, XGBoost, PyTorch, pandas
"""


@pytest.fixture(scope="session", autouse=True)
def knowledge_base():
    settings = get_settings()
    chunks = chunk_pages(
        corpus_pages(), book_id="testbook", book_title="Test ML Textbook",
        chunk_size=settings.chunk_size, overlap=settings.chunk_overlap, min_chars=settings.min_chunk_chars,
    )
    embedder = get_embedder(refresh=True)
    embedder.fit([c.embedding_text for c in chunks] * 2)  # duplicate so min_df=2 keeps vocabulary
    vectors = embedder.embed([c.embedding_text for c in chunks])
    for role_id in ROLES:
        store = VectorStore(role_id)
        store.reset()
        store.add(chunks, vectors)
    HybridRetriever.invalidate()
    return chunks


class FakeLLM(LLMClient):
    """Deterministic stand-in for Gemini that answers by prompt type."""

    name = "fake"
    model = "fake-llm"

    def __init__(self, scores=(8.5, 5.0, 3.0)):
        self.calls: list[str] = []
        self._scores = list(scores)

    def generate_json(self, system: str, user: str, *, temperature=None) -> dict:
        if "structured profile" in system:
            self.calls.append("resume")
            return {
                "name": "Priya Sharma", "headline": "ML engineer in fintech",
                "skills": ["gradient boosting", "credit risk modelling"], "technologies": ["XGBoost", "FastAPI"],
                "domains": ["Fintech"], "years_experience": 3, "seniority": "mid",
                "education": ["B.Tech"], "projects": [{"name": "Credit scoring", "summary": "XGBoost model", "technologies": ["XGBoost"]}],
                "strength_signals": ["Improved AUC"],
            }
        if "follow-up" in system:
            self.calls.append("follow_up")
            return {"question": "Why does early stopping help gradient boosting?", "expected_points": ["validation set"], "source_ids": ["S1"], "rationale": "probe"}
        if "ONE interview question" in system:
            self.calls.append("question")
            n = self.calls.count("question")
            return {"question": f"Grounded question number {n} about the sources?", "question_type": "applied",
                    "expected_points": ["point a", "point b"], "source_ids": ["S2", "S1"], "rationale": "fits resume"}
        if "grading one answer" in system:
            self.calls.append("grade")
            score = self._scores.pop(0) if self._scores else 6.0
            return {"score": score, "verdict": "good", "covered_points": ["point a"], "missing_points": ["point b"],
                    "misconceptions": [], "feedback": "ok"}
        if "debrief" in system:
            self.calls.append("report")
            return {"summary": "LLM summary", "strengths": ["s"], "improvement_areas": ["i"],
                    "resume_alignment": "aligned", "suggested_next_steps": ["next"]}
        raise AssertionError(f"unexpected prompt: {system[:80]}")


@pytest.fixture
def fake_llm():
    fake = FakeLLM()
    llm_module.set_llm(fake)
    yield fake
    llm_module.set_llm(None)


@pytest.fixture
def offline_llm():
    llm_module.set_llm(None)
    yield
    llm_module.set_llm(None)


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def resume_text() -> str:
    return RESUME
