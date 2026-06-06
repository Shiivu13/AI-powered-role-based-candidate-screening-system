"""
Downloads the assignment-provided reference books into the knowledge base.

The book PDFs are copyrighted and therefore NOT committed to the repository.
This script fetches freely-available mirrors so the RAG pipeline can be
grounded in the actual reference texts (see assignment Section 9).

Usage:
    python scripts/download_books.py
    python scripts/ingest_knowledge.py     # then ingest

Backend role has no assignment-provided book, so curated .txt notes are used.
"""
import sys
from pathlib import Path
from urllib.request import urlopen, Request

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

KB = Path(__file__).parent.parent / "knowledge_base"

BOOKS = [
    {
        "role": "ai_ml",
        "filename": "tom_mitchell_ml.pdf",
        "title": "Machine Learning — Tom Mitchell",
        "url": "https://github.com/Algorithm-Master/Books/raw/master/McGrawHill%20-%20Machine%20Learning%20-Tom%20Mitchell.pdf",
    },
    {
        "role": "ai_ml",
        "filename": "burkov_hundred_page_ml.pdf",
        "title": "The Hundred-Page Machine Learning Book — Andriy Burkov",
        "url": "https://github.com/ammello/machine-learning-books/raw/master/books/Andriy%20Burkov%20-%20The%20Hundred-Page%20Machine%20Learning%20Book-Andriy%20Burkov%20(2019).pdf",
    },
    {
        "role": "data_science",
        "filename": "intro_ml_python.pdf",
        "title": "Introduction to Machine Learning with Python — Müller & Guido",
        "url": "https://github.com/dlsucomet/MLResources/raw/master/books/%5BML%5D%20Introduction%20to%20Machine%20Learning%20with%20Python%20(2017).pdf",
    },
]


def download(book: dict) -> bool:
    dest = KB / book["role"] / book["filename"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 500_000:
        print(f"  ✓ Already present: {book['title']}")
        return True
    print(f"  ↓ Downloading: {book['title']} …")
    try:
        req = Request(book["url"], headers={"User-Agent": "Mozilla/5.0"})
        data = urlopen(req, timeout=180).read()
        if len(data) < 500_000 or data[:4] != b"%PDF":
            print(f"  ✗ Invalid file for {book['title']} (got {len(data)} bytes)")
            return False
        dest.write_bytes(data)
        print(f"  ✓ Saved {len(data) // 1_048_576} MB → {dest.relative_to(KB.parent)}")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {book['title']} — {e}")
        return False


def main():
    print("Fetching assignment reference books...\n")
    ok = sum(download(b) for b in BOOKS)
    print(f"\n{ok}/{len(BOOKS)} books ready.")
    if ok < len(BOOKS):
        print("Some downloads failed — mirrors may be down. Place the PDFs manually in")
        print("the role folders under backend/knowledge_base/ and re-run ingest.")
        sys.exit(1)
    print("Next: python scripts/ingest_knowledge.py")


if __name__ == "__main__":
    main()
