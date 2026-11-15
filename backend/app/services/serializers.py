"""ORM -> API dict conversion (kept separate from routers and services)."""
from __future__ import annotations

from app.ai.catalog import get_role
from app.ai.planner import DIFFICULTY_LABELS
from app.models import InterviewSession, Question, QuestionStatus
from app.services.interview_service import pending_question, progress, role_for_session


def results_hidden(session: InterviewSession) -> bool:
    """Assessment mode keeps every score, answer key and source passage away
    from the candidate's browser until the interview is completed."""
    return session.mode == "assessment" and session.status != "completed"


def answer_dict(question: Question, hidden: bool = False) -> dict | None:
    a = question.answer
    if a is None:
        return None
    ev = a.evaluation or {}
    if hidden:
        return {"text": a.text, "score": None, "hidden": True, "response_seconds": a.response_seconds, "answered_at": a.answered_at}
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
        "rubric": ev.get("rubric"),
        "hint_penalty": ev.get("hint_penalty"),
        "evaluation": ev,
        "response_seconds": a.response_seconds,
        "answered_at": a.answered_at,
    }


def question_dict(q: Question, *, include_trace: bool = True, reveal: bool | None = None) -> dict:
    """``reveal`` controls the answer key; by default it is shown only once the
    question is closed (answered or skipped), and in assessment mode only once
    the interview is completed."""
    hidden = results_hidden(q.session) if reveal is None else not reveal
    if reveal is None:
        reveal = q.status != QuestionStatus.ASKED and not hidden
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
        "hint": ((q.trace or {}).get("hint") or {}).get("hint"),
        "answer": answer_dict(q, hidden=hidden),
        "trace": q.trace if include_trace and not hidden else None,
    }


def session_summary(s: InterviewSession) -> dict:
    try:
        role = role_for_session(s)
    except Exception:  # unknown legacy role id
        role = get_role(s.role_id)
    return {
        "id": s.id,
        "candidate_name": s.candidate_name,
        "role_id": s.role_id,
        "role_title": role.title if role else s.role_id,
        "custom_role": bool(s.role_spec),
        "status": s.status,
        "mode": s.mode or "practice",
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
