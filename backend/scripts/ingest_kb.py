"""Build the vector knowledge base.

Usage (from ``backend/``)::

    python -m scripts.ingest_kb                       # all roles
    python -m scripts.ingest_kb --roles ai_ml_engineer
    python -m scripts.ingest_kb --add-file notes.pdf --role data_scientist --title "Team notes"
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from app.ai.catalog import ROLES
from app.rag.ingest import ingest_all, ingest_extra_document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--roles", nargs="*", choices=list(ROLES), help="roles to (re)ingest")
    parser.add_argument("--no-refit", action="store_true", help="reuse the existing LSA model")
    parser.add_argument("--add-file", type=Path, help="add one extra document to a role")
    parser.add_argument("--role", choices=list(ROLES), help="role for --add-file")
    parser.add_argument("--title", help="display title for --add-file")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.add_file:
        if not args.role:
            parser.error("--add-file requires --role")
        print(json.dumps(ingest_extra_document(args.role, args.add_file, args.title), indent=2))
        return
    manifest = ingest_all(args.roles, refit=not args.no_refit)
    print(json.dumps(manifest["roles"], indent=2))


if __name__ == "__main__":
    main()
