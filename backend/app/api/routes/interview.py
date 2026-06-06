from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.db_models import Session as InterviewSession, Question
from app.models.schemas import (
    AnswerSubmit, NextQuestionOut, QuestionOut, SummaryOut, AnswerEvaluation,
)
from app.api.serializers import question_to_out
from app.services.interview_service import (
    get_session, generate_next_question, record_answer,
    complete_session, is_interview_complete,
)
from app.services.summary_service import generate_summary, compute_topic_mastery
from app.config import settings

router = APIRouter(prefix="/api/interview", tags=["interview"])


@router.post("/{session_id}/answer", response_model=NextQuestionOut)
async def submit_answer(
    session_id: str,
    body: AnswerSubmit,
    db: AsyncSession = Depends(get_db),
):
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status != "active":
        raise HTTPException(400, f"Session is {session.status}, not active")
    if not body.answer.strip():
        raise HTTPException(400, "Answer cannot be empty")

    unanswered = [q for q in session.questions if not q.answer]
    if not unanswered:
        raise HTTPException(400, "No pending question to answer")

    current_question = unanswered[0]
    answer = await record_answer(db, session, current_question, body.answer.strip())

    # Inline feedback for the just-submitted answer (Adaptive Engine output)
    last_eval = AnswerEvaluation(
        score=answer.score, feedback=answer.feedback, detail=answer.eval_detail
    )

    # Reload session with eager-loaded relationships
    session = await get_session(db, session_id)

    if is_interview_complete(session):
        await complete_session(db, session)
        return NextQuestionOut(
            question=None,
            is_complete=True,
            question_number=session.current_question_index,
            total_questions=settings.MAX_QUESTIONS,
            last_answer_evaluation=last_eval,
        )

    next_q = await generate_next_question(db, session)
    return NextQuestionOut(
        question=question_to_out(next_q, include_answer=False),
        is_complete=False,
        question_number=next_q.question_number,
        total_questions=settings.MAX_QUESTIONS,
        last_answer_evaluation=last_eval,
    )


@router.get("/{session_id}/summary", response_model=SummaryOut)
async def get_summary(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    if session.status == "active":
        await complete_session(db, session)
        await db.refresh(session)

    summary = await generate_summary(db, session)

    questions_out = [question_to_out(q) for q in session.questions]
    topic_mastery, average_score = compute_topic_mastery(session)

    return SummaryOut(
        session_id=session.id,
        candidate_name=session.candidate_name,
        role=session.role,
        total_questions=summary.total_questions,
        topics_covered=summary.topics_covered or [],
        overall_assessment=summary.overall_assessment,
        strengths=summary.strengths or [],
        improvements=summary.improvements or [],
        technical_score=summary.technical_score,
        recommendation=summary.recommendation,
        full_analysis=summary.full_analysis,
        topic_mastery=topic_mastery,
        average_score=average_score,
        questions=questions_out,
        created_at=summary.created_at,
    )


@router.post("/{session_id}/complete")
async def force_complete(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.status == "completed":
        return {"message": "Already completed"}
    await complete_session(db, session)
    return {"message": "Session completed", "session_id": session_id}
