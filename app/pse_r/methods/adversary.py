"""
The adversarial mode (round 3, item 31; from the "three directions" skeleton,
Andrej 2026-10-25). The skeptic attacks a claim with WORDS; this attacks it with
NUMBERS — a deterministic search over one method's parameter space:

  (a) better B   — with the method's own conditions kept (the licence κ = 2B − 1,
                   x = 1/2, δ ∈ [dlo, 5/6]), is there a b giving a larger admissible
                   ℓ (smaller B) than the claim? If so, the claim is not the optimum.
  (b) breaks     — with κ set free, points that DO beat the claim; for each, which
                   condition it needs to break (the licence, or a wall of
                   Xu–Sang §6.2). That shows exactly what stands between the claim and
                   a better number.
  (c) emptiness certificate (direction A) — a STRICT statement in interval
                   arithmetic: for every ℓ ∈ [ℓ* + ε, 1/5] and every b in the search
                   box (κ = 2B(ℓ) − 1), some δ gives E > 0, so no admissible
                   parameters exist above B* down to B(1/5). Each cell of the box is
                   checked with mpmath.iv at one δ; cells that cannot be decided within
                   the budget are counted and the certificate then says PARTIAL.

Everything is plain Python on the method's own E (no model). Results go to the
human queue, onto the Grafovi plane (ℓ, B) as points, and into a lab run labelled
NAŠE-NERECENZIRANO. The limiters are respected (a "→ ∞" pause stops the search).
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import core as C

KIND = "adversary"                       # human queue + journal
POINTS_KEY = "adversary_points"          # (ℓ, B) points the Grafovi tab draws
B_RANGE = (0.0, 0.3)                     # the b box the optimiser itself searches
K_RANGE = (0.6, 0.9)


class Stop(Exception):
    pass


def _check(cancel: Optional[threading.Event]):
    if cancel is not None and cancel.is_set():
        raise Stop("prekinuto")
    try:
        from ..llm import limits as LIM
        if LIM.paused():
            raise Stop("„→ ∞“ pauza")
    except ImportError:
        pass


def family(name: str):
    """(E function, dlo, claimed B, source) for a registered method with an E."""
    from . import registry as R
    m = R.by_name(name)
    if m is None:
        raise KeyError(f"nema metode '{name}'")
    if m.system is not None:
        # a system-as-data pack has several E branches and its own B(ℓ); the search and
        # the certificate here assume the Liu/Xu–Sang geometry — say so, never pretend
        raise ValueError(f"metoda '{name}' je zadata kao podatak (sistem eksponenata) — "
                         "adversarijalni mod je zasad samo za Liu/Xu–Sang geometriju")
    Ef = {"liu": C.E_liu, "xs": C.E_xs}.get(m.family)
    if Ef is None:
        raise ValueError(f"metoda '{name}' nema funkciju eksponenta (vrsta '{m.family}') — "
                         "adversarijalni mod treba E(b, ℓ, κ, δ, x)")
    return Ef, m.dlo, m.claimed_B, m.source


def _l_licence(Ef, b: float, dlo: float) -> float:
    """Largest ℓ with max_δ E ≤ 0 when κ follows the licence κ = 2B(ℓ) − 1."""
    return C._bisect(lambda l: C.vmax(Ef, b, l, 2 * C.Bof(l) - 1, dlo), 0.0, 0.6)


def _l_free(Ef, b: float, k: float, dlo: float) -> float:
    return C._bisect(lambda l: C.vmax(Ef, b, l, k, dlo), 0.0, 0.6)


@dataclass
class Report:
    method: str
    claimed_B: float
    best_B: float = 1.0
    best_at: dict = field(default_factory=dict)
    better_than_claim: bool = False
    breaks: list = field(default_factory=list)            # free-κ points that beat the claim
    walls_at_best: dict = field(default_factory=dict)
    certificate: dict = field(default_factory=dict)
    seconds: float = 0.0
    curve: list = field(default_factory=list)             # (b, B_licence(b))

    def summary(self) -> str:
        c = self.certificate
        cert = ("certifikat: NEMA dopustivih parametara za B ∈ [{lo:.6f}, {hi:.9f}] ({n} ćelija{p})"
                .format(lo=c.get("B_low", 0), hi=c.get("B_high", 0), n=c.get("cells", 0),
                        p="" if c.get("complete") else f", NEODLUČENO {c.get('undecided', 0)} — DJELIMIČNO")
                if c else "certifikat nije rađen")
        head = (f"{self.method}: tvrđeno B = {self.claimed_B:.12f}; najbolje uz uslove metode "
                f"B = {self.best_B:.12f} → " + ("TVRDNJA NIJE OPTIMUM" if self.better_than_claim
                                                 else "tvrdnja odolijeva (u tačnosti pretrage)"))
        return f"{head}; {len(self.breaks)} tačaka bolje od tvrdnje traži kršenje uslova; {cert}"


def search(name: str, nb: int = 61, nk: int = 25, cancel=None, tol: float = 1e-9) -> Report:
    Ef, dlo, claimed, _src = family(name)
    t0 = time.perf_counter()
    rep = Report(name, claimed)
    l_claim = C.lof(claimed)
    # (a) the method's own conditions: licence, x = 1/2, δ ∈ [dlo, 5/6]
    best = (-1.0, None)
    for i in range(nb):
        _check(cancel)
        b = B_RANGE[0] + (B_RANGE[1] - B_RANGE[0]) * i / (nb - 1)
        l = _l_licence(Ef, b, dlo)
        rep.curve.append((b, C.Bof(l)))
        if l > best[0]:
            best = (l, b)
    step = (B_RANGE[1] - B_RANGE[0]) / (nb - 1)        # golden refinement around the best grid b
    lo_b, hi_b = max(B_RANGE[0], best[1] - step), min(B_RANGE[1], best[1] + step)
    b_star = C._gss_argmax(lambda bb: _l_licence(Ef, bb, dlo), lo_b, hi_b)
    l_star = _l_licence(Ef, b_star, dlo)
    if l_star < best[0]:
        l_star, b_star = best
    k_star = 2 * C.Bof(l_star) - 1
    rep.best_B = C.Bof(l_star)
    rep.best_at = {"b": b_star, "l": l_star, "k": k_star, "x": 0.5}
    rep.better_than_claim = rep.best_B < claimed - tol
    rep.walls_at_best = {k: v for k, v in C.walls(rep.best_B, l_star, b_star, k_star).items()}
    # (b) κ set free: what beats the claim, and what it has to break
    for i in range(nb // 4 + 1):
        b = B_RANGE[0] + (B_RANGE[1] - B_RANGE[0]) * i / max(1, nb // 4)
        for j in range(nk):
            _check(cancel)
            k = K_RANGE[0] + (K_RANGE[1] - K_RANGE[0]) * j / (nk - 1)
            l = _l_free(Ef, b, k, dlo)
            if l > l_claim + 1e-7:
                B = C.Bof(l)
                broken = C.broken_walls(B, l, b, k)
                if abs(k - (2 * B - 1)) > 1e-6:
                    broken = ["licenca κ=2B−1"] + broken
                rep.breaks.append({"b": b, "k": k, "l": l, "B": B, "krši": broken})
    rep.breaks.sort(key=lambda r: r["B"])
    rep.seconds = time.perf_counter() - t0
    return rep


def certify_empty(name: str, l_star: float, eps: float = 1e-6, l_hi: float = 0.2,
                  max_cells: int = 20000, cancel=None) -> dict:
    """Strict: for all ℓ ∈ [ℓ*+ε, l_hi] and b ∈ B_RANGE (κ = 2B(ℓ)−1, x = 1/2) there is a
    δ with E > 0 — checked cell by cell in interval arithmetic (mpmath.iv)."""
    from mpmath import iv
    Ef, dlo, _claimed, _src = family(name)
    t0 = time.perf_counter()
    todo = [(B_RANGE[0], B_RANGE[1], l_star + eps, l_hi)]
    done, undecided, evals = 0, [], 0
    while todo:
        _check(cancel)
        b0, b1, l0, l1 = todo.pop()
        bc, lc = (b0 + b1) / 2, (l0 + l1) / 2
        kc = 2 * C.Bof(lc) - 1
        d = C._gss_argmax(lambda dd: Ef(bc, lc, kc, dd, 0.5), dlo, 5 / 6)
        bI, lI = iv.mpf([b0, b1]), iv.mpf([l0, l1])
        kI = 2 * (iv.mpf(11) / 12 - lI / 4) - 1
        try:
            v = Ef(bI, lI, kI, iv.mpf(d), iv.mpf(0.5))
            lower = float(v.a)
        except Exception:                               # noqa: BLE001 — e.g. 0 in a divisor
            lower = float("-inf")
        evals += 1
        if lower > 0:
            done += 1
            continue
        if done + len(todo) + len(undecided) >= max_cells or (b1 - b0) < 1e-6:
            undecided.append((b0, b1, l0, l1))
            continue
        if (b1 - b0) / (B_RANGE[1] - B_RANGE[0]) >= (l1 - l0) / (l_hi - l_star):
            todo += [(b0, bc, l0, l1), (bc, b1, l0, l1)]
        else:
            todo += [(b0, b1, l0, lc), (b0, b1, lc, l1)]
    return {"l_range": [l_star + eps, l_hi], "b_range": list(B_RANGE),
            "B_high": C.Bof(l_star + eps), "B_low": C.Bof(l_hi),
            "cells": done, "undecided": len(undecided), "complete": not undecided,
            "evals": evals, "seconds": time.perf_counter() - t0,
            "assumptions": ["κ = 2B − 1 (licenca)", "x = 1/2 (validirana kritična tačka)",
                            f"δ ∈ [{dlo:g}, 5/6]", f"b ∈ [{B_RANGE[0]:g}, {B_RANGE[1]:g}]"]}


def run(name: str, certificate: bool = True, cancel=None, nb: int = 61, nk: int = 25,
        eps: float = 1e-6, max_cells: int = 20000) -> Report:
    from ..pse import measure as PM
    from ..pse import path as PATH
    ok, why = PATH.may_act("adversary")
    if not ok:                                          # Faza 6d: a frozen unit does not act
        raise PATH.Refused(f"adversarijalni mod: {why}")
    rep = search(name, nb, nk, cancel)
    if certificate:
        rep.certificate = certify_empty(name, rep.best_at["l"], eps=eps, max_cells=max_cells,
                                        cancel=cancel)
    acts = [PM.Action("pretraga prostora parametara", "f")]
    if certificate:
        acts.append(PM.Action("certifikat praznine", "f"))
    PATH.work("adversary", acts, entity=(f"metoda:{name}", "document"),
              note=f"bolje={rep.better_than_claim}")
    return rep


# --------------------------------------------------------------------------- #
# where the results go: queue, Grafovi points, journal
# --------------------------------------------------------------------------- #
def publish(rep: Report, run_id: str = "") -> str:
    """Queue the finding for the operator, put the points on the Grafovi plane."""
    from ..core import journal as J
    from ..shared_lib.store import store
    pts = store().kv_get(POINTS_KEY) or []
    pts = [p for p in pts if p.get("method") != rep.method]
    pts.append({"method": rep.method, "l": rep.best_at.get("l"), "B": rep.best_B,
                "kind": "kontraprimjer" if rep.better_than_claim else "najbolje uz uslove"})
    for br in rep.breaks[:3]:
        pts.append({"method": rep.method, "l": br["l"], "B": br["B"],
                    "kind": "krši: " + ", ".join(br["krši"][:2])})
    store().kv_set(POINTS_KEY, pts)
    c = rep.certificate
    cert = ("certifikat kompletan do B = {:.9f}".format(c["B_high"]) if c.get("complete")
            else "certifikat DJELIMIČAN" if c else "bez certifikata")
    title = (f"Adversarijalni nalaz: {rep.method} — TVRDNJA NIJE OPTIMUM (B = {rep.best_B:.12f})"
             if rep.better_than_claim else
             f"Adversarijalna provjera: {rep.method} — tvrdnja odolijeva; "
             f"{len(rep.breaks)} boljih tačaka traži kršenje uslova; {cert}")
    pid = store().propose(KIND, title, {"method": rep.method, "summary": rep.summary(),
                                        "best_B": rep.best_B, "claimed_B": rep.claimed_B,
                                        "better": rep.better_than_claim, "run_id": run_id,
                                        "certificate": rep.certificate,
                                        "breaks": rep.breaks[:10]}, proposer="adversary")
    J.log(J.METHOD, "adversary", {"event": "attacked", "method": rep.method,
                                  "better": rep.better_than_claim, "best_B": rep.best_B,
                                  "breaks": len(rep.breaks),
                                  "certificate_complete": rep.certificate.get("complete"),
                                  "run_id": run_id, "label": "NAŠE-NERECENZIRANO"},
          subject=rep.method, verdict="countered" if rep.better_than_claim else "withstood")
    return pid


_LAST: dict = {}                         # method → last Report (the lab run fills it)


def attack(name: str, eps: float = 1e-6) -> dict:
    """The whole thing: a lab run (PNG, card, NAŠE-NERECENZIRANO), then the queue item
    and the Grafovi points. Returns {"run_id", "pid", "summary"}."""
    from ..lab import runner as LR
    fam = {"liu": 0, "xs": 1}
    from . import registry as R
    m = R.by_name(name)
    if m is None or m.system is not None or m.family not in fam:
        family(name)                                    # raises with the honest reason
    res = LR.run("qrh_adversary", {"family": fam[m.family], "eps_exp": int(round(-__import__("math").log10(eps)))},
                 make_card=True)
    rep = _LAST.get(name)
    run_id = res["record"]["run_id"]
    pid = publish(rep, run_id)
    return {"run_id": run_id, "pid": pid, "summary": rep.summary()}


def attack_in_background(name: str) -> Optional[threading.Thread]:
    """After a method passes the door: attack it without blocking the window."""
    try:
        family(name)
    except (KeyError, ValueError) as e:
        from ..core import journal as J
        J.log(J.METHOD, "adversary", {"event": "skipped", "method": name, "why": str(e)[:200]},
              subject=name, verdict="skipped")
        return None

    def work():
        try:
            attack(name)
        except Exception as e:                          # noqa: BLE001
            from ..core import journal as J
            J.log(J.METHOD, "adversary", {"event": "failed", "method": name, "error": str(e)[:300]},
                  subject=name, verdict="failed")
    t = threading.Thread(target=work, name=f"adversary-{name}", daemon=True)
    t.start()
    return t


def _on_decision(item: dict, approved: bool) -> None:
    """Approved = the operator takes the finding into the mission as a step."""
    if not approved:
        return
    from ..shared_lib import missions as MIS
    p = item["payload"]
    m = MIS.get(MIS.FIRST_ID)
    if m is None:
        return
    MIS.step(MIS.FIRST_ID, f"adversarijalni mod nad metodom {p['method']}",
             ("NAĐENO bolje B (tvrdnja nije optimum)" if p.get("better") else "tvrdnja odolijeva")
             + " — NAŠE-NERECENZIRANO", m["state"], ref=p.get("run_id") or p["method"])


def install_hooks() -> None:
    from ..shared_lib.store import store
    store().on_decision(KIND, _on_decision)
