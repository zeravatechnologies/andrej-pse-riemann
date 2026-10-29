"""
The SSH guardian — a PSE unit that always runs (round 3, item 14; master §10).

Every poll: read new sshd lines (logsource), turn them into events (parse),
and for every hostile event:
  COLLECT   the Guardian Source Record in SHARED_LIB (kv "ssh_sources"): first
            and last seen, counts by kind, user names tried, the three key counts;
  COUNT     by the three keys (identity · cluster · target), each under "→ ∞";
  REPORT    1–2 keys diverging → TIER 1: threat record + closer watch (nothing
            irreversible, no human needed);
  REMOVE    all three diverging → TIER 2, reversible and automatic: end the
            session, block the source for 24 h (auto-undo). Permanent block and
            stopping SSH are proposals with the exact command.
  ALARM     no sudoers rule → DANGER alarm (kv "danger_alarm"), never silence.

THETA (master §10.6–10.7). The guardian's own balance: OTHER = attention spent
on the environment (hostile events, interventions), SELF = its own verification
(re-reading the source record and the key counts before acting, undo checks).
It must stay in [25, 35] and must not be flat: above 35 the guardian is
over-absorbing the attacker; flat (σ < 0.01 while traffic flows) it is asleep —
then it is REPLACED (fresh counters; the record in SHARED_LIB stays).
"""
from __future__ import annotations

import time
from typing import Optional

from ...core import journal as J
from .. import containment as C
from .. import templates as T
from . import keys as K
from . import logsource as LS
from . import parse as P

KV_STATE = "ssh_guardian"
KV_SOURCES = "ssh_sources"
KV_ALARM = "danger_alarm"
THETA_BAND = (25.0, 35.0)
ACCEPT_AFTER_ATTACK = 5         # a login that succeeds after ≥ N failures = alarm


def _store():
    from ...shared_lib.store import store
    return store()


