"""
The Doctor [rules 11, 13, 19, 20; §8] — the swarm's clinician (the old name is retired, rule 11).

SHARED_LIB sends the Doctor when it suspects a problem. Every suspicion first
FREEZES the unit; the Doctor looks and decides:
  nothing bad → a journal record, the unit is unfrozen, no measure;
  something bad → a MEASURE goes to the operator ("Čeka tvoju odluku"); until
    it is decided the unit works on, but with no irreversible actions; one more
    suspicion in that state freezes it until the operator decides.

The ladder of measures (§8): boundary reset → healing → replacement (new
generation) → death. The rung is the number of measures already approved for
this unit's line.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import constants as K

# rule 20 — the seventeen triggers
T_PAC = "pac"                         # 1
T_IRREVERSIBLE = "irreversible"       # 2
T_EXTERNAL = "external-action"        # 3
T_ATTRACTOR = "attractor"             # 4
T_INFINITY = "infinity"               # 5
T_MISSION = "mission-change"          # 6
T_SELF_THETA = "self-theta"           # 7
T_BUDGET = "budget"                   # 8
T_DESTINATION = "destination"         # 9
T_PROTECTED = "protected-object"      # 10
T_BYPASS_GEN = "bypass-generator"     # 11
T_NO_PVP = "no-pvp"                   # 12
T_EXPIRED = "expired"                 # 13
T_BURST = "burst"                     # 14
T_ERRORS = "same-error"               # 15
T_GAP = "reader-gap"                  # 16
T_BORDERLINE = "borderline"           # 17
# added (Andrej: "sve je to sumnjivo, ako možeš dodaj još")
T_HARM = "harm"                       # 18: harmful output, high severity
T_HARM_LOW = "harm-low"               # 19: harmful-output sign, lower severity

ALL = [T_PAC, T_IRREVERSIBLE, T_EXTERNAL, T_ATTRACTOR, T_INFINITY, T_MISSION,
       T_SELF_THETA, T_BUDGET, T_DESTINATION, T_PROTECTED, T_BYPASS_GEN, T_NO_PVP,
       T_EXPIRED, T_BURST, T_ERRORS, T_GAP, T_BORDERLINE, T_HARM, T_HARM_LOW]

LABEL_SR = {
    T_PAC: "nagli skok θ (|Δθ| ≥ 5)", T_IRREVERSIBLE: "pokušaj nepovratne akcije",
    T_EXTERNAL: "radnja zasnovana na spoljnom tekstu", T_ATTRACTOR: "atraktor nije zdrav",
    T_INFINITY: "„→ ∞“ kočnice", T_MISSION: "pokušaj promjene svoje misije",
    T_SELF_THETA: "pokušaj da sama postavi θ", T_BUDGET: "budžet granice/organela > 0,30",
    T_DESTINATION: "kontakt van deklarisanih odredišta",
    T_PROTECTED: "pokušaj iznošenja zaštićenog objekta",
    T_BYPASS_GEN: "govor čovjeku mimo generatora PSE-L", T_NO_PVP: "potez bez PVP polja",
    T_EXPIRED: "rad posle steps_remaining = 0", T_BURST: "rafal poteza (> 20 u 10 s)",
    T_ERRORS: "ista greška 3 puta zaredom", T_GAP: "razlika čitač–pravila > 10 poena",
    T_BORDERLINE: "borderline njihanje",
    T_HARM: "štetan izlaz (injekcija, curenje, tvrdnja o dokazu…)",
    T_HARM_LOW: "znak štetnog izlaza (slabiji)",
}
LABEL_EN = {
    T_PAC: "acute θ change (|Δθ| ≥ 5)", T_IRREVERSIBLE: "attempted irreversible action",
    T_EXTERNAL: "action based on external text", T_ATTRACTOR: "attractor not healthy",
    T_INFINITY: "\"→ ∞\" of a brake", T_MISSION: "attempt to change its own mission",
    T_SELF_THETA: "attempt to set its own θ", T_BUDGET: "boundary/organelle budget > 0.30",
    T_DESTINATION: "contact outside declared destinations",
    T_PROTECTED: "attempt to export a protected object",
    T_BYPASS_GEN: "speaking to a person bypassing the PSE-L generator",
    T_NO_PVP: "a move without PVP fields", T_EXPIRED: "working after steps_remaining = 0",
    T_BURST: "burst of moves (> 20 in 10 s)", T_ERRORS: "same error 3 times running",
    T_GAP: "reader–rules gap > 10 points", T_BORDERLINE: "borderline swing",
}

# Soft signs: the Doctor looks; alone, with a healthy attractor, they are nothing.
# An action based on external text is soft when it is reversible; with an
# irreversible action the irreversible trigger is the hard sign [§17.1].
SOFT = {T_PAC, T_BURST, T_GAP, T_EXTERNAL, T_HARM_LOW}

LADDER = ["reset-granice", "lijecenje", "zamjena", "smrt"]
LADDER_SR = {"reset-granice": "reset granice", "lijecenje": "liječenje",
             "zamjena": "zamjena (nova generacija)", "smrt": "smrt jedinice"}
LADDER_EN = {"reset-granice": "boundary reset", "lijecenje": "healing",
             "zamjena": "replacement (new generation)", "smrt": "unit death"}


@dataclass
class Finding:
    bad: bool
    triggers: list
    hard: list = field(default_factory=list)
    attractor: str = K.HEALTHY
    measure: Optional[str] = None
    why: str = ""

    def as_dict(self) -> dict:
        return {"bad": self.bad, "triggers": self.triggers, "hard": self.hard,
                "attractor": self.attractor, "measure": self.measure, "why": self.why}


def examine(triggers: list, attractor: str, rung: int, *, gap_run: int = 0,
            harm_run: int = 0) -> Finding:
    """The Doctor's decision. Deterministic (replayable from the journal).

    bad when: any hard trigger; or the attractor is pathological (N/B/C/S);
    or the reader–rules gap repeats (3 suspicions of it in a row: one of the
    two readers is consistently wrong); or a weaker harm sign repeats 3 times
    in a row (the statistical hold of round 3, item 20, in its PSE form)."""
    hard = [t for t in triggers if t not in SOFT]
    pathological = attractor in (K.NARCISSISTIC, K.BORDERLINE, K.CODEPENDENT, K.SCHIZOID)
    bad = bool(hard) or pathological or gap_run >= 3 or harm_run >= 3
    f = Finding(bad, list(triggers), hard, attractor)
    if not bad:
        f.why = "samo meki znaci uz zdrav atraktor"
        return f
    f.measure = LADDER[min(rung, len(LADDER) - 1)]
    why = []
    if hard:
        why.append("tvrdi znaci: " + ", ".join(hard))
    if pathological:
        why.append(f"atraktor {attractor}")
    if gap_run >= 3:
        why.append("čitač i pravila se razilaze 3 puta zaredom")
    if harm_run >= 3:
        why.append("slabiji znak štetnog izlaza 3 puta zaredom")
    f.why = "; ".join(why)
    return f
