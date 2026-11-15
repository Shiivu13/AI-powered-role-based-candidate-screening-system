"""Answer evaluation.

LLM path: grade against the expected points *and* the source excerpts the
question was generated from (the reference truth), returning a 0-10 score,
covered/missing points and feedback.

Offline path: semantic + lexical coverage of each expected point. For every
point we take the best of (a) embedding similarity between the point and any
window of the answer and (b) recall of the point's content words in the answer.
The score blends point coverage with similarity to the source context and an
answer-substance factor.
"""
from __future__ import annotations

import logging
import re

import numpy as np

from app.ai.llm import LLMError, get_llm
from app.ai.planner import DIFFICULTY_LABELS
from app.ai.prompts import ANSWER_EVALUATION_SYSTEM, ANSWER_EVALUATION_USER, PROMPT_VERSION
from app.rag.embeddings import get_embedder
from app.rag.retriever import tokenize

logger = logging.getLogger(__name__)

_NON_ANSWERS = re.compile(r"^\s*(i\s*(do\s*not|don'?t)\s*know|no\s*idea|not\s*sure|skip|pass|n/?a|-+|\?+)\s*[.!]*\s*$", re.I)


def verdict_for(score: float) -> str:
    if score >= 8.5:
        return "excellent"
    if score >= 7:
        return "good"
    if score >= 4.5:
        return "partial"
    if score >= 2:
        return "weak"
    return "incorrect"


def _windows(answer: str, size: int = 3) -> list[str]:
    sentences = [s for s in re.split(r"(?<=[.!?])\s+|\n+", answer) if s.strip()]
    if len(sentences) <= size:
        return [answer]
    return [" ".join(sentences[i : i + size]) for i in range(len(sentences) - size + 1)]


def _offline_evaluate(question: str, expected_points: list[str], answer: str, context: str) -> dict:
    answer_tokens = set(tokenize(answer))
    words = len(answer.split())
    embedder = get_embedder()
    use_vectors = embedder.is_ready
    coverage: list[tuple[str, float]] = []
    if use_vectors:
        windows = _windows(answer)
        win_vecs = embedder.embed(windows)
        point_vecs = embedder.embed(expected_points) if expected_points else np.zeros((0, 1))
    for i, point in enumerate(expected_points):
        point_tokens = set(tokenize(point)) - set(tokenize(question)) or set(tokenize(point))
        lexical = len(point_tokens & answer_tokens) / max(len(point_tokens), 1)
        semantic = float(np.max(win_vecs @ point_vecs[i])) if use_vectors else 0.0
        coverage.append((point, max(lexical, semantic)))
    covered = [p for p, s in coverage if s >= 0.42]
    missing = [p for p, s in coverage if s < 0.42]
    point_score = float(np.mean([min(s / 0.6, 1.0) for _, s in coverage])) if coverage else 0.0
    context_sim = 0.0
    if use_vectors and context:
        context_sim = max(float(embedder.embed_one(context) @ embedder.embed_one(answer)), 0.0)
    substance = min(words / 80, 1.0)
    score = 10 * (0.6 * point_score + 0.25 * min(context_sim / 0.5, 1.0) + 0.15 * substance)
    if words < 12:
        score = min(score, 3.0)
    score = round(max(0.0, min(10.0, score)), 1)
    feedback_parts = []
    if covered:
        feedback_parts.append(f"You covered {len(covered)} of {len(expected_points)} key points.")
    if missing:
        feedback_parts.append("Strengthen your answer on: " + "; ".join(m[:110].rstrip(".") for m in missing[:2]) + ".")
    if words < 40:
        feedback_parts.append("The answer is brief - explain the mechanism and give an example.")
    return {
        "score": score,
        "verdict": verdict_for(score),
        "covered_points": covered,
        "missing_points": missing,
        "misconceptions": [],
        "feedback": " ".join(feedback_parts) or "Solid answer.",
        "signals": {
            "point_coverage": round(point_score, 3),
            "context_similarity": round(context_sim, 3),
            "word_count": words,
        },
    }


def evaluate_answer(
    *,
    question: str,
    expected_points: list[str],
    answer: str,
    context: str,
    difficulty: int,
) -> dict:
    if not answer.strip() or _NON_ANSWERS.match(answer):
        return {
            "score": 0.0,
            "verdict": "incorrect",
            "covered_points": [],
            "missing_points": expected_points,
            "misconceptions": [],
            "feedback": "No substantive answer was given.",
            "evaluation": {"mode": "rule", "prompt_version": PROMPT_VERSION},
        }

    llm = get_llm()
    meta = {"prompt_version": PROMPT_VERSION}
    if llm.available:
        try:
            data = llm.generate_json(
                ANSWER_EVALUATION_SYSTEM,
                ANSWER_EVALUATION_USER.format(
                    difficulty_label=DIFFICULTY_LABELS.get(difficulty, "intermediate"),
                    question=question,
                    expected_points="\n".join(f"- {p}" for p in expected_points),
                    context=context[:8000],
                    answer=answer[:6000],
                ),
                temperature=0.0,
            )
            score = float(data.get("score", 0))
            score = round(max(0.0, min(10.0, score)), 1)
            meta.update(mode="llm", model=llm.model)
            return {
                "score": score,
                "verdict": data.get("verdict") or verdict_for(score),
                "covered_points": [str(x) for x in data.get("covered_points", [])],
                "missing_points": [str(x) for x in data.get("missing_points", [])],
                "misconceptions": [str(x) for x in data.get("misconceptions", [])],
                "feedback": str(data.get("feedback", "")),
                "evaluation": meta,
            }
        except (LLMError, ValueError, TypeError) as exc:
            logger.warning("LLM evaluation failed, using offline evaluator: %s", exc)
            meta["fallback_reason"] = str(exc)[:200]

    result = _offline_evaluate(question, expected_points, answer, context)
    meta.update(mode="heuristic", model="semantic-coverage")
    result["evaluation"] = meta
    return result
