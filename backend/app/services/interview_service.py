"""Interview lifecycle orchestration.

    create_session ──► [ready] ──next_question──► [in_progress] ◄─┐
                                                   │  answer/skip ──┘
                                                   ▼
                                     complete ──► [completed] (report stored)

All AI/ML work is delegated to ``app.ai`` and ``app.rag``; this layer owns
state transitions, persistence and the adaptive policy.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.answer_evaluator import evaluate_answer
from app.ai.catalog import Role, get_role
from app.ai.integrity import assess as assess_integrity
from app.ai.planner import DIFFICULTY_LABELS, build_plan
from app.ai.question_generator import generate_follow_up, generate_hint, generate_question
from app.ai.report_generator import build_report
from app.ai.resume_parser import extract_resume_text, parse_resume
from app.config import get_settings
from app.errors import InvalidState, KnowledgeBaseUnavailable, NotFound, ValidationFailed
from app.models import Answer, InterviewSession, Question, QuestionStatus, Report, SessionStatus
from app.rag.retriever import HybridRetriever, RetrievalResult, RetrievedChunk

logger = logging.getLogger(__name__)

# Adaptive policy thresholds (0-10 scale)
RAISE_BAR_AT = 8.0
LOWER_BAR_BELOW = 4.0
FOLLOW_UP_WINDOW = (4.0, 7.0)  # partial answers earn a follow-up
HINT_PENALTY = 0.15  # share of the question's score lost when a hint was used
MODES = ("practice", "assessment")


# --------------------------------------------------------------------------- helpers
def _role_or_error(role_id: str) -> Role:
    role = get_role(role_id)
    if role is None:
        raise ValidationFailed(f"Unknown role '{role_id}'", details={"role_id": role_id})
    return role


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _clamp_difficulty(value: int) -> int:
    return max(1, min(3, value))


def _used_chunk_ids(session: InterviewSession) -> set[str]:
    return {
        c["chunk_id"]
        for q in session.questions
        for c in (q.trace or {}).get("retrieval", {}).get("chunks", [])
    }


def _context_from_trace(question: Question) -> str:
    chunks = (question.trace or {}).get("retrieval", {}).get("chunks", [])
    return "\n\n".join(f"[S{i}] {c['citation']}\n{c['snippet']}" for i, c in enumerate(chunks, 1))


def _result_from_trace(question: Question) -> RetrievalResult:
    retrieval = (question.trace or {}).get("retrieval", {})
    chunks = [
        RetrievedChunk(
            id=c["chunk_id"], text=c["snippet"], book_id=c["book_id"], book_title=c["book_title"],
            section=c["section"], page_start=c["page_start"], page_end=c["page_end"],
            rrf_score=c["rrf_score"], dense_score=c["dense_score"], bm25_rank=c["bm25_rank"],
            dense_rank=c["dense_rank"], matched_queries=c["matched_queries"],
        )
        for c in retrieval.get("chunks", [])
    ]
    return RetrievalResult(retrieval.get("queries", []), chunks, retrieval.get("diagnostics", {}))


def pending_question(session: InterviewSession) -> Question | None:
    return next((q for q in session.questions if q.status == QuestionStatus.ASKED), None)


def progress(session: InterviewSession) -> dict:
    qs = session.questions
    return {
        "planned": len(session.plan),
        "primary_asked": sum(q.kind == "primary" for q in qs),
        "asked": len(qs),
        "answered": sum(q.status == QuestionStatus.ANSWERED for q in qs),
        "skipped": sum(q.status == QuestionStatus.SKIPPED for q in qs),
        "follow_ups": sum(q.kind == "follow_up" for q in qs),
        "current_difficulty_offset": session.difficulty_offset,
    }


# --------------------------------------------------------------------------- lifecycle
def create_session(
    db: Session,
    *,
    candidate_name: str,
    role_id: str,
    num_questions: int | None,
    resume_filename: str | None,
    resume_bytes: bytes | None,
    resume_text: str | None,
    mode: str = "practice",
) -> InterviewSession:
    settings = get_settings()
    role = _role_or_error(role_id)
    if mode not in MODES:
        raise ValidationFailed(f"mode must be one of {', '.join(MODES)}")

    num_questions = num_questions or settings.default_num_questions
    if not settings.min_num_questions <= num_questions <= settings.max_num_questions:
        raise ValidationFailed(
            f"num_questions must be between {settings.min_num_questions} and {settings.max_num_questions}"
        )

    if resume_bytes:
        if len(resume_bytes) > settings.max_resume_bytes:
            raise ValidationFailed(f"Resume file exceeds {settings.max_resume_bytes // (1024 * 1024)} MB")
        text = extract_resume_text(resume_filename or "resume", resume_bytes)
    elif resume_text and resume_text.strip():
        text = resume_text.strip()
        resume_filename = None
    else:
        raise ValidationFailed("Provide a resume file or paste the resume text")
    if len(text) < settings.min_resume_chars:
        raise ValidationFailed("The resume is too short to analyse", details={"chars": len(text)})

    if not HybridRetriever(role.id).is_ready():
        raise KnowledgeBaseUnavailable(
            f"The knowledge base for '{role.title}' has not been ingested. Run `python -m scripts.ingest_kb`."
        )

    profile = parse_resume(text)
    plan = build_plan(role, profile, text, num_questions)
    name = (candidate_name or "").strip() or profile.get("name") or "Candidate"

    session = InterviewSession(
        candidate_name=name[:200],
        role_id=role.id,
        resume_filename=resume_filename,
        resume_text=text,
        profile=profile,
        plan=[p.to_dict() for p in plan],
        num_questions=num_questions,
        mode=mode,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    logger.info("Session %s created for role %s with %d planned questions", session.id, role.id, len(plan))
    return session


def get_session(db: Session, session_id: str) -> InterviewSession:
    session = db.get(InterviewSession, session_id)
    if session is None:
        raise NotFound(f"Session '{session_id}' not found")
    return session


def list_sessions(db: Session, limit: int = 50) -> list[InterviewSession]:
    stmt = select(InterviewSession).order_by(InterviewSession.created_at.desc()).limit(limit)
    return list(db.scalars(stmt))


def delete_session(db: Session, session_id: str) -> None:
    db.delete(get_session(db, session_id))
    db.commit()


def _adaptive_note(session: InterviewSession) -> str:
    answered = [q for q in session.questions if q.status != QuestionStatus.ASKED]
    if not answered:
        return "Opening question: start in the candidate's comfort zone."
    last = answered[-1]
    score = last.answer.score if last.answer else 0.0
    if last.status == QuestionStatus.SKIPPED:
        return "The candidate skipped the previous question; keep this one approachable."
    if score is not None and score >= RAISE_BAR_AT:
        return f"Previous answer scored {score}/10: raise the bar (more depth, edge cases)."
    if score is not None and score < LOWER_BAR_BELOW:
        return f"Previous answer scored {score}/10: keep it focused on fundamentals."
    return ""


def _should_follow_up(session: InterviewSession) -> Question | None:
    if session.follow_ups_used >= get_settings().max_follow_ups or not session.questions:
        return None
    last = session.questions[-1]
    if last.kind != "primary" or last.status != QuestionStatus.ANSWERED or not last.answer:
        return None
    lo, hi = FOLLOW_UP_WINDOW
    if last.answer.score is not None and lo <= last.answer.score < hi and last.answer.evaluation.get("missing_points"):
        return last
    return None


def _build_trace(plan_item: dict, result: RetrievalResult, generated: dict, difficulty: int, note: str) -> dict:
    used = set(generated.get("source_chunk_ids", []))
    return {
        "plan_item": plan_item,
        "effective_difficulty": difficulty,
        "adaptive_note": note,
        "retrieval": {
            "queries": result.queries,
            "diagnostics": result.diagnostics,
            "chunks": [dict(c.to_trace(snippet_chars=4000), used_by_question=c.id in used) for c in result.chunks],
        },
        "generation": generated.get("generation", {}),
    }


def next_question(db: Session, session: InterviewSession) -> Question | None:
    """Return the open question, or generate the next one. ``None`` means the plan is exhausted."""
    if session.status == SessionStatus.COMPLETED:
        raise InvalidState("This interview is already completed")
    open_q = pending_question(session)
    if open_q is not None:
        return open_q

    role = _role_or_error(session.role_id)
    retriever = HybridRetriever(role.id)
    previous = [q.text for q in session.questions]
    position = len(session.questions) + 1

    parent = _should_follow_up(session)
    if parent is not None:
        result = _result_from_trace(parent)
        generated = generate_follow_up(
            role=role,
            original_question=parent.text,
            answer=parent.answer.text,
            missing_points=parent.answer.evaluation.get("missing_points", []),
            result=result,
        )
        plan_item = session.plan[parent.plan_index]
        difficulty = parent.difficulty
        question = Question(
            session_id=session.id, position=position, plan_index=parent.plan_index, kind="follow_up",
            parent_question_id=parent.id, topic_id=parent.topic_id, topic_name=parent.topic_name,
            question_type="follow_up", difficulty=difficulty, text=generated["question"],
            expected_points=generated["expected_points"], rationale=generated["rationale"],
            trace=_build_trace(plan_item, result, generated, difficulty, "Follow-up on a partial answer."),
        )
        session.follow_ups_used += 1
    else:
        plan_index = sum(q.kind == "primary" for q in session.questions)
        if plan_index >= len(session.plan):
            return None
        plan_item = session.plan[plan_index]
        difficulty = _clamp_difficulty(plan_item["difficulty"] + session.difficulty_offset)
        note = _adaptive_note(session)
        result = retriever.retrieve(
            plan_item["queries"], exclude_ids=_used_chunk_ids(session), focus_terms=plan_item.get("focus_terms")
        )
        if not result.chunks:
            raise KnowledgeBaseUnavailable("No knowledge-base context could be retrieved for this topic")
        generated = generate_question(
            role=role, plan=plan_item, difficulty=difficulty, profile=session.profile,
            previous_questions=previous, result=result, adaptive_note=note,
            seed=hash((session.id, plan_index)) & 0xFFFF,
        )
        question = Question(
            session_id=session.id, position=position, plan_index=plan_index, kind="primary",
            topic_id=plan_item["topic_id"], topic_name=plan_item["topic_name"],
            question_type=generated["question_type"], difficulty=difficulty, text=generated["question"],
            expected_points=generated["expected_points"], rationale=generated["rationale"],
            trace=_build_trace(plan_item, result, generated, difficulty, note),
        )

    db.add(question)
    session.status = SessionStatus.IN_PROGRESS
    db.commit()
    db.refresh(session)
    return question


def _get_open_question(session: InterviewSession, question_id: str) -> Question:
    if session.status == SessionStatus.COMPLETED:
        raise InvalidState("This interview is already completed")
    question = next((q for q in session.questions if q.id == question_id), None)
    if question is None:
        raise NotFound(f"Question '{question_id}' not found in this session")
    if question.status != QuestionStatus.ASKED:
        raise InvalidState(f"Question already {question.status}")
    return question


def _apply_adaptation(session: InterviewSession, score: float) -> None:
    if score >= RAISE_BAR_AT:
        session.difficulty_offset = min(session.difficulty_offset + 1, 1)
    elif score < LOWER_BAR_BELOW:
        session.difficulty_offset = max(session.difficulty_offset - 1, -1)


def submit_answer(
    db: Session, session: InterviewSession, question_id: str, text: str, telemetry: dict | None = None
) -> Question:
    question = _get_open_question(session, question_id)
    evaluation = evaluate_answer(
        question=question.text,
        expected_points=question.expected_points,
        answer=text,
        context=_context_from_trace(question),
        difficulty=question.difficulty,
    )
    now = datetime.now(timezone.utc)
    response_seconds = round((now - _aware(question.asked_at)).total_seconds(), 1)
    sources = [c["snippet"] for c in (question.trace or {}).get("retrieval", {}).get("chunks", [])]
    hint = (question.trace or {}).get("hint")
    if hint:
        evaluation["score"] = round(evaluation["score"] * (1 - HINT_PENALTY), 1)
        evaluation["hint_penalty"] = HINT_PENALTY
    # Advisory only: integrity signals are stored for the reviewer, never folded into the score.
    evaluation["integrity"] = assess_integrity(text, telemetry, response_seconds, sources)
    evaluation["telemetry"] = telemetry or {}
    question.answer = Answer(
        text=text,
        score=evaluation["score"],
        evaluation=evaluation,
        response_seconds=response_seconds,
        answered_at=now,
    )
    question.status = QuestionStatus.ANSWERED
    _apply_adaptation(session, evaluation["score"])
    db.commit()
    db.refresh(session)
    return question


def request_hint(db: Session, session: InterviewSession, question_id: str) -> dict:
    """One grounded nudge per question; using it costs HINT_PENALTY of that question's score."""
    question = _get_open_question(session, question_id)
    existing = (question.trace or {}).get("hint")
    if existing:
        return existing
    hint = {**generate_hint(question=question.text, expected_points=question.expected_points), "penalty": HINT_PENALTY}
    question.trace = {**(question.trace or {}), "hint": hint}  # reassign so the JSON change is persisted
    db.commit()
    db.refresh(session)
    return hint


