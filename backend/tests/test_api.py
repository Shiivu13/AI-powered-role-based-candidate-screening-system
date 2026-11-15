import pytest


def _create(client, resume_text, **extra):
    data = {"role_id": "ai_ml_engineer", "num_questions": "3", "candidate_name": "", **extra}
    files = {"resume": ("resume.txt", resume_text.encode(), "text/plain")}
    return client.post("/api/sessions", data=data, files=files)


def test_health_and_roles(client):
    health = client.get("/api/health").json()
    assert health["status"] == "ok" and health["embedding_provider"] == "lsa"
    roles = client.get("/api/roles").json()
    assert {r["id"] for r in roles} == {"ai_ml_engineer", "data_scientist", "ml_research"}
    assert all(r["topics"] and r["books"] for r in roles)


@pytest.mark.parametrize(
    "data,files,code",
    [
        ({"role_id": "ai_ml_engineer"}, None, "validation_failed"),  # no resume
        ({"role_id": "nope", "resume_text": "x" * 200}, None, "validation_failed"),  # bad role
        ({"role_id": "ai_ml_engineer", "resume_text": "too short"}, None, "validation_failed"),
        ({"role_id": "ai_ml_engineer", "resume_text": "x" * 200, "num_questions": "50"}, None, "validation_failed"),
        ({"role_id": "ai_ml_engineer"}, {"resume": ("cv.docx", b"PK..", "application/octet-stream")}, "validation_failed"),
    ],
)
def test_create_session_validation(client, data, files, code):
    response = client.post("/api/sessions", data=data, files=files)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code


def test_full_interview_lifecycle_offline(client, offline_llm, resume_text):
    created = _create(client, resume_text)
    assert created.status_code == 201
    session = created.json()
    sid = session["id"]
    assert session["status"] == "ready"
    assert session["candidate_name"] == "Priya Sharma"  # taken from resume
    assert len(session["plan"]) == 3

    # report not available yet
    assert client.get(f"/api/sessions/{sid}/report").status_code == 409

    first = client.post(f"/api/sessions/{sid}/questions/next").json()
    q = first["question"]
    assert not first["done"] and q["expected_points"] is None  # answer key hidden
    trace = q["trace"]
    assert trace["retrieval"]["chunks"] and trace["generation"]["mode"] == "heuristic"
    assert trace["plan_item"]["topic_id"] == q["topic_id"]

    # idempotent while open
    again = client.post(f"/api/sessions/{sid}/questions/next").json()
    assert again["question"]["id"] == q["id"]

    answered = client.post(
        f"/api/sessions/{sid}/questions/{q['id']}/answer",
        json={"text": "Gradient boosting fits each new tree to the negative gradient of the loss; bagging averages bootstrap models to reduce variance."},
    )
    assert answered.status_code == 200
    body = answered.json()
    assert body["question"]["status"] == "answered"
    assert body["question"]["expected_points"]  # revealed after answering
    assert 0 <= body["question"]["answer"]["score"] <= 10

    # cannot answer twice
    dup = client.post(f"/api/sessions/{sid}/questions/{q['id']}/answer", json={"text": "again"})
    assert dup.status_code == 409

    # skip the next one, then walk the rest of the plan
    nxt = client.post(f"/api/sessions/{sid}/questions/next").json()["question"]
    client.post(f"/api/sessions/{sid}/questions/{nxt['id']}/skip")
    for _ in range(6):
        step = client.post(f"/api/sessions/{sid}/questions/next").json()
        if step["done"]:
            break
        client.post(f"/api/sessions/{sid}/questions/{step['question']['id']}/answer", json={"text": "Cross validation splits data into k folds."})
    assert step["done"]

    # every primary question was grounded in different chunks
    detail = client.get(f"/api/sessions/{sid}").json()
    primaries = [x for x in detail["questions"] if x["kind"] == "primary"]
    chunk_sets = [{c["chunk_id"] for c in x["trace"]["retrieval"]["chunks"]} for x in primaries]
    assert all(not (a & b) for i, a in enumerate(chunk_sets) for b in chunk_sets[i + 1 :])

    report = client.post(f"/api/sessions/{sid}/complete").json()["report"]
    assert report["recommendation"]["code"] in {"strong_yes", "yes", "borderline", "no"}
    assert report["insights"]["skipped"] == 1
    assert report["topic_breakdown"]
    assert client.get(f"/api/sessions/{sid}").json()["status"] == "completed"
    assert client.post(f"/api/sessions/{sid}/questions/next").status_code == 409

    listing = client.get("/api/sessions").json()
    assert any(s["id"] == sid and s["overall_score"] is not None for s in listing)


