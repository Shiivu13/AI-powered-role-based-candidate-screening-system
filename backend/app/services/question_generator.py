from app.ml.llm_client import get_llm_client
from app.services.resume_parser import format_skills_for_prompt

ROLE_LABELS = {
    "ai_ml": "AI/ML Engineer",
    "data_science": "Data Scientist",
    "backend": "Backend Engineer",
}

QUESTION_TYPES = ["conceptual", "applied", "problem-solving", "experiential"]


async def generate_interview_question(
    role: str,
    resume_skills: dict,
    context: str,
    previous_qa: list[dict],
    question_number: int,
    total_questions: int,
    difficulty: str = "intermediate",
    direction_hint: str = "",
) -> tuple[str, str]:
    llm = get_llm_client()
    role_label = ROLE_LABELS.get(role, role)
    candidate_profile = format_skills_for_prompt(resume_skills)
    qa_history = _format_qa_history(previous_qa)
    question_type = QUESTION_TYPES[question_number % len(QUESTION_TYPES)]

    system = f"You are a senior technical interviewer conducting a {role_label} interview. Your questions are precise, insightful, and tailored to the candidate. You adapt difficulty based on how the candidate is performing — like a real interviewer."

    prompt = f"""You are interviewing a candidate for a {role_label} position. Generate question #{question_number + 1} of {total_questions}.

CANDIDATE PROFILE:
{candidate_profile}

KNOWLEDGE CONTEXT (from technical reference books — ground your question in this):
{context[:2000] if context else f"Use your knowledge of {role_label} concepts."}

PREVIOUS INTERVIEW QUESTIONS & ANSWERS:
{qa_history if qa_history else "This is the first question."}

ADAPTIVE INSTRUCTIONS:
- Question type: {question_type}
- Target difficulty: {difficulty}
- Performance-based steer: {direction_hint or "Calibrate to the candidate's background."}
- Ground the question in the KNOWLEDGE CONTEXT above (the reference books), not generic trivia
- Reference the candidate's specific skills/projects when relevant
- Ask ONE clear, specific question only — no preamble, no explanation, no answer

Generate only the interview question:"""

    question_text = await llm.generate(prompt, system=system)
    question_text = _clean_question(question_text)
    return question_text, question_type


def _format_qa_history(previous_qa: list[dict]) -> str:
    if not previous_qa:
        return ""
    lines = []
    for i, qa in enumerate(previous_qa, 1):
        lines.append(f"Q{i}: {qa.get('question', '')}")
        lines.append(f"A{i}: {qa.get('answer', '')[:300]}")
        lines.append("")
    return "\n".join(lines)


def _get_difficulty(resume_skills: dict, question_number: int, total_questions: int) -> str:
    exp_years = resume_skills.get("experience_years") or 0
    if exp_years >= 5:
        base = "advanced"
    elif exp_years >= 2:
        base = "intermediate"
    else:
        base = "beginner-to-intermediate"

    progress = question_number / max(total_questions - 1, 1)
    if progress > 0.7:
        return "advanced"
    elif progress > 0.4:
        return "intermediate"
    return base


def _clean_question(text: str) -> str:
    prefixes = ["Question:", "Q:", "Interview Question:", "Here's the question:"]
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    return text.strip()
