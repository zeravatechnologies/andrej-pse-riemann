"""
SHARED_LIB at runtime — the heartbeat that makes the library an overseer while
the app is open (wired 2026-10-25 after review: these pieces existed as library
code and tests but nothing ran them).

tick()            called by the GUI timer:
  * KEEPERS       every file in vault/reports is sealed when it appears; keeper
                  units are allocated in proportion to resources (not 1:1) and
                  patrol the seals; a broken seal is restored and logged as a
                  threat — the keepers' PSE unit records it as its move
  * ARXIV         at most once a day and only if the network answers: new QRH
                  papers become queue items "izvući metodu?" — the operator decides
                  whether the main AI may spend effort extracting it

Faza 6d: every agent is a PSE unit. Model outputs are screened on the unit's path
(pse/path.py) and judged by the Doctor (pse/doctor.py, shared_lib/pse_registry.py).

write_final_report() puts a final report under vault/reports and seals it.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from .. import config
from ..core import journal as J
from . import operator as OP
from . import reports as RP
from .store import store

REPORT_EXT = {".md", ".txt", ".pdf", ".html", ".json", ".png"}
ARXIV_INTERVAL_S = 24 * 3600
ARXIV_KIND = "arxiv-paper"
GUARD_KIND = "guard-pause"          # "→ ∞" tripped: approve = resume model calls

_SYNC_FOR_TESTS = False


# --------------------------------------------------------------------------- #
# keepers
# --------------------------------------------------------------------------- #
def _report_files() -> list[Path]:
    d = config.DIR_REPORTS
    if not d.exists():
        return []
    return sorted(p for p in d.rglob("*") if p.is_file() and p.suffix.lower() in REPORT_EXT)


def keepers_round() -> dict:
    """Seal what is new, allocate keepers, patrol. Returns a summary."""
    files = _report_files()
    sealed_paths = {r["path"] for r in RP.sealed()}
    newly = []
    for p in files:
        if str(p.resolve()) not in sealed_paths:
            RP.seal(p, actor="keeper")
            newly.append(p.name)
    n = len(files)
    keepers = RP.keepers_for(n)
    prev = store().kv_get("keepers_allocated", 0)
    if keepers != prev:
        J.log(J.UNIT, "shared_lib", {"event": "keepers_allocated", "keepers": keepers,
                                     "reports": n, "previous": prev},
              subject="keepers", verdict="allocated")
        store().kv_set("keepers_allocated", keepers)
    events = RP.patrol(actor="keeper") if keepers else []
    # the keepers' PSE unit: sealing and patrolling is work for the field; a
    # broken seal is found, journalled as a threat by an unknown writer and
    # restored (reversible) — the keepers did their job, it is not their harm
    from ..pse import measure as PM
    from ..pse import path as PATH
    acts = ([PM.Action("pečati novi izvještaj", "f")] * min(len(newly), 10) +
            [PM.Action("patrola pečata", "f")] * (1 if keepers else 0) +
            [PM.Action("vraća izmijenjen izvještaj iz pečata", "f")] * len(events))
    if acts:
        PATH.work("keepers", acts, entity=("izvjestaji", "document"),
                  note=f"{len(events)} izmjena" if events else "")
    return {"reports": n, "keepers": keepers, "sealed_now": newly,
            "tampered": [e["path"] for e in events]}


def write_final_report(name: str, text: str, actor: Optional[str] = None) -> Path:
    """Write a final report and seal it at once (the keepers take it from here)."""
    from ..guardian import content as C
    d = config.DIR_REPORTS
    d.mkdir(parents=True, exist_ok=True)
    fname = C.safe_filename(name)
    if not fname.endswith(".md"):
        fname += ".md"
    p = d / fname
    if p.exists():
        p = d / f"{p.stem}-{time.strftime('%H%M%S')}{p.suffix}"
    p.write_text(text, encoding="utf-8")
    J.log(J.REPORT, actor or OP.current() or "system",
          {"event": "issued", "path": str(p)}, subject=p.name, verdict="issued")
    RP.seal(p, actor=actor)
    return p


# --------------------------------------------------------------------------- #
# arXiv
# --------------------------------------------------------------------------- #
def arxiv_round(force: bool = False, fetch=None) -> dict:
    """At most daily: new QRH papers → queue items asking whether to extract."""
    last = store().kv_get("arxiv_last", 0)
    if not force and time.time() - last < ARXIV_INTERVAL_S:
        return {"skipped": True}
    from ..methods import arxiv as AX
    from . import missions as MIS
    owner = MIS.FEED_OWNER["arxiv-qrh"]
    if MIS.get(owner) is None:          # rule 38: the public edition has no QRH mission
        return {"skipped": True, "no_mission": owner}
    if not MIS.accepts_background(owner):
        # item 28a: the owning mission is parked and frozen — nothing is collected
        J.log(J.INGEST, "arxiv", {"event": "frozen", "mission": owner}, verdict="frozen")
        return {"skipped": True, "frozen": owner}
    from ..pse import measure as PM
    from ..pse import path as PATH
    ok, why = PATH.may_act("arxiv")
    if not ok:                        # Faza 6d: a frozen unit does not act
        J.log(J.INGEST, "arxiv", {"event": "unit_frozen", "why": why}, verdict="frozen")
        return {"skipped": True, "frozen": why}
    quiet = MIS.is_quiet(owner)
    items = (fetch or AX.watch)()
    store().kv_set("arxiv_last", time.time())
    seen = set(store().kv_get("arxiv_seen", []))
    new = []
    for it in items:
        rid = getattr(it, "source_ref", "") or getattr(it, "id", "") or getattr(it, "url", "")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        title = getattr(it, "title", rid)
        payload = {"ref": rid, "title": title, "mission": owner,
                   "abstract": (getattr(it, "abstract", "") or "")[:2000]}
        if quiet:                     # parked + collecting: no queue noise until resume
            MIS.hold(owner, ARXIV_KIND, payload)
        else:
            store().propose(ARXIV_KIND, f"Novi QRH rad: {title[:120]} — izvući metodu?",
                            payload, proposer="arxiv")
        new.append(rid)
    store().kv_set("arxiv_seen", sorted(seen))
    try:                              # item 28: what was read may inspire (never a claim)
        from . import ideas as IDEAS
        IDEAS.consider(items, ask_main=False)
    except Exception as e:                              # noqa: BLE001
        J.log(J.INGEST, "ideas", {"event": "consider_failed", "error": str(e)[:200]},
              verdict="failed")
    PATH.work("arxiv", [PM.Action("straži arXiv za misiju", "f")] +
              [PM.Action("novi rad u red operatera", "o", external=True)] * min(len(new), 20),
              entity=("arxiv.org", "source"), note=f"{len(new)} novih")
    J.log(J.INGEST, "arxiv", {"event": "qrh_watch", "found": len(items), "new": new},
          verdict="watched")
    return {"skipped": False, "found": len(items), "new": new, "quiet": quiet}


def _on_arxiv(item: dict, approved: bool) -> None:
    """Approved → the main AI extracts a method pack, which goes through the door."""
    if not approved:
        return
    import threading

    def work():
        from ..methods import extract as EXT
        try:
            EXT.extract_and_propose(item["payload"]["ref"], item["payload"].get("title", ""))
        except Exception as e:                          # noqa: BLE001
            J.log(J.METHOD, "extract", {"event": "failed", "ref": item["payload"]["ref"],
                                        "error": str(e)[:300]}, verdict="failed")
    # a model call takes minutes: never block the window; the result lands in
    # the queue (reproduced) or in the journal (failed / refused at the door)
    t = threading.Thread(target=work, name="extract", daemon=True)
    t.start()
    if _SYNC_FOR_TESTS:
        t.join()


# --------------------------------------------------------------------------- #
# "→ ∞" (master §5, fix A1): pause → free → tell the operator
# --------------------------------------------------------------------------- #
_METRIC_TEXT = {"latency": "trajanje poziva (s)", "rss": "memorija procesa (GB)",
                "queue": "dužina reda poziva"}


def _on_guard_trip(metric: str, value: float, L: float) -> None:
    from ..core import actions as A
    from ..llm.gguf import GGUFBackend
    A.require_auto("guard.pause")
    A.require_auto("model.unload")
    GGUFBackend.unload()
    from ..core import replay as RPL
    from ..llm import limits as LIM
    st = LIM.pause_state()
    inp = {"metric": metric, "L": L, "floor": st.get("floor", 0.5),
           "history": st.get("history") or [value]}
    J.log(J.SYSTEM, "guard", {"event": "diverging", "metric": metric,
                              "value": value, "L": L,
                              "replay": RPL.record("guard.trip", inp, {"trip": True})},
          subject=metric, verdict="paused")
    from ..pse import path as PATH                     # rule 20 (5): the unit that was calling
    PATH.brake_tripped(f"→ ∞ {metric}")
    if store().open_items(GUARD_KIND):
        return
    store().propose(GUARD_KIND,
                    f"„→ ∞“: {_METRIC_TEXT.get(metric, metric)} = {value:.3g} (L = {L:.3g})"
                    " — pozivi modelu pauzirani, model oslobođen. Odobri = nastavi.",
                    {"metric": metric, "value": value, "L": L}, proposer="guard")


def _on_guard_decision(item: dict, approved: bool) -> None:
    from ..llm import limits as LIM
    if approved:
        LIM.resume()
        J.log(J.SYSTEM, "guard", {"event": "resumed", "id": item["id"]},
              subject=item["payload"].get("metric", ""), verdict="resumed")


def install_hooks() -> None:
    from ..llm import limits as LIM
    store().on_decision(ARXIV_KIND, _on_arxiv)
    store().on_decision(GUARD_KIND, _on_guard_decision)
    from ..guardian import unit as _GU                  # quarantine → operator (live test fix)
    _GU.install_hooks()
    LIM.on_pause(_on_guard_trip)
    from ..pse import path as PATH                     # Faza 6d: units and their reader
    PATH.install_reader()
    from . import mission_agent as MA                  # P3: proposals from mission talks
    MA.install_hooks()
    LIM.configure(LIM.Limits.from_settings())
    # a pause survives a restart: an open "→ ∞" item means calls stay paused
    for it in store().open_items(GUARD_KIND):
        p = it["payload"]
        LIM.trip(p.get("metric", "?"), float(p.get("value", 0)), float(p.get("L", 0)),
                 notify=False)
        break


REPLAY_INTERVAL_S = 24 * 3600


def replay_round(force: bool = False) -> dict:
    """At most daily, in the background: re-derive every recorded decision
    (round 3, item 6). A mismatch is journalled and queued by core.replay."""
    last = store().kv_get("replay_last", 0)
    if not force and time.time() - last < REPLAY_INTERVAL_S:
        return {"skipped": True}
    store().kv_set("replay_last", time.time())
    import threading

    def work():
        from ..core import replay as RPL
        rep = RPL.replay_all()
        store().kv_set("replay_report", {"at": time.time(), "summary": rep.summary(),
                                         "intact": rep.intact, "checked": rep.checked})
        J.log(J.SYSTEM, "replay", {"event": "replayed", "summary": rep.summary(),
                                   "intact": rep.intact}, subject="journal",
              verdict="intact" if rep.intact else "violation")
    t = threading.Thread(target=work, name="replay", daemon=True)
    t.start()
    if _SYNC_FOR_TESTS:
        t.join()
    return {"skipped": False}


def retention_round(force: bool = False) -> dict:
    """At most daily: archive the journal's oldest events behind an anchor, and
    check every archive against its anchor (a broken archive is a threat)."""
    from ..core import archive as AR
    last = store().kv_get("retention_last", 0)
    if not force and time.time() - last < REPLAY_INTERVAL_S:
        return {"skipped": True}
    store().kv_set("retention_last", time.time())
    from .. import settings as S
    st = S.load()
    out = AR.retention_round(keep_days=float(st.get("journal_keep_days", 90)),
                             keep_min=int(st.get("journal_keep_min", 20000)),
                             max_live=int(st.get("journal_max_live", 200000)))
    ok, problems = AR.verify_archives()
    if not ok:
        J.log(J.THREAT, "keeper", {"event": "archive_broken", "problems": problems[:20]},
              subject="archive", verdict="threat")
        if not store().open_items("integrity"):
            store().propose("integrity", "NARUŠEN INTEGRITET arhive dnevnika: "
                            + "; ".join(problems[:3]), {"problems": problems[:50]},
                            proposer="keeper")
    out["archives_ok"] = ok
    return out


def tick(online: Optional[bool] = None) -> dict:
    out = {"keepers": keepers_round(), "replay": replay_round(),
           "retention": retention_round()}
    if online:
        try:
            out["arxiv"] = arxiv_round()
        except Exception as e:                          # noqa: BLE001
            out["arxiv"] = {"error": str(e)[:200]}
        try:                                            # item 28: weekly inspiration round
            from . import ideas as IDEAS
            out["ideas"] = IDEAS.ideas_round()
        except Exception as e:                          # noqa: BLE001
            out["ideas"] = {"error": str(e)[:200]}
    try:
        from . import ideas as IDEAS
        out["ideas_publish"] = IDEAS.publish_async()
    except Exception as e:                              # noqa: BLE001
        out["ideas_publish"] = {"error": str(e)[:200]}
    try:                                                # Faza 6d, rule 17: weekly proposal
        from ..pse import weights as WT
        out["vote_weights"] = WT.propose(store())
    except Exception as e:                              # noqa: BLE001
        out["vote_weights"] = {"error": str(e)[:200]}
    return out
