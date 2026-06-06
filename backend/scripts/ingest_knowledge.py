"""
Knowledge base ingestion script.
Run directly: python scripts/ingest_knowledge.py
Or triggered automatically on backend startup.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from app.ml.vector_store import add_chunks, get_collection_count

KNOWLEDGE_BASE_DIR = Path(__file__).parent.parent / "knowledge_base"

ROLE_DIR_MAP = {
    "ai_ml": KNOWLEDGE_BASE_DIR / "ai_ml",
    "data_science": KNOWLEDGE_BASE_DIR / "data_science",
    "backend": KNOWLEDGE_BASE_DIR / "backend",
}

CHUNK_SIZE = 600
CHUNK_OVERLAP = 80


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


def load_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_pdf_file(path: Path) -> str:
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(str(path)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        return text
    except Exception as e:
        print(f"  Warning: Could not parse PDF {path.name}: {e}")
        return ""


def ingest_role(role: str, role_dir: Path) -> int:
    if not role_dir.exists():
        print(f"  Directory not found: {role_dir}")
        return 0

    files = list(role_dir.glob("*.txt")) + list(role_dir.glob("*.pdf"))
    if not files:
        print(f"  No files found in {role_dir}")
        return 0

    all_chunks = []
    all_ids = []
    all_metadatas = []

    for f in files:
        print(f"  Processing: {f.name}")
        if f.suffix == ".pdf":
            text = load_pdf_file(f)
        else:
            text = load_text_file(f)

        if not text.strip():
            continue

        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            chunk_id = f"{role}_{f.stem}_{i}_{str(uuid.uuid4())[:8]}"
            all_chunks.append(chunk)
            all_ids.append(chunk_id)
            all_metadatas.append({"source": f.name, "role": role, "chunk_index": i})

    if all_chunks:
        batch_size = 100
        for i in range(0, len(all_chunks), batch_size):
            add_chunks(
                role,
                all_chunks[i:i+batch_size],
                all_ids[i:i+batch_size],
                all_metadatas[i:i+batch_size],
            )
        print(f"  Ingested {len(all_chunks)} chunks for role: {role}")

    return len(all_chunks)


def ingest_all():
    print("Starting knowledge base ingestion...")
    total = 0
    for role, role_dir in ROLE_DIR_MAP.items():
        current_count = get_collection_count(role)
        if current_count > 0:
            print(f"[{role}] Already has {current_count} chunks, skipping (delete chroma_db to re-ingest)")
            total += current_count
            continue
        print(f"[{role}] Ingesting from {role_dir}...")
        count = ingest_role(role, role_dir)
        total += count

    print(f"\nIngestion complete. Total chunks: {total}")
    return total


if __name__ == "__main__":
    ingest_all()
