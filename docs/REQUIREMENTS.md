# Requirements coverage

Every requirement in the assignment brief, where it is implemented, and how it is verified. "Tests" refers to `backend/tests/` (56 tests, `make test`).

## 3. Expected system flow

| Requirement | Implementation | Verified by |
|---|---|---|
| Upload resume (PDF or text) | `frontend/src/pages/SetupPage.tsx` (drag-and-drop or paste); `backend/app/ai/resume_parser.py::extract_resume_text`. Scanned PDFs, wrong types, files over 4 MB and too-short text are rejected with clear errors | `test_create_session_validation` |
| Select target role | Role cards with books, chunk counts and readiness, and a % fit computed from the resume (best fit pre-selected); or a custom role built from a pasted job description | `test_health_and_roles`, `test_resume_fit_recommends_a_role`, `test_job_description_builds_a_custom_role`, `test_interview_for_a_custom_role` |
| Parse resume; extract skills, technologies, domain exposure | Taxonomy matcher (54 skills, word-boundary aliases, mention counts), date-range experience estimate, seniority; LLM extraction (projects, headline, extra skills) merged on top | `test_skill_matching_is_word_bounded`, `test_years_*`, `test_parse_resume_offline`, `test_parse_resume_merges_llm_output` |
| Context construction: meaningful queries, topics to evaluate | `backend/app/ai/planner.py`: per-topic resume affinity, resume-anchored vs core-gap slots, 3 queries per topic (textbook view, candidate vocabulary, difficulty angle) | `test_plan_prioritises_resume_then_probes_gaps` |
| Query a role-specific knowledge base; most relevant chunks; grounded context | `backend/app/rag/retriever.py`: dense + BM25, RRF, MMR, session de-duplication, grounding diagnostics stored per question | `test_hybrid_retrieval_is_relevant_and_traceable`, `test_retrieval_excludes_used_chunks`, retrieval benchmark |
| Generate questions from retrieved context; relevant to role, influenced by background, conceptual/applied | `backend/app/ai/question_generator.py` + `prompts.py`: profile, plan item, style (conceptual / applied / scenario / derivation), numbered sources; returns expected points and source ids | `test_llm_path_adaptivity_and_follow_up`, live demo |
| Candidate answers in the UI; session continuity | `SessionPage.tsx` + `useInterview.ts` reducer; sessions resume after reload; self-healing snapshots keep sessions alive across serverless instances | `test_full_interview_lifecycle_offline`, `test_session_restores_*`, two-instance round-robin browser test |
| Questions adapt to previous responses (optional) | Difficulty raised at score ≥ 8 and lowered below 4; follow-up on partial answers (4 to 7) | `test_llm_path_adaptivity_and_follow_up`, `test_resume_strength_raises_difficulty` |
| Store responses; structured record of questions and answers | `models.py`: `interview_sessions` → `questions` (with trace) → `answers` (with evaluation) → `reports` | lifecycle tests |
| Structured summary and insights at the end | `report_generator.py` + `ReportView.tsx`: weighted score, recommendation, topic radar, competency profile, resume claims vs demonstrated knowledge, score/difficulty timeline, integrity summary, debrief, full transcript, JSON export | `test_full_interview_lifecycle_offline`, `test_hint_is_grounded_and_costs_points` |

## 4. System architecture

| Requirement | Implementation |
|---|---|
| Frontend in React or Next.js: upload, role selection, interview flow, results | React 18 + TypeScript + Vite (`frontend/`): Setup, Profile & plan, Interview, Report, plus Sessions, Compare and Retrieval Lab pages |
| Backend in Python (FastAPI/Flask): business logic, sessions, AI pipeline, storage | FastAPI (`backend/app/`): `api/` (HTTP), `services/` (lifecycle, adaptive policy), `ai/` (pipeline), `rag/` (knowledge layer) |
| A database for persistence: sessions, Q&A, generated outputs/reports | SQLAlchemy 2.0; SQLite by default, Postgres through `DATABASE_URL` / `POSTGRES_URL` |
| Modular code, separation of concerns | `ai/` and `rag/` never import FastAPI or SQLAlchemy; routers only parse requests |
| Configuration through environment variables | `backend/app/config.py` (pydantic-settings); every option is listed in `backend/.env.example` |

## 5. Backend and API design

