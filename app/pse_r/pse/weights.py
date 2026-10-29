"""
Vote weights [rule 17; §2.5 "who learns the vote weights"].

The weights live in SHARED_LIB, are versioned, and the version is logged with
every move (so a decision stays replayable). They change only when the
operator approves a proposal:

  * SHARED_LIB proposes once a week (and on "Predloži sada");
  * a proposal needs ≥ 200 decided cases since the last one, otherwise the
    answer is "nedovoljno podataka" and nothing is proposed;
  * one weight moves at most ±10 % per proposal.

What is learned now: the reader weights (rules vs model). A CASE is an
operator decision on a Doctor measure for a move that both readers read; the
operator's answer is the label (approved = something really was wrong). A
reader "said wrong" when its θ left the 30 ± 5 band. The six vote weights stay
at 1.0 until there is a label for the division of θ (none exists yet).
"""
from __future__ import annotations

import json
import time
from typing import Optional

from . import constants as K

DEFAULT = {"reader.rules": 0.5, "reader.model": 0.5,
           "vote.cardinality_affected": 1.0, "vote.absent_third_parties": 1.0,
           "vote.spoken_reversibility": 1.0, "vote.task_relationship": 1.0,
           "vote.relational_continuity": 1.0, "vote.delegation_depth": 1.0}

DDL = [
    """CREATE TABLE IF NOT EXISTS pse_vote_weights (
        version INTEGER PRIMARY KEY, ts REAL, weights TEXT, status TEXT,
        pending_id TEXT, cases INTEGER, by TEXT)""",
    """CREATE TABLE IF NOT EXISTS pse_cases (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, pending_id TEXT,
        theta_rules REAL, theta_model REAL, label INTEGER)""",
]
QUEUE = "vote-weights"
KV_LAST = "vote_weights_last_proposal"


def _ensure(st) -> None:
    st.ensure(DDL)
    if not st.rows("SELECT 1 FROM pse_vote_weights LIMIT 1"):
        st.execute("INSERT INTO pse_vote_weights VALUES (?,?,?,?,?,?,?)",
                   (1, time.time(), json.dumps(DEFAULT), "aktivno", "", 0, "SHARED_LIB"))


def current(st) -> tuple[int, dict]:
    _ensure(st)
    r = st.rows("SELECT version, weights FROM pse_vote_weights WHERE status='aktivno' "
                "ORDER BY version DESC LIMIT 1")
    return int(r[0]["version"]), json.loads(r[0]["weights"])


def history(st) -> list[dict]:
    _ensure(st)
    out = st.rows("SELECT * FROM pse_vote_weights ORDER BY version DESC")
    for d in out:
        d["weights"] = json.loads(d["weights"])
    return out


def record_case(st, item: dict, approve: bool) -> None:
    _ensure(st)
    r = st.rows("SELECT theta_rules, theta_model FROM pse_doctor WHERE pending_id=? "
                "ORDER BY id DESC LIMIT 1", (item["id"],))
    if not r or r[0]["theta_rules"] is None or r[0]["theta_model"] is None:
        return
    st.execute("INSERT INTO pse_cases (ts,pending_id,theta_rules,theta_model,label) "
               "VALUES (?,?,?,?,?)", (time.time(), item["id"], r[0]["theta_rules"],
                                      r[0]["theta_model"], int(bool(approve))))


def _since(st) -> list[dict]:
    last = st.rows("SELECT MAX(ts) t FROM pse_vote_weights WHERE status IN ('aktivno','odbijeno') "
                   "AND version > 1")
    t0 = last[0]["t"] or 0.0
    return st.rows("SELECT * FROM pse_cases WHERE ts > ? ORDER BY id", (t0,))


def proposal(st) -> Optional[dict]:
    """The weights SHARED_LIB would propose now, or None (not enough data)."""
    cases = _since(st)
    if len(cases) < K.WEIGHTS_MIN_CASES:
        return None
    _, w = current(st)

    def acc(col: str) -> float:
        ok = 0
        for c in cases:
            said_bad = abs(c[col] - K.THETA_NOM) > K.THETA_BAND
            ok += int(said_bad == bool(c["label"]))
        return ok / len(cases)

    ar, am = acc("theta_rules"), acc("theta_model")
    tot = ar + am or 1.0
    target = {"reader.rules": ar / tot, "reader.model": am / tot}
    new = dict(w)
    for k, t in target.items():
        lo, hi = w[k] * (1 - K.WEIGHTS_MAX_STEP), w[k] * (1 + K.WEIGHTS_MAX_STEP)
        new[k] = round(min(hi, max(lo, t)), 6)
    return {"weights": new, "cases": len(cases), "accuracy": {"rules": ar, "model": am}}


def propose(st, actor: str = "SHARED_LIB", force: bool = False) -> dict:
    """Weekly (or forced by "Predloži sada"). Returns {"status": ...}."""
    _ensure(st)
    now = time.time()
    last = st.kv_get(KV_LAST, 0.0) or 0.0
    if not force and now - last < K.WEIGHTS_PERIOD_S:
        return {"status": "nije-vrijeme"}
    if st.open_items(QUEUE):
        return {"status": "prijedlog-vec-ceka"}
    st.kv_set(KV_LAST, now)
    p = proposal(st)
    if p is None:
        return {"status": "nedovoljno-podataka", "cases": len(_since(st)),
                "needed": K.WEIGHTS_MIN_CASES}
    v = int(st.rows("SELECT MAX(version) v FROM pse_vote_weights")[0]["v"]) + 1
    pid = st.propose(QUEUE, f"Težine glasova v{v} ({p['cases']} slučajeva)",
                     {"version": v, **p}, actor)
    st.execute("INSERT INTO pse_vote_weights VALUES (?,?,?,?,?,?,?)",
               (v, now, json.dumps(p["weights"]), "ceka", pid, p["cases"], actor))
    return {"status": "predlozeno", "pending": pid, "version": v}


def on_decision(st):
    def _fn(item: dict, approve: bool) -> None:
        v = item["payload"]["version"]
        st.execute("UPDATE pse_vote_weights SET status=?, by=? WHERE version=?",
                   ("aktivno" if approve else "odbijeno", item.get("decided_by") or "operater", v))
    return _fn
