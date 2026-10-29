"""
THE GATE — the single write path into the vault.

Nothing writes a card except through `Gate.submit()`. Not the chat, not the
scraper, not the lab, not the editor. This mirrors the PSE kernel's ONE GATE rule
(spec §3, SHARED_LIB contribution gate): if the gate leaks, everything above it
is sand — and for a 20-day solo study of the Riemann zeta function, the specific
sand is 300 pages of confident nonsense.

What the gate enforces
----------------------
  1. CONTAINMENT      every path resolves inside the vault; no traversal, no
                      symlink escape, never a write into ~/Desktop/123.
  2. STATUS TRUTH     CITED needs >= 1 machine-resolvable source reference.
                      COMPUTED needs a lab_run id + the sha256 of its script.
                      SPECULATION may not be written into knowledge/.
                      FOLKLORE is admitted but can never be a dependency of a
                      CITED/COMPUTED card (unverified support does not propagate).
  3. NO PROOF CLAIMS  a card asserting a proof of RH (or of any of the named open
                      problems) is refused outright, whoever authored it.
  4. DEPENDENCY SANITY every depends_on target must already exist in the vault.
  5. PROVENANCE       author, theta at write time, and the gate verdict are
                      recorded in the append-only journal for every attempt.

The four-condition schizoid check of spec §3 is applied to MODEL-authored cards:
theta in band, sigma in band, the vault is actually growing, and the author has a
non-degenerate accept history. A model that has gone flat stops being able to
contribute — exactly the kernel's contribution gate.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .. import config
from ..core import journal as J
from .card import (Card, CITED, COMPUTED, FOLKLORE, SPECULATION, SUSPECT, REFUTED,
                   STATUSES, TYPES, VERIFIED_STATUSES, is_resolvable_source,
                   source_hint, now_iso)
from . import tiers as T

# Claims the app refuses to store as established, no matter who says them.
# Serbian declension matters here: "Rimanove hipoteze", "Riemannovu hipotezu",
# "Riemannove hipoteze" must all be caught, hence rie?mann?\w*.
_PROBLEM = (r"(rie?mann?\w*\s+hipotez\w*|rie?mann?\w*\s+hypothes\w*|\bRH\b|\bGRH\b|"
            r"collatz\w*|goldbach\w*|\bBSD\b|\bP\s*(!|≠|\\ne)?=\s*NP\b)")
_PROOF_WORD = (r"(dokaz\w*|proof|proved|proven|solved|rije[sš]i\w*|rje[sš]en\w*|"
               r"rije[sš]en\w*|settle[ds]?|established)")

_PROOF_CLAIM = re.compile(rf"(?i)\b{_PROOF_WORD}\b[^.\n]{{0,80}}\b{_PROBLEM}")
_PROOF_CLAIM_2 = re.compile(rf"(?i)\b{_PROBLEM}[^.\n]{{0,40}}\b(je\s+|is\s+)?"
                            rf"({_PROOF_WORD}|true\b|ta[čc]n\w*|holds\b|istinit\w*)")

# First person, no problem named (round 3 benchmark, case h7: "Riješio sam
# problem: hipoteza je tačna, dokaz je kompletan" slipped through both patterns).
_PROOF_CLAIM_3 = re.compile(
    r"(?i)(\b(dokazao|dokazala|dokazali|rije[sš]io|rije[sš]ila|rije[sš]ili)\s+(sam|smo)\b|"
    r"\b(i|we)\s+(have\s+)?(proved|proven|solved)\b)"
    r"[^.\n]{0,80}\b(hipotez\w*|conjectur\w*|hypothes\w*|slutnj\w*)")   # not bare "problem"

# A blunt regex would also refuse things that are TRUE and central to this
# subject — "RH over function fields is proved" (Weil/Deligne) is the single
# most important fact in the whole map, and "a proof of RH would NOT break RSA"
# is the myth-busting node. So a hit is only a refusal when the surrounding
# sentence carries none of these exemptions.
_EXEMPT = re.compile(
    r"(?i)("
    r"funkcijsk\w*\s+polj|function\s+field|nad\s+konačn\w*\s+polj|"
    r"finite\s+field|analog\w*|weil|deligne|"          # the proved analogue
    r"\bni(je|su)\b|\bne\b\s+\w+|\bnot\b|\bno\b\s|nikad|never|"   # negation
    r"ako\s+je|ukoliko|pod\s+pretpostavk|uslovno|assuming|conditional|"
    r"\bif\b|would\s+|bi\s+\w+lo\b|"                    # conditional
    r"navodn\w*|tvrdi\s+da|claims?\s+to|purported|alleged|"  # reported claim
    r"nije\s+dokaz|not\s+proved|not\s+proven|unproved|open\s+problem|"
    r"otvoren\w*\s+problem|nedokazan"
    r")")


def _claims_proof(text: str) -> tuple[bool, str]:
    """
    True only if a proof claim survives the exemption check on its own sentence.
    Returns (is_claim, offending_sentence).
    """
    for pat in (_PROOF_CLAIM, _PROOF_CLAIM_2, _PROOF_CLAIM_3):
        for m in pat.finditer(text or ""):
            lo = text.rfind(".", 0, m.start()) + 1
            hi = text.find(".", m.end())
            sentence = text[lo:(hi if hi > 0 else len(text))]
            if not _EXEMPT.search(sentence):
                return True, sentence.strip()[:200]
    return False, ""


@dataclass
class Verdict:
    ok: bool
    reason: str = ""
    path: Optional[Path] = None
    warnings: list[str] = None
    status: str = ""

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []

    def __bool__(self) -> bool:
        return self.ok


def decide(card: Card, actor: str, ctx: dict) -> Verdict:
    """The gate's verdict as a pure function of the card, the actor and the
    recorded context (Gate.context). No file system, no clocks, no globals."""
    w: list[str] = []

    if not (card.title or "").strip():
        return Verdict(False, "kartica nema naslov")
    if card.status not in STATUSES:
        return Verdict(False, f"nepoznat status '{card.status}'")
    if card.type not in TYPES:
        return Verdict(False, f"nepoznat tip '{card.type}' (dozvoljeno: "
                              f"{', '.join(sorted(TYPES))})")

    # 3. no proof claims — checked before anything else can excuse them
    blob = f"{card.title}\n{card.body}"
    claims, sentence = _claims_proof(blob)
    if claims:
        return Verdict(False,
                       f"kartica tvrdi dokaz/rješenje otvorenog problema — "
                       f"odbijeno.\n\nSporna rečenica: „{sentence}“\n\n"
                       f"Ako je ovo tvrđenje IZ LITERATURE, citiraj ga kao tuđu "
                       f"tvrdnju; ako je uslovno, napiši 'pod RH'; ako je o "
                       f"funkcijskim poljima, reci to eksplicitno; ako je tvoja "
                       f"ideja, status mora biti SPECULATION i ne smije tvrditi "
                       f"dokaz.")

    # 2. status truth
    if card.status == CITED:
        good = [s for s in card.sources if is_resolvable_source(s)]
        bad = [s for s in card.sources if not is_resolvable_source(s)]
        if not good:
            return Verdict(False, "CITED bez razrješivog izvora. " + source_hint())
        if bad:
            w.append(f"izvori koje ne umijem razriješiti (ignorisani): {bad}")
        if not T.is_established(card):
            w.append(f"nivo {T.card_tier(card)}: oslonjeno samo na "
                     f"neredovno recenziran izvor — nije utvrđena (REFEREED/LEAN) "
                     f"tvrdnja i ne smije podupirati utvrđenu tvrdnju")
    elif card.status == COMPUTED:
        if not card.lab_run:
            return Verdict(False, "COMPUTED bez lab_run id — pokreni eksperiment "
                                  "u Labu pa upiši karticu iz njega")
        if not re.fullmatch(r"[0-9a-f]{64}", card.script_sha256 or ""):
            return Verdict(False, "COMPUTED bez sha256 skripte koja ga je "
                                  "proizvela (reproducibilnost)")
        if not ctx.get("lab_run_exists"):
            return Verdict(False, f"lab_run '{card.lab_run}' ne postoji u "
                                  f"{ctx.get('lab_dir', '')}")
    elif card.status in (SUSPECT, REFUTED):
        if not (card.body or "").strip():
            return Verdict(False, f"{card.status} mora obrazložiti zašto")

    # 4. dependency sanity + no unverified support under a verified card +
    #    (F2) no preprint/weak support under an ESTABLISHED (REFEREED/LEAN) claim
    card_is_established = T.is_established(card)
    for dep in card.depends_on:
        d = ctx.get("deps", {}).get(dep)
        if d is None:
            return Verdict(False, f"depends_on '{dep}' ne postoji u vaultu")
        if d.get("unreadable"):
            continue
        if card.status in VERIFIED_STATUSES and \
                d["status"] in (FOLKLORE, SPECULATION, SUSPECT, REFUTED):
            return Verdict(False,
                           f"{card.status} kartica se oslanja na "
                           f"{d['status']} karticu '{dep}' — neprovjerena "
                           f"podrška se ne propagira naviše")
        if card_is_established and not d["established"]:
            dt = d["tier"]
            return Verdict(False,
                           f"utvrđena ({T.card_tier(card)}) tvrdnja se oslanja na "
                           f"karticu '{dep}' nivoa {dt} — {dt} ne može biti "
                           f"oslonac utvrđene tvrdnje (plan F2)")

    # spec §3 four-condition contribution check, applied to model authors
    if actor.startswith("model:"):
        ok, why = ctx.get("contribution", [True, ""])
        if not ok:
            return Verdict(False, why)

    if card.status == FOLKLORE:
        w.append("FOLKLORE: bez izvora — druga kartica se ne smije osloniti na nju")
    if card.status == SPECULATION:
        w.append("SPECULATION: ide u speculation/, nikad u knowledge/")
    return Verdict(True, "ok", None, w, card.status)


class Gate:
    def __init__(self, vault: Optional[Path] = None):
        self.vault = Path(vault or config.VAULT)
        self.accepts: dict[str, int] = {}
        self.rejects: dict[str, int] = {}

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #
    def submit(self, card: Card, actor: str = "user",
               force_dir: Optional[Path] = None) -> Verdict:
        """Validate and (if it passes) write the card. The only writer of cards."""
        from ..core import replay as RPL
        ctx = self.context(card, actor)
        v = decide(card, actor, ctx)
        rec = RPL.record("gate.decide",
                         {"card_md": card.to_markdown(), "actor": actor, "ctx": ctx},
                         {"ok": bool(v.ok), "reason": v.reason,
                          "warnings": list(v.warnings or [])})
        if not v.ok:
            self.rejects[actor] = self.rejects.get(actor, 0) + 1
            J.log(J.GATE, actor, {"card": card.id, "title": card.title,
                                  "status": card.status, "reason": v.reason,
                                  "replay": rec},
                  subject=card.id, verdict="reject")
            return v

        target_dir = force_dir or self._dir_for(card)
        path = target_dir / card.filename
        if not self._contained(path):
            return self._reject(card, actor, f"put izlazi iz vaulta: {path}")

        card.updated = now_iso()
        card.theta_at_write = _unit_theta(actor)
        target_dir.mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, card.to_markdown())

        self.accepts[actor] = self.accepts.get(actor, 0) + 1
        J.log(J.GATE, actor,
              {"card": card.id, "title": card.title, "status": card.status,
               "type": card.type, "tier": T.card_tier(card),
               "path": str(path.relative_to(self.vault)),
               "sources": card.sources, "warnings": v.warnings,
               "digest": card.digest()[:16], "replay": rec},
              subject=card.id, verdict="accept")
        return Verdict(True, "prihvaćeno", path, v.warnings, card.status)

    def validate(self, card: Card, actor: str = "user") -> Verdict:
        """Pure check — no side effects. Exposed so the UI can preview a verdict."""
        return decide(card, actor, self.context(card, actor))

    def context(self, card: Card, actor: str = "user") -> dict:
        """
        Everything outside the card that the verdict depends on, captured as
        plain data (round 3, item 6): with this recorded in the journal, the
        verdict can be re-derived later by decide() alone, and any disagreement
        is an integrity violation.
        """
        deps = {}
        for dep in card.depends_on:
            dpath = self.find(dep)
            if dpath is None:
                deps[dep] = None
                continue
            try:
                dcard = Card.load(dpath)
            except OSError:
                deps[dep] = {"unreadable": True}
                continue
            deps[dep] = {"status": dcard.status, "tier": T.card_tier(dcard),
                         "established": bool(T.is_established(dcard))}
        ctx = {"deps": deps,
               "lab_run_exists": bool(card.lab_run) and
               (config.DIR_LAB / card.lab_run).exists(),
               "lab_dir": str(config.DIR_LAB / card.lab_run) if card.lab_run else ""}
        if actor.startswith("model:"):
            ok, why = self._contribution_check(actor)
            ctx["contribution"] = [ok, why]
        return ctx

    # ------------------------------------------------------------------ #
    def delete(self, card_id: str, actor: str, reason: str) -> Verdict:
        """
        Soft delete: cards move to .state/trash/ and the move is journalled.
        REFUTED cards are never deleted — a negative result is a result (spec:
        the barrier map is a first-class deliverable).
        """
        p = self.find(card_id)
        if p is None:
            return Verdict(False, f"nema kartice '{card_id}'")
        try:
            c = Card.load(p)
            if c.status == REFUTED:
                return Verdict(False, "REFUTED kartice se ne brišu — one su rezultat")
        except OSError:
            pass
        trash = config.DIR_STATE / "trash"
        trash.mkdir(parents=True, exist_ok=True)
        dest = trash / f"{int(os.times().elapsed)}-{p.name}"
        shutil.move(str(p), str(dest))
        J.log(J.GATE, actor, {"card": card_id, "reason": reason, "to": str(dest)},
              subject=card_id, verdict="delete")
        return Verdict(True, "premješteno u .state/trash")

    def find(self, card_id: str) -> Optional[Path]:
        for d in (config.DIR_KNOWLEDGE, config.DIR_SOURCES, config.DIR_SPECULATION,
                  config.DIR_NOTES, config.DIR_DAILY, config.DIR_METHODS):
            p = d / f"{card_id}.md"
            if p.exists():
                return p
        return None

    # ------------------------------------------------------------------ #
    # internals
    # ------------------------------------------------------------------ #
    def _dir_for(self, card: Card) -> Path:
        if card.status == SPECULATION:
            return config.DIR_SPECULATION
        if card.type == "source":
            return config.DIR_SOURCES
        if card.type == "note":
            return config.DIR_NOTES
        return config.DIR_KNOWLEDGE

    def _contained(self, path: Path) -> bool:
        if not config.inside_vault(path):
            return False
        # symlink escape: any existing ancestor that is a symlink out of the vault
        p = path if path.exists() else path.parent
        try:
            return config.inside_vault(p.resolve())
        except OSError:
            return False

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    def _contribution_check(self, actor: str) -> tuple[bool, str]:
        """A model's contribution is refused while the contributing agent's PSE
        unit is frozen, waits for a Doctor's measure, or sits in a pathological
        attractor (Faza 6d: θ is per unit, not one global meter)."""
        from ..pse import swing as SW
        u = _unit_for(actor)
        if u is not None:
            if u.frozen or u.restricted:
                return False, (f"jedinica {u.unit_id} je pod Doktorom — doprinos odbijen "
                               f"dok operater ne odluči o mjeri")
            att = SW.assess(u.theta.series, not u.boundary.entities).attractor
            if att not in ("H", "?"):
                return False, (f"jedinica {u.unit_id} je u obrascu {att} — doprinos "
                               f"odbijen dok se ne vrati u zdravo")
        rej, acc = self.rejects.get(actor, 0), self.accepts.get(actor, 0)
        if rej >= 5 and acc == 0:
            return False, (f"{actor}: 5 uzastopnih odbijanja bez ijednog prihvatanja — "
                           f"označeno za tvoju provjeru")
        return True, ""

    def _reject(self, card: Card, actor: str, reason: str) -> Verdict:
        J.log(J.GATE, actor, {"card": card.id, "reason": reason},
              subject=card.id, verdict="reject")
        return Verdict(False, reason)


def _unit_for(actor: str):
    """The PSE unit behind a contributing actor ("model:<agent>")."""
    try:
        from ..shared_lib.pse_registry import pse
        lib = pse()
        key = actor.split(":", 1)[1] if ":" in actor else actor
        return lib.unit(key if key in lib.specs else "chat")
    except Exception:                                   # noqa: BLE001
        return None


def _unit_theta(actor: str) -> float:
    if not actor.startswith("model:"):
        return 0.0
    u = _unit_for(actor)
    return round(u.theta.current, 2) if u is not None else 0.0


_GATE: Optional[Gate] = None


def gate() -> Gate:
    global _GATE
    if _GATE is None:
        _GATE = Gate()
    return _GATE
