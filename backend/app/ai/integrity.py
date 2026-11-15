"""Answer integrity signals.

A remote screening interview is easy to game: paste from a chatbot, copy the
textbook paragraph, or type something in suspiciously little time. This module
turns browser telemetry and the answer text into a few explainable flags.

Design choices:

* Signals are **advisory**. They never change the score; they are shown to the
  reviewer with the evidence, because every heuristic here has innocent
  explanations (a candidate drafting in a notes app, dictating by voice...).
* Each flag carries the number that triggered it, so a reviewer can judge it.
* Copying is measured against the retrieved source passages the question was
  built from, which is exactly the material a cheating candidate would find.
"""
from __future__ import annotations

import re

from app.rag.retriever import tokenize

PASTE_RATIO_FLAG = 0.5  # more than half of the answer arrived via paste
VERBATIM_FLAG = 0.35  # share of answer 6-grams found verbatim in the sources
WPM_FLAG = 120  # sustained typing faster than this is unusual for considered answers
FOCUS_LOSS_FLAG = 3


def _shingles(tokens: list[str], n: int = 6) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def verbatim_overlap(answer: str, sources: list[str], n: int = 6) -> float:
    """Fraction of the answer's word n-grams that appear verbatim in the sources."""
    words = re.findall(r"[a-z0-9]+", answer.lower())
    answer_sh = _shingles(words, n)
    if not answer_sh:
        return 0.0
    source_sh: set[tuple[str, ...]] = set()
    for text in sources:
        source_sh |= _shingles(re.findall(r"[a-z0-9]+", text.lower()), n)
    return len(answer_sh & source_sh) / len(answer_sh)


def assess(answer: str, telemetry: dict | None, response_seconds: float | None, sources: list[str]) -> dict:
    telemetry = telemetry or {}
    chars = max(len(answer), 1)
    words = len(answer.split())
    pasted = int(telemetry.get("pasted_chars", 0) or 0)
    voice = int(telemetry.get("voice_chars", 0) or 0)
    typing_ms = telemetry.get("active_typing_ms")
    focus_losses = int(telemetry.get("focus_losses", 0) or 0)

    signals = {
        "paste_ratio": round(min(pasted / chars, 1.0), 2),
        "voice_ratio": round(min(voice / chars, 1.0), 2),
        "verbatim_source_overlap": round(verbatim_overlap(answer, sources), 2),
        "focus_losses": focus_losses,
        "words_per_minute": None,
    }
    minutes = (typing_ms / 60000) if typing_ms else (response_seconds / 60 if response_seconds else None)
    typed_words = words * (1 - signals["paste_ratio"] - signals["voice_ratio"])
    if minutes and minutes > 0 and typed_words > 15:
        signals["words_per_minute"] = round(typed_words / minutes)

    flags = []
    if signals["paste_ratio"] >= PASTE_RATIO_FLAG and pasted > 80:
        flags.append({"code": "pasted_answer", "detail": f"{int(signals['paste_ratio'] * 100)}% of the answer was pasted ({pasted} chars)"})
    if signals["verbatim_source_overlap"] >= VERBATIM_FLAG and words >= 20:
        flags.append({"code": "copied_from_source", "detail": f"{int(signals['verbatim_source_overlap'] * 100)}% of 6-word phrases match the reference text verbatim"})
    if signals["words_per_minute"] and signals["words_per_minute"] > WPM_FLAG:
        flags.append({"code": "implausible_speed", "detail": f"~{signals['words_per_minute']} words/min of typing"})
    if focus_losses >= FOCUS_LOSS_FLAG:
        flags.append({"code": "left_the_tab", "detail": f"window lost focus {focus_losses} times while answering"})

    level = "none" if not flags else "review" if len(flags) == 1 else "high"
    return {"level": level, "flags": flags, "signals": signals}
