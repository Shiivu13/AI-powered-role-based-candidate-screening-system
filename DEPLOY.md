# Deployment (Vercel)

The repo deploys to Vercel as a single project: the React site and the FastAPI backend ship together, and the browser calls `/api` on the same domain.

**No settings or environment variables are required.** `vercel.json` overrides the framework preset and the build command, and it works whether the project's Root Directory is the repo root or `frontend`.

## How it works

`frontend/scripts/vercel-build.sh` writes a [Build Output API](https://vercel.com/docs/build-output-api/v3) bundle:

| Output | Contents |
|---|---|
| `static/` | the Vite build |
| `functions/api/index.func` | Python 3.12 function: `backend/app`, the compact knowledge base `backend/kb`, and the dependencies from `backend/requirements-vercel.txt` (147 MB, within Vercel's 250 MB limit) |
| `config.json` | routes `/api/*` to the function, and everything else to `index.html` (client-side routing) |

The function uses the NumPy backend (no scikit-learn or ChromaDB) and writes its SQLite database to `/tmp`.

## Optional settings (Project → Settings → Environment Variables)

- `GEMINI_API_KEY`: switches question generation and grading from offline mode to Gemini.
- `SESSION_SECRET`: a long random string used to sign the session snapshots the browser keeps. Without it a built-in development key is used.
- **Shared database (optional):** each serverless instance keeps its own SQLite file in `/tmp`, and the browser's signed snapshots heal any instance that is missing a session, so interviews work without a database. For server-side history across browsers, add a Postgres database from the Vercel Marketplace (Neon); it sets `POSTGRES_URL`, which the backend picks up automatically.

## Updating the knowledge base

```bash
make kb    # download books -> ingest into ChromaDB -> export backend/kb
git add backend/kb && git commit -m "Rebuild knowledge base" && git push
```

## Local check of the deployment build

```bash
npx vercel build      # produces .vercel/output exactly as the cloud build does
```
