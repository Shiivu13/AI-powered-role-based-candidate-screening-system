# ScreenRAG: project report

AI/ML and Backend Engineering Intern Assignment
Live demo: https://ai-powered-role-based-candidate-scr-sage.vercel.app
Code: https://github.com/Shiivu13/ai-powered-role-based-candidate-screening-system

## What I built

ScreenRAG runs a technical screening interview whose questions come from three inputs: the candidate's resume, the role they apply for, and the reference textbooks for that role. Nothing is drawn from a fixed question bank. Each question is generated from passages retrieved from the books for this particular candidate, and the interface can show which resume skills chose the topic, which queries were run, and which book pages the question came from.

The backend is FastAPI with SQLAlchemy. The knowledge base is ChromaDB, and the frontend is React with TypeScript. Gemini writes the questions and grades the answers when an API key is set. Without a key, every stage falls back to a deterministic version, so the whole system still runs offline.

## How an interview works

A recruiter or candidate uploads a resume (PDF or text). The system scores it against the three roles straight away and pre-selects the best fit; on the sample ML engineer resume the fits were 64%, 57% and 36%. You can also skip the fixed roles and paste a job description. The system then pulls the topics the JD asks for and picks the knowledge bases that cover them. For a fraud-detection JD it chose seven topics, including model evaluation, ensemble methods and decision trees, and combined the Data Science and AI/ML books.

The resume parser counts skills with a 54-entry taxonomy and estimates experience from date ranges. Gemini then adds projects and anything the taxonomy missed. From this profile, the planner decides what to ask before any question is written. About 60% of the slots go to topics the candidate claims, so those claims get checked. The rest go to core topics for the role that the resume does not show. Seniority sets the starting difficulty, and topics with strong resume evidence start one level higher. I kept the planner deterministic so the direction of an interview can always be explained.

Each question runs three retrieval queries. One uses the textbook's wording for the topic, one uses the candidate's own skills, and one targets the difficulty level. The answer is graded on four rubric dimensions: correctness, depth, application and communication. The overall score is computed in code from the rubric (weights 0.4, 0.25, 0.2 and 0.15), so it can never disagree with the breakdown. A score of 8 or more raises the difficulty of later questions, and a score below 4 lowers it. A partial answer gets one follow-up on whatever was missed.

The final report has a weighted score, a recommendation, a topic radar, the competency profile from the rubric, and a table of resume claims against what the candidate actually showed. It also includes integrity flags and the full transcript with each question's sources.

## The retrieval pipeline and why it looks the way it does

Six of the seven books in the brief are ingested, about 5,100 chunks across three role collections. The seventh, Burkov's Hundred-Page ML Book, sits on a server whose TLS certificate is issued for a different domain. I did not want the downloader to turn off certificate checks, so the README explains how to add that PDF by hand.

Most of the work on this part went into cleaning the PDFs. Tables of contents and back-of-book indexes kept coming back as top results, because they list every heading word in a few lines. Mitchell's exercise lines such as "13.4. Note in many MDPs..." were detected as section headings. One chapter title in the Müller and Guido book wraps over three lines. Over 1,300 words were split across line breaks ("vari- ations") because my dehyphenation ran before whitespace cleanup. Fixing that one ordering bug raised hybrid hit@4 on the AI/ML books from 0.647 to 0.667.

The chunker treats section headings as hard boundaries. It packs whole sentences up to about 1,000 characters with about 200 characters of overlap, and embeds each chunk with its book and section name in front. Retrieval combines dense LSA vectors with BM25 through reciprocal rank fusion, then uses MMR to avoid handing the generator four copies of the same paragraph. Chunks already used in the session are excluded, so every question draws on new material.

I wanted to measure these choices instead of asserting them, but the books have no relevance labels. So I used their structure: a numbered section title is the query, and that section's chunks are the relevant results. The first version of this benchmark said dense retrieval clearly beat hybrid, with a hit@4 of 0.87 against 0.79. That turned out to be a leak. The embedding model had been fitted on text that included the section headers, so the query words were already in the vector space. After refitting on chunk bodies only, the result was:

