"""Structure-aware chunking.

Strategy (see README "Chunking strategy" for the reasoning):

1. Detect section headings (``CHAPTER 6 BAYESIAN LEARNING``, ``6.2 BAYES
   THEOREM``, ``Chapter 17``...) and treat them as hard boundaries, so one chunk
   never mixes two unrelated sections.
2. Inside a section, split the text into sentences and greedily pack them into
   chunks of ~``chunk_size`` characters. Chunks never cut a sentence in half.
3. Consecutive chunks of the same section share ~``overlap`` characters of
   trailing sentences, so a definition that straddles a boundary survives in at
   least one chunk.
4. Each chunk keeps its book, section heading and page span as metadata, and
   the heading is prepended to the text that gets *embedded* ("contextual
   chunk header") so short chunks still carry their topic.
5. Low-quality chunks (TOC, index, references, equation soup) and exact
   duplicates are dropped.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from app.rag.loaders import Page, is_low_quality

_HEADING_PATTERNS = [
    re.compile(r"^chapter\s+\d+[\s:.-]*.{0,80}$", re.IGNORECASE),
    re.compile(r"^\d{1,2}(\.\d{1,2}){0,3}\.?\s+[A-Z][A-Za-z0-9 ,:&()'/-]{3,80}$"),
    re.compile(r"^(part|section)\s+[ivx\d]+[\s:.-]+.{3,80}$", re.IGNORECASE),
]
_BARE_CHAPTER = re.compile(r"^chapter\s+\d+$", re.IGNORECASE)
_SENTENCE_SPLIT =re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'])")


@dataclass
class Chunk:
    id: str
    book_id: str
    book_title: str
    section: str
    page_start: int
    page_end: int
    text: str
    position: int
    metadata: dict = field(default_factory=dict)

    @property
    def embedding_text(self) -> str:
        header = f"{self.book_title}"
        if self.section:
            header += f" | {self.section}"
        return f"{header}\n{self.text}"


_SMALL_WORDS = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "vs", "with"}


def _title_like(text: str) -> bool:
    """Headings are Title Case or UPPER CASE; sentence fragments are not."""
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]*", text)]
    if not words:
        return False
    if text.isupper():
        return True
    content = [w for w in words if w.lower() not in _SMALL_WORDS]
    if not content:
        return False
    capitalised = sum(w[0].isupper() for w in content)
    return capitalised / len(content) >= 0.75


def _is_heading(line: str) -> bool:
    line = line.strip()
    if not (4 <= len(line) <= 90):
        return False
    if _BARE_CHAPTER.match(line):
        return True
    if line.endswith((".", ",", ";", ")")):
        return False
    if sum(c.isalpha() for c in line) < 4 or re.match(r"^0\b", line):
        return False
    if not any(p.match(line) for p in _HEADING_PATTERNS):
        return False
    title = re.sub(r"^(chapter|part|section)\s+[ivx\d]+[\s:.-]*|^[\d.]+\s*", "", line, flags=re.IGNORECASE)
    # Table rows ("1 San Jose 1015785", "2 False True") look like numbered headings.
    words = title.split()
    if re.search(r"\d", title) or len(words) < 2 or {w.lower() for w in words} & {"true", "false", "nan", "none"}:
        return False
    return _title_like(title)


def _clean_heading(line: str) -> str:
    line = re.sub(r"\s+\d{1,4}$", "", line.strip())  # trailing page numbers
    return line.title() if line.isupper() else line


def _iter_units(pages: list[Page]):
    """Yield ("heading", text, page) or ("text", sentence, page) units."""
    for page in pages:
        buffer: list[str] = []

        def flush():
            if buffer:
                joined = " ".join(buffer)
                buffer.clear()
                for sentence in _SENTENCE_SPLIT.split(joined):
                    sentence = sentence.strip()
                    if sentence:
                        yield ("text", sentence, page.number)

        pending_chapter: str | None = None
        title_parts: list[str] = []
        for line in page.text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if pending_chapter is not None:
                # "CHAPTER 4" on its own line is followed by a title that may wrap:
                # "Representing Data and" / "Engineering Features".
                title_like = len(stripped) <= 80 and not stripped.endswith((".", ",", ";")) and _title_like(stripped)
                if title_like:
                    title_parts.append(_clean_heading(stripped))
                    if title_parts[-1].split()[-1].lower() in _SMALL_WORDS and len(title_parts) < 3:
                        continue  # title continues on the next line
                heading = f"{pending_chapter}: {' '.join(title_parts)}" if title_parts else pending_chapter
                pending_chapter, title_parts = None, []
                yield ("heading", heading, page.number)
                if title_like:
                    continue
            if _is_heading(stripped):
                yield from flush()
                if _BARE_CHAPTER.match(stripped):
                    pending_chapter = stripped.title()
                else:
                    yield ("heading", _clean_heading(stripped), page.number)
            else:
                buffer.append(stripped)
        if pending_chapter is not None:
            heading = f"{pending_chapter}: {' '.join(title_parts)}" if title_parts else pending_chapter
            yield ("heading", heading, page.number)
        yield from flush()


def chunk_pages(
    pages: list[Page],
    *,
    book_id: str,
    book_title: str,
    chunk_size: int = 1000,
    overlap: int = 200,
    min_chars: int = 200,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    seen_hashes: set[str] = set()
    section = ""
    current: list[tuple[str, int]] = []  # (sentence, page)

    def emit(carry_overlap: bool) -> None:
        nonlocal current
        if not current:
            return
        text = " ".join(s for s, _ in current).strip()
        pages_in = [p for _, p in current]
        if len(text) >= min_chars and not is_low_quality(text):
            digest = hashlib.sha1(text.lower().encode()).hexdigest()
            if digest not in seen_hashes:
                seen_hashes.add(digest)
                chunks.append(
                    Chunk(
                        id=f"{book_id}:{len(chunks):05d}",
                        book_id=book_id,
                        book_title=book_title,
                        section=section,
                        page_start=min(pages_in),
                        page_end=max(pages_in),
                        text=text,
                        position=len(chunks),
                    )
                )
        if carry_overlap:
            tail: list[tuple[str, int]] = []
            size = 0
            for sentence, page in reversed(current):
                if size + len(sentence) > overlap:
                    break
                tail.insert(0, (sentence, page))
                size += len(sentence) + 1
            current = tail
        else:
            current = []

    for kind, value, page in _iter_units(pages):
        if kind == "heading":
            emit(carry_overlap=False)
            section = value
            continue
        # Guard against pathological "sentences" (tables, code) longer than a chunk.
        while len(value) > chunk_size * 1.5:
            current.append((value[:chunk_size], page))
            value = value[chunk_size:]
            emit(carry_overlap=False)
        size = sum(len(s) + 1 for s, _ in current)
        if current and size + len(value) > chunk_size:
            emit(carry_overlap=True)
        current.append((value, page))
    emit(carry_overlap=False)
    return chunks
