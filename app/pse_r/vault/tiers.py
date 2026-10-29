"""
Source tiers (plan F2).

STATUS says how a card earned its place; the TIER says how strong the ground
under it is. They are orthogonal: a CITED card can rest on a peer-reviewed
journal article or on a two-day-old arXiv preprint, and those are not the same
kind of fact. The plan names five tiers:

    REFEREED            peer-reviewed / published: a DOI, a book+page, or a
                        curated reference database (LMFDB, OEIS). Someone with a
                        name checked it.
    LEAN                machine-checked: a formal proof in a proof assistant
                        (Lean / mathlib). The computer checked it.
    PREPRINT            external but NOT peer-reviewed: arXiv, OpenAlex, a
                        MathOverflow answer, a wiki page, a bare URL. Public, but
                        nobody vouched for it yet.
    AI-UNREVIEWED       a model wrote the card. Whatever it cites, the model's
                        own rendering of it has not been checked by a human.
    NAŠE-NERECENZIRANO  our own reproducible computation (a COMPUTED lab run).
                        We can rerun it; no outsider has reviewed it.

The one rule the gate enforces from this (plan F2):

    a PREPRINT (or anything weaker) may NOT be the support of an ESTABLISHED
    claim — "preprint ne može biti oslonac za utvrđenu tvrdnju".

"Established" means a card whose own tier is REFEREED or LEAN. Preprints are
still allowed into the vault — they just cannot prop up a settled theorem.

The tier is DERIVED from (status, author, sources); it is never stored in the
frontmatter, so a hand-edit cannot promote a card by typing a stronger word.
"""
from __future__ import annotations

import re
from typing import Optional

from .card import (CITED, COMPUTED, FOLKLORE, SPECULATION, SUSPECT, REFUTED)

REFEREED = "REFEREED"
LEAN = "LEAN"
PREPRINT = "PREPRINT"
AI_UNREVIEWED = "AI-UNREVIEWED"
OURS = "NAŠE-NERECENZIRANO"
UNSOURCED = "UNSOURCED"            # folklore / speculation / refuted — no ground at all

# Higher = stronger. Used only for "strongest source wins" and never exposed as a
# number to the operator (the words are what they see).
_RANK = {REFEREED: 5, LEAN: 5, PREPRINT: 3, OURS: 2, AI_UNREVIEWED: 1, UNSOURCED: 0}

# A claim whose own tier is one of these is "utvrđena" — settled enough that its
# supports must be settled too.
ESTABLISHED = frozenset({REFEREED, LEAN})

# Which source *scheme* (the part before the first ':') maps to which tier.
# Schemes not listed here are treated as PREPRINT (external, unreviewed) as long
# as the card's gate already accepted them as resolvable.
_SCHEME_TIER = {
    "doi": REFEREED,
    "book": REFEREED,
    "lmfdb": REFEREED,
    "oeis": REFEREED,
    "lean": LEAN,
    "arxiv": PREPRINT,
    "openalex": PREPRINT,
    "mathoverflow": PREPRINT,
    "wikipedia": PREPRINT,
    "url": PREPRINT,
}

_SCHEME_RE = re.compile(r"^\s*([a-z]+)\s*:", re.I)


def rank(tier: str) -> int:
    return _RANK.get(tier, 0)


def source_tier(ref: str) -> Optional[str]:
    """The tier a single source reference confers, or None if it has no scheme."""
    m = _SCHEME_RE.match(ref or "")
    if not m:
        return None
    return _SCHEME_TIER.get(m.group(1).lower(), PREPRINT)


def _strongest(tiers: list[str]) -> Optional[str]:
    tiers = [t for t in tiers if t]
    if not tiers:
        return None
    return max(tiers, key=rank)


def card_tier(card) -> str:
    """
    The tier of a whole card (duck-typed: needs .status, .author, .sources).

    Order of reasoning, strongest constraint first:
      * a card that is not even verified (speculation / folklore / suspect /
        refuted) has no ground — UNSOURCED;
      * a model-authored card is AI-UNREVIEWED no matter what it cites, because
        we have not checked that the model quoted its source faithfully;
      * our own computation is NAŠE-NERECENZIRANO;
      * otherwise a CITED card inherits the strongest tier among its sources.
    """
    status = getattr(card, "status", "")
    if status in (SPECULATION, FOLKLORE, SUSPECT, REFUTED):
        return UNSOURCED
    if (getattr(card, "author", "") or "").startswith("model:"):
        return AI_UNREVIEWED
    if status == COMPUTED:
        return OURS
    if status == CITED:
        return _strongest([source_tier(s) for s in getattr(card, "sources", [])]) \
            or UNSOURCED
    return UNSOURCED


def is_established(card) -> bool:
    """A settled claim — its supports must be settled too."""
    return card_tier(card) in ESTABLISHED


def tier_hint() -> str:
    return ("nivoi izvora: REFEREED (doi/book/lmfdb/oeis) · LEAN (lean:) · "
            "PREPRINT (arxiv/openalex/wikipedia/mathoverflow/url) · "
            "AI-UNREVIEWED (model) · NAŠE-NERECENZIRANO (naš COMPUTED). "
            "Preprint ne može biti oslonac utvrđene (REFEREED/LEAN) tvrdnje.")
