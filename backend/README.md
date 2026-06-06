---
title: AI Interview Backend
emoji: 🧠
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# AI Interview System — Backend (FastAPI)

RAG-powered candidate screening backend. Deployed on Hugging Face Spaces (Docker).

## Endpoints
- `POST /api/sessions` — create session (resume upload + role)
- `POST /api/interview/{id}/answer` — submit answer, get adaptively-chosen next question
- `GET /api/interview/{id}/summary` — final analysis + knowledge-gap radar data
- `GET /api/knowledge/status` — vector store status
- `GET /health` — health check

## Configuration (Space secrets / variables)
| Var | Purpose |
|-----|---------|
| `GEMINI_API_KEY` | LLM key (required) — set as a **secret** |
| `LLM_PROVIDER` | `gemini` (default), `openai`, or `anthropic` |
| `FRONTEND_URL` | Deployed frontend origin (for CORS) |

The vector store is baked into the image at build time from the reference books
(see `Dockerfile` → `download_books.py` + `ingest_knowledge.py`).

See the repository root README for full architecture and design notes.
