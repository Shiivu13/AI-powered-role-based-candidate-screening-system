"""Pre-interview analysis: resume-to-role fit and roles built from job descriptions."""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, Field

from app.ai.resume_parser import extract_resume_text, parse_resume
from app.ai.role_fit import looks_like_job_description, role_from_job_description, score_roles
from app.config import get_settings
from app.errors import ValidationFailed

router = APIRouter(tags=["analysis"])


@router.post("/resume/analyze")
def analyze_resume(resume: UploadFile | None = File(None), resume_text: str | None = Form(None)):
    """Parse a resume without starting an interview and score it against every role."""
    settings = get_settings()
    if resume is not None:
        content = resume.file.read()
        if len(content) > settings.max_resume_bytes:
            raise ValidationFailed(f"Resume file exceeds {settings.max_resume_bytes // (1024 * 1024)} MB")
        text = extract_resume_text(resume.filename or "resume", content)
    elif resume_text and resume_text.strip():
        text = resume_text.strip()
    else:
        raise ValidationFailed("Provide a resume file or paste the resume text")
    if len(text) < settings.min_resume_chars:
        raise ValidationFailed("The resume is too short to analyse")
    profile = parse_resume(text)
    return {
        "profile": {k: profile.get(k) for k in ("name", "headline", "seniority", "years_experience", "skills", "technologies", "domains")},
        "role_fit": score_roles(profile, text),
    }


class JobDescriptionIn(BaseModel):
    text: str = Field(min_length=20, max_length=20_000)


@router.post("/roles/from-job-description")
def role_from_jd(payload: JobDescriptionIn):
    """Preview the interview role a job description would produce."""
    if not looks_like_job_description(payload.text):
        raise ValidationFailed("The job description is too short (at least 25 words)")
    role, details = role_from_job_description(payload.text)
    return {"role_id": role.id, **details}