def test_llm_path_adaptivity_and_follow_up(client, fake_llm, resume_text):
    sid = _create(client, resume_text, num_questions="3").json()["id"]
    q1 = client.post(f"/api/sessions/{sid}/questions/next").json()["question"]
    assert q1["trace"]["generation"]["mode"] == "llm"
    used = [c for c in q1["trace"]["retrieval"]["chunks"] if c["used_by_question"]]
    assert used, "source ids should map to retrieved chunks"

    # FakeLLM grades 8.5 -> difficulty goes up
    r1 = client.post(f"/api/sessions/{sid}/questions/{q1['id']}/answer", json={"text": "a strong answer"}).json()
    assert r1["progress"]["current_difficulty_offset"] == 1

    q2 = client.post(f"/api/sessions/{sid}/questions/next").json()["question"]
    assert q2["kind"] == "primary"
    assert "raise the bar" in q2["trace"]["adaptive_note"]
    # FakeLLM grades 5.0 -> partial answer triggers a follow-up
    client.post(f"/api/sessions/{sid}/questions/{q2['id']}/answer", json={"text": "a partial answer"})
    q3 = client.post(f"/api/sessions/{sid}/questions/next").json()["question"]
    assert q3["kind"] == "follow_up" and q3["parent_question_id"] == q2["id"]
    assert q3["topic_id"] == q2["topic_id"]

    report = client.post(f"/api/sessions/{sid}/complete").json()["report"]
    assert report["narrative"]["mode"] == "llm"


def test_delete_and_missing_session(client, offline_llm, resume_text):
    sid = _create(client, resume_text).json()["id"]
    assert client.delete(f"/api/sessions/{sid}").status_code == 204
    missing = client.get(f"/api/sessions/{sid}")
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "not_found"


def test_complete_requires_a_question(client, offline_llm, resume_text):
    sid = _create(client, resume_text).json()["id"]
    response = client.post(f"/api/sessions/{sid}/complete")
    assert response.status_code == 409


def test_answer_telemetry_produces_integrity_signals(client, offline_llm, resume_text):
    sid = _create(client, resume_text).json()["id"]
    q = client.post(f"/api/sessions/{sid}/questions/next").json()["question"]
    copied = q["trace"]["retrieval"]["chunks"][0]["snippet"][:600]
    body = client.post(
        f"/api/sessions/{sid}/questions/{q['id']}/answer",
        json={"text": copied, "telemetry": {"pasted_chars": len(copied), "paste_events": 1, "focus_losses": 3}},
    ).json()
    integrity = body["question"]["answer"]["integrity"]
    assert integrity["level"] == "high"
    report = client.post(f"/api/sessions/{sid}/complete").json()["report"]
    assert report["insights"]["integrity"]["flagged_answers"][0]["position"] == q["position"]


def test_knowledge_search(client):
    result = client.post("/api/knowledge/search", json={"role_id": "data_scientist", "query": "one-hot encoding categorical"}).json()
    assert result["chunks"] and "one-hot" in result["chunks"][0]["snippet"].lower()
    dense = client.post("/api/knowledge/search", json={"role_id": "data_scientist", "query": "scaling", "mode": "dense"}).json()
    assert dense["mode"] == "dense"
    bad = client.post("/api/knowledge/search", json={"role_id": "data_scientist", "query": "scaling", "mode": "magic"})
    assert bad.status_code == 422


def test_benchmark_endpoint(client):
    response = client.get("/api/knowledge/benchmark")
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        assert "roles" in response.json()


def test_session_restores_from_encrypted_snapshot(client, offline_llm, resume_text):
    from app.db import SessionLocal
    from app.models import InterviewSession

    sid = _create(client, resume_text).json()["id"]
    q = client.post(f"/api/sessions/{sid}/questions/next").json()["question"]
    client.post(f"/api/sessions/{sid}/questions/{q['id']}/answer", json={"text": "Bagging averages bootstrap models."})
    snap = client.get(f"/api/sessions/{sid}/snapshot").json()

    # Simulate a serverless instance that has never seen this session.
    with SessionLocal() as db:
        db.delete(db.get(InterviewSession, sid))
        db.commit()
    assert client.get(f"/api/sessions/{sid}").status_code == 404

    restored = client.post("/api/sessions/restore", json=snap)
    assert restored.status_code == 200
    detail = restored.json()
    assert detail["id"] == sid and detail["questions"][0]["answer"]["score"] is not None
    # interview continues normally after the restore
    assert client.post(f"/api/sessions/{sid}/questions/next").status_code == 200
    # restoring an older snapshot never rolls back newer progress
    again = client.post("/api/sessions/restore", json=snap).json()
    assert len(again["questions"]) == 2

    tampered = dict(snap, body=snap["body"][:-4] + "AAAA")
    assert client.post("/api/sessions/restore", json=tampered).status_code == 422


