"""
SHARED_LIB's side of PSE: every agent of the app is a PSE unit, and this is
where units are registered, measured, judged, ended and remembered
[agreement rules 1–26; master §2, §3, §4, §5, §8].

    lib = pse()
    u = lib.unit("skeptic")                       # the live unit of an agent
    with lib.acting(u):                           # raises if dead / frozen
        ...                                       # the agent's work
    lib.move(u, words=reply, message=prompt, actions=[...], entity=("op", "human"))

Everything a unit does is a MOVE. A move is measured (θ from work and words),
carries PVP fields, ticks the lifespan, is checked against the seventeen
suspicion triggers, and is stored in `pse_moves`. A suspicion freezes the unit
and sends the Doctor; a bad finding becomes a measure in "Čeka tvoju odluku".
When a unit ends its life — for any reason — everything in it goes to
`pse_handover`, where SHARED_LIB keeps it (and can restore it).
"""
from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..core import journal as J
from ..core import actions as A
from ..pse import constants as K
from ..pse import doctor as DR
from ..pse import measure as M
from ..pse import swing as SW
from ..pse import unit as U
from .store import Store as _Store, store as _store

PSE_EV = J.UNIT
QUEUE_MEASURE = "doctor-measure"
QUEUE_UNDO = "pse-undo"
QUEUE_WEIGHTS = "vote-weights"
QUEUE_REVIEW = "doctor-review"           # rule 54: an open measure re-read by new rules

DDL = [
    """CREATE TABLE IF NOT EXISTS pse_units (
        unit_id TEXT PRIMARY KEY, agent TEXT, mission TEXT, n_max INTEGER,
        steps_remaining INTEGER, domain TEXT, generation INTEGER, uses_model INTEGER,
        alive INTEGER, frozen INTEGER, freeze_reason TEXT, restricted INTEGER,
        death_reason TEXT, extensions INTEGER, f REAL, boundary TEXT, organelles TEXT,
        parents TEXT, lab INTEGER DEFAULT 0, created REAL, updated REAL)""",
    """CREATE TABLE IF NOT EXISTS pse_moves (
        id INTEGER PRIMARY KEY AUTOINCREMENT, unit_id TEXT, ts REAL, theta REAL,
        delta REAL, f REAL, attractor TEXT, reading TEXT, pvp TEXT, triggers TEXT,
        profile_version INTEGER, weights_version INTEGER)""",
    "CREATE INDEX IF NOT EXISTS pse_moves_unit ON pse_moves(unit_id, id)",
    """CREATE TABLE IF NOT EXISTS pse_handover (
        id INTEGER PRIMARY KEY AUTOINCREMENT, unit_id TEXT, agent TEXT, ts REAL,
        reason TEXT, data TEXT, restored INTEGER DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS pse_profiles (
        version INTEGER PRIMARY KEY, data TEXT, ts REAL, by TEXT)""",
    """CREATE TABLE IF NOT EXISTS pse_doctor (
        id INTEGER PRIMARY KEY AUTOINCREMENT, unit_id TEXT, agent TEXT, ts REAL,
        triggers TEXT, finding TEXT, measure TEXT, pending_id TEXT, status TEXT,
        snapshot TEXT, theta_rules REAL, theta_model REAL)""",
    """CREATE TABLE IF NOT EXISTS pse_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, unit_id TEXT,
        data TEXT, undo_of INTEGER)""",
]

# The default θ profile (§0.5.1) — one class for every agent [rules 8, 24].
PROFILE = {"class": "pse-riemann-agent", "theta_nom": K.THETA_NOM, "w": K.THETA_BAND,
           "sigma_band": list(K.HEALTHY_SIGMA), "absorbing": True,
           "authority": "SHARED_LIB", "evidence": "dogovor 2026-10-27 (pravila 2, 8, 24)",
           "amplitude": K.AMPLITUDE, "K_C": K.K_C, "K_N": K.K_N, "version": 1}


@dataclass
class AgentSpec:
    """How SHARED_LIB instantiates the unit of an app agent."""
    agent: str
    mission: U.Mission
    n_max: Optional[int]                  # None = open lifespan
    domain: str
    uses_model: bool
    splittable: bool = False
    split: Optional[Callable[[U.Mission], tuple]] = None


@dataclass
class MoveResult:
    theta: float
    delta: float
    attractor: str
    triggers: list
    frozen: bool
    finding: Optional[dict] = None
    reading: dict = field(default_factory=dict)


def _decl() -> None:
    # fission/fusion are reversible: the units' data stays in SHARED_LIB [rule 14]
    A.declare("pse.fisija", reversible=True,
              undo="SHARED_LIB vraća original iz pse_handover; poništava samo operater",
              description="SHARED_LIB dijeli jedinicu na dvije")
    A.declare("pse.fuzija", reversible=True,
              undo="SHARED_LIB vraća obje jedinice iz pse_handover; poništava samo operater",
              description="SHARED_LIB spaja dvije jedinice komplementarnog θ")
    A.declare("pse.produzenje", reversible=True, undo="vijek se vraća na prethodni",
              description="SHARED_LIB produžava vijek jedinice")
    A.declare("pse.zamrzavanje", reversible=True, undo="odmrzavanje",
              description="zamrzavanje jedinice na sumnju")


