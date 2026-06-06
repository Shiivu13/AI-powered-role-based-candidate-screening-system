# Backend for Hugging Face Spaces (Docker SDK) — free tier, 16GB RAM
FROM python:3.11-slim

WORKDIR /app

# Build tools for any native wheels
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only torch first (small), then the rest
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.3.1 --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# App code (knowledge_base .txt files included; book PDFs fetched below)
COPY . .

# Writable caches for HF Spaces (HOME is /app on Spaces)
ENV HF_HOME=/app/.cache \
    TRANSFORMERS_CACHE=/app/.cache \
    CHROMA_DB_PATH=/app/chroma_db \
    DATABASE_URL=sqlite+aiosqlite:///./interview.db

# Bake the vector store into the image so startup is fast (no runtime ingest).
# Resilient: if a book mirror is down, curated .txt notes still get ingested.
RUN python scripts/download_books.py || true \
    && python scripts/ingest_knowledge.py || true

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
