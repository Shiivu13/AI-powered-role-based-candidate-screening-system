from app.rag.chunking import chunk_pages
from app.rag.loaders import Page, is_low_quality, normalize_text
from app.rag.retriever import HybridRetriever, tokenize
from tests.corpus import corpus_pages


def test_normalize_rejoins_hyphenation_and_ligatures():
    assert normalize_text("classiﬁcation is learn-\ning") == "classification is learning"


def test_low_quality_detects_toc_and_accepts_prose():
    toc = "\n".join(f"{i}.{j} Some Section Title ........ {10 * i + j}" for i in range(1, 6) for j in range(1, 4))
    assert is_low_quality(toc)
    prose = corpus_pages()[0].text
    assert not is_low_quality(prose)


def test_chunks_respect_sections_and_carry_metadata():
    chunks = chunk_pages(corpus_pages(), book_id="b", book_title="Book", chunk_size=450, overlap=100, min_chars=120)
    assert chunks, "expected chunks"
    for c in chunks:
        assert c.section, "every chunk should know its section"
        assert len(c.text) <= 450 * 1.6
        assert c.embedding_text.startswith("Book | ")
    sections = {c.section for c in chunks}
    assert "3.1 Decision Tree Learning" in sections
    # No chunk mixes two sections: the backprop text never appears in a decision-tree chunk
    for c in chunks:
        if c.section.startswith("3.1"):
            assert "backpropagation" not in c.text.lower()


def test_overlap_between_consecutive_chunks():
    page = Page(1, "1.1 Long Section Title\n" + " ".join(f"Sentence number {i} talks about learning algorithms in depth." for i in range(40)))
    chunks = chunk_pages([page], book_id="b", book_title="B", chunk_size=300, overlap=120, min_chars=50)
    assert len(chunks) > 2
    first_tail = chunks[0].text.split(". ")[-1]
    assert first_tail.rstrip(".") in chunks[1].text


def test_heading_detection_ignores_sentence_fragments():
    page = Page(1, "13.4. Note in many cases it is possible to find two policies\nSome text follows here that is long enough to be a sentence about learning.")
    chunks = chunk_pages([page], book_id="b", book_title="B", chunk_size=500, overlap=50, min_chars=20)
    assert all(not c.section.startswith("13.4") for c in chunks)


def test_tokenize_light_stemming():
    assert tokenize("Decision trees and networks") == ["decision", "tree", "network"]


def test_hybrid_retrieval_is_relevant_and_traceable():
    result = HybridRetriever("ai_ml_engineer").retrieve(
        ["decision tree information gain entropy"], top_k=3, focus_terms=["entropy"]
    )
    assert result.chunks
    assert "decision tree" in result.chunks[0].text.lower() or "entropy" in result.chunks[0].text.lower()
    assert result.diagnostics["status"] == "ok"
    trace = result.chunks[0].to_trace()
    assert {"chunk_id", "citation", "rrf_score", "snippet"} <= trace.keys()


def test_retrieval_excludes_used_chunks():
    retriever = HybridRetriever("ai_ml_engineer")
    first = retriever.retrieve(["gradient boosting bagging ensemble"], top_k=2)
    used = {c.id for c in first.chunks}
    second = retriever.retrieve(["gradient boosting bagging ensemble"], top_k=2, exclude_ids=used)
    assert not used & {c.id for c in second.chunks}


def test_mmr_returns_distinct_chunks():
    result = HybridRetriever("ai_ml_engineer").retrieve(["overfitting", "overfitting regularization"], top_k=4)
    ids = [c.id for c in result.chunks]
    assert len(ids) == len(set(ids))
