import json
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.db_models import Session as InterviewSession, SessionSummary, Question
from app.ml.llm_client import get_llm_client
from app.services.resume_parser import format_skills_for_prompt

ROLE_LABELS = {
    "ai_ml": "AI/ML Engineer",
    "data_science": "Data Scientist",
    "backend": "Backend Engineer",
}


def _short_topic_label(topic: str) -> str:
    """Turn a long retrieval-topic string into a short radar-axis label."""
    if not topic:
        return "General"
    words = topic.split()
    # First two meaningful words, title-cased
    label = " ".join(words[:2]).title()
    return label


def compute_topic_mastery(session: InterviewSession):
    """Aggregates per-answer scores into topic-level mastery for the Knowledge-Gap Radar.

    Returns (mastery: [{topic, score, count}], average_score: float|None)
    """
    buckets: dict[str, list[float]] = {}
    all_scores: list[float] = []

    for q in session.questions:
        if not q.answer or q.answer.score is None:
            continue
        all_scores.append(q.answer.score)
        label = _short_topic_label(q.topic or (q.question_type or "General"))
        buckets.setdefault(label, []).append(q.answer.score)

    mastery = [
        {"topic": label, "score": round(sum(scores) / len(scores), 1), "count": len(scores)}
        for label, scores in buckets.items()
    ]
    mastery.sort(key=lambda m: m["score"])  # weakest first — highlights gaps
    average = round(sum(all_scores) / len(all_scores), 1) if all_scores else None
    return mastery, average


async def generate_summary(db: AsyncSession, session: InterviewSession) -> SessionSummary:
    existing = await db.execute(
        select(SessionSummary).where(SessionSummary.session_id == session.id)
    )
    existing_summary = existing.scalar_one_or_none()
    if existing_summary:
        return existing_summary

    result = await db.execute(
        select(InterviewSession)
        .options(selectinload(InterviewSession.questions).selectinload(Question.answer))
        .where(InterviewSession.id == session.id)
    )
    full_session = result.scalar_one()

    qa_pairs = []
    for q in full_session.questions:
        qa_pairs.append({
            "question": q.question_text,
            "answer": q.answer.answer_text if q.answer else "[No answer provided]",
            "type": q.question_type or "general",
        })

    analysis = await _generate_analysis(full_session, qa_pairs)

    summary = SessionSummary(
        session_id=session.id,
        total_questions=len(qa_pairs),
        topics_covered=analysis.get("topics_covered", []),
        overall_assessment=analysis.get("overall_assessment", ""),
        strengths=analysis.get("strengths", []),
        improvements=analysis.get("improvements", []),
        technical_score=analysis.get("technical_score"),
        recommendation=analysis.get("recommendation", ""),
        full_analysis=analysis.get("full_analysis", ""),
    )
    db.add(summary)
    await db.commit()
    await db.refresh(summary)
    return summary


async def _generate_analysis(session: InterviewSession, qa_pairs: list[dict]) -> dict:
    llm = get_llm_client()
    role_label = ROLE_LABELS.get(session.role, session.role)
    candidate_profile = format_skills_for_prompt(session.resume_skills or {})
    transcript = _format_transcript(qa_pairs)

    prompt = f"""You are a senior technical hiring manager analyzing a {role_label} interview.

CANDIDATE: {session.candidate_name or "Anonymous"}
ROLE: {role_label}

CANDIDATE PROFILE:
{candidate_profile}

INTERVIEW TRANSCRIPT:
{transcript}

Provide a comprehensive structured analysis. Return ONLY valid JSON:
{{
  "overall_assessment": "2-3 sentence overall assessment of the candidate",
  "strengths": ["strength1", "strength2", "strength3"],
  "improvements": ["area1", "area2", "area3"],
  "topics_covered": ["topic1", "topic2", "topic3", "topic4"],
  "technical_score": 7.5,
  "recommendation": "Strong Hire",
  "full_analysis": "Detailed paragraph analysis referencing specific answers and demonstrating depth of evaluation"
}}

For recommendation use exactly one of: "Strong Hire", "Hire", "Maybe", "No Hire"
Technical score is 1-10."""

    try:
        response = await llm.generate(prompt)
        # Strip markdown code blocks if present
        cleaned = re.sub(r'```(?:json)?\s*', '', response).strip()
        # Find the JSON object
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"[summary] LLM analysis error: {e}")

    return {
        "overall_assessment": "Interview completed. Manual review recommended.",
        "strengths": [],
        "improvements": [],
        "topics_covered": [],
        "technical_score": None,
        "recommendation": "Maybe",
        "full_analysis": "Analysis could not be generated automatically.",
    }


def _format_transcript(qa_pairs: list[dict]) -> str:
    lines = []
    for i, qa in enumerate(qa_pairs, 1):
        lines.append(f"Q{i} ({qa['type']}): {qa['question']}")
        lines.append(f"A{i}: {qa['answer']}")
        lines.append("")
    return "\n".join(lines)
