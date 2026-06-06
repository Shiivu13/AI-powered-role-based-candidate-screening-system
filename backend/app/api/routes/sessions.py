import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.db_models import Session as InterviewSession, Question
from app.models.schemas import SessionOut, QuestionOut
from app.services.resume_parser import parse_resume
from app.services.interview_service import generate_next_question, get_session

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

ALLOWED_ROLES = {"ai_ml", "data_science", "backend"}
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx"}


@router.post("", response_model=dict)
async def create_session(
    resume: UploadFile = File(...),
    role: str = Form(...),
    candidate_name: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
):
    if role not in ALLOWED_ROLES:
        raise HTTPException(400, f"Role must be one of: {', '.join(ALLOWED_ROLES)}")

    ext = "." + resume.filename.split(".")[-1].lower() if "." in resume.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, "Resume must be PDF or TXT file")

    file_bytes = await resume.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        raise HTTPException(400, "File size must be under 5MB")

    resume_text, skills_data = await parse_resume(file_bytes, resume.filename)

    session = InterviewSession(
        id=str(uuid.uuid4()),
        candidate_name=candidate_name.strip() or None,
        role=role,
        status="processing",
        resume_text=resume_text,
        resume_skills=skills_data,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    first_question = await generate_next_question(db, session)
    session.status = "active"
    await db.commit()

    from app.api.serializers import question_to_out
    from app.config import settings as _settings

    return {
        "session_id": session.id,
        "status": "active",
        "role": role,
        "candidate_name": session.candidate_name,
        "first_question": question_to_out(first_question, include_answer=False).model_dump(mode="json"),
        "total_questions": _settings.MAX_QUESTIONS,
    }


@router.get("/{session_id}", response_model=SessionOut)
async def get_session_details(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    from app.api.serializers import question_to_out
    questions_out = [question_to_out(q) for q in session.questions]

    return SessionOut(
        id=session.id,
        candidate_name=session.candidate_name,
        role=session.role,
        status=session.status,
        resume_skills=session.resume_skills,
        current_question_index=session.current_question_index,
        created_at=session.created_at,
        completed_at=session.completed_at,
        questions=questions_out,
    )
