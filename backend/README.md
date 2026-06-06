# AI Interview System — Backend (FastAPI)

RAG-powered candidate screening backend. Deployed on **Render** (free web service) from this repo via `render.yaml`.

## Endpoints
- `POST /api/sessions` — create session (resume upload + role)
- `POST /api/interview/{id}/answer` — submit answer, get adaptively-chosen next question
- `GET /api/interview/{id}/summary` — final analysis + knowledge-gap radar data
- `GET /api/knowledge/status` — vector store status
- `GET /health` — health check

## Configuration (env vars / Render dashboard)
| Var | Purpose |
|-----|---------|
| `GEMINI_API_KEY` | LLM + embeddings key (required) — set as a **secret** |
| `LLM_PROVIDER` | `gemini` (default), `openai`, or `anthropic` |
| `FRONTEND_URL` | Deployed frontend origin (for CORS) |

## Embeddings & vector store
Embeddings use the **Gemini API** (`gemini-embedding-001`) — no local ML model, so the
service stays lightweight and fits Render's free tier. The pre-built `chroma_db/` (grounded
in the reference books) is committed so the service needs no ingest step at deploy.

To rebuild the vector store locally:
```bash
python scripts/download_books.py
rm -rf chroma_db && python scripts/ingest_knowledge.py
```

See the repository root `README.md` for full architecture and design notes.
