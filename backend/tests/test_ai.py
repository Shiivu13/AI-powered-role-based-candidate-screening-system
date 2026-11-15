from app.ai.answer_evaluator import evaluate_answer
from app.ai.catalog import ROLES
from app.ai.planner import build_plan
from app.ai.resume_parser import estimate_years, match_skills, parse_resume


def test_skill_matching_is_word_bounded():
    skills = match_skills("Used XGBoost and scikit-learn; built a Java service. Wrote JavaScript too.")
    assert {"XGBoost", "scikit-learn", "Java", "JavaScript"} <= skills.keys()
    assert "R" not in match_skills("Research and Recommendation")


def test_years_from_date_ranges_and_explicit_statement():
    assert estimate_years("5+ years of experience in ML") == 5
    assert estimate_years("EXPERIENCE\nEngineer 2019 - 2022\nAnalyst 2017 - 2019\nEDUCATION") == 5


def test_parse_resume_offline(offline_llm, resume_text):
    profile = parse_resume(resume_text)
    assert profile["name"] == "Priya Sharma"
    assert profile["seniority"] in {"junior", "mid"}
    assert "XGBoost" in profile["technologies"]
    assert profile["extraction"]["mode"] == "heuristic"


def test_parse_resume_merges_llm_output(fake_llm, resume_text):
    profile = parse_resume(resume_text)
    assert profile["extraction"]["mode"] == "llm+heuristic"
    assert "credit risk modelling" in profile["skills"]
    assert profile["projects"][0]["name"] == "Credit scoring"


def test_plan_prioritises_resume_then_probes_gaps(offline_llm, resume_text):
    role = ROLES["ai_ml_engineer"]
    profile = parse_resume(resume_text)
    plan = build_plan(role, profile, resume_text, 6)
    assert len(plan) == 6
    assert plan[0].source == "resume"  # open on the candidate's strongest topic
    sources = {p.source for p in plan}
    assert {"resume", "core"} <= sources
    assert len({p.topic_id for p in plan}) == 6
    ensembles = next((p for p in plan if p.topic_id == "ensembles"), None)
    assert ensembles is not None and ensembles.source == "resume"
    assert any(e in {"xgboost", "random forest", "gradient boosting"} for e in ensembles.evidence)
    for p in plan:
        assert 1 <= p.difficulty <= 3 and p.queries and p.reason


def test_resume_strength_raises_difficulty(offline_llm):
    role = ROLES["ai_ml_engineer"]
    junior = {"seniority": "junior", "skills": [], "technologies": []}
    text = "random forest xgboost boosting gradient boosting bagging random forest"
    plan = build_plan(role, junior, text, 3)
    ens = next(p for p in plan if p.topic_id == "ensembles")
    assert ens.difficulty == 2  # junior base 1, +1 for strong evidence


def test_non_answer_scores_zero(offline_llm):
    result = evaluate_answer(question="q", expected_points=["a"], answer="I don't know", context="", difficulty=1)
    assert result["score"] == 0 and result["missing_points"] == ["a"]


def test_offline_evaluation_rewards_coverage(offline_llm):
    points = [
        "Information gain is the expected reduction in entropy from splitting on an attribute.",
        "Pruning on a validation set reduces overfitting of decision trees.",
    ]
    good = evaluate_answer(
        question="How does ID3 choose attributes and avoid overfitting?",
        expected_points=points,
        answer="ID3 picks the attribute with the highest information gain, i.e. the expected reduction in entropy after the split. "
        "Because full trees overfit, we prune nodes using a separate validation set, keeping only splits that improve validation accuracy.",
        context=" ".join(points),
        difficulty=2,
    )
    weak = evaluate_answer(
        question="How does ID3 choose attributes and avoid overfitting?",
        expected_points=points,
        answer="It uses a tree and some maths to decide things.",
        context=" ".join(points),
        difficulty=2,
    )
    assert good["score"] > weak["score"]
    assert len(good["covered_points"]) >= 1
    assert good["evaluation"]["mode"] == "heuristic"


def test_llm_rubric_drives_the_overall_score(fake_llm, monkeypatch):
    from app.ai import answer_evaluator

    monkeypatch.setattr(fake_llm, "generate_json", lambda system, user, **kw: {
        "rubric": {"correctness": 9, "depth": 6, "application": 4, "communication": 8},
        "score": 2, "verdict": "good", "covered_points": [], "missing_points": [], "misconceptions": [], "feedback": "ok",
    })
    result = answer_evaluator.evaluate_answer(question="q", expected_points=["a"], answer="a real answer here", context="c", difficulty=2)
    # 0.4*9 + 0.25*6 + 0.2*4 + 0.15*8 = 7.1, the model's inconsistent "score": 2 is ignored
    assert result["score"] == 7.1 and result["rubric"]["application"] == 4


def test_llm_hint(fake_llm):
    from app.ai.question_generator import generate_hint

    assert generate_hint(question="q", expected_points=["variance reduction"])["mode"] == "llm"
