"""Final session analysis: scores, resume-claim verification, insights."""
from __future__ import annotations

import logging
from collections import defaultdict
from statistics import mean

from app.ai.catalog import Role
from app.ai.llm import LLMError, get_llm
from app.ai.prompts import PROMPT_VERSION, REPORT_SYSTEM, REPORT_USER

logger = logging.getLogger(__name__)

RECOMMENDATIONS = [
    (7.5, "strong_yes", "Strongly recommend for next round"),
    (6.0, "yes", "Recommend for next round"),
    (4.5, "borderline", "Borderline - consider a focused follow-up interview"),
    (0.0, "no", "Not recommended at this time"),
]


def _weight(difficulty: int) -> float:
    return 1.0 + 0.25 * (difficulty - 1)


def recommendation_for(score: float) -> tuple[str, str]:
    for threshold, code, label in RECOMMENDATIONS:
        if score >= threshold:
            return code, label
    return RECOMMENDATIONS[-1][1], RECOMMENDATIONS[-1][2]


def build_report(*, role: Role, profile: dict, plan: list[dict], questions: list[dict], candidate_name: str) -> dict:
    """``questions`` are serialised question dicts each with an optional ``answer``."""
    scored = []
    for q in questions:
        answer = q.get("answer")
        if q["status"] == "skipped":
            scored.append((q, 0.0))
        elif answer and answer.get("score") is not None:
            scored.append((q, float(answer["score"])))

    if scored:
        overall = sum(s * _weight(q["difficulty"]) for q, s in scored) / sum(_weight(q["difficulty"]) for q, _ in scored)
    else:
        overall = 0.0
    overall = round(overall, 1)
    rec_code, rec_label = recommendation_for(overall)

    by_topic: dict[str, list[tuple[dict, float]]] = defaultdict(list)
    for q, s in scored:
        by_topic[q["topic_id"]].append((q, s))
    plan_by_topic = {p["topic_id"]: p for p in plan}

    topic_breakdown = []
    for topic_id, items in by_topic.items():
        p = plan_by_topic.get(topic_id, {})
        avg = round(mean(s for _, s in items), 1)
        topic_breakdown.append(
            {
                "topic_id": topic_id,
                "topic_name": items[0][0]["topic_name"],
                "source": p.get("source", "follow_up"),
                "score": avg,
                "questions": len(items),
                "max_difficulty": max(q["difficulty"] for q, _ in items),
            }
        )
    topic_breakdown.sort(key=lambda t: t["score"], reverse=True)

    claims = []
    for t in topic_breakdown:
        p = plan_by_topic.get(t["topic_id"], {})
        if p.get("source") != "resume":
            continue
        status = "verified" if t["score"] >= 7 else "partially_verified" if t["score"] >= 4.5 else "not_verified"
        claims.append({"topic_name": t["topic_name"], "evidence": p.get("evidence", []), "score": t["score"], "status": status})

    gaps = [
        {"topic_name": t["topic_name"], "score": t["score"]}
        for t in topic_breakdown
        if plan_by_topic.get(t["topic_id"], {}).get("source") in {"core", "breadth"}
    ]

    answered = [q for q in questions if q.get("answer") and q["status"] == "answered"]
    response_times = [q["answer"]["response_seconds"] for q in answered if q["answer"].get("response_seconds")]
    word_counts = [len(q["answer"]["text"].split()) for q in answered]
    insights = {
        "questions_asked": len(questions),
        "answered": len(answered),
        "skipped": sum(q["status"] == "skipped" for q in questions),
        "follow_ups": sum(q["kind"] == "follow_up" for q in questions),
        "avg_response_seconds": round(mean(response_times), 1) if response_times else None,
        "avg_answer_words": round(mean(word_counts)) if word_counts else 0,
        "difficulty_progression": [
            {"position": q["position"], "difficulty": q["difficulty"], "score": (q.get("answer") or {}).get("score")}
            for q in questions
        ],
        "score_trend": _trend([s for _, s in scored]),
        "integrity": _integrity_summary(answered),
        "grounding": {
            "books_used": sorted({c["book_title"] for q in questions for c in q.get("trace", {}).get("retrieval", {}).get("chunks", [])}),
            "llm_generated": sum(q.get("trace", {}).get("generation", {}).get("mode") == "llm" for q in questions),
        },
    }

    strengths = [f"{t['topic_name']} ({t['score']}/10)" for t in topic_breakdown if t["score"] >= 7]
    improvements = [f"{t['topic_name']} ({t['score']}/10)" for t in topic_breakdown if t["score"] < 5]
    narrative = {
        "summary": _template_summary(candidate_name, role, overall, rec_label, strengths, improvements, claims),
        "strengths": strengths or ["No topic reached a strong score yet."],
        "improvement_areas": improvements or ["No major weaknesses observed in the topics covered."],
        "resume_alignment": _alignment_text(claims),
        "suggested_next_steps": _next_steps(rec_code, improvements),
        "mode": "heuristic",
    }

    llm = get_llm()
    if llm.available and scored:
        evidence = "\n".join(
            f"- [{q['topic_name']} | {q['question_type']} | diff {q['difficulty']}] Q: {q['text'][:200]} | score {s}/10 | "
            f"missed: {', '.join((q.get('answer') or {}).get('evaluation', {}).get('missing_points', [])[:2])[:200]}"
            for q, s in scored
        )
        try:
            data = llm.generate_json(
                REPORT_SYSTEM.format(role_title=role.title),
                REPORT_USER.format(
                    candidate=candidate_name,
                    seniority=profile.get("seniority"),
                    skills=", ".join((profile.get("skills") or [])[:10]),
                    overall=overall,
                    recommendation=rec_label,
                    evidence=evidence,
                ),
                temperature=0.2,
            )
            narrative.update({k: data[k] for k in ("summary", "strengths", "improvement_areas", "resume_alignment", "suggested_next_steps") if data.get(k)})
            narrative["mode"] = "llm"
        except LLMError as exc:
            logger.warning("LLM report narrative failed: %s", exc)

    return {
        "candidate_name": candidate_name,
        "role_id": role.id,
        "role_title": role.title,
        "overall_score": overall,
        "recommendation": {"code": rec_code, "label": rec_label},
        "topic_breakdown": topic_breakdown,
        "resume_claims": claims,
        "gap_probes": gaps,
        "insights": insights,
        "narrative": narrative,
        "prompt_version": PROMPT_VERSION,
    }


