"""
DL1 input layer and the provenance tag [rules 10, 16; §17.1, §2.5].

normalize()      Unicode NFKC, invisible/format characters removed, homoglyph
                 Cyrillic→Latin for the letters that look the same.
first_letters()  first letters of lines, sentences and words — read by the same
                 reading as the text (catches the classic acrostic, nothing more).
Tagged text      every text that enters a unit carries its origin. EXTERNAL text
                 (papers, abstracts, ar5iv, fetched pages, unknown) never reaches
                 an irreversible action.
classify_source  a source's class from its four shape series, by majority;
                 a tie = "unknown" = external [rule 16].
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Sequence

INTERNAL = "internal"        # operator, our lab runs, our own cards
EXTERNAL = "external"        # papers, abstracts, ar5iv, web, model output about them
UNKNOWN = "unknown"          # treated as external

_HOMO = str.maketrans({"а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y",
                       "х": "x", "і": "i", "ј": "j", "А": "A", "В": "B", "Е": "E",
                       "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C",
                       "Т": "T", "Х": "X"})


def normalize(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "")
    t = "".join(ch for ch in t if unicodedata.category(ch) not in ("Cf", "Co", "Cs"))
    # mixed-script words only: a fully Cyrillic word stays Cyrillic
    out = []
    for w in re.split(r"(\s+)", t):
        if re.search(r"[A-Za-z]", w) and re.search(r"[Ѐ-ӿ]", w):
            w = w.translate(_HOMO)
        out.append(w)
    return "".join(out)


def first_letters(text: str) -> dict:
    t = normalize(text)
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    sents = [s.strip() for s in re.split(r"[.!?]+", t) if s.strip()]
    words = re.findall(r"\w+", t)
    return {"lines": "".join(ln[0] for ln in lines),
            "sentences": "".join(s[0] for s in sents),
            "words": "".join(w[0] for w in words)}


TRANSFORM_EXECUTE = [r"(pročitaj|uzmi) prv[ae] slov", r"read the first letters",
                     r"(primijeni|apply) (ovo|this) (mapiranj|mapping)", r"then (do|follow) (that|it)"]


def transform_and_execute(text: str) -> bool:
    """§2.5: an instruction to execute the result of a transformation → UNKNOWN."""
    t = normalize(text).lower()
    return any(re.search(p, t) for p in TRANSFORM_EXECUTE)


@dataclass(frozen=True)
class Tagged:
    text: str
    origin: str               # internal | external | unknown
    source: str = ""          # e.g. "arxiv:2410.01234v2", "operator", "lab:run-17"

    @property
    def external(self) -> bool:
        return self.origin != INTERNAL


def tag(text: str, origin: str, source: str = "") -> Tagged:
    if origin not in (INTERNAL, EXTERNAL, UNKNOWN):
        origin = UNKNOWN
    return Tagged(normalize(text), origin, source)


def classify_source(series: dict[str, Sequence[float]], threshold: float = 0.5,
                    min_obs: int = 30) -> str:
    """Majority over the four shape series (N, B, C, S) of a source [rule 16].
    Each series votes for its shape when its mean ≥ threshold; no votes →
    'healthy'; a tie between shapes → 'unknown'."""
    n = min((len(v) for v in series.values()), default=0)
    if n < min_obs:
        return "unknown"
    means = {k: sum(v) / len(v) for k, v in series.items() if v}
    voted = {k: m for k, m in means.items() if m >= threshold}
    if not voted:
        return "healthy"
    top = max(voted.values())
    best = [k for k, m in voted.items() if m == top]
    return best[0] if len(best) == 1 else "unknown"