| AI/ML books, 150 queries | hit@4 | precision@4 | MRR@10 | redundancy@4 |
|---|---|---|---|---|
| dense (LSA) | 0.640 | 0.325 | 0.510 | 0.480 |
| BM25 | 0.627 | 0.265 | 0.474 | 0.349 |
| hybrid, BM25 weight 0.5 | 0.667 | 0.308 | 0.534 | 0.444 |
| hybrid + MMR 0.9 (used) | 0.667 | 0.263 | 0.533 | 0.381 |

No single retriever won on all three knowledge bases, and that is the actual case for hybrid. MMR at 0.9 lowers redundancy by about 14% and costs about 15% of precision@4. I accepted that trade because four related passages make better question material than four overlapping ones. In a chunk-size test on one fixed query set, 1,000 characters scored best on precision and MRR (hit@4 0.712, MRR 0.571), ahead of 500 (0.673, 0.453) and 1,500 (0.712, 0.523).

## Deployment

I wanted the live demo to work on Vercel without anyone having to set it up, and that turned out to be most of the engineering in the second half.

ChromaDB, scikit-learn, SciPy and NumPy together take about 400 MB installed, which is too much for a serverless function. After ingestion I export the knowledge base to a compact form: float16 embeddings, the chunk texts, and the LSA model stored as a vocabulary plus a 256 by 20,000 projection. At runtime this needs only NumPy and a small reimplementation of the TF-IDF transform, which a test checks against scikit-learn. Shrinking the model from 384 dimensions over 60,000 terms to 256 over 20,000 took it from 179 MB to 10 MB with no measurable loss on the benchmark. A build script uses Vercel's Build Output API to ship the site and the API as one deployment, with a 147 MB Python function under `/api`.

Running the full flow against the live site surfaced three problems. The Sessions page was empty, because each serverless instance keeps its own SQLite file and a later request can reach an instance that has never seen the session. My first fix (restore the session, then retry the request) also failed, since the two calls could reach different instances, and a two-instance round-robin test showed exactly that. Now every response carries an encrypted snapshot of the session, the browser keeps the latest one, and if an instance does not know the session, the client resends the same request with the snapshot attached. A middleware restores the session and replays the request on that same instance. The second problem was that the database tables were never created on Vercel, because serverless runtimes do not send the ASGI startup event. The third was that once a Gemini key was added, every LLM call still fell back to offline mode. The SDK was defaulting to the v1 API, which rejects system instructions.

## Extras

Practice mode shows the score, the rubric and the sources after every answer. Assessment mode is meant for real screening: the server withholds scores, feedback, answer keys and sources until the interview ends, so the browser's network tab holds nothing either. The session snapshots are encrypted for the same reason.

A stuck candidate can ask for one hint per question. The hint is generated from that question's expected points without stating them, and costs 15% of the question's score.

Voice mode reads each question aloud and then opens the microphone, so a whole interview can be done hands-free.

While a candidate answers, the page records paste volume, keystrokes, typing time and tab switches. The server also checks how much of the answer matches the source passages word for word. These signals are shown to the reviewer as advisory flags and never change the score, because there are innocent explanations for each of them. In testing, the headless browser's simulated typing was flagged at about 860 words per minute.

A compare page ranks every completed interview for a role, with rubric averages and a heatmap of topic scores. A retrieval lab lets you run one query through dense, BM25 and hybrid side by side.

## Testing

There are 56 backend tests. They build a small synthetic textbook and replace Gemini with a deterministic fake, so they need no network, books or API key. They cover chunking, cleaning, retrieval, planning, grading, the full interview lifecycle, assessment mode, hints, snapshot restore, custom roles and the compact knowledge base. I also ran the complete interview in a browser with Playwright, locally and against the live site, after each major change.

## Limits and next steps

The offline question generator is grounded in the books but follows a few phrasing patterns; with a Gemini key the questions read much better. LSA handles paraphrases less well than a neural embedding model, and the next thing I would try is a cross-encoder re-ranker over the top fused results, measured with the same benchmark. Recruiter and candidate views share one screen today and should be separated behind login. Scanned resumes are rejected with a clear message instead of being run through OCR.
