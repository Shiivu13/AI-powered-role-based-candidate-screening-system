import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    candidate_name: Mapped[str] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="created")
    resume_text: Mapped[str] = mapped_column(Text, nullable=True)
    resume_skills: Mapped[dict] = mapped_column(JSON, nullable=True)
    current_question_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    questions: Mapped[list["Question"]] = relationship(
        "Question", back_populates="session", cascade="all, delete-orphan", order_by="Question.question_number"
    )
    summary: Mapped["SessionSummary"] = relationship(
        "SessionSummary", back_populates="session", uselist=False, cascade="all, delete-orphan"
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False)
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_used: Mapped[str] = mapped_column(Text, nullable=True)
    question_type: Mapped[str] = mapped_column(String, nullable=True)
    difficulty: Mapped[str] = mapped_column(String, nullable=True)
    topic: Mapped[str] = mapped_column(String, nullable=True)
    # Glass-box / explainable-RAG metadata: {query, reasoning, sources:[{book, snippet, score}]}
    retrieval_meta: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["Session"] = relationship("Session", back_populates="questions")
    answer: Mapped["Answer"] = relationship(
        "Answer", back_populates="question", uselist=False, cascade="all, delete-orphan"
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    question_id: Mapped[str] = mapped_column(String, ForeignKey("questions.id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Adaptive engine: per-answer evaluation against retrieved book context
    score: Mapped[float] = mapped_column(Float, nullable=True)
    feedback: Mapped[str] = mapped_column(Text, nullable=True)
    eval_detail: Mapped[dict] = mapped_column(JSON, nullable=True)  # {correctness, depth, relevance}
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    question: Mapped["Question"] = relationship("Question", back_populates="answer")


class SessionSummary(Base):
    __tablename__ = "session_summaries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id"), unique=True, nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    topics_covered: Mapped[list] = mapped_column(JSON, nullable=True)
    overall_assessment: Mapped[str] = mapped_column(Text, nullable=True)
    strengths: Mapped[list] = mapped_column(JSON, nullable=True)
    improvements: Mapped[list] = mapped_column(JSON, nullable=True)
    technical_score: Mapped[float] = mapped_column(Float, nullable=True)
    recommendation: Mapped[str] = mapped_column(String, nullable=True)
    full_analysis: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["Session"] = relationship("Session", back_populates="summary")
