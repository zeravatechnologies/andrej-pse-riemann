"""
The Card — one atom of knowledge, one markdown file.

A card is plain markdown with YAML-ish frontmatter, so the vault stays usable in
any editor (Obsidian included) with the app closed. The frontmatter is written by
the app and parsed defensively, because you will hand-edit these.

STATUS is the whole point of the design:

    CITED       carries at least one resolvable external source (arXiv id / DOI /
                LMFDB url / book+page). Somebody else proved it and we can find it.
    COMPUTED    carries a lab run id + the sha256 of the script that produced it.
                We computed it and can recompute it.
    FOLKLORE    stated without a source. Allowed into the vault but marked, and it
                may never be cited as support by another card.
    SPECULATION yours or the model's idea. Lives in speculation/ and NEVER in
                knowledge/. This is the anti-crank firewall.
    SUSPECT     the skeptic pass landed a hit; needs resolution.
    REFUTED     shown false. Kept, never deleted — negative results are results.

Frontmatter is deliberately a small fixed schema (no arbitrary YAML) so a hand-edit
cannot smuggle structure past the gate.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

CITED = "CITED"
COMPUTED = "COMPUTED"
FOLKLORE = "FOLKLORE"
SPECULATION = "SPECULATION"
SUSPECT = "SUSPECT"
REFUTED = "REFUTED"

STATUSES = {CITED, COMPUTED, FOLKLORE, SPECULATION, SUSPECT, REFUTED}
VERIFIED_STATUSES = {CITED, COMPUTED}          # may live in knowledge/

TYPES = {"definition", "theorem", "lemma", "conjecture", "equivalence",
         "numeric-fact", "open-question", "note", "source", "barrier"}

_LIST_FIELDS = {"sources", "depends_on", "tags", "supersedes"}
_NUM_FIELDS = {"theta_at_write", "confidence"}
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(s: str, maxlen: int = 60) -> str:
    out = _SLUG_RE.sub("-", (s or "").lower()).strip("-")
    return (out[:maxlen].rstrip("-")) or "kartica"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@dataclass
class Card:
    id: str = ""
    title: str = ""
    type: str = "note"
    status: str = SPECULATION
    sources: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    supersedes: list[str] = field(default_factory=list)
    author: str = "user"                 # user | model:<provider> | lab | ingest
    lab_run: str = ""                    # required for COMPUTED
    script_sha256: str = ""              # required for COMPUTED
    theta_at_write: float = 0.0
    confidence: float = 0.0
    created: str = ""
    updated: str = ""
    body: str = ""

    # -- construction -------------------------------------------------------- #
    def __post_init__(self):
        if not self.created:
            self.created = now_iso()
        self.updated = self.updated or self.created
        if not self.id:
            stamp = hashlib.sha1(
                f"{self.title}|{self.created}".encode()).hexdigest()[:6]
            self.id = f"{slugify(self.title)}-{stamp}"

    @property
    def filename(self) -> str:
        return f"{self.id}.md"

    def links(self) -> list[str]:
        """Wiki-links found in the body — the graph edges."""
        return re.findall(r"\[\[([^\]|#]+)", self.body or "")

    # -- serialization ------------------------------------------------------- #
    def to_markdown(self) -> str:
        d = asdict(self)
        body = d.pop("body") or ""
        lines = ["---"]
        for k in ("id", "title", "type", "status", "author", "created", "updated",
                  "lab_run", "script_sha256", "theta_at_write", "confidence"):
            v = d.get(k)
            if v in ("", None):
                continue
            lines.append(f"{k}: {_scalar(v)}")
        for k in ("sources", "depends_on", "tags", "supersedes"):
            v = d.get(k) or []
            if v:
                lines.append(f"{k}:")
                lines.extend(f"  - {_scalar(x)}" for x in v)
        lines.append("---")
        lines.append("")
        lines.append(body.rstrip() + "\n")
        return "\n".join(lines)

    @classmethod
    def from_markdown(cls, text: str) -> "Card":
        meta, body = parse_frontmatter(text)
        kwargs: dict[str, Any] = {"body": body}
        for k, v in meta.items():
            if k not in cls.__dataclass_fields__:
                continue                      # unknown keys are dropped, not honoured
            if k in _LIST_FIELDS:
                kwargs[k] = list(v) if isinstance(v, list) else ([v] if v else [])
            elif k in _NUM_FIELDS:
                try:
                    kwargs[k] = float(v)
                except (TypeError, ValueError):
                    kwargs[k] = 0.0
            else:
                kwargs[k] = str(v)
        return cls(**kwargs)

    @classmethod
    def load(cls, path: Path) -> "Card":
        return cls.from_markdown(Path(path).read_text(encoding="utf-8"))

    def digest(self) -> str:
        return hashlib.sha256(self.to_markdown().encode()).hexdigest()


def _scalar(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return f"{v:.4f}".rstrip("0").rstrip(".") or "0"
    s = str(v)
    if s != s.strip() or s.startswith(("[", "{", "#", "&", "*", "!", "%", "@")) \
            or ": " in s or s.endswith(":"):
        return '"' + s.replace('"', '\\"') + '"'
    return s


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Minimal, defensive frontmatter parser for the fixed schema above.
    Supports `key: value` and block lists (`key:` then `  - item`). Anything else
    is ignored rather than guessed at — the gate then rejects the card for missing
    required fields, which is the correct failure direction.
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("\n")
    if not parts or parts[0].strip() != "---":
        return {}, text
    meta: dict[str, Any] = {}
    i, cur_list_key = 1, None
    while i < len(parts):
        line = parts[i]
        if line.strip() == "---":
            i += 1
            break
        if re.match(r"^\s+-\s", line) and cur_list_key:
            meta.setdefault(cur_list_key, []).append(_unquote(line.split("-", 1)[1].strip()))
        elif ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            k, v = k.strip(), v.strip()
            if v == "":
                cur_list_key = k
                meta.setdefault(k, [])
            else:
                cur_list_key = None
                meta[k] = _unquote(v)
        i += 1
    return meta, "\n".join(parts[i:]).lstrip("\n")


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1].replace('\\"', '"')
    return s


# --------------------------------------------------------------------------- #
# Source references — what makes a CITED card actually citable
# --------------------------------------------------------------------------- #
_SOURCE_PATTERNS = [
    re.compile(r"^arxiv:\d{4}\.\d{4,5}(v\d+)?$", re.I),
    re.compile(r"^arxiv:[a-z\-]+(\.[A-Z]{2})?/\d{7}$", re.I),
    re.compile(r"^doi:10\.\d{4,9}/\S+$", re.I),
    re.compile(r"^lmfdb:\S+$", re.I),
    re.compile(r"^oeis:A\d{6}$", re.I),
    re.compile(r"^openalex:W\d+$", re.I),
    re.compile(r"^mathoverflow:\d+$", re.I),
    re.compile(r"^wikipedia:\S+$", re.I),
    re.compile(r"^book:.+,\s*(p\.|pp\.|ch\.|§)\s*\S+", re.I),   # book:Edwards 1974, ch. 6
    re.compile(r"^lean:\S+$", re.I),                            # lean:Mathlib.NumberTheory... (machine-checked)
    re.compile(r"^url:https://\S+$", re.I),
]


def is_resolvable_source(ref: str) -> bool:
    """
    A source reference must be machine-checkable, not a vibe. 'Edwards says so'
    fails; 'book:Edwards 1974, ch. 6' passes. This is the single most load-bearing
    validation in the app.
    """
    ref = (ref or "").strip()
    return any(p.match(ref) for p in _SOURCE_PATTERNS)


def source_hint() -> str:
    return ("dozvoljeni oblici izvora: arxiv:2405.12345 · doi:10.xxxx/yyy · "
            "lmfdb:... · oeis:A000040 · openalex:W... · mathoverflow:12345 · "
            "wikipedia:Riemann_zeta_function · book:Edwards 1974, ch. 6 · "
            "lean:Mathlib.NumberTheory... · url:https://...")
