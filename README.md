# ScreenRAG

A screening interview that writes its own questions. You upload a resume and pick a role. The system reads the resume, decides which topics to probe, pulls the relevant pages out of that role's textbooks, and asks questions grounded in those pages. Every question can be traced back to the resume line that motivated it and the book page it came from.

**Live demo:** https://ai-powered-role-based-candidate-scr-sage.vercel.app (runs in offline mode; no API key is configured on the demo)

Built for the AI/ML & Backend intern assignment. Stack: FastAPI, SQLAlchemy, ChromaDB, scikit-learn, React + TypeScript, and Gemini (optional).

```
resume ──► profile ──► interview plan ──► retrieval (dense + BM25 → RRF → MMR) ──► grounded question
                                                                                      │
             report ◄── adaptive policy (difficulty, follow-ups) ◄── evaluation ◄── answer (+ integrity signals)
```

## Running it

You need Python 3.11+ and Node 18+.

```bash
make install   # virtualenv, backend + frontend dependencies
make kb        # optional: re-download the books and rebuild the knowledge base (~1 min)
make api       # http://localhost:8000   (API docs at /docs)
make web       # http://localhost:5173
make test      # 42 backend tests + frontend type-check and build
```

A compact, pre-built knowledge base is committed in `backend/kb/` (14 MB, NumPy only), so a fresh clone works without `make kb`. `make kb` rebuilds the full ChromaDB pipeline from the books and re-exports `backend/kb/`.

**Deploying:** push to a Vercel project and it builds the frontend and the API together, with no settings or environment variables needed. See [DEPLOY.md](DEPLOY.md).

The system works with no API key at all. To get fluent LLM-written questions and grading, put a Gemini key in `backend/.env`; the free tier is enough:

```bash
cp backend/.env.example backend/.env    # then set GEMINI_API_KEY
```

Two sample resumes are in `backend/samples/`.

One book, Burkov's *Hundred-Page ML Book*, is hosted on a server whose TLS certificate does not match its domain. The downloader refuses it instead of turning off certificate checks. If you want it, drop the PDF into `backend/data/books/burkov.pdf` and run `make kb` again. The AI/ML role works without it, using Mitchell and *ML for Absolute Beginners*.

## What happens in an interview

1. **Resume → profile.** A skill taxonomy (54 skills with aliases, word-boundary matching) counts how often each skill is mentioned. Experience is estimated from date ranges, and seniority from experience plus title words. With an LLM available, its extraction (projects, headline, skills the taxonomy misses) is merged on top. The taxonomy always runs, because its counts are what the planner relies on.

2. **Profile → plan.** This step is deterministic on purpose: I wanted the direction of the interview to be explainable rather than "the model felt like it".
   - Every topic of the role is scored against the resume.
   - About 60% of the slots go to topics the candidate claims (to verify them), the rest to core topics the resume doesn't show (to probe gaps).
   - Seniority sets the base difficulty; strong evidence on a topic bumps it up a level.
   - The interview opens on the candidate's strongest topic, then alternates between claims and gaps.
   - Every plan item has a written reason and three retrieval queries: the textbook view of the topic, the topic in the candidate's own vocabulary, and a difficulty-specific angle.

3. **Plan → context.** Hybrid retrieval over the role's collection: dense vectors and BM25, fused with reciprocal rank fusion, then MMR for diversity. Chunks already used earlier in the session are excluded, so no two questions are built on the same passage.

4. **Context → question.** The LLM receives the candidate profile, the plan item, the questions asked so far, and four numbered excerpts with book/section/page citations. It must return the question, the points a good answer covers, and which excerpts it used. Without an LLM, an extractive generator picks the most definitional sentences from the excerpts and builds the question around the section's concept and the candidate's skills.

5. **Answer → evaluation.** The answer is graded 0–10 against the expected points *and* the source excerpts, returning covered points, missed points, misconceptions and feedback. Offline, grading uses the semantic and lexical coverage of each expected point.

6. **Adaptation.** A score of 8 or more raises the difficulty of later questions; below 4 lowers it. A partial answer (4–7) gets one follow-up question on what was missed, and the follow-up never quotes the answer.

7. **Report.**
   - Difficulty-weighted overall score and a recommendation.
   - Topic radar and per-topic scores.
   - A score/difficulty timeline.
   - A table of **resume claims vs. what the candidate demonstrated**.
   - Integrity flags.
   - Full transcript with traces; JSON export.

## Things I added beyond the brief