def test_stale_copy_is_reported_as_missing(client, offline_llm, resume_text):
    sid = _create(client, resume_text).json()["id"]
    snap = client.get(f"/api/sessions/{sid}/snapshot").json()
    assert client.get(f"/api/sessions/{sid}", headers={"X-Session-Version": str(snap["version"])}).status_code == 200
    stale = client.get(f"/api/sessions/{sid}", headers={"X-Session-Version": str(snap["version"] + 5)})
    assert stale.status_code == 404 and stale.json()["error"]["details"]["stale"] is True


def test_restore_and_replay_in_one_request(client, offline_llm, resume_text):
    import base64
    import json

    from app.db import SessionLocal
    from app.models import InterviewSession

    sid = _create(client, resume_text).json()["id"]
    q = client.post(f"/api/sessions/{sid}/questions/next").json()["question"]
    snap = client.get(f"/api/sessions/{sid}/snapshot").json()
    with SessionLocal() as db:  # this "instance" forgets the session
        db.delete(db.get(InterviewSession, sid))
        db.commit()

    body = json.dumps({"text": "Bagging averages models trained on bootstrap samples."}).encode()
    response = client.post(
        f"/api/sessions/{sid}/questions/{q['id']}/answer",
        headers={"X-Session-Restore": "1", "X-Original-Method": "POST"},
        json={"snapshot": snap, "body": base64.b64encode(body).decode(), "content_type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["question"]["status"] == "answered"

    # replaying a GET works the same way
    with SessionLocal() as db:
        db.delete(db.get(InterviewSession, sid))
        db.commit()
    got = client.post(f"/api/sessions/{sid}", headers={"X-Session-Restore": "1", "X-Original-Method": "GET"},
                      json={"snapshot": response.json()["snapshot"], "body": None})
    assert got.status_code == 200 and got.json()["id"] == sid

    bad = client.post(f"/api/sessions/{sid}", headers={"X-Session-Restore": "1", "X-Original-Method": "GET"},
                      json={"snapshot": dict(snap, body=snap["body"][:-8] + "AAAAAAAA"), "body": None})
    assert bad.status_code == 422


def test_assessment_mode_hides_results_until_completion(client, offline_llm, resume_text):
    sid = _create(client, resume_text, mode="assessment").json()["id"]
    q = client.post(f"/api/sessions/{sid}/questions/next").json()["question"]
    assert q["trace"] is None and q["expected_points"] is None  # no source passages to peek at
    body = client.post(f"/api/sessions/{sid}/questions/{q['id']}/answer", json={"text": "Bagging averages bootstrap models to cut variance."}).json()
    answer = body["question"]["answer"]
    assert answer["hidden"] is True and answer["score"] is None and answer.get("feedback") is None
    assert body["question"]["expected_points"] is None
    detail = client.get(f"/api/sessions/{sid}").json()
    assert detail["mode"] == "assessment" and detail["questions"][0]["answer"]["score"] is None

    client.post(f"/api/sessions/{sid}/complete")
    after = client.get(f"/api/sessions/{sid}").json()["questions"][0]
    assert after["answer"]["score"] is not None and after["expected_points"] and after["trace"]


def test_hint_is_grounded_and_costs_points(client, offline_llm, resume_text):
    sid = _create(client, resume_text).json()["id"]
    q = client.post(f"/api/sessions/{sid}/questions/next").json()["question"]
    hint = client.post(f"/api/sessions/{sid}/questions/{q['id']}/hint").json()
    assert hint["hint"] and hint["penalty"] == 0.15
    again = client.post(f"/api/sessions/{sid}/questions/{q['id']}/hint").json()
    assert again["hint"] == hint["hint"]  # one hint per question, stable
    answer = client.post(f"/api/sessions/{sid}/questions/{q['id']}/answer",
                         json={"text": "Gradient boosting fits each new tree to the negative gradient of the loss, for example on residuals."}).json()
    assert answer["question"]["answer"]["hint_penalty"] == 0.15
    assert answer["question"]["hint"] == hint["hint"]
    report = client.post(f"/api/sessions/{sid}/complete").json()["report"]
    assert report["insights"]["hints_used"] == 1
    assert set(report["competencies"]) == {"correctness", "depth", "application", "communication"}


def test_invalid_mode_rejected(client, resume_text):
    assert _create(client, resume_text, mode="exam").status_code == 422
