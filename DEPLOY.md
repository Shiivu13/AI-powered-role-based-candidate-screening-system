# Deployment

Backend on Render, frontend on Vercel. Both have free tiers that are enough for a demo.

## Backend (Render)

1. New → Blueprint → select this repo. `render.yaml` defines the service.
2. Optionally set `GEMINI_API_KEY` in the service's environment. Without it the API runs in offline mode.
3. The build downloads the books and builds the vector store, which takes a few minutes the first time.
   Check `https://<service>.onrender.com/api/health`: every role should show a non-zero chunk count.

The SQLite database lives on the instance's disk, so sessions reset on redeploy. Set `DATABASE_URL` to a hosted Postgres if they need to persist.

## Frontend (Vercel)

1. Import the repo and set **Root Directory** to `frontend`. Vercel detects Vite.
2. Add the environment variable `VITE_API_URL` = the Render URL (no trailing slash).
3. Deploy. `vercel.json` rewrites every path to `index.html` so client-side routes such as `/sessions/...` survive a reload.

The backend accepts any `*.vercel.app` origin through `CORS_ORIGIN_REGEX`. Tighten it to your exact domain if you like.
