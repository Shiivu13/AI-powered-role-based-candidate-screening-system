"""Resume processing: file -> text -> structured candidate profile.

Two complementary extractors are merged:

* a deterministic taxonomy matcher (always runs; explainable, offline, gives
  per-skill evidence counts used for topic selection and difficulty), and
* an LLM extractor (when available) that understands context - projects,
  seniority, domains, skills the taxonomy does not list.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from functools import lru_cache

from app.ai.llm import LLMError, get_llm
from app.ai.prompts import PROMPT_VERSION, RESUME_EXTRACTION_SYSTEM
from app.ai.skills_taxonomy import DOMAINS, SKILLS
from app.errors import ValidationFailed
from app.rag.loaders import load_pdf, normalize_text

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md"}


def extract_resume_text(filename: str, content: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf") or content[:4] == b"%PDF":
        try:
            pages = load_pdf(content)
        except Exception as exc:
            raise ValidationFailed(f"Could not read PDF: {exc}") from exc
        text = "\n".join(p.text for p in pages)
        if len(text.strip()) < 40:
            raise ValidationFailed(
                "The PDF has no extractable text (is it a scanned image?). Upload a text-based PDF or paste the text."
            )
        return text
    if any(name.endswith(ext) for ext in (".txt", ".md")):
        return normalize_text(content.decode("utf-8", errors="ignore"))
    raise ValidationFailed(f"Unsupported resume format. Use one of: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")


def _alias_pattern(alias: str, spec: dict) -> re.Pattern:
    flags = 0 if spec.get("case_sensitive") else re.IGNORECASE
    if spec.get("regex"):
        return re.compile(alias, flags)
    return re.compile(rf"(?<![\w+#]){re.escape(alias)}(?![\w+#])", flags)


@lru_cache
def _compiled_taxonomy() -> list[tuple[str, str, list[re.Pattern]]]:
    return [
        (skill, spec["category"], [_alias_pattern(a, spec) for a in spec["aliases"]])
        for skill, spec in SKILLS.items()
    ]


def match_skills(text: str) -> dict[str, dict]:
    """Return {canonical_skill: {"category", "mentions", "aliases"}}."""
    found: dict[str, dict] = {}
    for skill, category, patterns in _compiled_taxonomy():
        mentions = sum(len(pattern.findall(text)) for pattern in patterns)
        if mentions:
            found[skill] = {"category": category, "mentions": mentions}
    return found


def match_domains(text: str) -> list[str]:
    lower = text.lower()
    scored = []
    for domain, terms in DOMAINS.items():
        hits = sum(lower.count(t) for t in terms)
        if hits:
            scored.append((hits, domain))
    return [d for _, d in sorted(scored, reverse=True)[:4]]


_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_RANGE = re.compile(
    rf"(?:{_MONTHS}\s*)?((?:19|20)\d{{2}})\s*(?:-|–|—|to)\s*(?:{_MONTHS}\s*)?((?:19|20)\d{{2}}|present|current|now|date)",
    re.IGNORECASE,
)


def estimate_years(text: str) -> float | None:
    explicit = [float(m) for m in re.findall(r"(\d{1,2}(?:\.\d)?)\+?\s*(?:years|yrs)(?:\s+of)?\s+(?:professional\s+|industry\s+|work\s+)?experience", text, re.IGNORECASE)]
    if explicit:
        return max(explicit)
    # Sum date ranges inside the experience section (fallback: whole resume)
    section = text
    m = re.search(r"(experience|employment|work history)(.*?)(education|projects|skills|certifications|$)", text, re.IGNORECASE | re.DOTALL)
    if m and len(m.group(2)) > 50:
        section = m.group(2)
    current = date.today().year
    total = 0.0
    for start, end in _RANGE.findall(section):
        s = int(start)
        e = current if not end.isdigit() else int(end)
        if 0 <= e - s <= 40:
            total += max(e - s, 0.5)
    return round(total, 1) if total else None


def infer_seniority(text: str, years: float | None) -> str:
    lower = text.lower()
    if re.search(r"\b(senior|staff|principal|lead|head of|manager)\b", lower) and (years or 0) >= 4:
        return "senior"
    if years is None or years < 1:
        if re.search(r"\b(student|b\.?tech|bachelor|undergraduate|intern|pursuing|expected graduation)\b", lower):
            return "student"
        return "junior"
    if years < 2.5:
        return "junior"
    if years < 6:
        return "mid"
    return "senior"


def guess_name(text: str) -> str | None:
    for line in text.splitlines()[:5]:
        line = line.strip()
        if 2 <= len(line.split()) <= 4 and re.fullmatch(r"[A-Za-z][A-Za-z .'-]+", line) and not re.search(r"resume|curriculum|vitae", line, re.I):
            return line.title() if line.isupper() else line
    return None


def heuristic_profile(text: str) -> dict:
    skills = match_skills(text)
    years = estimate_years(text)
    return {
        "name": guess_name(text),
        "headline": None,
        "skills": [s for s, v in skills.items() if v["category"] == "ml_concept"],
        "technologies": [s for s, v in skills.items() if v["category"] != "ml_concept"],
        "domains": match_domains(text),
        "years_experience": years,
        "seniority": infer_seniority(text, years),
        "education": [],
        "projects": [],
        "strength_signals": [],
        "skill_evidence": skills,
    }


def _clean_list(values, limit: int = 25) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for v in values or []:
        if not isinstance(v, str):
            continue
        v = v.strip()
        if v and v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return out[:limit]


def parse_resume(text: str) -> dict:
    """Build the structured candidate profile used by the rest of the pipeline."""
    profile = heuristic_profile(text)
    profile["extraction"] = {"mode": "heuristic", "prompt_version": PROMPT_VERSION}

    llm = get_llm()
    if llm.available:
        try:
            data = llm.generate_json(RESUME_EXTRACTION_SYSTEM, f"RESUME:\n{text[:12000]}", temperature=0.0)
            profile["name"] = data.get("name") or profile["name"]
            profile["headline"] = data.get("headline")
            profile["skills"] = _clean_list(profile["skills"] + _clean_list(data.get("skills")))
            profile["technologies"] = _clean_list(profile["technologies"] + _clean_list(data.get("technologies")))
            profile["domains"] = _clean_list(_clean_list(data.get("domains")) + profile["domains"], 6)
            if isinstance(data.get("years_experience"), (int, float)):
                profile["years_experience"] = float(data["years_experience"])
            if data.get("seniority") in {"student", "junior", "mid", "senior"}:
                profile["seniority"] = data["seniority"]
            profile["education"] = _clean_list(data.get("education"), 5)
            projects = data.get("projects") or []
            profile["projects"] = [
                {
                    "name": str(p.get("name", ""))[:120],
                    "summary": str(p.get("summary", ""))[:400],
                    "technologies": _clean_list(p.get("technologies"), 10),
                }
                for p in projects
                if isinstance(p, dict)
            ][:6]
            profile["strength_signals"] = _clean_list(data.get("strength_signals"), 8)
            profile["extraction"] = {"mode": "llm+heuristic", "model": llm.model, "prompt_version": PROMPT_VERSION}
        except LLMError as exc:
            logger.warning("LLM resume extraction failed, using heuristics: %s", exc)
            profile["extraction"]["note"] = "LLM unavailable; heuristic extraction used"
    if not profile.get("headline"):
        top = ", ".join(list(profile["skill_evidence"])[:4]) or "general background"
        profile["headline"] = f"{profile['seniority'].title()} candidate with experience in {top}"
    return profile
