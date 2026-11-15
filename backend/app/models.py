"""Persistence model.

    InterviewSession 1──* Question 1──0..1 Answer
           │
           └──0..1 Report

* ``InterviewSession`` holds the resume, the extracted profile and the
  interview plan (the "context" stage of the pipeline).
* ``Question.trace`` stores the full provenance of each question: plan item,
  retrieval queries, retrieved chunks with scores and page citations, and the
  generation mode/model/prompt version (Context -> Question).
* ``Answer`` stores the response and its evaluation (Answer -> Storage).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SessionStatus:
    READY = "ready"  # resume parsed, plan built, no question yet
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class QuestionStatus:
    ASKED = "asked"
    ANSWERED = "answered"
    SKIPPED = "skipped"


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    candidate_name: Mapped[str] = mapped_column(String(200))
    role_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default=SessionStatus.READY, index=True)
    resume_filename: Mapped[str | None] = mapped_column(String(255))
    resume_text: Mapped[str] = mapped_column(Text)
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    plan: Mapped[list] = mapped_column(JSON, default=list)
    num_questions: Mapped[int] = mapped_column(Integer)
    difficulty_offset: Mapped[int] = mapped_column(Integer, default=0)  # adaptive adjustment
    follow_ups_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    questions: Mapped[list["Question"]] = relationship(
        back_populates="session", order_by="Question.position", cascade="all, delete-orphan"
    )
    report: Mapped["Report | None"] = relationship(back_populates="session", cascade="all, delete-orphan", uselist=False)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("interview_sessions.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)  # 1-based order in the interview
    plan_index: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20), default="primary")  # primary | follow_up
    parent_question_id: Mapped[str | None] = mapped_column(String(32))
    topic_id: Mapped[str] = mapped_column(String(64))
    topic_name: Mapped[str] = mapped_column(String(200))
    question_type: Mapped[str] = mapped_column(String(32))
    difficulty: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    expected_points: Mapped[list] = mapped_column(JSON, default=list)
    rationale: Mapped[str] = mapped_column(Text, default="")
    trace: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default=QuestionStatus.ASKED)
    asked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped[InterviewSession] = relationship(back_populates="questions")
    answer: Mapped["Answer | None"] = relationship(back_populates="question", cascade="all, delete-orphan", uselist=False)


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), unique=True)
    text: Mapped[str] = mapped_column(Text)
    score: Mapped[float | None] = mapped_column(Float)
    evaluation: Mapped[dict] = mapped_column(JSON, default=dict)
    response_seconds: Mapped[float | None] = mapped_column(Float)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    question: Mapped[Question] = relationship(back_populates="answer")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("interview_sessions.id", ondelete="CASCADE"), unique=True)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped[InterviewSession] = relationship(back_populates="report")
