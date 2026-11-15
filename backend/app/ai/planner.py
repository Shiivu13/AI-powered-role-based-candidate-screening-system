"""Context construction: resume profile + role  ->  interview plan.

The plan decides *what* to ask about and *how hard*, before any question is
written. It is deterministic and every decision carries a human-readable
reason, which makes the interview direction auditable.

How the resume steers the interview:

* **Topic selection** - each role topic gets an affinity score from how often
  its vocabulary appears in the resume. ~60% of slots go to the strongest
  resume-anchored topics ("verify what you claim"), the rest to the role's core
  topics the resume does *not* cover ("probe the gaps").
* **Difficulty** - baseline from seniority; topics the candidate claims deep
  experience in are bumped up one level.
* **Direction** - interview opens on the candidate's strongest topic, then
  alternates claims and gaps; resume-anchored slots favour applied/scenario
  questions, gap slots favour conceptual ones.
* **Retrieval queries** - built from the topic's textbook vocabulary *and* the
  candidate's own matching skills, so retrieved passages sit at the
  intersection of the role and the candidate.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from app.ai.catalog import Role, Topic, role_topics

DIFFICULTY_LABELS = {1: "foundational", 2: "intermediate", 3: "advanced"}
SENIORITY_BASE = {"student": 1, "junior": 1, "mid": 2, "senior": 3}


@dataclass
class PlanItem:
    index: int
    topic_id: str
    topic_name: str
    topic_description: str
    source: str  # "resume" | "core" | "breadth"
    reason: str
    evidence: list[str]
    affinity: int
    difficulty: int
    question_type: str
    queries: list[str]
    focus_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["difficulty_label"] = DIFFICULTY_LABELS[self.difficulty]
        return data


def topic_affinity(topic: Topic, resume_text: str, profile: dict) -> tuple[int, list[str]]:
    """Score how strongly the resume evidences a topic. Returns (score, evidence)."""
    lower = resume_text.lower()
    score = 0
    evidence: list[str] = []
    for keyword in topic.keywords:
        hits = len(re.findall(rf"(?<![\w-]){re.escape(keyword.lower())}(?![\w-])", lower))
        if hits:
            score += min(hits, 3)
            evidence.append(keyword)
    # LLM-extracted skills that the regex vocabulary may have missed
    extracted = [s.lower() for s in profile.get("skills", []) + profile.get("technologies", [])]
    for skill in extracted:
        if any(k in skill or skill in k for k in topic.keywords if len(k) > 3) and skill not in evidence:
            score += 1
            evidence.append(skill)
    return score, evidence[:6]


def _difficulty(base: int, affinity: int, source: str) -> int:
    level = base
    if source == "resume" and affinity >= 4:
        level += 1
    return max(1, min(3, level))


def _question_type(role: Role, source: str, slot: int, difficulty: int, has_projects: bool) -> str:
    styles = list(role.question_styles)
    if source == "resume":
        preferred = [s for s in styles if s != "conceptual"] or styles
        if not has_projects and "conceptual" in styles and slot % 3 == 2:
            return "conceptual"
        return preferred[slot % len(preferred)]
    if "derivation" in styles and difficulty >= 3:
        return "derivation"
    return "conceptual" if slot % 2 == 0 or "conceptual" not in styles else styles[(slot // 2) % len(styles)]


def _queries(topic: Topic, evidence: list[str], difficulty: int) -> list[str]:
    queries = [f"{topic.name}: {topic.retrieval_terms[0]}"]
    if evidence:
        queries.append(f"{topic.retrieval_terms[1 % len(topic.retrieval_terms)]} {' '.join(evidence[:3])}")
    else:
        queries.append(topic.retrieval_terms[1 % len(topic.retrieval_terms)])
    level_hint = {1: "introduction definition intuition", 2: "algorithm how it works", 3: "theory assumptions analysis"}[difficulty]
    queries.append(f"{topic.retrieval_terms[2 % len(topic.retrieval_terms)]} {level_hint}")
    return queries


def build_plan(role: Role, profile: dict, resume_text: str, num_questions: int) -> list[PlanItem]:
    topics = role_topics(role)
    scored = {t.id: topic_affinity(t, resume_text, profile) for t in topics}
    by_id = {t.id: t for t in topics}
    base = SENIORITY_BASE.get(profile.get("seniority", "junior"), 1)
    has_projects = bool(profile.get("projects")) or (profile.get("years_experience") or 0) >= 1

    anchored = sorted((t for t in topics if scored[t.id][0] > 0), key=lambda t: scored[t.id][0], reverse=True)
    n_resume = min(len(anchored), max(1, round(num_questions * 0.6))) if anchored else 0

    resume_picks = anchored[:n_resume]
    picked = {t.id for t in resume_picks}
    core_gaps = [by_id[t] for t in role.core_topic_ids if t not in picked and scored[t][0] == 0]
    core_rest = [by_id[t] for t in role.core_topic_ids if t not in picked and scored[t][0] > 0]
    core_picks: list[Topic] = []
    for t in core_gaps + core_rest:
        if len(resume_picks) + len(core_picks) >= num_questions:
            break
        core_picks.append(t)
        picked.add(t.id)
    breadth = [t for t in anchored[n_resume:] + topics if t.id not in picked]
    breadth_picks: list[Topic] = []
    for t in breadth:
        if len(resume_picks) + len(core_picks) + len(breadth_picks) >= num_questions:
            break
        if t.id not in picked:
            breadth_picks.append(t)
            picked.add(t.id)

    # Interleave: strongest claim first, then alternate gaps and claims.
    sequence: list[tuple[Topic, str]] = []
    r, c = list(resume_picks), list(core_picks) + list(breadth_picks)
    if r:
        sequence.append((r.pop(0), "resume"))
    while r or c:
        if c:
            t = c.pop(0)
            sequence.append((t, "core" if t in core_picks else "breadth"))
        if r:
            sequence.append((r.pop(0), "resume"))

    plan: list[PlanItem] = []
    for slot, (topic, source) in enumerate(sequence[:num_questions]):
        affinity, evidence = scored[topic.id]
        difficulty = _difficulty(base, affinity, source)
        if source == "resume":
            reason = f"Resume shows {', '.join(evidence[:3])} - verify depth in {topic.name.lower()}."
        elif source == "core":
            reason = (
                f"Core competency for {role.title}; the resume does not evidence it, so probe the gap."
                if affinity == 0
                else f"Core competency for {role.title} (lightly evidenced on the resume)."
            )
        else:
            reason = f"Breadth check across {role.title} fundamentals."
        plan.append(
            PlanItem(
                index=slot,
                topic_id=topic.id,
                topic_name=topic.name,
                topic_description=topic.description,
                source=source,
                reason=reason,
                evidence=evidence,
                affinity=affinity,
                difficulty=difficulty,
                question_type=_question_type(role, source, slot, difficulty, has_projects),
                queries=_queries(topic, evidence, difficulty),
                focus_terms=[w for w in topic.retrieval_terms[0].split() if len(w) > 3][:5],
            )
        )
    return plan
