"""ORM -> API dict conversion (kept separate from routers and services)."""
from __future__ import annotations

from app.ai.catalog import get_role
from app.ai.planner import DIFFICULTY_LABELS
from app.models import InterviewSession, Question, QuestionStatus
from app.services.interview_service import pending_question, progress


def answer_dict(question: Question) -> dict | None:
    a = question.answer
    if a is None:
        return None
    ev = a.evaluation or {}
    return {
        "text": a.text,
        "score": a.score,
        "verdict": ev.get("verdict"),
        "feedback": ev.get("feedback"),
        "covered_points": ev.get("covered_points", []),
        "missing_points": ev.get("missing_points", []),
        "misconceptions": ev.get("misconceptions", []),
        "evaluation_mode": (ev.get("evaluation") or {}).get("mode"),
        "integrity": ev.get("integrity"),
        "evaluation": ev,
        "response_seconds": a.response_seconds,
        "answered_at": a.answered_at,
    }


def question_dict(q: Question, *, include_trace: bool = True, reveal: bool | None = None) -> dict:
    """``reveal`` controls the answer key; by default it is shown only once the
    question is closed (answered or skipped)."""
    if reveal is None:
        reveal = q.status != QuestionStatus.ASKED
    return {
        "id": q.id,
        "position": q.position,
        "plan_index": q.plan_index,
        "kind": q.kind,
        "parent_question_id": q.parent_question_id,
        "topic_id": q.topic_id,
        "topic_name": q.topic_name,
        "question_type": q.question_type,
        "difficulty": q.difficulty,
        "difficulty_label": DIFFICULTY_LABELS.get(q.difficulty, "intermediate"),
        "text": q.text,
        "rationale": q.rationale,
        "status": q.status,
        "asked_at": q.asked_at,
        "expected_points": q.expected_points if reveal else None,
        "answer": answer_dict(q),
        "trace": q.trace if include_trace else None,
    }


def session_summary(s: InterviewSession) -> dict:
    role = get_role(s.role_id)
    return {
        "id": s.id,
        "candidate_name": s.candidate_name,
        "role_id": s.role_id,
        "role_title": role.title if role else s.role_id,
        "status": s.status,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
        "completed_at": s.completed_at,
        "progress": progress(s),
        "overall_score": s.report.data.get("overall_score") if s.report else None,
    }


def session_detail(s: InterviewSession) -> dict:
    open_q = pending_question(s)
    return {
        **session_summary(s),
        "resume_filename": s.resume_filename,
        "profile": s.profile,
        "plan": s.plan,
        "questions": [question_dict(q) for q in s.questions],
        "current_question_id": open_q.id if open_q else None,
        "report_available": s.report is not None,
    }
