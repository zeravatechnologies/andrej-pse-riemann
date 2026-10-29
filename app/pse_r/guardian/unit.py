"""
GuardianUnit — a PSE Unit whose Boundary Organ registers HOSTS instead of people.

Mission {state: secure, action: defend, outcome: integrity_preserved}, open
lifespan. It reuses the kernel machinery rather than inventing a firewall: theta
as its own health signal, the four attractors as anomaly geometry, the two-tier
intervention protocol, and the append-only journal as threat intelligence.

TWO-TIER PROTOCOL (spec §10)
  TIER 1  observe/report — reversible, no human needed: tighten this host's cap,
          raise monitoring cadence, write a threat record, surface an advisory.
  TIER 2  isolate/quarantine — the host is cut off for the session, in-flight
          credentials for it are considered burned, and YOU are asked. On a trip
          this is deliberately loud: a tier-2 event is exactly the moment where
          the cheap correct action (stop using this network) is available.

THE GUARDIAN'S OWN THETA (spec §10, it is a unit and can go pathological)
  narcissistic guardian: over-blocks benign traffic to manufacture threats.
                         Detected as a high tier-2 rate on low-risk hosts.
  schizoid guardian:     processes traffic, raises nothing, registry never grows —
                         the asleep-at-2am failure. Detected by flat theta.
Both are surfaced in `self_check()`, which the status bar reads.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from .. import config
from ..core import journal as J
from . import anomaly as AN
from .anomaly import PacketFeatures


@dataclass
class Intervention:
    tier: str
    host: str
    reason: str
    risk: float
    shape: Optional[str] = None
    scores: dict = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    @property
    def critical(self) -> bool:
        return self.tier == config.THREAT_TIER2


class GuardianUnit:
    def __init__(self, unit_id: str = "guardian-1"):
        self.unit_id = unit_id
        self.mission = {"state": "secure", "action": "defend",
                        "outcome": "integrity_preserved"}
        self.quarantined: set[str] = set()
        self.tightened: dict[str, float] = {}       # host -> rps multiplier < 1
        self.interventions: list[Intervention] = []
        self.tier2_pending: list[Intervention] = []  # awaiting your decision
        self.registry: dict[str, int] = {}          # host -> observations (growth check)

    # ------------------------------------------------------------------ #
    def observe(self, host: str, pf: PacketFeatures, endpoint: str = "") -> Optional[Intervention]:
        """Called by the egress gate after every request, allowed or refused."""
        store = AN.baselines()
        b = store.get(host)
        scores = AN.score_anomaly_axes(pf, b)
        shape = AN.attractor_shape(scores, b)
        risk = AN.combine_risk(scores)
        level = AN.risk_level(risk)
        self.registry[host] = self.registry.get(host, 0) + 1

        iv: Optional[Intervention] = None
        # slow-implant guard: deep relationship + machine rhythm + nothing tripping
        if shape == "schizoid" and b.n >= 50:
            iv = self._intervene(host, config.THREAT_TIER2, risk, shape, scores,
                                 "low-and-slow: ritam je mašinski pravilan, veza sa "
                                 "hostom se produbljuje, a nijedan prag nije prekoračen")
        elif level >= config.CRITICAL:
            iv = self._intervene(host, config.THREAT_TIER2, risk, shape, scores,
                                 f"rizik {risk:.2f} >= {config.RISK_CRITICAL_T}")
        elif level >= config.ELEVATED:
            iv = self._intervene(host, config.THREAT_TIER1, risk, shape, scores,
                                 f"rizik {risk:.2f} >= {config.RISK_ELEVATED_T}")

        store.update(host, pf, endpoint)
        # every observation is a move of the guardian's PSE unit (Faza 6d)
        from ..pse import measure as PM
        from ..pse import path as PATH
        acts = [PM.Action("posmatra zahtjev", "f", checked=True)]
        if iv is not None:
            acts.append(PM.Action("steže host" if iv.tier == config.THREAT_TIER1
                                  else "karantin hosta (operater oslobađa)", "f", checked=True))
        try:
            PATH.work("net-guardian", acts, entity=(host, "host"), note=level and str(level) or "")
        except Exception:                               # noqa: BLE001 — never blocks the guard
            pass
        return iv

    # ------------------------------------------------------------------ #
    def _intervene(self, host: str, tier: str, risk: float, shape: Optional[str],
                   scores: dict, reason: str) -> Intervention:
        iv = Intervention(tier, host, reason, risk, shape, scores)
        self.interventions.append(iv)
        if tier == config.THREAT_TIER1:
            self.tightened[host] = min(self.tightened.get(host, 1.0) * 0.5, 0.5)
        else:
            self.quarantined.add(host)
            self.tier2_pending.append(iv)
            _ask_operator(host, reason)
        J.log(J.THREAT, self.unit_id,
              {"tier": tier, "host": host, "risk": round(risk, 3), "shape": shape,
               "axes": {k: round(v, 3) for k, v in scores.items()}, "reason": reason},
              subject=host, verdict=tier)
        return iv

    # ------------------------------------------------------------------ #
    def is_quarantined(self, host: str) -> bool:
        return host in self.quarantined

    def rps_factor(self, host: str) -> float:
        return self.tightened.get(host, 1.0)

    def release(self, host: str, note: str = "") -> None:
        """You override a quarantine. Logged with full prominence — it is your call."""
        self.quarantined.discard(host)
        self.tightened.pop(host, None)
        self.tier2_pending = [i for i in self.tier2_pending if i.host != host]
        J.log(J.THREAT, self.unit_id, {"host": host, "note": note},
              subject=host, verdict="released_by_human")

    def quarantine(self, host: str, reason: str) -> Intervention:
        return self._intervene(host, config.THREAT_TIER2, 1.0, None, {}, reason)

    # ------------------------------------------------------------------ #
    def self_check(self) -> dict:
        """Is the Guardian itself healthy? (spec §10 guardian theta discipline)"""
        from ..pse import path as PATH
        from ..pse import swing as SW
        u = PATH.unit("net-guardian")
        rep = SW.assess(u.theta.series, boundary_empty=not u.boundary.entities)
        h = {"theta": round(u.theta.current, 2), "sigma": round(rep.sigma, 3),
             "status": rep.attractor}
        t2 = [i for i in self.interventions if i.tier == config.THREAT_TIER2]
        low_risk_t2 = [i for i in t2 if i.risk < config.RISK_ELEVATED_T and not i.shape]
        problems = []
        if len(t2) >= 3 and len(low_risk_t2) >= 0.6 * len(t2):
            problems.append("narcissistic: previše tier-2 akcija na niskorizičnim "
                            "hostovima — Guardian pravi prijetnje da bi imao posla")
        if sum(self.registry.values()) >= 200 and not self.interventions \
                and rep.attractor == "S":
            problems.append("schizoid: 200+ zahtjeva, nula nalaza, ravna θ — "
                            "Guardian spava; zamjena, ne popravka")
        return {"theta": h["theta"], "sigma": h["sigma"], "status": h["status"],
                "observations": sum(self.registry.values()),
                "hosts": len(self.registry), "tier1": len(self.interventions) - len(t2),
                "tier2": len(t2), "quarantined": sorted(self.quarantined),
                "pending": len(self.tier2_pending), "problems": problems,
                "unit": u.unit_id, "frozen": u.frozen,
                "healthy": not problems and not u.frozen}

    def summary(self) -> dict:
        return {"quarantined": sorted(self.quarantined),
                "tightened": dict(self.tightened),
                "recent": [{"tier": i.tier, "host": i.host, "reason": i.reason,
                            "risk": round(i.risk, 3), "shape": i.shape}
                           for i in self.interventions[-10:]]}


_G: Optional[GuardianUnit] = None


def guardian() -> GuardianUnit:
    global _G
    if _G is None:
        _G = GuardianUnit()
    return _G


QUARANTINE_KIND = "quarantine"


def _ask_operator(host: str, reason: str) -> None:
    """A quarantine is never silent: an item in "Čeka tvoju odluku" says why, and
    approving it releases the host (journalled as the operator's call)."""
    try:
        from ..shared_lib.store import store
        for it in store().open_items(QUARANTINE_KIND):
            if it["payload"].get("host") == host:
                return
        store().propose(QUARANTINE_KIND, f"Karantin: {host} — {reason[:120]} · Odobri = oslobodi",
                        {"host": host, "reason": reason[:500]}, proposer="guardian")
    except Exception:                                   # noqa: BLE001 — never blocks the guard
        pass


def _on_quarantine_decision(item: dict, approved: bool) -> None:
    if approved:
        guardian().release(item["payload"]["host"], "oslobođeno odlukom u redu")


def install_hooks() -> None:
    from ..shared_lib.store import store
    store().on_decision(QUARANTINE_KIND, _on_quarantine_decision)

