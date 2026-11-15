"""Role fit and custom roles.

* ``score_roles`` - how well a resume fits each predefined role, so the UI can
  recommend one before the interview starts.
* ``role_from_job_description`` - turns any pasted job description into an
  interview role: the topics it asks for, and the knowledge bases (book
  collections) that cover those topics. Retrieval for such a role searches all
  of those collections (see ``rag.retriever.MultiRetriever``).

Both reuse the planner's topic-affinity scoring, so "what the resume shows"
and "what the job asks for" are measured on the same vocabulary.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import asdict

from app.ai.catalog import ROLES, TOPICS, Role
from app.ai.llm import LLMError, get_llm
from app.ai.planner import topic_affinity

logger = logging.getLogger(__name__)

CUSTOM_PREFIX = "custom_"
MAX_CUSTOM_TOPICS = 10

JD_SYSTEM = """You read a job description for a technical role and extract what an interviewer should probe.
Return JSON:
{
  "title": string (short role title, e.g. "Senior ML Engineer, Fraud"),
  "seniority": "junior"|"mid"|"senior"|null,
  "required_skills": [string] (concepts and techniques, most important first),
  "nice_to_have": [string]
}"""


def score_roles(profile: dict, resume_text: str) -> list[dict]:
    """Fit of the resume against every predefined role, best first (0-100)."""
    results = []
    for role in ROLES.values():
        matched, missing_core, strength = [], [], 0.0
        for topic_id in role.topic_ids:
            score, evidence = topic_affinity(TOPICS[topic_id], resume_text, profile)
            weight = 1.5 if topic_id in role.core_topic_ids else 1.0
            if score > 0:
                matched.append({"topic": TOPICS[topic_id].name, "evidence": evidence[:3]})
                strength += weight * min(score, 6) / 6
            elif topic_id in role.core_topic_ids:
                missing_core.append(TOPICS[topic_id].name)
        max_strength = sum(1.5 if t in role.core_topic_ids else 1.0 for t in role.topic_ids)
        coverage = len(matched) / len(role.topic_ids)
        fit = round(100 * (0.6 * strength / max_strength + 0.4 * coverage))
        results.append({
            "role_id": role.id,
            "title": role.title,
            "fit": fit,
            "matched_topics": matched,
            "missing_core_topics": missing_core,
        })
    results.sort(key=lambda r: r["fit"], reverse=True)
    if results:
        results[0]["recommended"] = True
    return results


def _title_from_text(text: str) -> str:
    """First line or first sentence of the JD, e.g. "Data Scientist - Healthcare Analytics"."""
    for line in text.splitlines():
        head = re.split(r"(?<=[a-z0-9)])[.:!?](\s|$)", line.strip(" -*#\t"))[0].strip()
        if 3 <= len(head) <= 70:
            return head
    return "Custom role"


def role_from_job_description(text: str) -> tuple[Role, dict]:
    """Build an interview role from a job description. Returns (role, details)."""
    text = text.strip()
    extracted: dict = {}
    llm = get_llm()
    if llm.available:
        try:
            extracted = llm.generate_json(JD_SYSTEM, f"JOB DESCRIPTION:\n{text[:8000]}", temperature=0.0)
        except LLMError as exc:
            logger.warning("LLM job-description extraction failed: %s", exc)

    # Score every topic against the JD text plus the skills the LLM extracted.
    skills = [str(s) for s in extracted.get("required_skills", [])][:20]
    nice = [str(s) for s in extracted.get("nice_to_have", [])][:10]
    pseudo_profile = {"skills": skills + nice, "technologies": []}
    scored = []
    for topic in TOPICS.values():
        score, evidence = topic_affinity(topic, text, pseudo_profile)
        if score > 0:
            scored.append((score, topic.id, evidence))
    scored.sort(reverse=True)
    topic_ids = [t for _, t, _ in scored[:MAX_CUSTOM_TOPICS]]
    if len(topic_ids) < 3:
        # Too little signal: fall back to the general ML fundamentals.
        for t in ("supervised_fundamentals", "evaluation", "bias_variance"):
            if t not in topic_ids:
                topic_ids.append(t)

    # Knowledge bases: every role collection that covers at least one chosen topic,
    # ranked by how many it covers.
    coverage = sorted(
        ((sum(t in role.topic_ids for t in topic_ids), role.id) for role in ROLES.values()),
        reverse=True,
    )
    # Keep the collections that cover at least half as many topics as the best one.
    best = coverage[0][0] if coverage else 0
    kb_roles = [rid for n, rid in coverage if n > 0 and n * 2 >= best]
    book_ids = tuple(b for rid in kb_roles for b in ROLES[rid].book_ids)

    title = str(extracted.get("title") or _title_from_text(text))[:80]
    digest = hashlib.sha1(text.encode()).hexdigest()[:10]
    role = Role(
        id=f"{CUSTOM_PREFIX}{digest}",
        title=title,
        description="Custom role built from a job description.",
        book_ids=book_ids,
        topic_ids=tuple(topic_ids),
        core_topic_ids=tuple(topic_ids[:4]),
        question_styles=("applied", "scenario", "conceptual"),
        extra={"kb_roles": kb_roles, "source": "job_description", "seniority": extracted.get("seniority")},
    )
    details = {
        "title": title,
        "topics": [{"id": t, "name": TOPICS[t].name, "evidence": ev[:3]} for _, t, ev in scored[:MAX_CUSTOM_TOPICS]],
        "knowledge_bases": [{"role_id": r, "title": ROLES[r].title} for r in kb_roles],
        "required_skills": skills,
        "extraction": "llm" if extracted else "keyword",
    }
    return role, details


def role_to_spec(role: Role) -> dict:
    data = asdict(role)
    return {k: list(v) if isinstance(v, tuple) else v for k, v in data.items()}


def role_from_spec(spec: dict) -> Role:
    return Role(**{k: tuple(v) if isinstance(v, list) else v for k, v in spec.items()})


def is_custom(role: Role) -> bool:
    return role.id.startswith(CUSTOM_PREFIX)


_WORD = re.compile(r"\w+")


def looks_like_job_description(text: str) -> bool:
    return len(_WORD.findall(text or "")) >= 25
