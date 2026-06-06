# AI Interview System — PGAGI Assignment

An AI-powered role-based candidate screening system that conducts dynamic technical interviews using Retrieval-Augmented Generation (RAG).

**🚀 Live Demo:** [https://ai-powered-role-based-candidate-scr-sage.vercel.app](https://ai-powered-role-based-candidate-scr-sage.vercel.app)

## ✨ What makes this different

Beyond the baseline (upload → RAG → questions → summary), this system ships three standout capabilities:

### 1. 🔍 Glass-box Interviewer (Explainable RAG)
A live side-panel during the interview that makes the invisible RAG pipeline **visible**. For every question it shows:
- the **retrieval query** constructed from the resume + role + prior answers,
- the **exact book chunks retrieved** with their source (e.g. *Machine Learning — Tom Mitchell*) and a **% similarity match**,
- the **adaptive decision** explaining *why* this question was asked.

This turns the system from a black box into a transparent, auditable interviewer.

### 2. ⚡ Adaptive Difficulty Engine
Every answer is **scored 0–10 against the retrieved book context** (correctness / depth / relevance) by the LLM. That score drives the **next** question in real time:
- strong answers → harder questions / deeper probes,
- weak answers → the engine eases down and probes the revealed gap.

Difficulty reflects the rolling performance with **no lag** — it behaves like a real interviewer reading the room. Inline per-answer feedback is shown to the candidate.

### 3. 🧭 Knowledge-Gap Radar
The final report renders a **radar chart of per-topic mastery** plus ranked strength bars (weakest-first), computed from the live per-answer scores — an at-a-glance map of where the candidate is strong vs needs work.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js 14)                    │
│  Home Page → Upload Resume + Select Role                       │
│  Interview Page → Chat-style Q&A interface                     │
│  Results Page → AI-generated analysis + transcript             │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTP (REST API)
┌──────────────────────▼──────────────────────────────────────────┐
│                      BACKEND (FastAPI)                          │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │ Resume      │  │ RAG Pipeline │  │ Question Generator  │    │
│  │ Parser      │→ │ (ChromaDB +  │→ │ (LLM: Gemini/      │    │
│  │ (pdfplumber)│  │ Embeddings)  │  │  OpenAI/Anthropic) │    │
│  └─────────────┘  └──────────────┘  └────────────────────┘    │
│                                                                 │
│  ┌─────────────────────┐    ┌─────────────────────────────┐   │
│  │ SQLite (Sessions,   │    │ ChromaDB (Vector Store)     │   │
│  │ Questions, Answers, │    │ Embeddings: all-MiniLM-L6   │   │
│  │ Summaries)          │    │ Collections per role        │   │
│  └─────────────────────┘    └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI (Python 3.12) |
| LLM | Google Gemini (`google-genai` SDK, `gemini-3.1-flash-lite` + auto-fallback) / OpenAI / Anthropic |
| Embeddings | `all-MiniLM-L6-v2` via `transformers` (local, free) |
| Vector Store | ChromaDB — local, persistent |
| Database | SQLite + SQLAlchemy (async) |

## Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- A Gemini API key (free at [makersuite.google.com](https://makersuite.google.com/app/apikey))

### 1. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Run backend
uvicorn app.main:app --reload --port 8000
```

The backend will:
- Create SQLite database automatically
- Ingest knowledge base documents on first run (background thread)
- Be available at http://localhost:8000

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend will be at http://localhost:3000

### 3. Knowledge Base (Books)

The RAG knowledge base is grounded in the **assignment-provided reference books** (per Section 9 of the brief):

```
backend/knowledge_base/
├── ai_ml/          ← Machine Learning (Tom Mitchell) + Hundred-Page ML Book (Burkov)  → 432 chunks
├── data_science/   ← Introduction to Machine Learning with Python (Müller & Guido)    → 201 chunks
└── backend/        ← Curated System Design / API / Database notes (no book provided)  → 6 chunks
```

Total: **639 chunks** indexed in ChromaDB.

The book PDFs are copyrighted, so they are **not committed** to the repo. Fetch them
with the helper script, then ingest:
```bash
cd backend
python scripts/download_books.py       # downloads the reference books
python scripts/ingest_knowledge.py     # chunk + embed → ChromaDB
# To force a full rebuild, delete the chroma_db/ folder first
```

Or via API: `POST http://localhost:8000/api/knowledge/ingest`

The ingestion pipeline handles both `.pdf` (via pdfplumber) and `.txt` files automatically.

## Key Design Decisions

### RAG Pipeline
- **Chunking**: 600-word chunks with 80-word overlap — preserves semantic context across boundaries
- **Embeddings**: `all-MiniLM-L6-v2` — 80MB, fast, no API cost, strong performance
- **Vector DB**: ChromaDB with cosine similarity — persistent, no infrastructure needed
- **Collections**: one per role (`ai_ml`, `data_science`, `backend`) for targeted retrieval
- **Query construction**: combines resume skills + role topic + previous Q&A context

### Question Generation
- **Adaptive difficulty**: scales with candidate experience years and interview progress
- **Question types**: conceptual → applied → problem-solving → experiential (rotated)
- **Context injection**: full Q&A history in prompt enables follow-up and topic pivots
- **RAG grounding**: questions reference retrieved textbook content, not just model knowledge

### Session Management
- Sessions are stateful (stored in SQLite with full Q&A history)
- Each answer submission triggers: store answer → build context → query RAG → generate next Q
- Sessions auto-complete after MAX_QUESTIONS (default: 7)

### Resume Utilisation
- LLM extracts structured skills/technologies/domains from raw resume text
- Extracted skills directly influence: RAG query construction, question difficulty, topic selection
- Resume text is preserved for full context

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions` | Create session (upload resume + role) |
| GET | `/api/sessions/{id}` | Get session details |
| POST | `/api/interview/{id}/answer` | Submit answer, get next question |
| GET | `/api/interview/{id}/summary` | Get final analysis |
| POST | `/api/interview/{id}/complete` | Force end session |
| GET | `/api/knowledge/status` | Check knowledge base |
| POST | `/api/knowledge/ingest` | Trigger re-ingestion |
| GET | `/health` | Health check |

Interactive docs: http://localhost:8000/docs

## System Flow

```
1. User uploads resume (PDF/TXT) + selects role
2. Backend extracts skills via LLM (structured JSON)
3. RAG query built from skills + role topic
4. ChromaDB retrieves top-5 relevant chunks
5. LLM generates contextual question using chunks + resume
6. User answers → stored in SQLite
7. Steps 3-6 repeat (adapting to previous answers)
8. After 7 questions → LLM generates full analysis
9. Summary displayed with score, recommendation, transcript
```
