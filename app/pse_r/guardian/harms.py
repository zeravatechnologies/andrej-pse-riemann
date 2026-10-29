"""
The three harms (plan F5, master §4 S3 / §10).

Every agent and every final artifact is watched for three kinds of harm. One is
enough to treat an agent as infected (healing.py):

  TO THE HUMAN   a number with no source, a preprint stated as established fact,
                 a claim to have proved an open problem, a private leak (an IP,
                 a MAC address, an API key).
  TO AN AGENT    an instruction taken from data (prompt injection), an action
                 outside the agent's mission, an answer given without a check
                 ("sir, yes sir" — the C pattern), a sudden jump in its balance.
  TO A FILE      a write that did not go through the gate, a hash that does not
                 match with a trail leading to an agent, a change to a sealed file.

Detectors are deterministic and reuse the guardian's existing scanners
(content.scan_injection, secrets patterns) plus the gate's proof-claim check and
the source tiers. They return findings; they never decide treatment — that is
healing.py, and tier-2 steps are the operator's.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from ..vault import gate as GATE
from ..vault import tiers as T
from . import content as C
from . import secrets as SEC

HUMAN, AGENT, FILE = "human", "agent", "file"
LOW, MED, HIGH = "niska", "srednja", "visoka"

# private identifiers that must never leak (master §10, egress)
_IPV4 = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_MAC = re.compile(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b")
_NUMBER = re.compile(r"(?<![\w.])-?\d+\.\d{3,}(?:[eE][-+]?\d+)?")   # a "result-looking" number
# a public, harmless IP we expect in text about the subject (loopback, 7/8 etc.)
_IP_OK = {"127.0.0.1", "0.0.0.0"}


@dataclass
class Finding:
    harm: str                      # HUMAN | AGENT | FILE
    sign: str                      # short machine label
    evidence: str                  # what was seen
    severity: str = MED


# --------------------------------------------------------------------------- #
def to_human(text: str, sources: Optional[list] = None,
             tier: Optional[str] = None) -> list[Finding]:
    out: list[Finding] = []
    sources = sources or []
    resolvable = [s for s in sources if GATE.is_resolvable_source(s)]

    # number without a source
    if _NUMBER.search(text or "") and not resolvable:
        m = _NUMBER.search(text)
        out.append(Finding(HUMAN, "broj-bez-izvora",
                           f"broj '{m.group(0)}' bez razrješivog izvora", HIGH))

    # preprint stated as established fact
    if tier is not None and tier not in T.ESTABLISHED and _looks_assertive(text):
        out.append(Finding(HUMAN, "preprint-kao-činjenica",
                           f"tvrdnja nivoa {tier} iznesena kao utvrđena", HIGH))

    # proof claim for an open problem
    claims, sentence = GATE._claims_proof(text or "")
    if claims:
        out.append(Finding(HUMAN, "tvrdnja-o-dokazu",
                           f"tvrdi dokaz/rješenje: „{sentence[:80]}“", HIGH))

    # private leak: IP / MAC / secret-shaped token
    for m in _IPV4.finditer(text or ""):
        if m.group(0) not in _IP_OK:
            out.append(Finding(HUMAN, "curenje-IP", f"IP adresa '{m.group(0)}'", HIGH))
            break
    if _MAC.search(text or ""):
        out.append(Finding(HUMAN, "curenje-MAC", "MAC adresa u tekstu", HIGH))
    red = SEC.redact(text or "")
    if red != (text or ""):
        out.append(Finding(HUMAN, "curenje-ključa", "materijal nalik tajni/ključu", HIGH))
    return out


def chat_human(text: str) -> list[Finding]:
    """The deterministic leak checks of to_human, for EVERY chat reply too
    (round 3 benchmark: a key / private address in a chat reply went unseen,
    because only final outputs were checked)."""
    keep = {"curenje-IP", "curenje-MAC", "curenje-ključa"}
    return [f for f in to_human(text, sources=["chat"]) if f.sign in keep]


def _looks_assertive(text: str) -> bool:
    """A bald assertion (no hedging), the shape that makes a preprint read as fact."""
    t = (text or "").lower()
    hedges = ("pod pretpostavk", "uslovno", "navodno", "tvrdi se", "preprint",
              "nerecenzir", "možda", "vjerovatno", "if ", "ako je")
    return len(t) > 0 and not any(h in t for h in hedges)


def to_agent(text_from_data: str = "", actions: Optional[list] = None,
             mission_actions: Optional[set] = None,
             reply: str = "", theta_delta: Optional[float] = None,
             theta_jump: float = 0.15) -> list[Finding]:
    out: list[Finding] = []
    for hit in C.scan_injection(text_from_data or ""):
        out.append(Finding(AGENT, "injekcija", hit["why"], HIGH))
        break
    if actions and mission_actions is not None:
        stray = [a for a in actions if a not in mission_actions]
        if stray:
            out.append(Finding(AGENT, "van-misije",
                               f"radnje izvan misije: {stray}", HIGH))
    if reply and _is_sir_yes_sir(reply):
        out.append(Finding(AGENT, "bez-provjere",
                           "slaganje bez provjere/izvora (obrazac C)", MED))
    if theta_delta is not None and abs(theta_delta) >= theta_jump:
        out.append(Finding(AGENT, "skok-ravnoteže",
                           f"skok ravnoteže Δ={theta_delta:+.3f}", MED))
    return out


_SIR = re.compile(r"(?i)\b(naravno|svakako|u pravu si|slažem se|apsolutno|"
                  r"of course|you'?re right|absolutely|certainly)\b")


def _is_sir_yes_sir(reply: str) -> bool:
    """Agreement with no citation and no hedge — the uncritical 'C' pattern."""
    t = reply or ""
    if not _SIR.search(t):
        return False
    has_cite = "[" in t or "arxiv:" in t.lower() or "doi:" in t.lower()
    return not has_cite and len(t) < 300


def to_file(path: str, via_gate: bool = True, expected_hash: str = "",
            actual_hash: str = "", sealed: bool = False,
            trail_agent: str = "") -> list[Finding]:
    out: list[Finding] = []
    if not via_gate:
        out.append(Finding(FILE, "upis-mimo-kapije",
                           f"upis u '{path}' nije prošao kroz kapiju", HIGH))
    mismatch = bool(expected_hash) and expected_hash != actual_hash
    if mismatch:
        sign = "izmjena-zapečaćenog" if sealed else "hash-ne-odgovara"
        ev = f"hash '{path}' ne odgovara" + (f" (trag → {trail_agent})" if trail_agent else "")
        out.append(Finding(FILE, sign, ev, HIGH))
    return out


def any_harm(*finding_lists: list) -> bool:
    return any(len(fl) > 0 for fl in finding_lists)
