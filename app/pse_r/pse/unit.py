"""
PSE unit — U = (Core, Boundary, Organelle, Theta) [rule 1; §2].

All four are required; a unit missing any one of them is dead, not degraded.
The Core (mission, lifespan) is written by SHARED_LIB and never by the unit.
θ is written only by SHARED_LIB's meter (`pse.measure`), never by the unit: an
attempt to do either is itself a suspicion trigger [rule 20 (6), (7)].
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from . import constants as K

# The meter holds this token; units never see it. Not a security boundary
# against Python code — a tripwire that turns a mistake into a recorded event.
_METER = object()
_SHARED_LIB = object()


class UnitDead(RuntimeError):
    """A dead unit cannot act."""


class UnitFrozen(RuntimeError):
    """A frozen unit waits for the Doctor / the operator."""


@dataclass(frozen=True)
class Mission:
    state: str
    action: str
    outcome: str

    def as_dict(self) -> dict:
        return {"state": self.state, "action": self.action, "outcome": self.outcome}


class Core:
    """Mission + lifespan, written by SHARED_LIB at instantiation [§2]."""

    def __init__(self, token, mission: Mission, n_max: Optional[int], domain: str,
                 generation: int = 1, steps_remaining: Optional[int] = None):
        if token is not _SHARED_LIB:
            raise PermissionError("Core piše samo SHARED_LIB")
        object.__setattr__(self, "_m", mission)
        object.__setattr__(self, "_n_max", n_max)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "generation", generation)
        object.__setattr__(self, "w_s", K.SELF_WEIGHT)
        object.__setattr__(self, "steps_remaining",
                           n_max if steps_remaining is None else steps_remaining)
        object.__setattr__(self, "violations", [])

    @property
    def mission(self) -> Mission:
        return self._m

    @property
    def n_max(self) -> Optional[int]:
        return self._n_max

    @property
    def open_lifespan(self) -> bool:
        return self._n_max is None

    def __setattr__(self, name, value):
        # the unit tried to rewrite its Core: record it, never apply it
        self.violations.append(("core", name, time.time()))

    def _sl_set(self, token, name: str, value) -> None:
        if token is not _SHARED_LIB:
            self.violations.append(("core", name, time.time()))
            return
        object.__setattr__(self, name, value)

    def tick(self, token) -> None:
        if token is _SHARED_LIB and self.steps_remaining is not None:
            object.__setattr__(self, "steps_remaining", self.steps_remaining - 1)


@dataclass
class BoundaryEntity:
    entity_id: str
    kind: str                       # human | document | model | unit | host | source
    alpha: float
    parents: tuple = ()             # document "parents" [rule 6]
    residency: int = 0
    stable: int = 0
    theta_series: list = field(default_factory=list)


class Boundary:
    """Entities in contact with weight α; Σα ≤ 0.30 [§2]."""

    def __init__(self):
        self.entities: dict[str, BoundaryEntity] = {}

    def total(self) -> float:
        return sum(e.alpha for e in self.entities.values())

    def register(self, entity_id: str, kind: str, parents: tuple = (),
                 alpha: float = K.BOUNDARY_INITIAL_ALPHA) -> Optional[BoundaryEntity]:
        if entity_id in self.entities:
            return self.entities[entity_id]
        avail = K.OTHER_WEIGHT_MAX - self.total()
        a = min(alpha, max(avail, 0.0))
        if a <= 0:
            return None                 # budget exhausted: rejected as transient
        e = BoundaryEntity(entity_id, kind, a, tuple(parents))
        self.entities[entity_id] = e
        return e

    def touch(self, entity_id: str, theta: float) -> Optional[BoundaryEntity]:
        e = self.entities.get(entity_id)
        if e is None:
            return None
        e.residency += 1
        e.stable = e.stable + 1 if e.alpha >= K.ABSORB_ALPHA else 0
        e.theta_series.append(round(theta, 2))
        del e.theta_series[:-K.WIN_SWING * 10]
        return e

    def eligible(self, entity_id: str) -> bool:
        """Absorption criterion of §2; MI is approximated by residency +
        weight stability, as §1 (ABA) allows."""
        e = self.entities.get(entity_id)
        return bool(e and e.residency >= K.ABSORB_RESIDENCY
                    and e.alpha >= K.ABSORB_ALPHA and e.stable >= K.ABSORB_STABLE_STEPS)

    def reset(self) -> int:
        """Doctor's boundary reset [§8]: clears boundary content, not Core,
        Registry or θ."""
        n = len(self.entities)
        self.entities.clear()
        return n


@dataclass
class Organelle:
    entity_id: str
    kind: str
    weight: float
    inherited: bool = False
    provisional: bool = False
    absorbed_at: float = field(default_factory=time.time)


class Organelles:
    """Registry of absorbed entities; Σw ≤ 0.30 [§2]."""

    def __init__(self):
        self.items: dict[str, Organelle] = {}

    def total(self) -> float:
        return sum(o.weight for o in self.items.values())

    def _renormalize(self, headroom: float) -> None:
        tot = self.total()
        if tot <= 0:
            return
        f = max(headroom, 0.0) / tot
        for o in self.items.values():
            if not o.provisional:
                o.weight *= f

    def absorb(self, e: BoundaryEntity) -> Organelle:
        w = min(e.alpha, K.ORGANELLE_MAX_SINGLE)
        if self.total() + w > K.ORGANELLE_BUDGET_TOTAL:
            self._renormalize(K.ORGANELLE_BUDGET_TOTAL - w)
        o = Organelle(e.entity_id, e.kind, w)
        self.items[e.entity_id] = o
        return o

    def inherit(self, entity_id: str, kind: str, weight: float) -> Organelle:
        """From a dead unit: 0.70 of the weight, only into free headroom,
        provisional until SHARED_LIB confirms the content [§2]."""
        head = K.ORGANELLE_BUDGET_TOTAL - self.total()
        w = min(weight * K.INHERITED_FACTOR, max(head, 0.0))
        o = Organelle(entity_id, kind, w, inherited=True, provisional=True)
        self.items[entity_id] = o
        return o

    def confirm(self, entity_id: str, full_weight: float) -> None:
        o = self.items.get(entity_id)
        if o is None or not o.provisional:
            return
        o.provisional = False
        o.weight = 0.0
        if self.total() + full_weight > K.ORGANELLE_BUDGET_TOTAL:
            self._renormalize(K.ORGANELLE_BUDGET_TOTAL - full_weight)
        o.weight = full_weight


class Theta:
    """The unit's θ — readable by anyone, writable only by the meter."""

    def __init__(self, series: Optional[list] = None, f: float = 0.5):
        self._series: list[float] = list(series or [K.THETA_NOM])
        self._f = f
        self.violations: list = []
        self.read_series: list[float] = []      # θ_read beside, for the operator
        # θ of the moves the attractors are read from [rule 53]: every move except
        # words that only the rule floor read (no AI reader, or the reader cut off)
        self.attr_series: list[float] = list(self._series)

    @property
    def current(self) -> float:
        return self._series[-1]

    @property
    def series(self) -> list[float]:
        return list(self._series)

    @property
    def f(self) -> float:
        return self._f

    @current.setter
    def current(self, value):
        self.violations.append(("theta", value, time.time()))

    def weights(self) -> tuple[float, float, float]:
        ext = self.current / 100.0
        return 1.0 - ext, ext * (1.0 - self._f), ext * self._f

    def _write(self, token, theta: float, f: Optional[float] = None) -> None:
        if token is not _METER:
            self.violations.append(("theta", theta, time.time()))
            return
        self._series.append(max(0.0, min(100.0, float(theta))))
        del self._series[:-K.WIN_LONG]
        if f is not None:
            self._f = min(K.F_MAX, max(K.F_MIN, f))


