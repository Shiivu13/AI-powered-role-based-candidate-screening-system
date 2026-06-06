# Deployment Guide (Free Tier)

| Component | Host | Why |
|-----------|------|-----|
| Frontend (Next.js) | **Vercel** | Native Next.js host, generous free tier |
| Backend (FastAPI + RAG) | **Hugging Face Spaces (Docker)** | 16 GB RAM free — handles torch + ChromaDB + books |

## 1. Backend → Hugging Face Spaces
1. Create a new Space → SDK: **Docker** → name it (e.g. `ai-interview-backend`).
2. Push the `backend/` folder to the Space's git repo (it already contains `Dockerfile` + HF `README.md` frontmatter with `app_port: 7860`).
3. In **Settings → Variables and secrets** add:
   - `GEMINI_API_KEY` = your key (as a **secret**)
   - `FRONTEND_URL` = your Vercel URL (add after step 2 below)
4. The build downloads the reference books and bakes the vector store into the image.
   Backend URL will be: `https://<user>-<space>.hf.space`

## 2. Frontend → Vercel
1. Import the GitHub repo → set **Root Directory** = `frontend`.
2. Add env var `NEXT_PUBLIC_API_URL` = the HF Space backend URL.
3. Deploy. Copy the resulting `*.vercel.app` URL.
4. Put that URL into the Space's `FRONTEND_URL` variable (CORS also allows any `*.vercel.app`).

## Notes
- Secrets (`.env`, API keys) are gitignored — set them in each host's dashboard.
- The backend's vector store is rebuilt at image-build time, so no manual ingest is needed in production.