def _trend(scores: list[float]) -> str:
    if len(scores) < 3:
        return "insufficient_data"
    half = len(scores) // 2
    first, second = mean(scores[:half]), mean(scores[half:])
    if second - first > 1:
        return "improving"
    if first - second > 1:
        return "declining"
    return "stable"


def _template_summary(name, role, overall, rec_label, strengths, improvements, claims) -> str:
    verified = sum(c["status"] == "verified" for c in claims)
    parts = [f"{name} scored {overall}/10 overall for the {role.title} role ({rec_label.lower()})."]
    if strengths:
        parts.append(f"Strongest areas: {', '.join(strengths[:3])}.")
    if improvements:
        parts.append(f"Needs work on: {', '.join(improvements[:3])}.")
    if claims:
        parts.append(f"{verified} of {len(claims)} resume-backed topics were verified in the interview.")
    return " ".join(parts)


def _alignment_text(claims: list[dict]) -> str:
    if not claims:
        return "No resume-anchored topics were assessed."
    weak = [c["topic_name"] for c in claims if c["status"] == "not_verified"]
    if not weak:
        return "Demonstrated knowledge is consistent with the skills claimed on the resume."
    return f"Resume claims not supported by interview answers: {', '.join(weak)}."


def _next_steps(code: str, improvements: list[str]) -> list[str]:
    steps = {
        "strong_yes": ["Advance to system-design / hands-on coding round."],
        "yes": ["Advance to next round; include a practical exercise."],
        "borderline": ["Run a focused follow-up on the weakest topics before deciding."],
        "no": ["Do not advance for this role at this time."],
    }[code]
    if improvements:
        steps.append(f"Probe further: {', '.join(i.split(' (')[0] for i in improvements[:3])}.")
    return steps


def _integrity_summary(answered: list[dict]) -> dict:
    flagged = []
    for q in answered:
        integrity = (q.get("answer") or {}).get("integrity") or {}
        if integrity.get("flags"):
            flagged.append({"position": q["position"], "topic_name": q["topic_name"], "flags": integrity["flags"]})
    level = "none" if not flagged else "review" if len(flagged) == 1 else "high"
    return {"level": level, "flagged_answers": flagged, "note": "Advisory signals for human review; not used in scoring."}
