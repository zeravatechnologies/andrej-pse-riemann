"""
Read side of the vault. The gate owns writes; this owns reads.

Deliberately dumb: it walks the tree and parses markdown. On a 4 GB machine with a
vault of a few thousand cards that is milliseconds, and it means the vault stays
the source of truth rather than a cache of a database. The FTS index (R10) is a
derived accelerator that can be rebuilt from these files at any time.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from .. import config
from .card import Card, VERIFIED_STATUSES, FOLKLORE, SPECULATION, SUSPECT, REFUTED

CARD_DIRS = ("knowledge", "sources", "speculation", "notes", "daily", "methods")


def iter_paths(dirs: tuple[str, ...] = CARD_DIRS) -> Iterator[Path]:
    for name in dirs:
        d = config.VAULT / name
        if not d.exists():
            continue
        for p in sorted(d.glob("*.md")):
            if "-masinski" in p.stem:           # a machine translation is not a card (33b)
                continue
            yield p


def iter_cards(dirs: tuple[str, ...] = CARD_DIRS) -> Iterator[Card]:
    for p in iter_paths(dirs):
        try:
            yield Card.load(p)
        except (OSError, UnicodeDecodeError):
            continue


def get(card_id: str) -> Optional[Card]:
    for p in iter_paths():
        if p.stem == card_id:
            try:
                return Card.load(p)
            except OSError:
                return None
    return None


def path_of(card_id: str) -> Optional[Path]:
    for p in iter_paths():
        if p.stem == card_id:
            return p
    return None


@dataclass
class Stats:
    total: int = 0
    by_status: dict = None
    by_type: dict = None
    verified: int = 0
    unverified: int = 0

    def __post_init__(self):
        self.by_status = self.by_status or {}
        self.by_type = self.by_type or {}


def stats() -> Stats:
    s = Stats()
    for c in iter_cards():
        s.total += 1
        s.by_status[c.status] = s.by_status.get(c.status, 0) + 1
        s.by_type[c.type] = s.by_type.get(c.type, 0) + 1
        if c.status in VERIFIED_STATUSES:
            s.verified += 1
        else:
            s.unverified += 1
    return s


def graph() -> tuple[list[dict], list[tuple[str, str, str]]]:
    """
    Nodes + edges for the graph tab.
    Edge kinds: 'link' (a [[wiki-link]] in the body) and 'depends' (frontmatter).
    """
    nodes, edges, known = [], [], set()
    cards = list(iter_cards())
    for c in cards:
        known.add(c.id)
        nodes.append({"id": c.id, "title": c.title, "status": c.status,
                      "type": c.type, "tags": c.tags})
    for c in cards:
        for dep in c.depends_on:
            if dep in known:
                edges.append((c.id, dep, "depends"))
        for l in c.links():
            l = l.strip()
            if l in known:
                edges.append((c.id, l, "link"))
    return nodes, edges


def orphans() -> list[str]:
    """Cards nothing points at and which point at nothing — candidates for review."""
    nodes, edges = graph()
    touched = {a for a, _, _ in edges} | {b for _, b, _ in edges}
    return [n["id"] for n in nodes if n["id"] not in touched]


def open_questions() -> list[Card]:
    return [c for c in iter_cards() if c.type == "open-question"]


def needs_attention() -> list[Card]:
    """SUSPECT cards and FOLKLORE that other cards lean on — the daily worklist."""
    cards = list(iter_cards())
    leaned_on: set[str] = set()
    for c in cards:
        for dep in c.depends_on:
            leaned_on.add(dep)
        for l in c.links():
            leaned_on.add(l.strip())
    out = []
    for c in cards:
        if c.status == SUSPECT:
            out.append(c)
        elif c.status == FOLKLORE and c.id in leaned_on:
            out.append(c)
    return out
