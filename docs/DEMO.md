# Demo video script (about 7 minutes)

Record on the live site (https://ai-powered-role-based-candidate-scr-sage.vercel.app) or locally (`make api`, `make web`). Use `backend/samples/ml_engineer_resume.txt`. Chrome is best, because voice mode uses its speech APIs.

| # | Time | Show | Say (the point to land) |
|---|---|---|---|
| 1 | 0:00 | Landing page, role cards | "Three roles, each with its own knowledge base built from the assignment's books. The chunk counts show what is indexed." |
| 2 | 0:30 | Upload the resume, pick AI/ML Engineer, choose **Practice**, 4 questions | "Practice mode shows feedback after every answer. Assessment mode hides it until the report, and the server enforces that." |
| 3 | 1:00 | Profile & plan screen | "Skills and projects come from the resume. The plan opens on the candidate's strongest topic, then alternates resume claims with core gaps. Each item says why it was chosen and which queries it will run." |
| 4 | 1:45 | Question 1, open **Why this question?** | "Here is the RAG trace: three queries, hybrid dense + BM25 retrieval, the four passages with book, section and page, and which of them the question actually used." |
| 5 | 2:30 | Turn on **Voice mode**; the question is read aloud, then answer by speaking | "Hands-free interview: speech synthesis for questions, speech recognition for answers." |
| 6 | 3:15 | Submit; show the rubric bars and covered/missing points | "Four rubric dimensions, and the overall score is computed from them in code." |
| 7 | 3:45 | Next question: click **Hint**, then answer | "One grounded hint per question, costing 15%. It nudges without giving the answer." |
| 8 | 4:15 | Give a weak or partial answer | "A partial answer triggers a follow-up on exactly what was missed, and difficulty adapts." |
| 9 | 4:45 | Paste an answer copied from the trace snippet | "Integrity signals: pasted answer, verbatim copy from the source. Advisory only, never scored." |
| 10 | 5:15 | Finish → report | "Weighted score, recommendation, topic radar, competency profile, resume claims vs demonstrated knowledge, timeline, integrity, and the full transcript with traces." |
| 11 | 6:00 | **Compare** page | "Recruiter view: candidates for one role side by side." |
| 12 | 6:20 | **Retrieval Lab**: query "information gain entropy", then the benchmark tables | "Dense, BM25 and hybrid side by side. The benchmark is how I chose the settings. My first version had a data leak that made dense look better than it was." |
| 13 | 6:50 | README "Problems I ran into" | "Most of the RAG work was cleaning PDFs. Fixing one hyphenation bug alone improved retrieval measurably." |

Tips:
- For an assessment-mode take, repeat steps 2–6 with **Assessment** selected and show that the network response contains no score.
- Keep the browser zoom at 90% so the trace panel fits on screen.
