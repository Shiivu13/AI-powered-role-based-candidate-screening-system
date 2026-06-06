import json
import re
from app.ml.llm_client import get_llm_client


async def evaluate_answer(
    question_text: str,
    answer_text: str,
    context: str,
    role_label: str,
) -> dict:
    """Scores a candidate's answer against the retrieved book context.

    Returns: {score: 0-10, correctness, depth, relevance, feedback}
    This drives the Adaptive Difficulty Engine and the Knowledge-Gap Radar.
    """
    llm = get_llm_client()

    prompt = f"""You are grading a candidate's answer in a {role_label} interview.
Grade STRICTLY and fairly against the reference material below. Be objective.

QUESTION:
{question_text}

REFERENCE MATERIAL (ground truth from technical books):
{context[:1800] if context else "Use your expert knowledge of the topic."}

CANDIDATE'S ANSWER:
{answer_text}

Score each dimension 0-10 and give ONE short actionable feedback sentence.
Return ONLY valid JSON:
{{
  "correctness": 7,
  "depth": 6,
  "relevance": 8,
  "score": 7.0,
  "feedback": "One concise sentence on what was good or missing."
}}

Scoring guide: 0-3 incorrect/empty, 4-6 partial/surface-level, 7-8 solid, 9-10 expert with nuance.
"score" is the overall (roughly the average). If the answer is empty or 'I don't know', score near 0."""

    try:
        response = await llm.generate(prompt)
        cleaned = re.sub(r'```(?:json)?\s*', '', response).strip()
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            data = json.loads(match.group())
            # Clamp + normalise
            for k in ("correctness", "depth", "relevance", "score"):
                if k in data and data[k] is not None:
                    data[k] = max(0.0, min(10.0, float(data[k])))
            if "score" not in data or data["score"] is None:
                parts = [data.get("correctness", 0), data.get("depth", 0), data.get("relevance", 0)]
                data["score"] = round(sum(parts) / 3, 1)
            return {
                "score": round(float(data["score"]), 1),
                "feedback": data.get("feedback", ""),
                "detail": {
                    "correctness": data.get("correctness"),
                    "depth": data.get("depth"),
                    "relevance": data.get("relevance"),
                },
            }
    except Exception as e:
        print(f"[answer_evaluator] error: {e}")

    return {"score": None, "feedback": "", "detail": {}}


def difficulty_from_performance(recent_scores: list[float], question_number: int, total: int) -> str:
    """Adaptive Difficulty Engine: next difficulty driven by how the candidate is doing."""
    valid = [s for s in recent_scores if s is not None]
    if not valid:
        # No signal yet — ease in based on interview position
        return "beginner-to-intermediate" if question_number < 2 else "intermediate"

    avg = sum(valid[-2:]) / len(valid[-2:])  # weight the last couple answers
    if avg >= 7.5:
        return "advanced"
    if avg >= 5.0:
        return "intermediate"
    if avg >= 3.0:
        return "beginner-to-intermediate"
    return "beginner"  # struggling — probe fundamentals / the revealed gap


def direction_hint(recent_scores: list[float]) -> str:
    """A natural-language steer for the question generator, based on performance."""
    valid = [s for s in recent_scores if s is not None]
    if not valid:
        return "Start with a foundational concept to calibrate the candidate's level."
    last = valid[-1]
    if last >= 7.5:
        return "The candidate answered the previous question well — increase difficulty and probe deeper or a more advanced sub-topic."
    if last >= 5.0:
        return "The candidate showed partial understanding — stay on a related area and test for depth."
    return "The candidate struggled with the previous question — probe the specific gap they revealed with a more fundamental angle, or pivot to a core concept they should know."