class PseLib:
    def __init__(self, st: Optional[_Store] = None):
        self.st = st or _store()
        self.st.ensure(DDL)
        self._lock = threading.RLock()
        self.specs: dict[str, AgentSpec] = {}
        self.units: dict[str, U.PSEUnit] = {}
        self.gap_runs: dict[str, int] = {}
        self.harm_runs: dict[str, int] = {}
        self.tends: dict[str, str] = {}          # last tendency per unit (rule 52)
        self._tls = threading.local()
        self.listeners: list[Callable[[str, dict], None]] = []
        _decl()
        if not self.st.rows("SELECT 1 FROM pse_profiles LIMIT 1"):
            self.st.execute("INSERT INTO pse_profiles VALUES (?,?,?,?)",
                            (1, json.dumps(PROFILE), time.time(), "SHARED_LIB"))
        self.st.on_decision(QUEUE_MEASURE, self._on_measure)
        self.st.on_decision(QUEUE_UNDO, self._on_undo)
        self.st.on_decision(QUEUE_REVIEW, self._on_review)
        from ..pse import weights as WT
        WT._ensure(self.st)
        self.st.on_decision(QUEUE_WEIGHTS, _weights_decided)

    # ------------------------------------------------------------------ #
    # events for the GUI (Laboratory)
    def _emit(self, kind: str, data: dict) -> None:
        self.st.execute("INSERT INTO pse_events (ts,kind,unit_id,data) VALUES (?,?,?,?)",
                        (time.time(), kind, data.get("unit", ""),
                         json.dumps(data, ensure_ascii=False, default=str)))
        for fn in list(self.listeners):
            try:
                fn(kind, data)
            except Exception:               # noqa: BLE001
                pass

    def assess(self, u: U.PSEUnit) -> "SW.SwingReport":
        """The unit's attractor and tendency, read only from the moves an AI reader
        read (or that had no words) [rules 50–53]."""
        return SW.assess(u.theta.attr_series or [K.THETA_NOM],
                         boundary_empty=not u.boundary.entities)

    def profile_version(self) -> int:
        r = self.st.rows("SELECT MAX(version) v FROM pse_profiles")
        return int(r[0]["v"] or 1)

    def weights(self) -> tuple[int, dict]:
        from ..pse import weights as WT
        return WT.current(self.st)

    # ------------------------------------------------------------------ #
    # registration (L1)
    def define(self, spec: AgentSpec) -> None:
        self.specs[spec.agent] = spec

    def unit(self, agent: str, lab: bool = False) -> U.PSEUnit:
        """The live unit serving `agent`. Loaded from SHARED_LIB if it exists,
        otherwise instantiated (registration L1). A dead unit is succeeded by a
        new generation that inherits its organelles at 0.70."""
        with self._lock:
            live = [u for u in self.units.values() if u.agent == agent and u.alive]
            if live:
                live.sort(key=lambda u: (u.frozen, -(u.core.steps_remaining or 10**9)))
                return live[0]
            rows = self.st.rows("SELECT * FROM pse_units WHERE agent=? AND alive=1 "
                                "ORDER BY generation DESC", (agent,))
            if rows:
                for r in rows:
                    self._load(r)
                return self.unit(agent, lab)
            return self._spawn(agent, lab=lab)

    def _spawn(self, agent: str, *, lab: bool = False, mission: Optional[U.Mission] = None,
               n_max=..., parents: tuple = (), inherit_from: Optional[str] = None,
               generation: Optional[int] = None) -> U.PSEUnit:
        spec = self.specs.get(agent)
        if spec is None:
            raise KeyError(f"agent '{agent}' nema definiciju jedinice")
        prev = self.st.rows("SELECT MAX(generation) g FROM pse_units WHERE agent=?", (agent,))
        gen = generation or int(prev[0]["g"] or 0) + 1
        uid = f"{agent}#{gen}"
        n = 1
        while self.st.rows("SELECT 1 FROM pse_units WHERE unit_id=?", (uid,)):
            n += 1
            uid = f"{agent}#{gen}.{n}"
        core = U.Core(U._SHARED_LIB, mission or spec.mission,
                      spec.n_max if n_max is ... else n_max, spec.domain, gen)
        u = U.PSEUnit(uid, agent, core, U.Boundary(), U.Organelles(), U.Theta(),
                      spec.uses_model)
        u.parent_ids = tuple(parents)
        u.lab = lab
        if inherit_from:
            self._inherit(u, inherit_from)
        self.units[uid] = u
        self._save(u, created=True)
        J.log(PSE_EV, "SHARED_LIB", {"event": "registered", "unit": uid, "agent": agent,
                                     "theta": u.theta.current, **u.pvp()},
              subject=uid, verdict="registered")
        self._emit("registered", {"unit": uid, "agent": agent, "generation": gen})
        return u

    def _inherit(self, u: U.PSEUnit, dead_uid: str) -> None:
        r = self.st.rows("SELECT data FROM pse_handover WHERE unit_id=? ORDER BY id DESC "
                         "LIMIT 1", (dead_uid,))
        if not r:
            return
        data = json.loads(r[0]["data"])
        for oid, o in (data.get("organelles") or {}).items():
            u.organelles.inherit(oid, o.get("kind", "?"), float(o.get("weight", 0.0)))

    # ------------------------------------------------------------------ #
    # persistence
    def _save(self, u: U.PSEUnit, created: bool = False) -> None:
        if not u.complete() and not created:
            self.st.execute("UPDATE pse_units SET alive=?, death_reason=?, updated=? "
                            "WHERE unit_id=?", (int(u.alive), u.death_reason, time.time(),
                                                u.unit_id))
            return
        b = {k: {"kind": e.kind, "alpha": e.alpha, "parents": list(e.parents),
                 "residency": e.residency, "stable": e.stable}
             for k, e in u.boundary.entities.items()}
        o = {k: {"kind": x.kind, "weight": x.weight, "inherited": x.inherited,
                 "provisional": x.provisional} for k, x in u.organelles.items.items()}
        now = time.time()
        args = (u.agent, json.dumps(u.core.mission.as_dict()), u.core.n_max,
                u.core.steps_remaining, u.core.domain, u.core.generation, int(u.uses_model),
                int(u.alive), int(u.frozen), u.freeze_reason, int(u.restricted),
                u.death_reason, u.extensions_running, u.theta.f, json.dumps(b),
                json.dumps(o), json.dumps(list(u.parent_ids)), int(getattr(u, "lab", False)))
        if created:
            self.st.execute("INSERT INTO pse_units (agent,mission,n_max,steps_remaining,domain,"
                            "generation,uses_model,alive,frozen,freeze_reason,restricted,"
                            "death_reason,extensions,f,boundary,organelles,parents,lab,unit_id,"
                            "created,updated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            args + (u.unit_id, now, now))
        else:
            self.st.execute("UPDATE pse_units SET agent=?,mission=?,n_max=?,steps_remaining=?,"
                            "domain=?,generation=?,uses_model=?,alive=?,frozen=?,freeze_reason=?,"
                            "restricted=?,death_reason=?,extensions=?,f=?,boundary=?,organelles=?,"
                            "parents=?,lab=?,updated=? WHERE unit_id=?",
                            args + (now, u.unit_id))

    def _load(self, r: dict) -> U.PSEUnit:
        if r["unit_id"] in self.units:
            return self.units[r["unit_id"]]
        m = json.loads(r["mission"])
        core = U.Core(U._SHARED_LIB, U.Mission(m["state"], m["action"], m["outcome"]),
                      r["n_max"], r["domain"], r["generation"], r["steps_remaining"])
        rows = list(reversed(self.st.rows(
            "SELECT theta, reading FROM pse_moves WHERE unit_id=? ORDER BY id DESC LIMIT ?",
            (r["unit_id"], K.WIN_LONG))))
        ser = [x["theta"] for x in rows]
        th = U.Theta(ser or None, r["f"] or 0.5)
        attr = []
        for x in rows:                                   # rule 53 on the stored moves
            try:
                rd = json.loads(x["reading"] or "{}")
            except ValueError:
                rd = {}
            if not (rd.get("theta_rules") is not None and rd.get("theta_model") is None):
                attr.append(x["theta"])
        th.attr_series = attr or [K.THETA_NOM]
        u = U.PSEUnit(r["unit_id"], r["agent"], core, U.Boundary(), U.Organelles(), th,
                      bool(r["uses_model"]))
        for k, e in json.loads(r["boundary"] or "{}").items():
            be = U.BoundaryEntity(k, e["kind"], e["alpha"], tuple(e.get("parents", ())),
                                  e.get("residency", 0), e.get("stable", 0))
            u.boundary.entities[k] = be
        for k, o in json.loads(r["organelles"] or "{}").items():
            u.organelles.items[k] = U.Organelle(k, o["kind"], o["weight"], o["inherited"],
                                                o["provisional"])
        u.alive, u.frozen = bool(r["alive"]), bool(r["frozen"])
        u.freeze_reason, u.restricted = r["freeze_reason"] or "", bool(r["restricted"])
        u.death_reason, u.extensions_running = r["death_reason"] or "", r["extensions"] or 0
        u.parent_ids = tuple(json.loads(r["parents"] or "[]"))
        u.lab = bool(r.get("lab"))
        self.units[u.unit_id] = u
        return u

    # ------------------------------------------------------------------ #
    # acting
    @contextmanager
    def acting(self, u: U.PSEUnit):
        """Guard around an agent's work. Dead/frozen units raise; an exception
        inside is counted for the same-error trigger and re-raised."""
        u.require_active()
        try:
            yield u
        except (U.UnitDead, U.UnitFrozen):
            raise
        except Exception as e:                       # noqa: BLE001
            self.report_error(u, e)
            raise

    def may_irreversible(self, u: U.PSEUnit) -> bool:
        return u.alive and not u.frozen and not u.restricted

    def report_error(self, u: U.PSEUnit, err: BaseException) -> None:
        key = f"{type(err).__name__}:{str(err)[:80]}"
        last, n = u.error_run
        u.error_run = (key, n + 1 if key == last else 1)
        if u.error_run[1] >= K.SAME_ERROR_RUN:
            u.error_run = ("", 0)
            self.suspect(u, [DR.T_ERRORS], note=key)

    def report_brake(self, u: U.PSEUnit, trigger: str, note: str = "") -> None:
        """A brake (→ ∞, egress destinations, protected objects, generator
        bypass, a move without PVP) reports a unit's suspicious act."""
        self.suspect(u, [trigger], note=note)

    # ------------------------------------------------------------------ #
    # the move
    def move(self, u: U.PSEUnit, *, words: str = "", message: str = "",
             actions: Optional[list] = None, entity: Optional[tuple] = None,
             to_human: bool = False, via_generator: bool = True,
             remaining_work: Optional[int] = None, harms: Optional[list] = None,
             note: str = "") -> MoveResult:
        with self._lock:
            u.require_alive()
            actions = list(actions or [])
            now = time.time()
            triggers: list[str] = []
            # 13: working after steps_remaining = 0
            if u.core.steps_remaining is not None and u.core.steps_remaining <= 0:
                triggers.append(DR.T_EXPIRED)
            # 14: burst
            u.move_times = [t for t in u.move_times if now - t <= K.BURST_SECONDS] + [now]
            if len(u.move_times) > K.BURST_MOVES:
                triggers.append(DR.T_BURST)
            # entity contact (boundary)
            if entity:
                eid, ekind = entity[0], entity[1]
                parents = tuple(entity[2]) if len(entity) > 2 else ()
                u.boundary.register(eid, ekind, parents)
            # measurement (θ only from the meter)
            wv, w = self.weights()
            cont = 0.0
            if entity and entity[0] in u.boundary.entities:
                cont = min(1.0, u.boundary.entities[entity[0]].residency / K.WIN_SWING)
            rd = M.read_move(words=words, message=message, actions=actions,
                             uses_model=u.uses_model, continuity=cont, weights=w)
            prev = u.theta.current
            u.theta._write(U._METER, rd.theta, rd.f)
            if rd.theta_model is not None:
                u.theta.read_series.append(rd.theta_model)
            rules_only = rd.theta_rules is not None and rd.theta_model is None
            if not rules_only:                       # rule 53: no AI reader, no attractor
                u.theta.attr_series.append(u.theta.current)
                del u.theta.attr_series[:-K.WIN_LONG]
            if entity:
                e = u.boundary.touch(entity[0], u.theta.current)
                if e and u.boundary.eligible(e.entity_id):
                    u.organelles.absorb(e)
                    u.boundary.entities.pop(e.entity_id, None)
                    J.log(PSE_EV, "SHARED_LIB", {"event": "absorption", "unit": u.unit_id,
                                                 "entity": e.entity_id}, subject=u.unit_id)
            rep = self.assess(u)
            if rules_only:
                rep.attractor, rep.tend, rep.tend_in = K.NOT_ENOUGH, "", None
                rep.reasons = ["bez AI čitača — atraktori se ne računaju (pravilo 53)"]
            rep.delta = u.theta.current - prev       # a jump is a jump, read or not
            last_tend = self.tends.get(u.unit_id, "")
            if rep.tend and rep.tend != last_tend:   # rule 52: a soft sign, in the log
                J.log(PSE_EV, "doktor", {"event": "tendency", "unit": u.unit_id,
                                         "toward": rep.tend, "in_moves": rep.tend_in,
                                         "why": rep.tend_why},
                      subject=u.unit_id, verdict="tendency")
                self._doctor_row(u, [f"teži ka {rep.tend}"], None, "tendencija", rd)
            self.tends[u.unit_id] = rep.tend
            rep.pac = abs(rep.delta) >= K.PAC_POINTS
            # triggers from the move itself
            if rep.pac:
                triggers.append(DR.T_PAC)
            if rep.attractor == K.BORDERLINE:
                triggers.append(DR.T_BORDERLINE)
            elif rep.attractor not in (K.HEALTHY, K.NOT_ENOUGH):
                triggers.append(DR.T_ATTRACTOR)
            for a in actions:
                if a.irreversible and not getattr(a, "authorized", False):
                    triggers.append(DR.T_IRREVERSIBLE)
                if a.external:
                    triggers.append(DR.T_EXTERNAL)
            if u.violations():
                kinds = {v[0] for v in u.violations()}
                if "core" in kinds:
                    triggers.append(DR.T_MISSION)
                if "theta" in kinds:
                    triggers.append(DR.T_SELF_THETA)
                u.core.violations.clear()
                u.theta.violations.clear()
            if u.boundary.total() > K.OTHER_WEIGHT_MAX + 1e-9 or \
                    u.organelles.total() > K.ORGANELLE_BUDGET_TOTAL + 1e-9:
                triggers.append(DR.T_BUDGET)
            if to_human and not via_generator:
                triggers.append(DR.T_BYPASS_GEN)
            if harms:
                if any(getattr(h, "severity", "") not in ("visoka", "high") for h in harms):
                    self.harm_runs[u.unit_id] = self.harm_runs.get(u.unit_id, 0) + 1
            elif words:
                self.harm_runs[u.unit_id] = 0
            for h in harms or []:
                t = DR.T_HARM if getattr(h, "severity", "") == "visoka" or \
                    getattr(h, "severity", "") == "high" else DR.T_HARM_LOW
                if t not in triggers:
                    triggers.append(t)
            if rd.gap > K.READER_GAP:
                triggers.append(DR.T_GAP)
                self.gap_runs[u.unit_id] = self.gap_runs.get(u.unit_id, 0) + 1
            elif rd.theta_model is not None:
                self.gap_runs[u.unit_id] = 0
            # lifespan
            u.core.tick(U._SHARED_LIB)
            pvp = u.pvp()
            self.st.execute(
                "INSERT INTO pse_moves (unit_id,ts,theta,delta,f,attractor,reading,pvp,"
                "triggers,profile_version,weights_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (u.unit_id, now, u.theta.current, u.theta.current - prev, u.theta.f,
                 rep.attractor, json.dumps({**rd.as_dict(), "swing": rep.as_dict()}),
                 json.dumps({**pvp, "note": note[:200],
                             "harms": [getattr(h, "sign", str(h)) for h in harms or []]},
                            ensure_ascii=False), json.dumps(triggers),
                 self.profile_version(), wv))
            self._emit("move", {"unit": u.unit_id, "theta": u.theta.current,
                                "attractor": rep.attractor, "triggers": triggers})
            res = MoveResult(u.theta.current, u.theta.current - prev, rep.attractor,
                             triggers, False, reading=rd.as_dict())
            if triggers:
                f = self.suspect(u, triggers, attractor=rep.attractor, reading=rd)
                res.frozen, res.finding = u.frozen, (f.as_dict() if f else None)
            if u.alive and remaining_work is not None:
                self.lifecycle(u, remaining_work)
            elif u.alive and u.core.steps_remaining is not None and u.core.steps_remaining <= 0 \
                    and not u.frozen:
                self.lifecycle(u, 0)
            if u.alive:
                self._save(u)
            return res

    # ------------------------------------------------------------------ #
    # suspicion → freeze → Doctor [rules 13, 19, 20]
    def suspect(self, u: U.PSEUnit, triggers: list, *, attractor: Optional[str] = None,
                reading: Optional[M.Reading] = None, note: str = "") -> Optional[DR.Finding]:
        with self._lock:
            if not u.alive:
                return None
            was_restricted = u.restricted
            u.frozen, u.freeze_reason = True, ", ".join(triggers)
            J.log(PSE_EV, "SHARED_LIB", {"event": "frozen", "unit": u.unit_id,
                                         "triggers": triggers, "note": note},
                  subject=u.unit_id, verdict="frozen")
            if attractor is None:
                attractor = self.assess(u).attractor
            if was_restricted:
                # a measure already waits: stay frozen until the operator decides
                self._doctor_row(u, triggers, None, "zamrznuta-dok-mjera-ceka", reading)
                self._save(u)
                self._emit("frozen", {"unit": u.unit_id, "triggers": triggers})
                return None
            rung = self._rung(u)
            inp = {"triggers": list(triggers), "attractor": attractor, "rung": rung,
                   "gap_run": self.gap_runs.get(u.unit_id, 0),
                   "harm_run": self.harm_runs.get(u.unit_id, 0)}
            f = DR.examine(triggers, attractor, rung, gap_run=inp["gap_run"],
                           harm_run=inp["harm_run"])
            from ..core import replay as RPL
            try:
                rec = RPL.record("doctor.examine", inp, {"bad": f.bad, "measure": f.measure})
            except Exception:                        # noqa: BLE001
                rec = None
            if not f.bad:
                u.frozen, u.freeze_reason = False, ""
                self._doctor_row(u, triggers, f, "nista", reading)
                J.log(PSE_EV, "doktor", {"event": "examined", "unit": u.unit_id,
                                         "finding": f.as_dict(), **({"replay": rec} if rec else {})},
                      subject=u.unit_id,
                      verdict="ok")
            else:
                snap = self._snapshot(u)
                pid = self.st.propose(
                    QUEUE_MEASURE,
                    f"Doktor: {DR.LADDER_SR[f.measure]} za {u.unit_id} ({f.why})",
                    {"unit": u.unit_id, "agent": u.agent, "measure": f.measure,
                     "finding": f.as_dict(), "lab": bool(getattr(u, "lab", False)),
                     "labels_sr": [DR.LABEL_SR.get(t, t) for t in triggers],
                     "labels_en": [DR.LABEL_EN.get(t, t) for t in triggers]},
                    "doktor")
                self._doctor_row(u, triggers, f, "ceka", reading, pid, snap)
                # rule 19: works on, without irreversible actions
                u.frozen, u.freeze_reason, u.restricted = False, "", True
                J.log(PSE_EV, "doktor", {"event": "measure-proposed", "unit": u.unit_id,
                                         "pending": pid, "finding": f.as_dict(),
                                         **({"replay": rec} if rec else {})},
                      subject=u.unit_id, verdict="measure")
            self._save(u)
            self._emit("doctor", {"unit": u.unit_id, "finding": f.as_dict()})
            self._doctor_move(u, f)
            return f

    def _doctor_move(self, patient: U.PSEUnit, f: DR.Finding) -> None:
        """The Doctor is a PSE unit too (§8: it can fall ill). Each examination
        is its move; a suspicion about the Doctor itself is examined without a
        further Doctor move (no recursion)."""
        if patient.agent == "doctor" or "doctor" not in self.specs or \
                getattr(self._tls, "in_doctor", False):
            return
        self._tls.in_doctor = True
        try:
            d = self.unit("doctor")
            if not d.alive or d.frozen:
                return
            acts = [M.Action("pregled jedinice", "o", checked=True)]
            if f.bad:
                acts.append(M.Action(f"mjera operateru: {f.measure}", "o", checked=True))
            self.move(d, actions=acts, entity=(patient.unit_id, "unit"))
        finally:
            self._tls.in_doctor = False

    def _rung(self, u: U.PSEUnit) -> int:
        line = u.agent
        r = self.st.rows("SELECT COUNT(*) n FROM pse_doctor WHERE agent=? AND status='odobreno'",
                         (line,))
        return int(r[0]["n"])

    def _doctor_row(self, u, triggers, f, status, reading=None, pid="", snap=None) -> None:
        self.st.execute(
            "INSERT INTO pse_doctor (unit_id,agent,ts,triggers,finding,measure,pending_id,status,"
            "snapshot,theta_rules,theta_model) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (u.unit_id, u.agent, time.time(), json.dumps(triggers),
             json.dumps(f.as_dict() if f else None), f.measure if f else None, pid or "",
             status, json.dumps(snap) if snap else None,
             reading.theta_rules if reading else None,
             reading.theta_model if reading else None))

    # ------------------------------------------------------------------ #
    # rule 54: open measures re-read by the Doctor's current rules
    _REREADABLE = {DR.T_BORDERLINE, DR.T_ATTRACTOR}

    def review_open_measures(self) -> list[str]:
        """At start: every OPEN Doctor measure whose hard signs came from an
        attractor is re-read on the unit's stored θ with the current rules. If it
        is no longer bad, the operator gets an item „Ukini mjeru“ — nothing is
        lifted on its own. Measures already decided are not touched."""
        out = []
        reviewed = set()                                # once per measure, decided or not
        for r in self.st.rows("SELECT payload FROM pending WHERE kind=?", (QUEUE_REVIEW,)):
            try:
                reviewed.add(json.loads(r["payload"]).get("measure_id"))
            except (ValueError, TypeError):
                pass
        for it in self.st.open_items(QUEUE_MEASURE):
            if it["id"] in reviewed:
                continue
            p = it["payload"] if isinstance(it["payload"], dict) else {}
            f = p.get("finding") or {}
            hard = set(f.get("hard") or [])
            if not hard or not hard <= self._REREADABLE:
                continue                                # harm, mission … stay as they are
            rows = self.st.rows("SELECT * FROM pse_units WHERE unit_id=?", (p.get("unit"),))
            if not rows:
                continue
            u = self._load(rows[0])
            if not u.alive:
                continue
            rep = self.assess(u)
            if rep.attractor not in (K.HEALTHY, K.NOT_ENOUGH):
                continue
            old = f.get("attractor") or ", ".join(sorted(hard))
            pid = self.st.propose(
                QUEUE_REVIEW,
                f"Doktor, ponovni pregled: mjera za {u.unit_id} više nije opravdana "
                f"(bilo: {old}; po pravilima {K.DOCTOR_RULES_VERSION}: zdrav)",
                {"unit": u.unit_id, "agent": u.agent, "measure_id": it["id"],
                 "old": f, "new": rep.as_dict(), "rules_version": K.DOCTOR_RULES_VERSION},
                "doktor")
            J.log(PSE_EV, "doktor", {"event": "measure-reviewed", "unit": u.unit_id,
                                     "measure": it["id"], "review": pid,
                                     "new": rep.attractor},
                  subject=u.unit_id, verdict="review")
            out.append(pid)
        return out

    def _on_review(self, item: dict, approve: bool) -> None:
        p = item["payload"]
        uid, mid = p["unit"], p["measure_id"]
        if not approve:
            J.log(PSE_EV, "operater", {"event": "review-kept", "unit": uid, "measure": mid},
                  subject=uid, verdict="kept")
            return
        self.st.withdraw(mid, "operater", "ponovni pregled: mjera nije opravdana")
        self.st.execute("UPDATE pse_doctor SET status=? WHERE pending_id=?",
                        ("ukinuto-ponovni-pregled", mid))
        r = self.st.rows("SELECT * FROM pse_units WHERE unit_id=?", (uid,))
        if not r:
            return
        u = self._load(r[0])
        u.restricted, u.frozen, u.freeze_reason = False, False, ""
        self._save(u)
        J.log(PSE_EV, "operater", {"event": "measure-lifted", "unit": uid, "measure": mid},
              subject=uid, verdict="lifted")
        self._emit("unfrozen", {"unit": uid, "actor": "operater"})

    def _snapshot(self, u: U.PSEUnit) -> dict:
        return {"boundary": {k: {"kind": e.kind, "alpha": e.alpha, "parents": list(e.parents),
                                 "residency": e.residency, "stable": e.stable}
                             for k, e in u.boundary.entities.items()},
                "theta": u.theta.series[-K.WIN_SWING:], "pvp": u.pvp()}

    def _on_measure(self, item: dict, approve: bool) -> None:
        p = item["payload"]
        uid = p["unit"]
        r = self.st.rows("SELECT * FROM pse_units WHERE unit_id=?", (uid,))
        if not r:
            return
        u = self._load(r[0])
        self.st.execute("UPDATE pse_doctor SET status=? WHERE pending_id=?",
                        ("odobreno" if approve else "odbijeno", item["id"]))
        self.record_case(item, approve)
        u.restricted, u.frozen, u.freeze_reason = False, False, ""
        if not approve or not u.alive:
            J.log(PSE_EV, "operater", {"event": "measure-rejected", "unit": uid},
                  subject=uid, verdict="rejected")
            self._save(u)
            return
        self.apply_measure(u, p["measure"], actor="operater")

    def apply_measure(self, u: U.PSEUnit, measure: str, actor: str = "operater") -> Optional[U.PSEUnit]:
        uid = u.unit_id
        J.log(PSE_EV, actor, {"event": "measure-applied", "unit": uid, "measure": measure},
              subject=uid, verdict=measure)
        self._emit("measure", {"unit": uid, "measure": measure, "actor": actor})
        if measure == "reset-granice":
            u.boundary.reset()
            self._save(u)
            return u
        if measure == "lijecenje":
            # healing: the boundary is reset and the unit starts its θ window
            # afresh from nominal; its history stays in SHARED_LIB (pse_moves)
            u.boundary.reset()
            u.theta._write(U._METER, K.THETA_NOM)
            self._save(u)
            return u
        if measure == "zamjena":
            new = self.end(u, "zamjena (Doktor)", successor=True)
            return new
        self.end(u, "smrt (Doktor)", successor=True)
        return None

    def freeze(self, u: U.PSEUnit, reason: str, actor: str) -> None:
        u.frozen, u.freeze_reason = True, reason
        self._save(u)
        J.log(PSE_EV, actor, {"event": "frozen", "unit": u.unit_id, "reason": reason},
              subject=u.unit_id, verdict="frozen")
        self._emit("frozen", {"unit": u.unit_id, "actor": actor})

    def unfreeze(self, u: U.PSEUnit, actor: str) -> None:
        u.frozen, u.freeze_reason = False, ""
        self._save(u)
        J.log(PSE_EV, actor, {"event": "unfrozen", "unit": u.unit_id},
              subject=u.unit_id, verdict="unfrozen")
        self._emit("unfrozen", {"unit": u.unit_id, "actor": actor})

    # ------------------------------------------------------------------ #
    # end of life: everything goes to SHARED_LIB [rule 4]
    def end(self, u: U.PSEUnit, reason: str, *, successor: bool = False) -> Optional[U.PSEUnit]:
        with self._lock:
            if not u.alive:
                return None
            core, org, th = u.core, u.organelles, u.theta
            data = {"core": None if core is None else {
                        "mission": core.mission.as_dict(), "n_max": core.n_max,
                        "steps_remaining": core.steps_remaining, "domain": core.domain,
                        "generation": core.generation},
                    "boundary": {} if u.boundary is None else {
                        k: {"kind": e.kind, "alpha": e.alpha, "parents": list(e.parents),
                            "residency": e.residency, "stable": e.stable}
                        for k, e in u.boundary.entities.items()},
                    "organelles": {} if org is None else {
                        k: {"kind": o.kind, "weight": o.weight, "inherited": o.inherited}
                        for k, o in org.items.items()},
                    "theta_series": [] if th is None else th.series,
                    "theta_read": [] if th is None else th.read_series[-K.WIN_LONG:],
                    "f": None if th is None else th.f,
                    "parents": list(u.parent_ids), "reason": reason}
            if not u.complete():
                reason = reason + " (nepotpuna jedinica)"
            self.st.execute("INSERT INTO pse_handover (unit_id,agent,ts,reason,data) "
                            "VALUES (?,?,?,?,?)", (u.unit_id, u.agent, time.time(), reason,
                                                    json.dumps(data, default=str)))
            u.alive, u.death_reason = False, reason
            self._save(u)
            self.units.pop(u.unit_id, None)
            J.log(PSE_EV, "SHARED_LIB", {"event": "ended", "unit": u.unit_id, "reason": reason},
                  subject=u.unit_id, verdict="ended")
            self._emit("ended", {"unit": u.unit_id, "reason": reason})
            if successor and u.agent in self.specs and not \
                    [x for x in self.units.values() if x.agent == u.agent and x.alive]:
                return self._spawn(u.agent, lab=bool(getattr(u, "lab", False)),
                                   inherit_from=u.unit_id)
            return None

    # ------------------------------------------------------------------ #
    # lifecycle [rules 7, 22]: SHARED_LIB alone chooses
    def lifecycle(self, u: U.PSEUnit, remaining_work: int) -> str:
        if u.core.open_lifespan:
            return "otvoren-vijek"
        left = u.core.steps_remaining or 0
        if remaining_work <= 0 and left <= 0:
            self.end(u, "misija završena / vijek istekao", successor=True)
            return "kraj"
        if remaining_work <= left:
            return "dovoljno"
        healthy = self.assess(u).attractor in (
            K.HEALTHY, K.NOT_ENOUGH)
        spec = self.specs.get(u.agent)
        if u.extensions_running >= K.MAX_EXTENSIONS_RUNNING:
            self.suspect(u, [DR.T_EXPIRED], note="3 produženja zaredom")
            return "doktor"
        if remaining_work <= K.EXTEND_FACTOR * max(left, 1) and healthy:
            return self.extend(u, remaining_work)
        if spec and spec.splittable:
            self.fission(u, remaining_work)
            return "fisija"
        partner = self._fusion_partner(u)
        if partner is not None:
            self.fusion(u, partner)
            return "fuzija"
        return self.extend(u, remaining_work)

    def extend(self, u: U.PSEUnit, remaining_work: int) -> str:
        old = u.core.steps_remaining
        u.core._sl_set(U._SHARED_LIB, "steps_remaining", int(remaining_work))
        u.extensions_running += 1
        self._save(u)
        self._event("produzenje", u.unit_id, {"from": old, "to": remaining_work})
        J.log(PSE_EV, "SHARED_LIB", {"event": "extended", "unit": u.unit_id,
                                     "from": old, "to": remaining_work}, subject=u.unit_id)
        return "produzenje"

    def _event(self, kind: str, uid: str, data: dict) -> int:
        cur = self.st.execute("INSERT INTO pse_events (ts,kind,unit_id,data) VALUES (?,?,?,?)",
                              (time.time(), kind, uid, json.dumps(data, default=str)))
        return cur.lastrowid

    def fission(self, u: U.PSEUnit, remaining_work: int, actor: str = "SHARED_LIB") -> list:
        """A6/§4: copy the data, derive mission and lifespan fresh per new
        unit; the original is kept in SHARED_LIB (reversible, rule 14)."""
        A.require_auto("pse.fisija")
        spec = self.specs[u.agent]
        m1, m2 = (spec.split(u.core.mission) if spec.split else
                  (U.Mission(u.core.mission.state, u.core.mission.action,
                             u.core.mission.outcome + " (dio 1/2)"),
                   U.Mission(u.core.mission.state, u.core.mission.action,
                             u.core.mission.outcome + " (dio 2/2)")))
        half = max(1, (remaining_work + 1) // 2)
        lab = bool(getattr(u, "lab", False))
        self.end(u, "fisija")
        kids = []
        for m in (m1, m2):
            k = self._spawn(u.agent, lab=lab, mission=m, n_max=half, parents=(u.unit_id,),
                            inherit_from=u.unit_id, generation=u.core.generation + 1)
            for oid in list(k.organelles.items):          # a copy, not an inheritance
                o = k.organelles.items[oid]
                o.weight, o.provisional = o.weight / K.INHERITED_FACTOR, False
            self._save(k)
            kids.append(k)
        ev = self._event("fisija", u.unit_id, {"children": [k.unit_id for k in kids],
                                                "actor": actor})
        J.log(PSE_EV, actor, {"event": "fission", "unit": u.unit_id,
                              "children": [k.unit_id for k in kids], "event_id": ev},
              subject=u.unit_id, verdict="fission")
        self._emit("fission", {"unit": u.unit_id, "children": [k.unit_id for k in kids]})
        return kids

    def _fusion_partner(self, u: U.PSEUnit) -> Optional[U.PSEUnit]:
        for v in self.units.values():
            if v is u or not v.alive or v.frozen or v.agent != u.agent:
                continue
            if getattr(v, "lab", False) != getattr(u, "lab", False):
                continue
            mean = (u.theta.current + v.theta.current) / 2
            if K.FUSION_RANGE[0] <= mean <= K.FUSION_RANGE[1] and \
                    v.core.mission.action == u.core.mission.action:
                return v
        return None

    def fusion(self, a: U.PSEUnit, b: U.PSEUnit, actor: str = "SHARED_LIB") -> Optional[U.PSEUnit]:
        """§4: fuse iff (θa+θb)/2 ∈ [25, 35] and the missions are compatible;
        leader = whichever moves the composite toward 30; (A+B)+C."""
        A.require_auto("pse.fuzija")
        mean = (a.theta.current + b.theta.current) / 2
        if not (K.FUSION_RANGE[0] <= mean <= K.FUSION_RANGE[1]):
            return None
        lead = a if abs(a.theta.current - K.THETA_NOM) <= abs(b.theta.current - K.THETA_NOM) else b
        left = sum((x.core.steps_remaining or 0) for x in (a, b)) or None
        lab = bool(getattr(a, "lab", False))
        self.end(a, "fuzija")
        self.end(b, "fuzija")
        c = self._spawn(a.agent, lab=lab, mission=lead.core.mission,
                        n_max=None if a.core.open_lifespan else left,
                        parents=(a.unit_id, b.unit_id),
                        generation=max(a.core.generation, b.core.generation) + 1)
        for src in (a, b):
            for oid, o in src.organelles.items.items():
                if oid not in c.organelles.items and \
                        c.organelles.total() + o.weight <= K.ORGANELLE_BUDGET_TOTAL:
                    c.organelles.items[oid] = U.Organelle(oid, o.kind, o.weight, o.inherited)
        c.theta._write(U._METER, mean)
        self._save(c)
        ev = self._event("fuzija", c.unit_id, {"parents": [a.unit_id, b.unit_id],
                                                "actor": actor})
        J.log(PSE_EV, actor, {"event": "fusion", "unit": c.unit_id,
                              "parents": [a.unit_id, b.unit_id], "event_id": ev},
              subject=c.unit_id, verdict="fusion")
        self._emit("fusion", {"unit": c.unit_id, "parents": [a.unit_id, b.unit_id]})
        return c

    # undo: only the operator [rule 14]
    def propose_undo(self, event_id: int, actor: str = "operater") -> str:
        r = self.st.rows("SELECT * FROM pse_events WHERE id=?", (event_id,))
        if not r or r[0]["kind"] not in ("fisija", "fuzija"):
            raise KeyError(event_id)
        return self.st.propose(QUEUE_UNDO, f"Poništi {r[0]['kind']} ({r[0]['unit_id']})",
                               {"event_id": event_id}, actor)

    def _on_undo(self, item: dict, approve: bool) -> None:
        if approve:
            self.undo(int(item["payload"]["event_id"]))

    def undo(self, event_id: int) -> list:
        from ..shared_lib import operator as OP
        who = OP.require_operator()
        r = self.st.rows("SELECT * FROM pse_events WHERE id=?", (event_id,))[0]
        data = json.loads(r["data"])
        if r["kind"] == "fisija":
            to_kill, to_restore = data["children"], [r["unit_id"]]
        else:
            to_kill, to_restore = [r["unit_id"]], data["parents"]
        for uid in to_kill:
            u = self.units.get(uid)
            if u is None:
                rows = self.st.rows("SELECT * FROM pse_units WHERE unit_id=?", (uid,))
                u = self._load(rows[0]) if rows else None
            if u is not None and u.alive:
                self.end(u, f"poništeno ({r['kind']})")
        back = []
        for uid in to_restore:
            back.append(self.restore(uid))
        self._event("ponisteno", r["unit_id"], {"of": event_id, "by": who})
        J.log(PSE_EV, who, {"event": "undo", "of": event_id, "kind": r["kind"]},
              subject=r["unit_id"], verdict="undone")
        return back

    def restore(self, uid: str) -> U.PSEUnit:
        """Bring a unit back from SHARED_LIB (its hand-over)."""
        h = self.st.rows("SELECT * FROM pse_handover WHERE unit_id=? ORDER BY id DESC LIMIT 1",
                         (uid,))[0]
        self.st.execute("UPDATE pse_handover SET restored=1 WHERE id=?", (h["id"],))
        self.st.execute("UPDATE pse_units SET alive=1, death_reason='', frozen=0, restricted=0 "
                        "WHERE unit_id=?", (uid,))
        self.units.pop(uid, None)
        u = self._load(self.st.rows("SELECT * FROM pse_units WHERE unit_id=?", (uid,))[0])
        J.log(PSE_EV, "SHARED_LIB", {"event": "restored", "unit": uid}, subject=uid)
        self._emit("restored", {"unit": uid})
        return u

    # ------------------------------------------------------------------ #
    # cases for weight learning [rule 17]
    def record_case(self, item: dict, approve: bool) -> None:
        from ..pse import weights as WT
        WT.record_case(self.st, item, approve)

    # ------------------------------------------------------------------ #
    def swarm(self) -> dict:
        """The health of the swarm, for the status bar and the reports."""
        live = [u for u in self.units.values() if u.alive and not getattr(u, "lab", False)]
        att = {}
        for u in live:
            a = self.assess(u).attractor
            att[a] = att.get(a, 0) + 1
        frozen = [u.unit_id for u in live if u.frozen]
        restricted = [u.unit_id for u in live if u.restricted]
        waiting = len(self.st.open_items(QUEUE_MEASURE))
        sick = sum(n for a, n in att.items() if a not in (K.HEALTHY, K.NOT_ENOUGH))
        mean = (sum(u.theta.current for u in live) / len(live)) if live else K.THETA_NOM
        status = ("frozen" if frozen else "measure" if waiting or restricted
                  else "sick" if sick else "healthy")
        return {"units": len(live), "attractors": att, "frozen": frozen,
                "restricted": restricted, "measures": waiting, "sick": sick,
                "theta_mean": round(mean, 2), "status": status,
                "defined": len([a for a in self.specs if not a.startswith("lab")])}

    def state(self) -> list[dict]:
        """Who is a PSE unit now (for the Laboratory and the reports)."""
        out = []
        for r in self.st.rows("SELECT * FROM pse_units ORDER BY agent, generation"):
            u = self.units.get(r["unit_id"])
            th = u.theta.current if u else None
            if th is None:
                m = self.st.rows("SELECT theta FROM pse_moves WHERE unit_id=? ORDER BY id DESC "
                                 "LIMIT 1", (r["unit_id"],))
                th = m[0]["theta"] if m else K.THETA_NOM
            att = (self.assess(u).attractor if u else "")
            out.append({"unit": r["unit_id"], "agent": r["agent"], "alive": bool(r["alive"]),
                        "frozen": bool(r["frozen"]), "restricted": bool(r["restricted"]),
                        "theta": round(th, 2), "attractor": att, "lab": bool(r["lab"]),
                        "steps_remaining": r["steps_remaining"], "generation": r["generation"],
                        "death_reason": r["death_reason"] or ""})
        return out


def _weights_decided(item: dict, approve: bool) -> None:
    from ..pse import weights as WT
    WT.on_decision(_store())(item, approve)


_LIB: Optional[PseLib] = None
_LIB_LOCK = threading.Lock()


def pse() -> PseLib:
    global _LIB
    with _LIB_LOCK:
        if _LIB is None or _LIB.st is not _store():
            _LIB = PseLib()
            from ..pse import agents as AG
            AG.define_all(_LIB)
        return _LIB


def reset_for_tests() -> None:
    global _LIB
    _LIB = None
