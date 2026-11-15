"""Export the ingested knowledge base to the compact, NumPy-only format in
``backend/kb`` (used by the Vercel deployment and by fresh clones that have not
run ingestion). Run after ``python -m scripts.ingest_kb``.
"""
from __future__ import annotations

import json

from app.config import get_settings
from app.rag.compact import export


def main() -> None:
    out = get_settings().kb_dir
    manifest = export(out)
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(json.dumps(manifest["compact"], indent=2))
    print(f"Wrote {out} ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
