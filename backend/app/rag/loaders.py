"""Document loading and text normalisation.

PDF text extraction is noisy: running headers, page numbers, hyphenated line
breaks, ligatures and table-of-contents/index pages. Cleaning happens here so
that the chunker and the embedder only ever see prose-like text.
"""
from __future__ import annotations

import io
import logging
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

logger = logging.getLogger(__name__)
# pypdf is chatty about font encodings in scanned/LaTeX PDFs; it is harmless.
logging.getLogger("pypdf").setLevel(logging.ERROR)

_LIGATURES = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl"}


@dataclass
class Page:
    number: int  # 1-based page index within the PDF
    text: str


def normalize_text(text: str) -> str:
    for src, dst in _LIGATURES.items():
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "")  # soft hyphen
    # Re-join words hyphenated across line breaks: "learn-\ning" -> "learning"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _strip_repeated_lines(pages: list[Page]) -> list[Page]:
    """Remove running headers/footers: short lines that repeat on many pages."""
    if len(pages) < 8:
        return pages
    counts: Counter[str] = Counter()
    for p in pages:
        lines = p.text.splitlines()
        edge = lines[:2] + lines[-2:]
        for line in {_header_key(l) for l in edge if l.strip()}:
            counts[line] += 1
    threshold = max(4, int(len(pages) * 0.04))
    repeated = {k for k, c in counts.items() if c >= threshold and len(k) < 80}
    if not repeated:
        return pages
    cleaned = []
    for p in pages:
        lines = [l for l in p.text.splitlines() if _header_key(l) not in repeated]
        cleaned.append(Page(p.number, "\n".join(lines)))
    return cleaned


def _header_key(line: str) -> str:
    # Page numbers vary between pages; compare headers with digits masked.
    return re.sub(r"\d+", "#", line.strip().lower())


def is_low_quality(text: str) -> bool:
    """Heuristics for pages/chunks that are useless as interview context:
    tables of contents, indexes, bibliographies, copyright pages, math soup."""
    stripped = text.strip()
    if len(stripped) < 120:
        return True
    letters = sum(c.isalpha() for c in stripped)
    if letters / max(len(stripped), 1) < 0.55:
        return True
    lines = [l for l in stripped.splitlines() if l.strip()]
    if lines:
        # TOC / index pages: many lines ending with page numbers or dot leaders
        numeric_tail = sum(bool(re.search(r"(\.{3,}|\s)\d{1,4}$", l)) for l in lines)
        if numeric_tail / len(lines) > 0.4:
            return True
        short = sum(len(l) < 25 for l in lines)
        if len(lines) > 12 and short / len(lines) > 0.7:
            return True
    # Dot leaders that survive line-joining: "Preprocessing. . . . . . . 131"
    if len(re.findall(r"(?:\.\s?){5,}\s*\d{1,4}", stripped)) >= 3:
        return True
    words_total = max(len(stripped.split()), 1)
    # TOC flattened into one line: "Challenges 132 Different Kinds of Preprocessing 133 Applying..."
    if len(re.findall(r"[A-Za-z)]\s+\d{1,4}\s+[A-Z]", stripped)) / words_total > 0.04:
        return True
    # Back-of-book index: "dimensionality reduction, 141, 156 discrete features, 211"
    if len(re.findall(r"\b\d{1,4}(?:[-–]\d{1,4})?\s*,", stripped)) / words_total > 0.05:
        return True
    lower = stripped.lower()
    if lower.count("et al") > 4 or lower.count("http") > 4:
        return True  # reference lists
    if "all rights reserved" in lower and len(stripped) < 2500:
        return True
    words = re.findall(r"[a-zA-Z]{3,}", stripped)
    if len(words) < 25:
        return True
    return False


def load_pdf(path: Path | str | bytes) -> list[Page]:
    reader = PdfReader(io.BytesIO(path) if isinstance(path, bytes) else str(path))
    pages: list[Page] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            raw = page.extract_text() or ""
        except Exception as exc:  # pragma: no cover - malformed pages
            logger.warning("Failed to extract page %s: %s", i, exc)
            raw = ""
        pages.append(Page(i, normalize_text(raw)))
    return _strip_repeated_lines(pages)


def load_text(path: Path | str) -> list[Page]:
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    return [Page(1, normalize_text(text))]


def load_document(path: Path | str) -> list[Page]:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return load_pdf(path)
    if suffix in {".txt", ".md"}:
        return load_text(path)
    raise ValueError(f"Unsupported document type: {suffix}")
