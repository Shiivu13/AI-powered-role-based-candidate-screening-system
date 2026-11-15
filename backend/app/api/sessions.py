"""Interview session endpoints: one resource, explicit lifecycle actions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import InvalidState, NotFound
from app.schemas import (
    AnswerIn,
    AnswerResult,
    HintOut,
    NextQuestionOut,
    ReportOut,
    SessionDetail,
    SessionSummary,
    SnapshotIO,
)
from app.services import interview_service as svc
from app.services.serializers import question_dict, session_detail, session_summary
from app.services.snapshot import export_snapshot, restore_snapshot, snapshot_version

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _load(db: Session, session_id: str, client_version: int | None):
    """Fetch a session, treating a copy older than the client's as missing so
    the client restores its newer snapshot (serverless instances can lag)."""
    session = svc.get_session(db, session_id)
    if client_version is not None and client_version > snapshot_version(session):
        raise NotFound("This server's copy of the session is out of date", details={"stale": True})
    return session


@router.post("", response_model=SessionDetail, status_code=status.HTTP_201_CREATED)
def create_session(
    role_id: str = Form(...),
    candidate_name: str = Form(""),
    num_questions: int | None = Form(None),
    mode: str = Form("practice"),
    resume_text: str | None = Form(None),
    resume: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    """Stage 1-2: upload resume + choose role -> parse resume, build interview plan."""
    content = resume.file.read() if resume is not None else None
    session = svc.create_session(
        db,
        candidate_name=candidate_name,
        role_id=role_id,
        num_questions=num_questions,
        resume_filename=resume.filename if resume is not None else None,
        resume_bytes=content or None,
        resume_text=resume_text,
        mode=mode,
    )
    return {**session_detail(session), "snapshot": export_snapshot(session)}


@router.get("", response_model=list[SessionSummary])
def list_sessions(limit: int = 50, db: Session = Depends(get_db)):
    return [session_summary(s) for s in svc.list_sessions(db, min(max(limit, 1), 200))]


@router.post("/restore", response_model=SessionDetail)
def restore_session(payload: SnapshotIO, db: Session = Depends(get_db)):
    """Re-create a session from a signed snapshot held by the browser. Needed on
    serverless hosts where instances do not share a database."""
    session = restore_snapshot(db, payload.model_dump())
    return {**session_detail(session), "snapshot": export_snapshot(session)}


@router.get("/{session_id}/snapshot", response_model=SnapshotIO)
def get_snapshot(session_id: str, db: Session = Depends(get_db)):
    return export_snapshot(svc.get_session(db, session_id))


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: str, db: Session = Depends(get_db), x_session_version: int | None = Header(None)):
    session = _load(db, session_id, x_session_version)
    return {**session_detail(session), "snapshot": export_snapshot(session)}


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: str, db: Session = Depends(get_db)):
    svc.delete_session(db, session_id)


@router.post("/{session_id}/questions/next", response_model=NextQuestionOut)
def next_question(session_id: str, db: Session = Depends(get_db), x_session_version: int | None = Header(None)):
    """Stage 3-5: retrieve context and generate the next question (idempotent while a
    question is open: the open question is returned again)."""
    session = _load(db, session_id, x_session_version)
    question = svc.next_question(db, session)
    return {
        "done": question is None,
        "question": question_dict(question) if question else None,
        "progress": svc.progress(session),
        "snapshot": export_snapshot(session),
    }


@router.post("/{session_id}/questions/{question_id}/answer", response_model=AnswerResult)
def answer_question(
    session_id: str, question_id: str, payload: AnswerIn, db: Session = Depends(get_db),
    x_session_version: int | None = Header(None),
):
    """Stage 6-7: store and evaluate the answer; adapts difficulty for later questions."""
    session = _load(db, session_id, x_session_version)
    telemetry = payload.telemetry.model_dump() if payload.telemetry else None
    question = svc.submit_answer(db, session, question_id, payload.text, telemetry)
    return {
        "question": question_dict(question),
        "progress": svc.progress(session),
        "next_action": "complete" if svc.is_plan_exhausted(session) else "next_question",
        "snapshot": export_snapshot(session),
    }


@router.post("/{session_id}/questions/{question_id}/hint", response_model=HintOut)
def hint(session_id: str, question_id: str, db: Session = Depends(get_db), x_session_version: int | None = Header(None)):
    """One grounded nudge for the open question; costs part of that question's score."""
    session = _load(db, session_id, x_session_version)
    data = svc.request_hint(db, session, question_id)
    return {"question_id": question_id, "hint": data["hint"], "penalty": data["penalty"], "mode": data["mode"],
            "snapshot": export_snapshot(session)}


@router.post("/{session_id}/questions/{question_id}/skip", response_model=AnswerResult)
def skip_question(session_id: str, question_id: str, db: Session = Depends(get_db), x_session_version: int | None = Header(None)):
    session = _load(db, session_id, x_session_version)
    question = svc.skip_question(db, session, question_id)
    return {
        "question": question_dict(question),
        "progress": svc.progress(session),
        "next_action": "complete" if svc.is_plan_exhausted(session) else "next_question",
        "snapshot": export_snapshot(session),
    }


@router.post("/{session_id}/complete", response_model=ReportOut)
def complete_session(session_id: str, db: Session = Depends(get_db), x_session_version: int | None = Header(None)):
    """Stage 8: close the interview and generate the structured report."""
    session = _load(db, session_id, x_session_version)
    report = svc.complete_session(db, session)
    return {"session_id": session.id, "created_at": report.created_at, "report": report.data, "snapshot": export_snapshot(session)}


@router.get("/{session_id}/report", response_model=ReportOut)
def get_report(session_id: str, db: Session = Depends(get_db), x_session_version: int | None = Header(None)):
    session = _load(db, session_id, x_session_version)
    if session.report is None:
        raise InvalidState("The interview has not been completed yet")
    return {"session_id": session.id, "created_at": session.report.created_at, "report": session.report.data}