class SSHGuardian:
    def __init__(self, source=None, limits: Optional[dict] = None,
                 accounts: Optional[set] = None, clock=time.time):
        st = _store().kv_get(KV_STATE, {}) or {}
        if source is None:
            kind, source = LS.default_source(st.get("source"))
            self.source_kind = kind
        else:
            self.source_kind = "test"
        self.source = source
        self.clock = clock
        if limits is None:
            from ... import settings as S
            limits = S.load().get("ssh_L") or {}
        self.keys = K.ThreeKeys(limits, accounts)
        self.stats = {"lines": 0, "events": 0, "tier1": 0, "tier2": 0}

    # ---------------------------------------------------------------- loop
    def poll(self) -> dict:
        lines = self.source.poll() if self.source else []
        o = s = 0.0
        out = {"lines": len(lines), "events": 0, "tier1": [], "tier2": [], "alarms": []}
        for ln in lines:
            ev = P.parse(ln)
            if ev is None:
                continue
            out["events"] += 1
            r = self.handle(ev)
            o += r["other"]
            s += r["self"]
            for k in ("tier1", "tier2", "alarms"):
                out[k] += r.get(k, [])
        undone = C.undo_expired(self.clock())
        s += 0.5 * len(undone)
        self._theta(o, s)
        self._persist()
        self.stats["lines"] += len(lines)
        out["theta"] = self.theta()
        out["unblocked"] = undone
        return out

    def handle(self, ev: P.Event) -> dict:
        now = self.clock()
        r = {"other": 0.0, "self": 0.0, "tier1": [], "tier2": [], "alarms": []}
        rec = self._record(ev, now)
        if ev.kind == P.ACCEPT:
            if rec.get("failed", 0) >= ACCEPT_AFTER_ATTACK:
                J.log(J.THREAT, "ssh-guardian", {"event": "login_after_attack", "ip": ev.ip,
                                                 "user": ev.user, "failed": rec["failed"]},
                      subject=ev.ip, verdict="alarm")
                r["alarms"].append(self._alarm("ssh.tier1", ip=ev.ip, n=rec["failed"], k=3))
            return r
        if not ev.hostile:
            return r
        self.stats["events"] += 1
        res = self.keys.observe(ev.ip, ev.user, now, shape=f"{ev.kind}:{ev.method or '-'}")
        rec["keys"] = {k: v["count"] for k, v in res.items()}
        k = K.ThreeKeys.violated(res)
        try:
            return self._decide(ev, rec, res, k, r, now)
        finally:
            _store().kv_set(KV_SOURCES, {**_store().kv_get(KV_SOURCES, {}), ev.ip: rec})

    def _decide(self, ev, rec, res, k, r, now) -> dict:
        r["other"] += 1.0
        # self: verify before any action — re-read the record, recount the keys
        r["self"] += 2.0 + (1.5 * k)
        if k == 0:
            return r
        if k < 3:
            self.stats["tier1"] += 1
            msg = T.render("ssh.tier1", ip=ev.ip, n=rec["hostile"], k=k)
            if rec.get("tier1_reported", 0) < k:            # report each escalation once
                rec["tier1_reported"] = k
                J.log(J.THREAT, "ssh-guardian", {"event": "tier1", "ip": ev.ip, "keys": res,
                                                 "message": msg}, subject=ev.ip, verdict="observe")
                r["tier1"].append(msg)
            r["other"] += 0.5
            return r
        # TIER 2 — all three keys "→ ∞"
        self.stats["tier2"] += 1
        r["other"] += 2.0
        try:
            if ev.pid:
                try:
                    C.kill_session(ev.pid, ev.ip)
                    r["tier2"].append(T.render("ssh.session_killed", pid=ev.pid, ip=ev.ip))
                except RuntimeError:
                    pass                                     # session already gone
            b = C.block_ip_24h(ev.ip, f"tri ključa: {res}", now)
            r["tier2"].append(T.render("ssh.blocked", ip=ev.ip, target=res["target"]["value"]
                                       if res["target"]["value"] != "sshd" else "sshd",
                                       until=b.get("until_text", "za 24 h")))
        except C.Protected as e:
            J.log(J.THREAT, "ssh-guardian", {"event": "protected_target", "ip": ev.ip,
                                             "why": str(e)}, subject=ev.ip, verdict="refused")
        except C.NoRights:
            r["alarms"].append(self._alarm("ssh.no_rights", ip=ev.ip,
                                           cmd=C.permanent_block_command(ev.ip)))
        return r

    # ---------------------------------------------------------------- record
    def _record(self, ev: P.Event, now: float) -> dict:
        allrec = _store().kv_get(KV_SOURCES, {})
        rec = allrec.get(ev.ip) or {"first": now, "hostile": 0, "failed": 0, "kinds": {},
                                    "users": []}
        rec["last"] = now
        rec["kinds"][ev.kind] = rec["kinds"].get(ev.kind, 0) + 1
        if ev.hostile:
            rec["hostile"] += 1
        if ev.kind in (P.FAIL, P.INVALID, P.MAXAUTH):
            rec["failed"] += 1
        if ev.user and ev.user not in rec["users"] and len(rec["users"]) < 50:
            rec["users"].append(ev.user[:32])
        allrec[ev.ip] = rec
        if len(allrec) > 5000:                               # bounded: keep the most recent
            allrec = dict(sorted(allrec.items(), key=lambda x: -x[1].get("last", 0))[:4000])
        _store().kv_set(KV_SOURCES, allrec)
        return rec

    def _alarm(self, tid: str, **slots) -> str:
        """DANGER (item 16): a template message, in SHARED_LIB, until acknowledged."""
        text = T.render(tid, **slots)
        cur = _store().kv_get(KV_ALARM) or {}
        if not cur or cur.get("acknowledged"):
            _store().kv_set(KV_ALARM, {"template": tid, "text": text, "at": self.clock(),
                                       "acknowledged": False})
        J.log(J.THREAT, "ssh-guardian", {"event": "danger_alarm", "template": tid,
                                         "text": text}, subject=slots.get("ip", ""),
              verdict="alarm")
        return text

    # ---------------------------------------------------------------- theta
    def _theta(self, o: float, s: float) -> None:
        """The poll is a move of the SSH guardian's PSE unit (Faza 6d): its θ is
        measured by SHARED_LIB's meter; a flat θ while traffic flows is the
        schizoid attractor, and the Doctor — not this class — replaces it."""
        if o + s <= 0:
            return                                           # nothing happened: no move
        from ...pse import measure as PM
        from ...pse import path as PATH
        acts = ([PM.Action("odgovara napadaču", "o", checked=True)] * min(int(o), 20) +
                [PM.Action("provjera prije radnje", "s", justified=True)] * min(int(s), 40))
        try:
            # attackers it actually engaged with are on its boundary; a guardian
            # that registers no one while it works is the schizoid one (rule 5a)
            PATH.work("ssh-guardian", acts, entity=("ssh-napadači", "source") if o > 0 else None)
        except Exception:                                    # noqa: BLE001 — never blocks
            pass

    def _unit(self):
        from ...pse import path as PATH
        return PATH.unit("ssh-guardian")

    @property
    def generation(self) -> int:
        try:
            return self._unit().core.generation
        except Exception:                                    # noqa: BLE001
            return 1

    def theta(self) -> Optional[float]:
        try:
            return round(self._unit().theta.current, 2)
        except Exception:                                    # noqa: BLE001
            return None

    def health(self) -> dict:
        from ...pse import swing as SW
        u = self._unit()
        rep = SW.assess(u.theta.series, boundary_empty=not u.boundary.entities)
        status = {"H": "zdrava", "S": "ravna (spava)", "C": "previše upija napadača",
                  "N": "ispod opsega", "B": "njiše se", "?": "zagrijavanje"}.get(
                      rep.attractor, rep.attractor)
        if u.frozen:
            status += " · zamrznuta (Doktor)"
        return {"theta": round(u.theta.current, 2), "sigma": round(rep.sigma, 3),
                "status": status, "generation": u.core.generation}

    def _persist(self) -> None:
        st = {"source": ({"kind": self.source_kind, **self.source.state()}
                         if self.source is not None and hasattr(self.source, "state") else {})}
        _store().kv_set(KV_STATE, st)


def acknowledge_alarm(actor: str) -> None:
    a = _store().kv_get(KV_ALARM) or {}
    if a:
        a["acknowledged"] = True
        a["ack_by"] = actor
        _store().kv_set(KV_ALARM, a)
        J.log(J.THREAT, actor, {"event": "danger_alarm_acknowledged"}, subject="alarm",
              verdict="acknowledged")


def pending_alarm() -> Optional[dict]:
    a = _store().kv_get(KV_ALARM) or {}
    return a if a and not a.get("acknowledged") else None
