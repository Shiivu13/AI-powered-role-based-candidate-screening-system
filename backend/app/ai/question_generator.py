"""Question generation grounded in retrieved knowledge-base context.

LLM path: the prompt carries the candidate profile, the plan item (topic,
reason, difficulty, style), the questions already asked, and numbered SOURCE
excerpts. The model must return the question, the expected answer points and
which sources it used, so each question is traceable to book pages.

Offline path: a grounded extractive generator. It picks the most salient,
definition-like sentences from the retrieved chunks (these become the expected
points), derives the key concept from the chunk's section heading, and phrases
a question in the requested style around that concept and the candidate's own
skills. It is less fluent than the LLM, but every question still comes from
the knowledge base, not from a fixed question bank.
"""
from __future__ import annotations

import logging
import random
import re

from app.ai.catalog import Role
from app.ai.llm import LLMError, get_llm
from app.ai.planner import DIFFICULTY_LABELS
from app.ai.prompts import (
    FOLLOW_UP_SYSTEM,
    FOLLOW_UP_USER,
    PROMPT_VERSION,
    QUESTION_GENERATION_SYSTEM,
    QUESTION_GENERATION_USER,
)
from app.rag.retriever import RetrievalResult, tokenize

logger = logging.getLogger(__name__)

_DEFINITION_CUES = (
    " is a ", " is the ", " are ", " refers to ", " because ", " therefore ", " in order to ",
    " the key ", " we can ", " allows ", " ensures ", " means that ", " is called ", " defined as ",
)


