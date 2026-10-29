"""
Missions (plan F9, PSE-L level L3: state → action → outcome).

A mission is a standing question the system is working on. It is not a to-do
list: it is a living record of where the frontier is and which way the last
piece of evidence moved it. Each mission carries the lowest exponent B it has
seen (the frontier) and a log of steps, each a {state, action, outcome} triple
in the PSE-L sense:

    state     where the frontier stood before this step
    action    what happened (a method imported, an extension explored)
    outcome   which way it moved — bliže / dalje / zid — and the new frontier

Missions live in the SHARED_LIB store, so `missions` and `mission_steps` are
automatically part of the read-only fact layer (views.py attaches every store
table). The first mission is the one the author dictated: is there a continuous
transformation between QRH methods, and does extending it move B toward the
targets (0.87, 5/6, 3/4, 1/2) or away?
"""
from __future__ import annotations

import time
from typing import Optional

from ..core import journal as J
from . import operator as OP
from .store import store

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS missions (
        id       TEXT PRIMARY KEY,
        title    TEXT NOT NULL,
        question TEXT NOT NULL,
        state    TEXT NOT NULL,
        best_B   REAL,
        created  REAL NOT NULL,
        updated  REAL NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS mission_steps (
        id         INTEGER PRIMARY KEY,
        mission_id TEXT NOT NULL,
        ts         REAL NOT NULL,
        state      TEXT NOT NULL,
        action     TEXT NOT NULL,
        outcome    TEXT NOT NULL,
        ref        TEXT
    )""",
    "CREATE INDEX IF NOT EXISTS idx_steps_mission ON mission_steps(mission_id)",
]

# Round 3, items 26–27: every mission has a GOAL the operator chooses (always in the
# Missions menu). The app may only PROPOSE a change (human queue), never make it.
GOALS = {1: "mapa prenosivosti (podrazumijevano)", 2: "E_d i T_d uslovno (pod pretpostavkom)",
         3: "samo praćenje (kartice i ideje)"}
GOAL_KIND = "mission-goal"
SECOND_ID = "misija-visi-stepen"


def _migrate() -> None:
    cols = {r["name"] for r in store().rows("PRAGMA table_info(missions)")}
    if "goal" not in cols:
        store().execute("ALTER TABLE missions ADD COLUMN goal INTEGER NOT NULL DEFAULT 1")
    # round 3, item 28a: work on missions in turn ("ostavi za kasnije")
    for col, ddl in (("parked", "INTEGER NOT NULL DEFAULT 0"), ("parked_at", "REAL"),
                     ("parked_note", "TEXT"), ("parked_snapshot", "TEXT"),
                     ("background", "TEXT NOT NULL DEFAULT 'freeze'")):
        if col not in cols:
            store().execute(f"ALTER TABLE missions ADD COLUMN {col} {ddl}")

FIRST_ID = "misija-kontinualna-transformacija"
TARGETS = (0.87, 5 / 6, 3 / 4, 1 / 2)


def _ensure() -> None:
    store().ensure(_SCHEMA)
    _migrate()


def create(mid: str, title: str, question: str, state: str,
           best_B: Optional[float] = None) -> str:
    _ensure()
    now = time.time()
    store().execute(
        "INSERT OR IGNORE INTO missions(id,title,question,state,best_B,created,updated)"
        " VALUES (?,?,?,?,?,?,?)", (mid, title, question, state, best_B, now, now))
    J.log(J.MISSION, OP.current() or "system",
          {"event": "created", "id": mid, "title": title, "best_B": best_B},
          subject=mid, verdict="open")
    return mid


def new_mission(title: str, question: str) -> str:
    """The operator opens a new mission (both editions; the public one starts
    with none). Its first state is "otvorena"."""
    import re as _re
    import unicodedata as _ud
    OP.require_operator()
    title, question = (title or "").strip(), (question or "").strip()
    if not title or not question:
        raise ValueError("misija treba naslov i pitanje")
    slug = _ud.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    slug = _re.sub(r"[^a-z0-9]+", "-", slug).strip("-")[:40] or "misija"
    mid, n = f"misija-{slug}", 1
    while get(mid) is not None:
        n += 1
        mid = f"misija-{slug}-{n}"
    return create(mid, title, question, "otvorena")


def get(mid: str) -> Optional[dict]:
    _ensure()
    r = store().rows("SELECT * FROM missions WHERE id=?", (mid,))
    if not r:
        return None
    m = r[0]
    m["steps"] = store().rows(
        "SELECT ts,state,action,outcome,ref FROM mission_steps WHERE mission_id=? "
        "ORDER BY ts", (mid,))
    return m


def all_missions() -> list[dict]:
    _ensure()
    return store().rows("SELECT * FROM missions ORDER BY created")


def step(mid: str, action: str, outcome: str, new_state: str,
         best_B: Optional[float] = None, ref: str = "") -> None:
    """Record one {state, action, outcome} step and move the mission forward."""
    _ensure()
    m = get(mid)
    if m is None:
        raise KeyError(mid)
    prev_state = m["state"]
    now = time.time()
    store().execute(
        "INSERT INTO mission_steps(mission_id,ts,state,action,outcome,ref)"
        " VALUES (?,?,?,?,?,?)", (mid, now, prev_state, action, outcome, ref))
    best = m["best_B"]
    if best_B is not None and (best is None or best_B < best):
        best = best_B
    store().execute("UPDATE missions SET state=?, best_B=?, updated=? WHERE id=?",
                    (new_state, best, now, mid))
    J.log(J.MISSION, OP.current() or "system",
          {"event": "step", "id": mid, "action": action, "outcome": outcome,
           "best_B": best}, subject=mid, verdict=outcome)


def record_method(mid: str, method_name: str, B: float, source: str = "") -> str:
    """
    A method was accepted against this mission. Compare its boundary to the
    current frontier and record the outcome (bliže / dalje / isto), noting how
    far it still is from the nearest target.
    """
    from ..methods import core as C
    m = get(mid)
    if m is None:
        raise KeyError(mid)
    old = m["best_B"]
    outcome = "bliže" if old is None else C.verdict(old, B)
    front = B if old is None else min(old, B)
    nearest = min(TARGETS, key=lambda t: abs(t - front))
    new_state = (f"Front na B={front:.9f}. Zadnji unos ({method_name}) "
                 f"{'je prva tačka' if old is None else f'je {outcome} (prije {old:.9f})'}; "
                 f"najbliži cilj {nearest:.6f}, udaljenost {abs(front - nearest):.6f}.")
    action = f"uvezena i potvrđena metoda {method_name} (B*={B:.9f})"
    outcome_line = (f"{outcome}: front {old:.9f} → {B:.9f}" if old is not None
                    else f"prva tačka fronta: {B:.9f}")
    step(mid, action, outcome_line, new_state, best_B=B, ref=source or method_name)
    return outcome


def seed_first() -> str:
    """The mission the author dictated (REPORT §7). Idempotent."""
    _ensure()
    if get(FIRST_ID) is not None:
        return FIRST_ID
    return create(
        FIRST_ID,
        "Kontinualna transformacija između QRH metoda",
        "Postoji li kontinualna funkcija transformacije koja eksponent visoke "
        "strane jedne QRH metode prevodi u sljedeću (Liu → Xu–Sang: "
        "E_XS = E_Liu + T, potvrđeno), i da li njeno proširenje (t, w, nove "
        "familije) pomjera B prema ciljevima (0.87, 5/6, 3/4, 1/2) ili od njih? "
        "Svaki novi rad = nova tačka i nova T.",
        state=("Otvorena. Unutar Liu/Xu–Sang familije transformacija JESTE "
               "kontinualna; proširenja se približavaju do zidova (~0.870 / 5/6), "
               "ne prema 1/2. Svaki novi rad kroz vrata dodaje tačku."),
        best_B=None)


# --------------------------------------------------------------------------- #
# goals (round 3, items 26–27)
# --------------------------------------------------------------------------- #
def set_goal(mid: str, goal: int, reason: str = "") -> None:
    """Only the operator changes a mission's goal; journalled with the name."""
    _ensure()
    who = OP.require_operator()
    if goal not in GOALS:
        raise ValueError(f"cilj mora biti 1, 2 ili 3 (ne {goal})")
    m = get(mid)
    if m is None:
        raise KeyError(mid)
    store().execute("UPDATE missions SET goal=?, updated=? WHERE id=?", (goal, time.time(), mid))
    J.log(J.MISSION, who, {"event": "goal_changed", "id": mid, "from": m.get("goal", 1),
                           "to": goal, "reason": reason[:300]}, subject=mid, verdict="goal")


def propose_goal(mid: str, goal: int, why: str, proposer: str = "system") -> str:
    """The app's only way to change a goal: ask the operator."""
    if goal not in GOALS:
        raise ValueError("cilj mora biti 1, 2 ili 3")
    for it in store().open_items(GOAL_KIND):
        if it["payload"].get("mission") == mid and it["payload"].get("goal") == goal:
            return it["id"]
    return store().propose(GOAL_KIND, f"Prijedlog: cilj misije „{mid}“ → {goal} ({GOALS[goal]})",
                           {"mission": mid, "goal": goal, "why": why[:1000]}, proposer)


def _on_goal_decision(item: dict, approved: bool) -> None:
    if approved:
        set_goal(item["payload"]["mission"], int(item["payload"]["goal"]),
                 "odobren prijedlog: " + item["payload"].get("why", "")[:200])


def install_hooks() -> None:
    store().on_decision(GOAL_KIND, _on_goal_decision)
    store().on_decision(SWITCH_KIND, _on_switch_decision)


# The transfer map of mission 2 (goal 1): every step of the 7/8 proof and whether
# it carries over to higher degree. First draft from research/langlands-2026-10
# (§4) — our reading, unreviewed; each later decision is a mission step.
TRANSFER_MAP = [
    ("Möbiusove sume nad karakterima", "vjerovatno se prenosi (koeficijenti 1/L)",
     "izvor-large-sieve-gln-2508-14888"),
    ("Gaussove sume → kubna theta (Kubota/Patterson)", "nema poznatog analoga — glavna prepreka",
     "tema-visi-stepen"),
    ("kvadratni large sieve", "GL_n large sieve postoji — prenosi se uz gubitak (utiče na eksponent)",
     "izvor-large-sieve-gln-2508-14888"),
    ("funkcionalna jednačina / analitičko produženje",
     "Sym^n: Newton–Thorne (recenzirano); Artin: pretpostavka", "izvor-newton-thorne-i"),
]


def seed_second() -> str:
    """Mission 2 (round 3, item 27). Idempotent."""
    _ensure()
    if get(SECOND_ID) is not None:
        return SECOND_ID
    create(SECOND_ID, "Viši stepen: prenosi li se 7/8?",
           "Prenosi li se metoda 7/8 (Liu, Xu–Sang) na L-funkcije višeg stepena (GL(2), Artin)? "
           "Ako da, kako se eksponent mijenja sa stepenom d i postoji li T_d između porodica? "
           "Vrsta rezultata: poluravan bez nula (ne miješati sa udjelom na pravoj).",
           state="Otvoreno pitanje. Prvi nacrt mape prenosivosti (NAŠE-NERECENZIRANO): "
                 "glavna prepreka je korak Gaussove sume → kubna theta.")
    for step_name, verdict, ref in TRANSFER_MAP:
        step(SECOND_ID, f"korak dokaza: {step_name}", verdict,
             "mapa prenosivosti u izradi (cilj 1)", ref=ref)
    return SECOND_ID


# --------------------------------------------------------------------------- #
# missions in turn (round 3, item 28a, Andrej 2026-10-25)
# --------------------------------------------------------------------------- #
# Exactly one mission is ACTIVE. The operator switches freely (menu) or with
# "Sljedeća misija" (cycle 1 → 2 → 3 → 1). Switching away PARKS the old mission
# with a "where I stopped" note (the operator's sentence + an automatic snapshot);
# coming back shows the "Gdje si stao" card first. A parked mission is FROZEN by
# default (nothing is collected for it); the operator can switch it to COLLECT
# (arXiv/ideas gathered quietly, no badge, shown on resume) and back at any time.
# The app never switches missions itself — at most it proposes (human queue).
ACTIVE_KEY = "mission_active"
SWITCH_KIND = "mission-switch"
FREEZE, COLLECT = "freeze", "collect"
BACKGROUND = {FREEZE: "potpuno zamrznuta (podrazumijevano)",
              COLLECT: "tiho skuplja (bez značke, prikaz pri nastavku)"}
# which mission owns which background feed (arXiv QRH watch → mission 1)
FEED_OWNER = {"arxiv-qrh": FIRST_ID}
_SNAPSHOTS: dict = {}          # name -> fn(mid) -> dict (e.g. Grafovi view, item 29)


def register_snapshot(name: str, fn) -> None:
    """Other parts (graphs, ideas) add their own piece to the parking snapshot."""
    _SNAPSHOTS[name] = fn


def active() -> Optional[str]:
    """The active mission id (first mission if none chosen yet)."""
    _ensure()
    mid = store().kv_get(ACTIVE_KEY)
    if mid and get(mid) is not None:
        return mid
    ms = all_missions()
    return ms[0]["id"] if ms else None


def _related_open_items(mid: str) -> list[dict]:
    out = []
    for it in store().open_items():
        p = it["payload"] if isinstance(it["payload"], dict) else {}
        if mid in (p.get("mission"), p.get("mission_id")):
            out.append({"id": it["id"], "title": it["title"]})
    return out


def snapshot(mid: str) -> dict:
    """Automatic part of "where I stopped": frontier, last step, open items, extras."""
    import json as _json
    m = get(mid)
    if m is None:
        raise KeyError(mid)
    last = m["steps"][-1] if m["steps"] else None
    snap = {"best_B": m["best_B"], "goal": int(m.get("goal") or 1), "state": m["state"],
            "n_steps": len(m["steps"]),
            "last_step": ({"action": last["action"], "outcome": last["outcome"]} if last else None),
            "open_items": _related_open_items(mid)}
    for name, fn in _SNAPSHOTS.items():
        try:
            snap[name] = fn(mid)
        except Exception as e:                          # noqa: BLE001 — a snapshot part may fail
            snap[name] = {"error": str(e)[:200]}
    _json.dumps(snap, default=str)                      # must be storable
    return snap


def park(mid: str, note: str = "") -> dict:
    """"Ostavi za kasnije": operator only; note + automatic snapshot, journalled."""
    import json as _json
    who = OP.require_operator()
    snap = snapshot(mid)
    now = time.time()
    store().execute("UPDATE missions SET parked=1, parked_at=?, parked_note=?, parked_snapshot=?,"
                    " updated=? WHERE id=?",
                    (now, (note or "")[:2000], _json.dumps(snap, ensure_ascii=False, default=str),
                     now, mid))
    J.log(J.MISSION, who, {"event": "parked", "id": mid, "note": (note or "")[:300],
                           "best_B": snap["best_B"], "n_steps": snap["n_steps"]},
          subject=mid, verdict="parked")
    return snap


def is_parked(mid: str) -> bool:
    m = get(mid)
    return bool(m and int(m.get("parked") or 0))


def background(mid: str) -> str:
    m = get(mid)
    return (m or {}).get("background") or FREEZE


def set_background(mid: str, mode: str) -> None:
    """Frozen ↔ collecting quietly. Operator only, always reversible."""
    who = OP.require_operator()
    if mode not in BACKGROUND:
        raise ValueError(f"način mora biti {FREEZE} ili {COLLECT}")
    if get(mid) is None:
        raise KeyError(mid)
    old = background(mid)
    store().execute("UPDATE missions SET background=?, updated=? WHERE id=?",
                    (mode, time.time(), mid))
    J.log(J.MISSION, who, {"event": "background", "id": mid, "from": old, "to": mode},
          subject=mid, verdict=mode)


def accepts_background(mid: Optional[str]) -> bool:
    """May a background feed (arXiv, ideas) work for this mission right now?"""
    if not mid or get(mid) is None:
        return True
    if mid == active() or not is_parked(mid):
        return True
    return background(mid) == COLLECT


def is_quiet(mid: Optional[str]) -> bool:
    """Collecting for a parked mission: gather, but no badge / no queue noise."""
    return bool(mid) and mid != active() and is_parked(mid) and background(mid) == COLLECT


def hold(mid: str, kind: str, item: dict) -> None:
    """Something collected quietly for a parked mission; released on resume."""
    held = store().kv_get(f"mission_held:{mid}", [])
    held.append({"kind": kind, "ts": time.time(), **item})
    store().kv_set(f"mission_held:{mid}", held[-500:])


def where_you_stopped(mid: str) -> dict:
    """The "Gdje si stao" card: the note, the snapshot, and what happened since."""
    import json as _json
    m = get(mid)
    if m is None:
        raise KeyError(mid)
    since = m.get("parked_at") or 0
    snap = _json.loads(m["parked_snapshot"]) if m.get("parked_snapshot") else None
    new_steps = [s for s in m["steps"] if since and s["ts"] > since]
    return {"mission": mid, "title": m["title"], "parked": bool(int(m.get("parked") or 0)),
            "parked_at": m.get("parked_at"), "note": m.get("parked_note") or "",
            "snapshot": snap, "steps_since": new_steps,
            "held": store().kv_get(f"mission_held:{mid}", []),
            "background": background(mid), "now": snapshot(mid)}


def resume(mid: str) -> dict:
    """Un-park: returns the card, then releases what was collected quietly."""
    card = where_you_stopped(mid)
    who = OP.require_operator()
    store().execute("UPDATE missions SET parked=0, updated=? WHERE id=?", (time.time(), mid))
    released = []
    for h in card["held"]:
        if h.get("kind") == "arxiv-paper":
            pid = store().propose("arxiv-paper", f"Novi QRH rad: {h.get('title', '')[:120]} — izvući metodu?",
                                  {"ref": h.get("ref"), "title": h.get("title", ""),
                                   "abstract": h.get("abstract", ""), "mission": mid},
                                  proposer="arxiv")
            released.append(pid)
    store().kv_set(f"mission_held:{mid}", [])
    J.log(J.MISSION, who, {"event": "resumed", "id": mid, "held_released": len(released),
                           "steps_since": len(card["steps_since"])}, subject=mid, verdict="resumed")
    card["released"] = released
    return card


def set_active(mid: str, note: str = "") -> dict:
    """Switch the active mission (operator only). The previous one is parked with
    `note`; the new one is resumed and its "Gdje si stao" card returned."""
    OP.require_operator()
    if get(mid) is None:
        raise KeyError(mid)
    prev = active()
    if prev == mid and not is_parked(mid):
        return where_you_stopped(mid)
    if prev and prev != mid:
        park(prev, note)
    store().kv_set(ACTIVE_KEY, mid)
    J.log(J.MISSION, OP.current(), {"event": "activated", "id": mid, "from": prev},
          subject=mid, verdict="active")
    return resume(mid)


def next_id(current: Optional[str] = None) -> Optional[str]:
    """The next mission in the cycle 1 → 2 → 3 → 1 (by creation order)."""
    ids = [m["id"] for m in all_missions()]
    if not ids:
        return None
    cur = current or active()
    return ids[(ids.index(cur) + 1) % len(ids)] if cur in ids else ids[0]


def next_mission(note: str = "") -> dict:
    """"Sljedeća misija": park the active one with `note`, activate the next."""
    return set_active(next_id(), note)


def propose_switch(mid: str, why: str, proposer: str = "system") -> str:
    """The app may only PROPOSE a switch; the operator decides."""
    if get(mid) is None:
        raise KeyError(mid)
    for it in store().open_items(SWITCH_KIND):
        if it["payload"].get("mission") == mid:
            return it["id"]
    return store().propose(SWITCH_KIND, f"Prijedlog: pređi na misiju „{mid}“",
                           {"mission": mid, "why": why[:1000]}, proposer)


def _on_switch_decision(item: dict, approved: bool) -> None:
    if approved:
        set_active(item["payload"]["mission"], "prebačeno odobrenim prijedlogom")


def context_line() -> str:
    """One line for the chat context: which mission the operator works on."""
    mid = active()
    m = get(mid) if mid else None
    if not m:
        return ""
    best = "—" if m["best_B"] is None else f"{m['best_B']:.9f}"
    return (f"AKTIVNA MISIJA (operater radi na njoj): {m['title']} — cilj "
            f"{int(m.get('goal') or 1)} ({GOALS.get(int(m.get('goal') or 1), '')}); front B = {best}; "
            f"stanje: {m['state'][:400]}")


# --------------------------------------------------------------------------- #
# mission 3 — the complex version (round 3, item 32)
# --------------------------------------------------------------------------- #
THIRD_ID = "misija-kompleksna"


def seed_third() -> str:
    """Mission 3. Idempotent. Same goal menu; the app only proposes."""
    _ensure()
    if get(THIRD_ID) is not None:
        return THIRD_ID
    from ..methods import complexver as CV
    create(THIRD_ID, "Kompleksna verzija: savija li se granica?",
           "(a) Zavisi li granica od visine γ — postaje li prava Re s = B kriva σ*(γ) i savija li se "
           "igdje prema 1/2? (b) Šta su funkcije eksponenata sa kompleksnim argumentom i gdje se "
           "signal i niska strana „sijeku“ u kompleksnom smislu?",
           state="Otvoreno pitanje. (a) U okviru Liu/Xu–Sang E ne sadrži γ → σ*(γ) ≡ B (čitanje, "
                 "NAŠE-NERECENZIRANO). (b) Brojilac E(δ) je kvadratni u δ: granica = nula "
                 "diskriminante; vidi lab „QRH: kompleksna verzija“.")
    step(THIRD_ID, "(a) σ*(γ): pročitan formalizam metode", "σ*(γ) ≡ B u okviru metode — NAŠE-NERECENZIRANO",
         "(a) zatvoreno u okviru metode; van nje otvoreno", ref="methods/complexver.py")
    return THIRD_ID