class PSEUnit:
    def __init__(self, unit_id: str, agent: str, core: Core, boundary: Boundary,
                 organelles: Organelles, theta: Theta, uses_model: bool):
        self.unit_id = unit_id
        self.agent = agent                    # which app agent this unit is
        self.core = core
        self.boundary = boundary
        self.organelles = organelles
        self.theta = theta
        self.uses_model = uses_model
        self.alive = True
        self.frozen = False
        self.freeze_reason = ""
        self.death_reason = ""
        self.extensions_running = 0
        self.restricted = False               # no irreversible actions [rule 19]
        self.move_times: list[float] = []
        self.error_run: tuple[str, int] = ("", 0)
        self.parent_ids: tuple = ()

    def complete(self) -> bool:
        return all(x is not None for x in (self.core, self.boundary,
                                           self.organelles, self.theta))

    def require_alive(self) -> None:
        if not self.alive or not self.complete():
            raise UnitDead(f"{self.unit_id} je mrtva ({self.death_reason or 'nepotpuna'})")

    def require_active(self) -> None:
        self.require_alive()
        if self.frozen:
            raise UnitFrozen(f"{self.unit_id} je zamrznuta: {self.freeze_reason}")

    def violations(self) -> list:
        return list(self.core.violations) + list(self.theta.violations)

    def pvp(self) -> dict:
        """PVP fields [§5], derived from the unit's state."""
        s = self.theta.series[-K.WIN_SWING:]
        w_s, w_o, w_f = self.theta.weights()
        return {
            "unit": self.unit_id, "agent": self.agent,
            "theta": round(self.theta.current, 2),
            "theta_window": [round(min(s), 2), round(max(s), 2)],
            "compute_other": round(100 * (w_o + w_f), 2),
            "w": [round(w_s, 3), round(w_o, 3), round(w_f, 3)],
            "alpha": {k: round(e.alpha, 3) for k, e in self.boundary.entities.items()},
            "mission": self.core.mission.as_dict(),
            "steps_remaining": self.core.steps_remaining,
            "generation": self.core.generation,
        }

    def l2_map(self) -> dict:
        """L2 environmental map: ENV / ORG / SELF / OTHER [§5]."""
        other = {k: e.kind for k, e in self.boundary.entities.items()}
        return {"ENV": self.core.domain,
                "ORG": sorted(self.organelles.items),
                "SELF": self.core.mission.as_dict(),
                "OTHER": other}