def skip_question(db: Session, session: InterviewSession, question_id: str) -> Question:
    question = _get_open_question(session, question_id)
    question.status = QuestionStatus.SKIPPED
    _apply_adaptation(session, 0.0)
    db.commit()
    db.refresh(session)
    return question


def is_plan_exhausted(session: InterviewSession) -> bool:
    primary = sum(q.kind == "primary" for q in session.questions)
    return primary >= len(session.plan) and pending_question(session) is None and _should_follow_up(session) is None


def complete_session(db: Session, session: InterviewSession) -> Report:
    if session.status == SessionStatus.COMPLETED and session.report is not None:
        return session.report
    if not session.questions:
        raise InvalidState("Answer at least one question before completing the interview")
    for q in session.questions:
        if q.status == QuestionStatus.ASKED:
            q.status = QuestionStatus.SKIPPED
    from app.services.serializers import question_dict  # local import avoids a cycle

    role = _role_or_error(session.role_id)
    data = build_report(
        role=role,
        profile=session.profile,
        plan=session.plan,
        questions=[question_dict(q, include_trace=True, reveal=True) for q in session.questions],
        candidate_name=session.candidate_name,
    )
    report = Report(session_id=session.id, data=data)
    session.report = report
    session.status = SessionStatus.COMPLETED
    session.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)
    return session.report


def difficulty_label(level: int) -> str:
    return DIFFICULTY_LABELS.get(level, "intermediate")
