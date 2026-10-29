"""
The skeptic (plan F3, master §0.5.5).

The skeptic has ONE job: attack. It attacks claims, proposed methods and draft
reports; it never writes as an author, it has no write access to the vault, and
its output has a fixed shape so it cannot smuggle prose:

    prigovor · razlog · gdje · ozbiljnost

Every objection lands in the human queue ("Čeka tvoju odluku"); the operator
decides. The skeptic is always a DIFFERENT model from the main one (selection.py)
— a model grading itself is not a check. If no distinct skeptic is available, the
skeptic is "unavailable" and only the deterministic checks (reproduction test,
provenance, gate, tiers) stand against a claim; that is honest, not a failure.

The skeptic is a PSE unit (Faza 6d): every attack is a move of the skeptic's
unit — measured, judged by the Doctor, and refused while the unit is frozen.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from typing import Callable, Optional

from ..core import journal as J
from ..shared_lib.store import store
from . import backend as B
from . import selection as SEL

SKEPTIC_KIND = "skeptic"                     # human-queue + journal kind
SEVERITIES = ("niska", "srednja", "visoka")

_SYSTEM = (
    "Ti si SKEPTIK. Tvoj jedini zadatak je da NAPADNEŠ tvrdnju — nikad da je "
    "braniš, dopuniš ili prepišeš. Ne pišeš kao autor i nemaš pravo upisa. "
    "Vrati ISKLJUČIVO JSON listu prigovora, svaki oblika "
    '{"prigovor": "...", "razlog": "...", "gdje": "...", "ozbiljnost": '
    '"niska|srednja|visoka"}. Ako nemaš nijedan valjan prigovor, vrati []. '
    "Bez ijedne riječi van JSON-a.")


@dataclass
class Objection:
    prigovor: str
    razlog: str
    gdje: str = ""
    ozbiljnost: str = "srednja"

    def normalised(self) -> "Objection":
        sev = (self.ozbiljnost or "").strip().lower()
        if sev not in SEVERITIES:
            sev = "srednja"
        return Objection(self.prigovor.strip(), self.razlog.strip(),
                         (self.gdje or "").strip(), sev)


def _parse(text: str) -> list[Objection]:
    """Pull the JSON objection list out of a model reply, defensively."""
    if not text:
        return []
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    out = []
    for d in data if isinstance(data, list) else []:
        if isinstance(d, dict) and d.get("prigovor") and d.get("razlog"):
            out.append(Objection(str(d["prigovor"]), str(d["razlog"]),
                                  str(d.get("gdje", "")),
                                  str(d.get("ozbiljnost", "srednja"))).normalised())
    return out


def _prompt(claim_title: str, claim_text: str, context: str) -> str:
    return (f"TVRDNJA: {claim_title}\n\n{claim_text}\n\n"
            + (f"KONTEKST:\n{context}\n\n" if context else "")
            + "Napadni je. Vrati JSON listu prigovora.")


def _default_ask(claim_title: str, claim_text: str, context: str) -> str:
    """The skeptic's unit calls its model (always a DIFFERENT model) on the
    unit's path; the move is recorded there."""
    from ..pse import path as PATH
    reply = PATH.ask("skeptic", [B.Msg("user", _prompt(claim_title, claim_text, context))],
                     system_extra=_SYSTEM, max_tokens=700,
                     data_in_context=claim_text[:20000])
    return reply.text


def attack(claim_title: str, claim_text: str, context: str = "",
           subject: str = "", ask: Optional[Callable[[str, str, str], str]] = None,
           queue: bool = True) -> dict:
    """
    Run the skeptic over a claim. Returns:
      {"available": bool, "objections": [Objection...], "pids": [queue ids]}
    If no distinct skeptic is available, returns available=False and does nothing
    else — the deterministic checks carry on without it.
    """
    if not SEL.skeptic_available():
        J.log(SKEPTIC_KIND, "skeptic", {"event": "unavailable", "claim": claim_title},
              subject=subject or claim_title, verdict="unavailable")
        return {"available": False, "objections": [], "pids": []}

    injected = ask is not None
    ask = ask or _default_ask
    try:
        raw = ask(claim_title, claim_text, context)
        if injected:
            from ..pse import path as PATH
            PATH.words("skeptic", raw, message=_prompt(claim_title, claim_text, context),
                       note="ask")
    except Exception as e:                              # noqa: BLE001
        J.log(SKEPTIC_KIND, "skeptic", {"event": "error", "claim": claim_title,
                                        "error": f"{type(e).__name__}: {e}"},
              subject=subject or claim_title, verdict="error")
        return {"available": True, "objections": [], "pids": [], "error": str(e)}

    objs = _parse(raw)
    pids = []
    if queue:
        for o in objs:
            pid = store().propose(
                SKEPTIC_KIND,
                f"Skeptik [{o.ozbiljnost}]: {o.prigovor[:80]}",
                {"objection": asdict(o), "claim": claim_title, "subject": subject},
                proposer="skeptic")
            pids.append(pid)
    J.log(SKEPTIC_KIND, "skeptic",
          {"event": "attacked", "claim": claim_title, "n_objections": len(objs),
           "severities": [o.ozbiljnost for o in objs]},
          subject=subject or claim_title, verdict="attacked")
    return {"available": True, "objections": objs, "pids": pids}
