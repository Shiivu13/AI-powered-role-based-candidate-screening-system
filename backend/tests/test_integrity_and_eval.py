from app.ai.integrity import assess, verbatim_overlap
from app.rag.evaluation import Doc, EvalIndex, build_eval_set, evaluate, fit_text_only_lsa, standard_methods
from app.rag.retriever import HybridRetriever, mmr_select

SOURCE = (
    "The ID3 algorithm grows the tree top-down, selecting at each node the attribute that best classifies "
    "the training examples using information gain."
)


def test_verbatim_overlap_detects_copy():
    assert verbatim_overlap(SOURCE, [SOURCE]) == 1.0
    own_words = "I would pick the split that reduces impurity the most, measured with entropy, and stop early."
    assert verbatim_overlap(own_words, [SOURCE]) == 0.0


def test_clean_answer_has_no_flags():
    answer = "I would pick the split that reduces impurity the most, measured by entropy. " * 3
    result = assess(answer, {"keystrokes": 400, "active_typing_ms": 90_000}, 120, [SOURCE])
    assert result["level"] == "none" and result["flags"] == []


def test_paste_copy_and_tab_switches_are_flagged():
    answer = SOURCE + " " + SOURCE
    result = assess(answer, {"pasted_chars": len(answer), "paste_events": 1, "focus_losses": 4}, 20, [SOURCE])
    codes = {f["code"] for f in result["flags"]}
    assert {"pasted_answer", "copied_from_source", "left_the_tab"} <= codes
    assert result["level"] == "high"


def test_voice_input_is_not_treated_as_fast_typing():
    answer = "word " * 200
    result = assess(answer, {"voice_chars": len(answer)}, 30, [])
    assert not any(f["code"] == "implausible_speed" for f in result["flags"])


def test_mmr_trades_relevance_for_diversity():
    import numpy as np

    a, b, c = np.array([1.0, 0.0]), np.array([0.99, 0.141]), np.array([0.0, 1.0])
    vecs = {"a": a, "b": b / np.linalg.norm(b), "c": c}
    rel = {"a": 1.0, "b": 0.95, "c": 0.6}
    assert mmr_select(["a", "b", "c"], rel, vecs, 2, lam=1.0) == ["a", "b"]
    assert mmr_select(["a", "b", "c"], rel, vecs, 2, lam=0.5) == ["a", "c"]


def test_benchmark_runs_on_synthetic_kb(knowledge_base):
    docs = [Doc(c.id, c.text, c.book_id, c.section) for c in knowledge_base]
    queries = build_eval_set(docs, min_chunks=1)
    assert queries and all(q.relevant for q in queries)
    index = EvalIndex(docs, fit_text_only_lsa(docs, dim=32))
    results = evaluate(index, queries, standard_methods(index))
    assert set(results["dense (LSA)"]) >= {"hit@4", "mrr@10", "ndcg@10", "redundancy@4"}
    assert results["hybrid RRF, equal weights"]["hit@4"] > 0.5


def test_single_retriever_modes():
    r = HybridRetriever("ai_ml_engineer")
    dense = r.retrieve(["entropy information gain"], top_k=3, mode="dense")
    sparse = r.retrieve(["entropy information gain"], top_k=3, mode="bm25")
    assert all(c.bm25_rank is None for c in dense.chunks)
    assert all(c.dense_rank is None for c in sparse.chunks)
