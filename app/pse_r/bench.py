"""
Measured benchmark (round 3, item 22; Svarog S7).

Labelled, SYNTHETIC scenarios (bench/corpus.json — written for this purpose,
not real attacks or real conversations) are run through the SAME decision
paths the app uses:

  three harms   the harm sensor + PSE test unit + Doctor, exactly as pse/path.py
                them (chat vs final output) → the 3-of-3 diagnoser; "detected"
                = hold or infected at any point of the scenario
  SSH           the SSHGuardian unit with the default three-key limits, its
                containment replaced by a recorder (nothing is blocked for real)
  kill switch   the "→ ∞" watch of the kill switch, with close() recorded
                instead of executed

Output: per detector TP/FP/TN/FN, false-positive and false-negative rates, and
every miss by name — so the numbers can be checked, not just believed.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path


def corpus_path() -> Path:
    from . import config
    for p in (config.APP_ROOT / "bench" / "corpus.json", config.APP_DIR / "bench" / "corpus.json"):
        if p.exists():
            return p
    raise FileNotFoundError("bench/corpus.json")


def _rates(rows: list) -> dict:
    tp = sum(1 for r in rows if r["truth"] and r["detected"])
    fn = sum(1 for r in rows if r["truth"] and not r["detected"])
    fp = sum(1 for r in rows if not r["truth"] and r["detected"])
    tn = sum(1 for r in rows if not r["truth"] and not r["detected"])
    return {"TP": tp, "FP": fp, "TN": tn, "FN": fn,
            "FPR": round(fp / max(1, fp + tn), 3), "FNR": round(fn / max(1, fn + tp), 3),
            "misses": [r["id"] for r in rows if r["truth"] != r["detected"]]}


# ---------------------------------------------------------------- three harms
def bench_harms(scen: list) -> dict:
    """Each scenario runs through a fresh PSE test unit, exactly as a model output
    runs through an agent's unit (pse/path.py): the harm sensor, the move, the
    Doctor. Detected = the Doctor found something bad (a measure to the operator)."""
    from .pse import path as PATH
    from .pse import unit as PU
    from .shared_lib.pse_registry import AgentSpec, pse
    lib = pse()
    rows = []
    for s in scen:
        key = f"lab-bench-{s['id']}"
        lib.define(AgentSpec(key, PU.Mission("bench", "odgovara", "bez zla"), 50, "bench",
                             False))
        old = [u for u in list(lib.units.values()) if u.agent == key]
        for u in old:
            lib.end(u, "nova bench runda")
        u = lib._spawn(key, lab=True)
        lib.harm_runs.pop(u.unit_id, None)
        detected = False
        for o in s["outputs"]:
            text, data, final = o.get("text", ""), o.get("data", ""), o.get("final", False)
            harms = PATH.screen(text, data_in_context=data, final=final,
                                sources=o.get("sources", []))
            res = lib.move(u, words=text, harms=harms, note="bench")
            if res.finding and res.finding.get("bad"):
                detected = True
            if u.restricted or u.frozen:
                detected = True
        lib.end(u, "kraj bench scenarija")
        rows.append({"id": s["id"], "truth": s["label"] == "harmful",
                     "detected": detected, "level": "mjera" if detected else "čisto"})
    return {"rows": rows, **_rates(rows)}


# ---------------------------------------------------------------- SSH
@contextmanager
def _recorded_containment():
    from .guardian import containment as C
    saved = (C.have_rights, C._helper, C._own_addresses)
    calls = []
    C.have_rights = lambda refresh=False: (True, "bench")
    C._helper = lambda verb, arg: calls.append((verb, arg)) or "bench"
    C._own_addresses = lambda: {"127.0.0.1", "::1"}
    try:
        yield calls
    finally:
        C.have_rights, C._helper, C._own_addresses = saved


def bench_ssh(scen: list) -> dict:
    from .guardian import containment as C
    from .guardian.ssh import unit as U
    from .shared_lib.store import store
    rows_block, rows_any = [], []
    ts = "2026-10-25T19:45:01.000000-04:00 bench "
    with _recorded_containment() as calls:
        for s in scen:
            for r in C.active():
                store().execute("UPDATE containment SET undone_at=1 WHERE id=?", (r["id"],))
            store().kv_set(U.KV_SOURCES, {})

            class Src:
                lines = [f"{ts}sshd[4242]: {ln}" for ln in s["lines"]]

                def poll(self):
                    out, self.lines = self.lines, []
                    return out

                def state(self):
                    return {}
            calls.clear()
            g = U.SSHGuardian(source=Src(), accounts={"root", "a"}, clock=lambda: 1.0e9)
            out = g.poll()
            blocked = any(c[0] == "block-ip" for c in calls)
            reported = bool(out["tier1"]) or blocked
            attack = s["label"] == "attack"
            rows_any.append({"id": s["id"], "truth": attack, "detected": reported})
            if s["expect"] in ("block", "none"):
                rows_block.append({"id": s["id"], "truth": s["expect"] == "block",
                                   "detected": blocked})
    return {"report_level": {"rows": rows_any, **_rates(rows_any)},
            "block_level": {"rows": rows_block, **_rates(rows_block)}}


# ---------------------------------------------------------------- kill switch
def bench_killswitch(scen: list) -> dict:
    from .guardian import killswitch as KS
    rows = []
    saved = KS.close
    try:
        for s in scen:
            KS._reset_for_tests()
            tripped = {"x": False}
            KS.close = lambda *a, **k: tripped.__setitem__("x", True) or {}
            t = 1.0e9
            for c in s["calls"]:
                t += c["dt"]
                if KS.observe_cloud_call("bench", c["tokens"], c["usd"], now=t):
                    break
            rows.append({"id": s["id"], "truth": s["label"] == "runaway",
                         "detected": tripped["x"]})
    finally:
        KS.close = saved
        KS._reset_for_tests()
    return {"rows": rows, **_rates(rows)}


# ---------------------------------------------------------------- all
def run() -> dict:
    c = json.loads(corpus_path().read_text(encoding="utf-8"))
    return {"note": c.get("note", ""), "harms": bench_harms(c["harms"]),
            "ssh": bench_ssh(c["ssh"]), "killswitch": bench_killswitch(c["killswitch"])}


def markdown(res: dict) -> str:
    def line(name, r):
        return (f"| {name} | {r['TP']} | {r['FP']} | {r['TN']} | {r['FN']} | "
                f"{r['FPR']:.3f} | {r['FNR']:.3f} | {', '.join(r['misses']) or '—'} |")
    L = ["# Benchmark čuvara i liječenja", "", f"_{res['note']}_", "",
         "| detektor | TP | FP | TN | FN | lažno pozitivni | lažno negativni | promašaji |",
         "|---|---|---|---|---|---|---|---|",
         line("tri zla (zadržavanje ili zaraza)", res["harms"]),
         line("SSH — prijava (nivo 1 ili 2)", res["ssh"]["report_level"]),
         line("SSH — blokada (nivo 2)", res["ssh"]["block_level"]),
         line("prekidač za online AI", res["killswitch"]), ""]
    return "\n".join(L)
