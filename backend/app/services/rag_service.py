import asyncio
from app.ml.vector_store import async_query_knowledge, query_knowledge_detailed
from app.services.resume_parser import format_skills_for_prompt


ROLE_TOPICS = {
    "ai_ml": [
        "supervised learning classification regression",
        "neural networks deep learning backpropagation",
        "decision trees random forests ensemble methods",
        "model evaluation cross-validation bias variance",
        "unsupervised learning clustering dimensionality reduction",
        "reinforcement learning reward policy optimization",
        "feature engineering selection preprocessing",
        "regularization overfitting generalization",
        "Bayesian learning probabilistic models",
        "support vector machines kernel methods",
    ],
    "data_science": [
        "data preprocessing cleaning missing values",
        "exploratory data analysis statistics visualization",
        "feature selection importance engineering",
        "model selection evaluation metrics",
        "machine learning algorithms scikit-learn",
        "time series analysis forecasting",
        "natural language processing text analysis",
        "data pipelines ETL workflows",
        "hypothesis testing statistical significance",
        "gradient boosting XGBoost LightGBM",
    ],
    "backend": [
        "REST API design principles HTTP methods",
        "database design normalization SQL queries",
        "system design scalability distributed systems",
        "caching strategies Redis performance",
        "microservices architecture service communication",
        "authentication authorization security JWT",
        "message queues async processing Kafka RabbitMQ",
        "containerization Docker Kubernetes deployment",
        "API rate limiting load balancing",
        "database indexing query optimization",
    ],
}


def _current_topic(role: str, question_number: int) -> str:
    role_topics = ROLE_TOPICS.get(role, [])
    if not role_topics:
        return role
    return role_topics[question_number % len(role_topics)]


async def retrieve_context_for_question(
    role: str,
    resume_skills: dict,
    previous_qa: list[dict],
    question_number: int,
) -> dict:
    """Returns a structured retrieval result powering both question-gen and the glass-box panel.

    {context, query, topic, sources: [{book, snippet, similarity}]}
    """
    query = _build_query(role, resume_skills, previous_qa, question_number)
    loop = asyncio.get_event_loop()
    hits = await loop.run_in_executor(None, query_knowledge_detailed, role, query, 4)

    if not hits:
        fallback_query = _current_topic(role, question_number)
        hits = await loop.run_in_executor(None, query_knowledge_detailed, role, fallback_query, 4)
        query = fallback_query

    context = "\n\n---\n\n".join(h["text"] for h in hits) if hits else ""
    sources = [
        {"book": h["book"], "snippet": h["snippet"], "similarity": h["similarity"]}
        for h in hits
    ]
    return {
        "context": context,
        "query": query,
        "topic": _current_topic(role, question_number),
        "sources": sources,
    }


def _build_query(role: str, resume_skills: dict, previous_qa: list[dict], question_number: int) -> str:
    parts = []

    skills = resume_skills.get("skills", [])[:5]
    techs = resume_skills.get("technologies", [])[:5]
    domains = resume_skills.get("domains", [])[:3]

    if skills:
        parts.append(" ".join(skills))
    if techs:
        parts.append(" ".join(techs))
    if domains:
        parts.append(" ".join(domains))

    if previous_qa:
        last = previous_qa[-1]
        last_q_words = last.get("question", "")[:100]
        parts.append(last_q_words)

    role_topics = ROLE_TOPICS.get(role, [])
    if role_topics:
        topic_idx = question_number % len(role_topics)
        parts.append(role_topics[topic_idx])

    return " ".join(parts)[:500]
