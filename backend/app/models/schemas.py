from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class SessionCreate(BaseModel):
    candidate_name: Optional[str] = None
    role: str


class RetrievalSource(BaseModel):
    book: str
    snippet: str
    similarity: Optional[float] = None


class RetrievalMeta(BaseModel):
    query: Optional[str] = None
    topic: Optional[str] = None
    difficulty: Optional[str] = None
    reasoning: Optional[str] = None
    sources: List[RetrievalSource] = []


class QuestionOut(BaseModel):
    id: str
    question_number: int
    question_text: str
    question_type: Optional[str] = None
    difficulty: Optional[str] = None
    topic: Optional[str] = None
    retrieval_meta: Optional[RetrievalMeta] = None
    created_at: datetime
    answer_text: Optional[str] = None
    score: Optional[float] = None
    feedback: Optional[str] = None
    eval_detail: Optional[dict] = None

    class Config:
        from_attributes = True


class AnswerEvaluation(BaseModel):
    score: Optional[float] = None
    feedback: Optional[str] = None
    detail: Optional[dict] = None


class AnswerSubmit(BaseModel):
    answer: str


class ResumeSkills(BaseModel):
    skills: List[str] = []
    technologies: List[str] = []
    domains: List[str] = []
    experience_years: Optional[int] = None
    education: List[str] = []
    projects: List[str] = []


class SessionOut(BaseModel):
    id: str
    candidate_name: Optional[str]
    role: str
    status: str
    resume_skills: Optional[dict]
    current_question_index: int
    created_at: datetime
    completed_at: Optional[datetime]
    questions: List[QuestionOut] = []

    class Config:
        from_attributes = True


class NextQuestionOut(BaseModel):
    question: Optional[QuestionOut]
    is_complete: bool
    question_number: int
    total_questions: int
    last_answer_evaluation: Optional[AnswerEvaluation] = None


class SummaryOut(BaseModel):
    session_id: str
    candidate_name: Optional[str]
    role: str
    total_questions: int
    topics_covered: List[str] = []
    overall_assessment: Optional[str]
    strengths: List[str] = []
    improvements: List[str] = []
    technical_score: Optional[float]
    recommendation: Optional[str]
    full_analysis: Optional[str]
    topic_mastery: List[dict] = []  # [{topic, score, count}] for the Knowledge-Gap Radar
    average_score: Optional[float] = None
    questions: List[QuestionOut] = []
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeStatusOut(BaseModel):
    ingested: bool
    collections: dict
    total_chunks: int
