import json
import re
from io import BytesIO
from app.ml.llm_client import get_llm_client


def extract_text_from_pdf(file_bytes: bytes) -> str:
    import pdfplumber
    text = ""
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()


def extract_text_from_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="replace").strip()


async def parse_resume(file_bytes: bytes, filename: str) -> tuple[str, dict]:
    if filename.lower().endswith(".pdf"):
        resume_text = extract_text_from_pdf(file_bytes)
    else:
        resume_text = extract_text_from_txt(file_bytes)

    if not resume_text:
        resume_text = "No content extracted from resume."

    skills_data = await extract_skills_with_llm(resume_text)
    return resume_text, skills_data


async def extract_skills_with_llm(resume_text: str) -> dict:
    llm = get_llm_client()
    prompt = f"""Analyze this resume and extract structured information. Return ONLY valid JSON, no markdown, no explanation.

Resume:
{resume_text[:4000]}

Return this exact JSON structure:
{{
  "skills": ["skill1", "skill2"],
  "technologies": ["tech1", "tech2"],
  "domains": ["domain1", "domain2"],
  "experience_years": 2,
  "education": ["degree and institution"],
  "projects": ["project name and brief description"],
  "previous_roles": ["role at company"]
}}"""

    try:
        response = await llm.generate(prompt)
        cleaned = re.sub(r'```(?:json)?\s*', '', response).strip()
        json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except Exception as e:
        print(f"[resume_parser] skill extraction error: {e}")

    return {
        "skills": [],
        "technologies": [],
        "domains": [],
        "experience_years": None,
        "education": [],
        "projects": [],
        "previous_roles": [],
    }


def format_skills_for_prompt(skills_data: dict) -> str:
    parts = []
    if skills_data.get("skills"):
        parts.append(f"Skills: {', '.join(skills_data['skills'][:10])}")
    if skills_data.get("technologies"):
        parts.append(f"Technologies: {', '.join(skills_data['technologies'][:10])}")
    if skills_data.get("domains"):
        parts.append(f"Domains: {', '.join(skills_data['domains'])}")
    if skills_data.get("experience_years"):
        parts.append(f"Experience: {skills_data['experience_years']} years")
    if skills_data.get("education"):
        parts.append(f"Education: {'; '.join(skills_data['education'])}")
    if skills_data.get("projects"):
        parts.append(f"Projects: {'; '.join(skills_data['projects'][:3])}")
    return "\n".join(parts) or "No structured info extracted."