**Retrieval benchmark** (`scripts/benchmark_retrieval.py`, results in [`docs/benchmarks/retrieval.md`](docs/benchmarks/retrieval.md) and in the app's Retrieval Lab). There is no labelled data for these books, so I used their structure:
- the title of a numbered section is the query;
- that section's chunks are the relevant results.

The first version of this benchmark said dense retrieval clearly beat hybrid (hit@4 0.87 vs 0.79 on the AI/ML books). That result was a leak. The embedding model had been fitted on text that included the section headers, so the query words were baked into the vector space. After re-fitting the space on chunk bodies only and dropping headers from the BM25 documents, the picture changed:

| AI/ML Engineer, 150 queries | hit@4 | precision@4 | MRR@10 | redundancy@4 |
|---|---|---|---|---|
| dense (LSA) | 0.620 | **0.315** | 0.501 | 0.490 |
| sparse (BM25) | 0.613 | 0.263 | 0.480 | **0.353** |
| hybrid, BM25 weight 0.5 | **0.647** | 0.302 | 0.520 | 0.450 |
| hybrid + MMR λ=0.9 (shipped) | 0.640 | 0.265 | **0.530** | 0.379 |

No single retriever won on all three knowledge bases: BM25 has the best hit@4 on the Data Science books, dense has the best precision on Bishop. That is the actual argument for hybrid. The benchmark also set three defaults:
- **BM25 at half weight** inside RRF;
- **MMR λ=0.9**: it cuts top-4 redundancy by about 16% for about 12% of precision@4, and λ=0.7 costs too much precision;
- **1000-character chunks**, after an ablation on one fixed query set:

| chunk size | hit@4 | precision@4 | MRR@10 |
|---|---|---|---|
| 500 | 0.673 | 0.245 | 0.454 |
| **1000** | **0.712** | **0.303** | **0.571** |
| 1500 | 0.712 | 0.264 | 0.523 |

**One-click serverless deployment.** The full pipeline (scikit-learn + ChromaDB) is ~300 MB of dependencies, too heavy for a serverless function. So after ingestion the knowledge base is exported to a compact format in `backend/kb/`: float16 chunk embeddings, chunk texts, and the LSA model as a vocabulary plus a 256×20k projection. At runtime only NumPy is needed: a small re-implementation of the TF-IDF transform (checked against scikit-learn in `tests/test_compact.py`) and brute-force cosine search over a few thousand rows. Shrinking the LSA model from 384 dimensions over 60k terms to 256 over 20k cut it from 179 MB to 10 MB with no measurable loss on the benchmark. `frontend/scripts/vercel-build.sh` uses Vercel's Build Output API to ship the Vite site and the FastAPI app as one deployment (a 147 MB Python function), so the browser calls `/api` on the same origin.

**Self-healing sessions on serverless.** On Vercel every function instance has its own SQLite file in `/tmp`, so an interview's next request can land on an instance that has never seen it. In testing against the live deployment the Sessions page came up empty for exactly this reason. Instead of requiring a database, every API response now carries a signed snapshot of the session (HMAC-SHA256), and the browser keeps the latest one. When an instance answers 404, or holds an older copy (detected from a progress version sent in `X-Session-Version`), the client retries the same request with the snapshot attached. A small ASGI middleware restores it and replays the original request **on that same instance**. A separate "restore, then retry" call does not work, because the two calls can hit different instances; a two-instance round-robin test reproduced that failure. With `POSTGRES_URL` or `DATABASE_URL` set, all of this is simply never triggered.

**Retrieval Lab** (`/lab` in the UI). Type a query and see what dense, BM25 and hybrid each return side by side, with ranks and scores, plus the benchmark tables. Useful for checking the retrieval layer directly instead of trusting it.

**Answer integrity signals.** Remote screening invites copy-paste. While the candidate answers, the UI records paste volume, keystrokes, active typing time and how often the tab lost focus. It never records what was typed beyond the answer itself. The backend combines this with how much of the answer appears verbatim in the source passages (6-gram overlap), which is the material a cheating candidate would find. The resulting flags are shown with their evidence: pasted answer, copied from the reference text, implausible typing speed, left the tab. They are **advisory and never change the score**: dictating into a notes app looks like pasting, and a reviewer should judge that, not a threshold. (During testing, the headless browser's simulated typing was flagged at ~860 wpm, as it should be.)

**Voice answers.** A mic button uses the browser's speech recognition with live captions, so a candidate can talk through an answer as in a real interview. Dictated text is counted separately, so it does not trigger the typing-speed flag.

**Answer key hidden from the browser.** The API leaves out the expected points while a question is open. They are only returned after the candidate answers or skips.

**Works offline, degrades gracefully.** Every LLM call goes through one client that retries on rate limits, and every stage has a deterministic fallback. The trace records which path produced each artefact and why it fell back.

## Problems I ran into

PDFs are messy, and most of the RAG work was cleaning:

- **Tables of contents and back-of-book indexes leaked into retrieval.** A query about preprocessing returned the TOC page of the book, because it literally lists every preprocessing heading. I added detectors for dot leaders, "title + page number" runs and comma-separated page lists. Retrieval improved visibly afterwards.
- **Heading detection had false positives.** In Mitchell's exercises, a line like `13.4. Note in many MDPs it is possible…` looks like a numbered section heading. Table rows like `1 San Jose 1015785` do too. Headings now have to be in Title Case or UPPER CASE with no digits in the title.
- **Wrapped chapter titles.** *Intro to ML with Python* puts `CHAPTER 4` on one line and `Representing Data and` / `Engineering Features` on the next two. The chunker now joins title lines that end in a connecting word.
- **"EDUCATION" counted as a domain.** Every resume has that section header, so every candidate looked like they worked in EdTech.
- **The offline follow-up gave the answer away.** The first version quoted the missed reference sentence back to the candidate. It now asks about the missing *concepts* without quoting.
- **Exercise sections** match many queries but explain nothing, so they get a 25% ranking penalty during fusion.
- **Sessions vanished between serverless instances**, and the first fix (restore, then retry) failed too, because the two requests hit different instances. See "self-healing sessions" above.
- **The API had no tables on Vercel.** Serverless runtimes never send the ASGI startup event, so the table creation in the lifespan hook never ran. Tables are now created lazily on the first database access.

## Design decisions, briefly

- **One Chroma collection per role** (named per embedding provider). Retrieval is scoped to the role's books without metadata filters, a role can be re-ingested on its own, and switching embedding models never mixes vectors.
- **LSA as the default embedding.** TF-IDF + truncated SVD fitted on the books themselves: no model download, no key, runs on CPU in seconds. `EMBEDDING_PROVIDER=gemini` or `sentence-transformers` swaps in a neural model.
- **Chunking.** Sections are hard boundaries, chunks are packed sentence by sentence to about 1000 characters with about 200 characters of overlap, and each chunk is embedded with its book and section as a header (the header is not shown to the LLM).
- **Traceability lives in the database.** Each question row stores its plan item, queries, retrieved chunks with their ranks, grounding diagnostics, model and prompt version. Context → question → answer → storage is literally the table structure.
- **Thin HTTP layer.**
  - Routers only parse requests.
  - `services/` owns the session state machine.
  - `ai/` and `rag/` never import FastAPI or SQLAlchemy, so they can be tested without the web layer.
  - Errors share one envelope: `{"error": {"code", "message", "details"}}`.
  - Wrong-state actions return 409.

## Layout

```
backend/app/
  api/            sessions.py (interview lifecycle), catalog.py (roles, health, search, benchmark)
  services/       interview_service.py (state machine + adaptive policy), serializers.py
  ai/             catalog (roles/books/topics), resume_parser, planner, question_generator,
                  answer_evaluator, integrity, report_generator, llm, prompts
  rag/            loaders, chunking, embeddings, vector_store, retriever, ingest, evaluation
backend/kb/       compact NumPy-only knowledge base (committed; used on Vercel and by fresh clones)
backend/scripts/  download_kb, ingest_kb, export_kb, benchmark_retrieval
backend/tests/    42 tests: synthetic mini-textbook + fake LLM, no network or books needed
frontend/scripts/vercel-build.sh   Build Output API bundle: static site + Python function
frontend/src/     pages (Setup, Session, History, Lab), components, state (interview reducer,
                  telemetry, speech)
docs/benchmarks/  retrieval benchmark output
```

## API

| | |
|---|---|
| `POST /api/sessions` | multipart: `role_id`, `resume` file or `resume_text`, optional `candidate_name`, `num_questions` |
| `POST /api/sessions/{id}/questions/next` | next question; returns the open one again if there is one (safe to retry) |
| `POST /api/sessions/{id}/questions/{qid}/answer` | `{text, telemetry?}`; returns the evaluation and integrity signals |
| `POST /api/sessions/{id}/questions/{qid}/skip` | skip a question |
| `POST /api/sessions/{id}/complete` | close the interview and build the report |
| `GET /api/sessions`, `GET/DELETE /api/sessions/{id}`, `GET /api/sessions/{id}/report` | history, details, report |
| `GET /api/roles`, `GET /api/health` | roles with knowledge-base status; providers |
| `POST /api/knowledge/search` | `{role_id, query, mode: hybrid\|dense\|bm25}` |
| `GET /api/knowledge/benchmark` | latest benchmark results |

## Configuration

Everything is set through environment variables; see [`backend/.env.example`](backend/.env.example). The main ones:
- `GEMINI_API_KEY` and `LLM_MODEL`;
- `EMBEDDING_PROVIDER`;
- `CHUNK_SIZE` and `CHUNK_OVERLAP`;
- `RETRIEVAL_TOP_K`, `MMR_LAMBDA` and `BM25_WEIGHT`;
- `DATABASE_URL` (SQLite by default; any SQLAlchemy URL works);
- `MAX_FOLLOW_UPS`.

## What I would do next

- Add a cross-encoder re-ranker over the top 20 fused results; the benchmark is ready to measure it.
- Generate the next question while the candidate is still answering, to hide LLM latency.
- Split recruiter and candidate views and add authentication. Right now one screen shows both the feedback and the integrity flags.
- Add OCR for image-only resumes. They are currently rejected with a clear message.
