"""API request/response schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class BookOut(BaseModel):
    id: str
    title: str
    author: str
    available: bool
    chunks: int = 0


class TopicOut(BaseModel):
    id: str
    name: str
    description: str


class RoleOut(BaseModel):
    id: str
    title: str
    description: str
    books: list[BookOut]
    topics: list[TopicOut]
    knowledge_base_ready: bool
    knowledge_base_chunks: int


class PlanItemOut(BaseModel):
    index: int
    topic_id: str
    topic_name: str
    topic_description: str
    source: Literal["resume", "core", "breadth"]
    reason: str
    evidence: list[str]
    affinity: int
    difficulty: int
    difficulty_label: str
    question_type: str
    queries: list[str]
    focus_terms: list[str] = []


class AnswerOut(BaseModel):
    text: str
    score: float | None
    verdict: str | None = None
    feedback: str | None = None
    covered_points: list[str] = []
    missing_points: list[str] = []
    misconceptions: list[str] = []
    evaluation_mode: str | None = None
    integrity: dict[str, Any] | None = None
    response_seconds: float | None = None
    answered_at: datetime


class QuestionOut(BaseModel):
    id: str
    position: int
    plan_index: int
    kind: Literal["primary", "follow_up"]
    parent_question_id: str | None = None
    topic_id: str
    topic_name: str
    question_type: str
    difficulty: int
    difficulty_label: str
    text: str
    rationale: str
    status: Literal["asked", "answered", "skipped"]
    asked_at: datetime
    # Hidden while the question is open so the answer key never reaches the candidate.
    expected_points: list[str] | None = None
    answer: AnswerOut | None = None
    trace: dict[str, Any] | None = None


class Progress(BaseModel):
    planned: int
    primary_asked: int
    asked: int
    answered: int
    skipped: int
    follow_ups: int
    current_difficulty_offset: int


class SessionSummary(BaseModel):
    id: str
    candidate_name: str
    role_id: str
    role_title: str
    status: Literal["ready", "in_progress", "completed"]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    progress: Progress
    overall_score: float | None = None


class SessionDetail(SessionSummary):
    resume_filename: str | None
    profile: dict[str, Any]
    plan: list[PlanItemOut]
    questions: list[QuestionOut]
    current_question_id: str | None
    report_available: bool


class NextQuestionOut(BaseModel):
    done: bool
    question: QuestionOut | None
    progress: Progress


class AnswerTelemetry(BaseModel):
    """Client-side signals collected while the candidate answers (all optional)."""

    pasted_chars: int = Field(default=0, ge=0, le=100_000)
    paste_events: int = Field(default=0, ge=0, le=10_000)
    voice_chars: int = Field(default=0, ge=0, le=100_000)
    keystrokes: int = Field(default=0, ge=0, le=1_000_000)
    active_typing_ms: int | None = Field(default=None, ge=0, le=24 * 3600 * 1000)
    focus_losses: int = Field(default=0, ge=0, le=10_000)


class AnswerIn(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    telemetry: AnswerTelemetry | None = None

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Answer cannot be blank")
        return value.strip()


class AnswerResult(BaseModel):
    question: QuestionOut
    progress: Progress
    next_action: Literal["next_question", "complete"]


class ReportOut(BaseModel):
    session_id: str
    created_at: datetime
    report: dict[str, Any]


class SearchIn(BaseModel):
    role_id: str
    query: str = Field(min_length=2, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)
    mode: Literal["hybrid", "dense", "bm25"] = "hybrid"


class SearchOut(BaseModel):
    role_id: str
    mode: str
    queries: list[str]
    diagnostics: dict[str, Any]
    chunks: list[dict[str, Any]]


class HealthOut(BaseModel):
    status: str
    llm_provider: str
    llm_model: str
    embedding_provider: str
    database: str
    knowledge_base: dict[str, Any]