_META_SENTENCE = re.compile(
    r"\b(this (chapter|section|book|part|lesson|tutorial)|next chapter|previous chapter|following chapter|"
    r"you will (learn|discover|see)|after reading|we will (see|discuss|look)|as we saw|as discussed|"
    r"documentation|o'reilly|exercise|github|download|website|in part [ivx\d]+|see (section|chapter|figure))\b",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _sentence_quality(sentence: str) -> bool:
    if not 60 <= len(sentence) <= 320:
        return False
    letters = sum(ch.isalpha() for ch in sentence)
    if letters / len(sentence) < 0.7:
        return False
    if re.search(r"(figure|table|exercise|chapter)\s+\d", sentence, re.IGNORECASE):
        return False
    if re.search(r"\b[A-Z]{3,}(\s+[A-Z0-9]{2,}){2,}", sentence):  # leaked running headers
        return False
    if _META_SENTENCE.search(sentence):  # talks about the book, not the concept
        return False
    if not sentence[0].isupper() or sentence.count("(") != sentence.count(")"):
        return False  # fragment or truncated sentence
    if re.search(r"[^\x20-\x7E‘-”–—]", sentence):
        return False  # symbol soup from equations / icon fonts
    return not sentence.lower().startswith(("see ", "for example, see", "note that", "http"))


def salient_sentences(result: RetrievalResult, focus: list[str], limit: int = 4) -> list[tuple[str, str]]:
    """Return [(sentence, chunk_id)] ranked by topical salience."""
    focus_tokens = set(tokenize(" ".join(focus)))
    scored = []
    for rank, chunk in enumerate(result.chunks):
        for sentence in _sentences(chunk.text):
            if not _sentence_quality(sentence):
                continue
            tokens = set(tokenize(sentence))
            overlap = len(tokens & focus_tokens)
            cue = sum(c in f" {sentence.lower()} " for c in _DEFINITION_CUES)
            score = overlap * 2 + cue - rank * 0.5
            scored.append((score, sentence, chunk.id))
    scored.sort(key=lambda x: x[0], reverse=True)
    picked, seen = [], set()
    for _, sentence, cid in scored:
        key = frozenset(tokenize(sentence))
        if any(len(key & s) / max(len(key | s), 1) > 0.6 for s in seen):
            continue
        seen.add(key)
        picked.append((sentence, cid))
        if len(picked) >= limit:
            break
    return picked


_GENERIC_SECTION = re.compile(
    r"summary|further reading|exercises?|introduction|overview|references|bibliography|wrapping up|preface|conclusion|chapter$",
    re.IGNORECASE,
)


def _sentence_case(text: str) -> str:
    return " ".join(w if (w.isupper() and len(w) > 1) else w.lower() for w in text.split())


def _concept(result: RetrievalResult, topic_name: str) -> str:
    # Prefer specific numbered sections ("3.4 The Basic Decision Tree Learning
    # Algorithm") over broad chapter titles ("Chapter 2: Supervised Learning").
    ordered = sorted(result.chunks, key=lambda c: c.section.lower().startswith("chapter"))
    for chunk in ordered:
        section = re.sub(r"^(chapter\s+\d+[:.]?\s*|\d+(\.\d+)*\.?\s*)", "", chunk.section, flags=re.IGNORECASE).strip()
        if 4 < len(section) < 70 and not _GENERIC_SECTION.search(section) and section.split()[-1].lower() not in {"and", "of", "the", "with", "for"}:
            return _sentence_case(section)
    return topic_name.lower()


def _offline_question(plan: dict, difficulty: int, profile: dict, result: RetrievalResult, rng: random.Random) -> dict:
    focus = plan.get("focus_terms", []) + plan.get("evidence", []) + [plan["topic_name"]]
    points = salient_sentences(result, focus)
    concept = _concept(result, plan["topic_name"])
    skill = (plan.get("evidence") or [None])[0]
    domain = (profile.get("domains") or ["a production"])[0]
    project = (profile.get("projects") or [{}])[0].get("name")
    qtype = plan["question_type"]
    depth = {
        1: "Keep it concrete and give a simple example.",
        2: "Be specific about how it works and when it fails.",
        3: "Discuss the underlying assumptions and the trade-offs involved.",
    }[difficulty]
    hook = ""
    if plan.get("source") == "resume" and skill:
        hook = f"Your resume mentions {skill}{f' (e.g. in {project})' if project else ''}. "

    templates = {
        "conceptual": [
            f"{hook}Explain {concept} in the context of {plan['topic_name'].lower()}: what problem does it solve, and what would break if it were ignored? {depth}",
            f"{hook}Walk me through {concept}. What is the core idea, and how does it influence the model you end up with? {depth}",
        ],
        "applied": [
            f"{hook}You are building a model for a {domain.lower()} use case. How would {concept} shape your design decisions, and how would you verify it is working? {depth}",
            f"{hook}Describe how you would apply {concept} on a real dataset, step by step, including what you would monitor. {depth}",
        ],
        "scenario": [
            f"{hook}A model your team shipped performs well offline but poorly in production. Using what you know about {concept}, how would you diagnose and fix it? {depth}",
            f"{hook}A stakeholder asks why you chose an approach based on {concept} over a simpler alternative. How do you justify the choice, and when would you change your mind? {depth}",
        ],
        "derivation": [
            f"Reason through {concept}: which assumptions does it rely on, and how does the result change if one of them is violated? {depth}",
        ],
    }
    options = templates.get(qtype) or templates["conceptual"]
    question = rng.choice(options)
    return {
        "question": question,
        "question_type": qtype,
        "expected_points": [s for s, _ in points] or [f"Accurate explanation of {concept}"],
        "source_chunk_ids": list(dict.fromkeys(cid for _, cid in points)) or [c.id for c in result.chunks[:2]],
        "rationale": plan["reason"],
    }


def _previous_block(previous: list[str]) -> str:
    return "\n".join(f"- {q}" for q in previous) if previous else "(none)"


def _map_sources(source_ids: list, result: RetrievalResult) -> list[str]:
    ids = []
    for sid in source_ids or []:
        m = re.search(r"\d+", str(sid))
        if m and 1 <= int(m.group()) <= len(result.chunks):
            ids.append(result.chunks[int(m.group()) - 1].id)
    return list(dict.fromkeys(ids)) or [c.id for c in result.chunks]


def generate_question(
    *,
    role: Role,
    plan: dict,
    difficulty: int,
    profile: dict,
    previous_questions: list[str],
    result: RetrievalResult,
    adaptive_note: str = "",
    seed: int | None = None,
) -> dict:
    llm = get_llm()
    generation = {"prompt_version": PROMPT_VERSION}
    if llm.available and result.chunks:
        try:
            system = QUESTION_GENERATION_SYSTEM.format(role_title=role.title, question_type=plan["question_type"])
            user = QUESTION_GENERATION_USER.format(
                seniority=profile.get("seniority", "unknown"),
                years=profile.get("years_experience") or "unknown",
                skills=", ".join(plan.get("evidence") or profile.get("skills", [])[:8]) or "none listed",
                domains=", ".join(profile.get("domains", [])) or "not specified",
                projects="; ".join(f"{p['name']}: {p['summary'][:120]}" for p in profile.get("projects", [])[:3]) or "none listed",
                topic_name=plan["topic_name"],
                topic_description=plan["topic_description"],
                plan_reason=plan["reason"],
                difficulty_label=DIFFICULTY_LABELS[difficulty],
                difficulty=difficulty,
                adaptive_note=f"- Adaptation: {adaptive_note}\n" if adaptive_note else "",
                previous_questions=_previous_block(previous_questions),
                context=result.context_block(),
            )
            data = llm.generate_json(system, user)
            question = str(data.get("question", "")).strip()
            if len(question) < 15:
                raise LLMError("empty question")
            generation.update(mode="llm", model=llm.model)
            return {
                "question": question,
                "question_type": data.get("question_type") or plan["question_type"],
                "expected_points": [str(p) for p in data.get("expected_points", [])][:6],
                "source_chunk_ids": _map_sources(data.get("source_ids"), result),
                "rationale": data.get("rationale") or plan["reason"],
                "generation": generation,
            }
        except LLMError as exc:
            logger.warning("LLM question generation failed, using offline generator: %s", exc)
            generation["fallback_reason"] = str(exc)[:200]

    rng = random.Random(seed)
    data = _offline_question(plan, difficulty, profile, result, rng)
    generation.update(mode="heuristic", model="extractive-grounded")
    data["generation"] = generation
    return data


def generate_follow_up(
    *,
    role: Role,
    original_question: str,
    answer: str,
    missing_points: list[str],
    result: RetrievalResult,
) -> dict:
    llm = get_llm()
    generation = {"prompt_version": PROMPT_VERSION}
    if llm.available:
        try:
            data = llm.generate_json(
                FOLLOW_UP_SYSTEM.format(role_title=role.title),
                FOLLOW_UP_USER.format(
                    question=original_question,
                    answer=answer[:3000],
                    missing="; ".join(missing_points) or "depth and precision",
                    context=result.context_block(),
                ),
            )
            question = str(data.get("question", "")).strip()
            if len(question) < 10:
                raise LLMError("empty follow-up")
            generation.update(mode="llm", model=llm.model)
            return {
                "question": question,
                "question_type": "follow_up",
                "expected_points": [str(p) for p in data.get("expected_points", [])][:4] or missing_points[:3],
                "source_chunk_ids": _map_sources(data.get("source_ids"), result),
                "rationale": data.get("rationale") or "Probe the point missed in the previous answer.",
                "generation": generation,
            }
        except LLMError as exc:
            generation["fallback_reason"] = str(exc)[:200]

    target = missing_points[0] if missing_points else ""
    answer_tokens = set(tokenize(answer))
    # Ask about the missed *concepts* without quoting the reference sentence.
    terms = [t for t in dict.fromkeys(tokenize(target)) if t not in answer_tokens and len(t) > 4]
    terms = sorted(terms, key=len, reverse=True)[:3]
    if terms:
        focus = ", ".join(f'"{t}"' for t in terms)
        question = (
            f"Let's go one level deeper. Your answer did not cover the role of {focus} here. "
            "How do they fit into the idea you described, and what changes in practice if you account for them?"
        )
    else:
        question = (
            "Let's go one level deeper. Can you make your previous answer more precise: "
            "state the underlying mechanism and give a concrete example where it matters?"
        )
    generation.update(mode="heuristic", model="extractive-grounded")
    return {
        "question": question,
        "question_type": "follow_up",
        "expected_points": missing_points[:3] or ["A precise statement of the mechanism with an example"],
        "source_chunk_ids": [c.id for c in result.chunks[:2]],
        "rationale": "Partial answer: probing the most important missed point.",
        "generation": generation,
    }
