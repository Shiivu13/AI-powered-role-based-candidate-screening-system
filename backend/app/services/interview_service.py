from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from sqlalchemy import func
from app.models.db_models import Session as InterviewSession, Question, Answer
from app.config import settings
from app.services.rag_service import retrieve_context_for_question
from app.services.question_generator import generate_interview_question, ROLE_LABELS
from app.services.answer_evaluator import (
    evaluate_answer, difficulty_from_performance, direction_hint,
)


async def get_session(db: AsyncSession, session_id: str) -> InterviewSession | None:
    result = await db.execute(
        select(InterviewSession)
        .options(selectinload(InterviewSession.questions).selectinload(Question.answer))
        .where(InterviewSession.id == session_id)
    )
    return result.scalar_one_or_none()


async def generate_next_question(
    db: AsyncSession,
    session: InterviewSession,
) -> Question:
    session_id = session.id
    result = await db.execute(
        select(InterviewSession)
        .options(selectinload(InterviewSession.questions).selectinload(Question.answer))
        .where(InterviewSession.id == session_id)
    )
    loaded = result.scalar_one()

    question_number = loaded.current_question_index
    # Direct column queries — bypass ORM identity-map staleness so the latest
    # committed answer is always counted (the adaptive engine must not lag a step)
    recent_scores = await _fetch_recent_scores(db, session_id)
    existing_qa = await _fetch_qa_history(db, session_id)

    # Adaptive Difficulty Engine: difficulty + direction driven by past performance
    difficulty = difficulty_from_performance(recent_scores, question_number, settings.MAX_QUESTIONS)
    hint = direction_hint(recent_scores)

    retrieval = await retrieve_context_for_question(
        role=loaded.role,
        resume_skills=loaded.resume_skills or {},
        previous_qa=existing_qa,
        question_number=question_number,
    )
    context = retrieval["context"]

    question_text, question_type = await generate_interview_question(
        role=loaded.role,
        resume_skills=loaded.resume_skills or {},
        context=context,
        previous_qa=existing_qa,
        question_number=question_number,
        total_questions=settings.MAX_QUESTIONS,
        difficulty=difficulty,
        direction_hint=hint,
    )

    # Glass-box / explainable-RAG metadata stored with the question for full traceability
    retrieval_meta = {
        "query": retrieval["query"],
        "topic": retrieval["topic"],
        "difficulty": difficulty,
        "reasoning": hint,
        "sources": retrieval["sources"],
    }

    question = Question(
        session_id=loaded.id,
        question_number=question_number + 1,
        question_text=question_text,
        context_used=context[:1000] if context else None,
        question_type=question_type,
        difficulty=difficulty,
        topic=retrieval["topic"],
        retrieval_meta=retrieval_meta,
    )
    db.add(question)
    loaded.current_question_index = question_number + 1
    await db.commit()
    await db.refresh(question)
    return question


async def _fetch_recent_scores(db: AsyncSession, session_id: str) -> list[float]:
    result = await db.execute(
        select(Answer.score)
        .join(Question, Answer.question_id == Question.id)
        .where(Answer.session_id == session_id)
        .order_by(Question.question_number)
    )
    return [s for (s,) in result.all() if s is not None]


async def _fetch_qa_history(db: AsyncSession, session_id: str) -> list[dict]:
    result = await db.execute(
        select(Question.question_text, Answer.answer_text)
        .outerjoin(Answer, Answer.question_id == Question.id)
        .where(Question.session_id == session_id)
        .order_by(Question.question_number)
    )
    history = []
    for q_text, a_text in result.all():
        entry = {"question": q_text}
        if a_text:
            entry["answer"] = a_text
        history.append(entry)
    return history


async def record_answer(
    db: AsyncSession,
    session: InterviewSession,
    question: Question,
    answer_text: str,
) -> Answer:
    # Adaptive engine: grade the answer against the book context that produced the question
    role_label = ROLE_LABELS.get(session.role, session.role)
    evaluation = await evaluate_answer(
        question_text=question.question_text,
        answer_text=answer_text,
        context=question.context_used or "",
        role_label=role_label,
    )

    answer = Answer(
        question_id=question.id,
        session_id=session.id,
        answer_text=answer_text,
        score=evaluation["score"],
        feedback=evaluation["feedback"],
        eval_detail=evaluation["detail"],
    )
    db.add(answer)
    await db.commit()
    await db.refresh(answer)
    return answer


async def complete_session(db: AsyncSession, session: InterviewSession):
    session.status = "completed"
    session.completed_at = datetime.utcnow()
    await db.commit()


def is_interview_complete(session: InterviewSession) -> bool:
    return session.current_question_index >= settings.MAX_QUESTIONS


def _build_qa_history(session: InterviewSession) -> list[dict]:
    history = []
    for q in session.questions:
        entry = {"question": q.question_text}
        if q.answer:
            entry["answer"] = q.answer.answer_text
        history.append(entry)
    return history
