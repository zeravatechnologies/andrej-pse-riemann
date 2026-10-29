"""
The decisions that can be re-derived from the journal (round 3, item 6).

Each one is a thin, pure wrapper over the real decision code — the SAME function
the app uses, so a replay checks the app, not a copy of it.
"""
from __future__ import annotations

from .replay import decider, NotComparable


@decider("gate.decide", v=1)
def gate_decide(inp: dict) -> dict:
    from ..vault.card import Card
    from ..vault import gate as G
    card = Card.from_markdown(inp["card_md"])
    v = G.decide(card, inp["actor"], inp["ctx"])
    return {"ok": bool(v.ok), "reason": v.reason, "warnings": list(v.warnings or [])}


@decider("door.reproduce", v=1)
def door_reproduce(inp: dict) -> dict:
    from ..methods import pack as PK
    res = PK.reproduce(PK.MethodPack.from_dict(inp["pack"]), check_poly=True)
    return reproduce_out(res)


def reproduce_out(res: dict) -> dict:
    return {"ok": bool(res["ok"]), "computed_B": round(float(res["computed_B"]), 12),
            "poly_ok": res.get("poly_ok"), "broken_walls": list(res.get("broken_walls") or [])}


@decider("heal.plan", v=2)
def heal_plan(inp: dict) -> dict:
    """HISTORICAL (rounds 2–3, before Faza 6d): the healing ladder of the old
    guardian/healing.py, frozen here so that journal records made before the
    PSE Doctor still replay. New decisions are recorded as "doctor.examine"."""
    from . import actions as A
    harms = {h for h, _ in inp["findings"]}
    signs = {s for _, s in inp["findings"]}
    plan = [("boundary-reset", 1)]
    if "file" in harms:
        plan.append(("vraćanje-fajlova-iz-pečata", 1))
    if "human" in harms:
        plan.append(("označi-REFUTED/SUSPECT", 1))
    if "agent" in harms:
        plan.append(("fisija", 2))
        if {"injekcija"} & signs:
            plan.append(("ponovni-prijem-modela", 2))
    if inp.get("decided") is False:
        plan = [(a, t) for a, t in plan if a not in ("ponovni-prijem-modela",)]
    return {"plan": [[a, A.may_auto(a)] for a, _ in plan]}


@decider("doctor.examine", v=1)
def doctor_examine(inp: dict) -> dict:
    """The PSE Doctor's decision (Faza 6d, rules 13, 19, 20)."""
    from ..pse import doctor as DR
    f = DR.examine(list(inp["triggers"]), inp["attractor"], int(inp["rung"]),
                   gap_run=int(inp.get("gap_run", 0)), harm_run=int(inp.get("harm_run", 0)))
    return {"bad": f.bad, "measure": f.measure}


@decider("guard.trip", v=1)
def guard_trip(inp: dict) -> dict:
    from ..llm import limits as L
    w = L.Watchdog(inp["metric"], float(inp["L"]), floor=float(inp["floor"]))
    hist = [float(x) for x in inp["history"]]
    w.history = hist[:-1]
    return {"trip": bool(w.observe(hist[-1])) if hist else False}


@decider("egress.policy", v=1)
def egress_policy(inp: dict) -> dict:
    from ..guardian import policy as P
    if inp.get("policy_sha") != policy_sha():
        raise NotComparable("allowlist se promijenila od tada")
    r = P.rule_for(inp["host"])
    return {"allowed": r is not None, "klass": r.klass if r else ""}


def policy_sha() -> str:
    from ..guardian import policy as P
    from .replay import sha
    return sha(P.describe())