| Requirement | Implementation |
|---|---|
| Separation of responsibilities, logical request flow | One session resource with explicit lifecycle actions: create → next question → answer / skip / hint → complete → report |
| Stages of the interview lifecycle | States `ready → in_progress → completed`; wrong-state actions return `409 invalid_state` (`test_full_interview_lifecycle_offline`) |
| Robust error handling and validation | One error envelope `{"error": {code, message, details}}`; 422/404/409/503 codes; request validation for files, sizes, roles, modes and answer length |
| Maintainable, scalable structure | Stateless API instances (state lives in the DB or the browser-held encrypted snapshot), so the same code runs locally and on serverless |

## 6/7. AI/ML requirements (RAG)

| Requirement | Implementation | Evidence |
|---|---|---|
| 7.1 Load and process role-specific documents | `rag/loaders.py`: ligatures, dehyphenation, running headers, TOC/index/reference-page detection | "Problems I ran into" in the README |
| 7.1 Chunking strategy | `rag/chunking.py`: section boundaries, ~1000-char sentence packing, ~200-char overlap, contextual headers | Chunk-size ablation (500/1000/1500) in `docs/benchmarks/retrieval.md` |
| 7.1 Embeddings | LSA fitted on the corpus (default, offline); Gemini or sentence-transformers pluggable | `test_numpy_lsa_matches_sklearn` |
| 7.1 Vector database | ChromaDB, one persistent collection per role (ingestion and local runs); on serverless, a NumPy export of the same vectors (`rag/compact.py`) | `test_numpy_store_ranks_like_chroma` |
| 7.1 Context preservation and retrieval efficiency | Section-scoped chunks with overlap; per-role collections; sub-millisecond brute-force search on the compact store | Benchmark |
| 7.2 Queries built from resume content and role | Planner queries mix textbook vocabulary with the candidate's matched skills | `trace.retrieval.queries` on every question |
| 7.2 Retrieved content useful downstream | Hybrid + MMR; exercise and reading-list sections down-weighted; grounding diagnostics | Retrieval benchmark (hit@4, MRR, nDCG, redundancy) |
| 7.3 Questions from retrieved context; not generic; depth, relevance, context awareness | Prompt forbids "What is X?" and questions unanswerable from the sources; previous questions passed to avoid repeats; style per slot | Live demo questions |
| 7.4 Resume drives topic selection, difficulty, direction | Affinity-based topics; seniority + evidence difficulty; opens on the strongest topic, then alternates claims and gaps | `test_plan_*`, `test_resume_strength_raises_difficulty` |
| 7.5 Context → Question → Answer → Storage; traceability | Each question stores plan item, queries, ranked chunks with citations, diagnostics, model and prompt version; shown in the UI as "Why this question?" | `test_full_interview_lifecycle_offline` |

## 7 (frontend expectations)

| Requirement | Implementation |
|---|---|
| Integration with backend services | Typed API client (`frontend/src/api/`) with error envelope handling and self-healing retries |
| Smooth interaction flow; state across the interview | Stepper (Setup → Profile & plan → Interview → Report); reducer state machine; resume after reload |
| Stages clearly visible | Stepper, progress bar with difficulty indicator, transcript sidebar, plan sidebar |

## 8. Creativity and extensions

Resume-to-role fit and custom roles from job descriptions · retrieval benchmark and Retrieval Lab · rubric scoring with competency profile · grounded hints with penalty · practice vs assessment mode (enforced server-side) · voice interview mode (questions read aloud, spoken answers) · answer integrity signals · candidate comparison view · encrypted self-healing sessions · one-deployment Vercel setup with no configuration needed · offline mode with graceful LLM fallback.

## 9. Knowledge base resources

| Book | Role | Status |
|---|---|---|
| Machine Learning (Mitchell) | AI / ML Engineer | Ingested |
| The Hundred-Page ML Book (Burkov) | AI / ML Engineer | **Not ingested.** The provided host serves a TLS certificate for a different domain (`cluster121.hosting.ovh.net`) and the downloader does not disable verification. Drop the PDF into `backend/data/books/burkov.pdf` and run `make kb` |
| ML for Absolute Beginners | AI / ML Engineer | Ingested |
| Introduction to ML with Python | Data Scientist | Ingested |
| Master ML Algorithms (Brownlee) | Data Scientist | Ingested |
| Pattern Recognition and ML (Bishop) | ML Research | Ingested |
| AI, ML & Deep Learning | ML Research | Ingested |

Questions are generated only from these books' retrieved passages, not from web queries.

## 10. Deliverables

| Deliverable | Where |
|---|---|
| Clean, structured codebase | This repository |
| README: setup, architecture, key design decisions | [README.md](../README.md), plus [DEPLOY.md](../DEPLOY.md) |
| Demo video | To be recorded by the author; a scene-by-scene script is in [DEMO.md](DEMO.md) |
