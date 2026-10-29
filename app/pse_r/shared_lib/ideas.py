"""
The inspiration engine — "Ideje" (round 3, item 28).

After reading what happens on the internet (arXiv and allowlisted sources, all
through the Guardian egress), the app proposes IDEAS, never claims. Every idea:

    oznaka      always INSPIRACIJA (a column, so even a raw SQL answer shows it)
    izvor       the paper / card it came from
    misija      which mission it is for, and why (the shared terms, the step)
    metoda      what would have to happen for it to become a checkable method

An idea never enters the vault as a fact: it lives only in this table of the
SHARED_LIB store. The operator decides: zadrži · odbaci · pretvori u otvoreno
pitanje (a mission step, NAŠE-NERECENZIRANO) · odgodi (comes back next week).

So it cannot flood the operator: at most `ideas_per_week` (default 3, operator
changes it) are SHOWN per ISO week, ranked by their link to a mission (the
active mission ranks first, item 28a), no duplicates (same source, or nearly the
same title), a small badge instead of pop-ups, a weekly review. A parked mission
that is frozen gets no ideas; one that collects quietly gets candidates that
wait until it is resumed.

The skeptic attacks every idea BEFORE the operator sees it; its objections are
stored with the idea. With no distinct skeptic, the idea is shown with
"skeptik nedostupan" — honest, not hidden. Claim language in an idea ("dokazano",
"we prove", "RH je tačna") is refused: the idea text falls back to the fixed
template, which only points at the source.
"""
from __future__ import annotations

import json
import re
import threading
import time
from typing import Callable, Optional

from ..core import journal as J
from . import missions as MIS
from . import operator as OP
from .store import store

LABEL = "INSPIRACIJA"
CAP_KEY = "ideas_per_week"
DEFAULT_CAP = 3
SNOOZE_S = 7 * 24 * 3600
ROUND_KEY = "ideas_last"
ROUND_INTERVAL_S = 7 * 24 * 3600
MIN_SCORE = 2.0
ACTIONS = {"keep": "zadržana", "drop": "odbačena", "question": "otvoreno pitanje",
           "snooze": "odgođena"}
_SYNC_FOR_TESTS = False

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS inspiracije (
        id          TEXT PRIMARY KEY,
        oznaka      TEXT NOT NULL DEFAULT 'INSPIRACIJA',
        created     REAL NOT NULL,
        week        TEXT,
        title       TEXT NOT NULL,
        idea        TEXT NOT NULL,
        why         TEXT NOT NULL,
        method_hint TEXT NOT NULL,
        source_ref  TEXT NOT NULL,
        source_title TEXT,
        mission_id  TEXT,
        score       REAL NOT NULL,
        dedup       TEXT NOT NULL UNIQUE,
        status      TEXT NOT NULL DEFAULT 'kandidat',
        snooze_until REAL,
        skeptic     TEXT,
        skeptic_state TEXT,
        origin      TEXT,
        decided_by  TEXT,
        decided_at  REAL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_insp_status ON inspiracije(status)",
]
CANDIDATE, SHOWN = "kandidat", "prikazana"
STATUS_OF = {"keep": "zadržana", "drop": "odbačena", "question": "pitanje", "snooze": "odgođena"}

# English terms per mission: papers are in English, missions are written in Serbian.
KEYWORDS = {
    MIS.FIRST_ID: {"quasi-riemann": 3, "zero-free": 2, "zero free": 2, "half-plane": 2,
                   "dirichlet": 1, "exponent": 1, "large sieve": 1.5, "mollifier": 1.5,
                   "zeta": 1, "riemann hypothesis": 1, "exponential sum": 1.5,
                   "density": 0.5, "7/8": 2, "liu": 1, "xu": 0.5},
    MIS.SECOND_ID: {"langlands": 2.5, "gl(2)": 2, "gl(n)": 2, "gl_n": 2, "artin": 2,
                    "automorph": 2, "symmetric power": 2, "functoriality": 2,
                    "higher degree": 2, "l-function": 1, "theta": 1.5, "cubic": 1,
                    "gauss sum": 2, "patterson": 2, "kubota": 2, "large sieve": 1.5,
                    "zero-free": 1.5, "geometric langlands": 2},
}
QUERIES = {MIS.FIRST_ID: ["quasi-Riemann hypothesis", "zero-free region Dirichlet L-functions"],
           MIS.SECOND_ID: ["zero-free region automorphic L-functions GL(2)",
                           "large sieve GL(n) zeros", "Langlands functoriality zero density"]}
STEP_HINT = {MIS.FIRST_ID: "izvući paket metode (E kao podatak) i pustiti ga kroz vrata — "
                           "test reprodukcije pokazuje da li pomjera front",
             MIS.SECOND_ID: "odrediti koji korak mape prenosivosti dodiruje i da li se taj "
                            "korak prenosi na stepen d (zapisati kao korak misije)"}
_CLAIM = re.compile(r"\b(dokazan[aoi]?|dokazuje|dokazali|we prove|proves?|proved|"
                    r"rh je ta[čc]n|riemannova hipoteza je ta[čc]n|sigurno vrijedi|"
                    r"definitivno)\b", re.I)


def _ensure() -> None:
    store().ensure(_SCHEMA)


def _week(ts: Optional[float] = None) -> str:
    return time.strftime("%G-W%V", time.localtime(ts or time.time()))


def cap() -> int:
    return int(store().kv_get(CAP_KEY, DEFAULT_CAP))


def set_cap(n: int) -> None:
    """The operator changes how many ideas a week may be shown (0–20)."""
    who = OP.require_operator()
    n = int(n)
    if not 0 <= n <= 20:
        raise ValueError("broj ideja sedmično mora biti 0–20")
    old = cap()
    store().kv_set(CAP_KEY, n)
    J.log(J.INGEST, who, {"event": "ideas_cap", "from": old, "to": n}, verdict="cap")


# --------------------------------------------------------------------------- #
# relevance, dedup, wording
# --------------------------------------------------------------------------- #
def _words(s: str) -> set:
    return {w for w in re.findall(r"[a-zčćšđž0-9]{4,}", (s or "").lower())}


def _mission_terms(mid: str) -> dict:
    if mid in KEYWORDS:
        return KEYWORDS[mid]
    m = MIS.get(mid) or {}
    return {w: 1.0 for w in _words(m.get("title", "") + " " + m.get("question", ""))}


def relevance(text: str, mid: str) -> tuple[float, list]:
    low = (text or "").lower()
    hits = [(k, w) for k, w in _mission_terms(mid).items() if k in low]
    return sum(w for _, w in hits), [k for k, _ in sorted(hits, key=lambda x: -x[1])]


def _dedup_key(ref: str, title: str) -> str:
    ref = (ref or "").lower()
    if ref.startswith("arxiv:"):
        ref = re.sub(r"v\d+$", "", ref)
    return ref or re.sub(r"[^a-z0-9]+", "", (title or "").lower())[:80]


def _near_duplicate(title: str) -> bool:
    w = _words(title)
    if not w:
        return False
    for r in store().rows("SELECT source_title FROM inspiracije"):
        o = _words(r["source_title"] or "")
        if o and len(w & o) / len(w | o) >= 0.7:
            return True
    return False


def is_claim(text: str) -> bool:
    return bool(_CLAIM.search(text or ""))


def _template(title: str, mid: str, terms: list) -> dict:
    m = MIS.get(mid) or {"title": mid}
    return {"idea": (f"Rad „{title[:160]}“ dodiruje misiju „{m['title']}“ "
                     f"({', '.join(terms[:4])}). Možda nudi korak ili alat koji vrijedi pogledati."),
            "why": f"zajednički pojmovi sa misijom: {', '.join(terms[:6])}",
            "method_hint": STEP_HINT.get(mid, "formulisati provjerljiv korak i pustiti ga kroz vrata")}


_MAIN_SYSTEM = (
    "Predlažeš INSPIRACIJU, nikad tvrdnju. Iz sažetka rada napiši JEDNU ideju koja bi "
    "mogla pomoći misiji. Ne tvrdi da išta važi ili da je dokazano. Vrati ISKLJUČIVO JSON "
    '{"ideja": "...", "zasto": "...", "metoda": "šta bi trebalo da postane provjerljiva metoda"}.')


def _default_ask_main(title: str, abstract: str, mission: dict) -> str:
    from ..llm import backend as B
    from ..pse import path as PATH
    user = (f"MISIJA: {mission['title']}\n{mission['question']}\n\n"
            f"RAD: {title}\n\n{abstract[:3000]}")
    return PATH.ask("ideas", [B.Msg("user", user)], system_extra=_MAIN_SYSTEM,
                    max_tokens=500, data_in_context=abstract[:3000],
                    entity=(title[:120], "document")).text


def _wording(title: str, abstract: str, mid: str, terms: list,
             ask: Optional[Callable]) -> tuple[dict, str]:
    """Main AI wording if it answers well; otherwise the fixed template."""
    from ..pse import measure as PM
    from ..pse import path as PATH
    base = _template(title, mid, terms)
    if ask is False:
        PATH.work("ideas", [PM.Action("šablon ideje iz sažetka", "f", external=True)],
                  entity=(title[:120], "document"), note="šablon")
        return base, "šablon"
    try:
        raw = (ask or _default_ask_main)(title, abstract, MIS.get(mid))
        if ask:
            PATH.words("ideas", raw, message=abstract[:3000], entity=(title[:120], "document"),
                       actions=[PM.Action("čita spoljni tekst", "f", external=True)], note="ask")
        d = json.loads(re.search(r"\{.*\}", raw or "", re.S).group(0))
        idea, why, meth = (str(d.get("ideja", "")).strip(), str(d.get("zasto", "")).strip(),
                           str(d.get("metoda", "")).strip())
    except Exception:                                   # noqa: BLE001 — no model / bad JSON
        return base, "šablon"
    if not idea or not meth or any(is_claim(x) for x in (idea, why, meth)):
        J.log(J.INGEST, "ideas", {"event": "claim_refused", "title": title[:200]},
              verdict="refused")
        return base, "šablon (model je tvrdio)"
    return {"idea": idea[:1200], "why": (why or base["why"])[:600], "method_hint": meth[:600]}, "model"


# --------------------------------------------------------------------------- #
# candidates → shown (with the skeptic first)
# --------------------------------------------------------------------------- #
def consider(items, ask_main=None, missions: Optional[list] = None) -> list[str]:
    """Turn read items into idea CANDIDATES (not shown yet). Returns new ids."""
    _ensure()
    mids = missions or [m["id"] for m in MIS.all_missions()]
    mids = [m for m in mids if MIS.accepts_background(m)]          # frozen → nothing
    act = MIS.active()
    out = []
    for it in items:
        ref = getattr(it, "source_ref", "") or getattr(it, "url", "")
        title = getattr(it, "title", "") or ref
        abstract = getattr(it, "abstract", "") or ""
        if not ref or getattr(it, "injection_hits", None):
            continue                                    # injected text never becomes an idea
        key = _dedup_key(ref, title)
        if store().rows("SELECT 1 FROM inspiracije WHERE dedup=?", (key,)) or _near_duplicate(title):
            continue
        best = None
        for mid in mids:
            sc, terms = relevance(f"{title}\n{abstract}", mid)
            if mid == act:
                sc *= 1.5                               # item 28a: the active mission first
            if sc >= MIN_SCORE and (best is None or sc > best[0]):
                best = (sc, mid, terms)
        if best is None:
            continue
        sc, mid, terms = best
        words, origin = _wording(title, abstract, mid, terms, ask_main)
        iid = f"ideja-{time.strftime('%Y%m%d-%H%M%S')}-{len(out)}-{abs(hash(key)) % 10**6:06d}"
        store().execute(
            "INSERT INTO inspiracije(id,created,title,idea,why,method_hint,source_ref,"
            "source_title,mission_id,score,dedup,origin) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (iid, time.time(), f"{LABEL}: {title[:140]}", words["idea"], words["why"],
             words["method_hint"], ref, title[:300], mid, round(sc, 3), key, origin))
        J.log(J.INGEST, "ideas", {"event": "candidate", "id": iid, "ref": ref,
                                  "mission": mid, "score": sc}, subject=iid, verdict="candidate")
        out.append(iid)
    return out


def _attack(row: dict, ask_skeptic) -> tuple[list, str]:
    from ..llm import skeptic as SK
    r = SK.attack(row["title"], f"{row['idea']}\n\nZašto: {row['why']}\n"
                  f"Provjerljivo: {row['method_hint']}", context=f"izvor: {row['source_ref']}",
                  subject=row["id"], ask=ask_skeptic, queue=False)
    if not r["available"]:
        return [], "nedostupan"
    if r.get("error"):
        return [], "greška"
    return [o.__dict__ for o in r["objections"]], "napao"


def shown_this_week(week: Optional[str] = None) -> int:
    _ensure()
    return store().rows("SELECT COUNT(*) n FROM inspiracije WHERE week=? AND status!=?",
                        (week or _week(), CANDIDATE))[0]["n"] - store().rows(
        "SELECT COUNT(*) n FROM inspiracije WHERE week=? AND status='odgođena'",
        (week or _week(),))[0]["n"]


def publish(ask_skeptic=None, now: Optional[float] = None) -> list[str]:
    """Fill this week's free slots with the best candidates, skeptic first."""
    _ensure()
    now = now or time.time()
    wk = _week(now)
    # snoozed ideas come back as candidates once their week is over
    store().execute("UPDATE inspiracije SET status=?, week=NULL WHERE status='odgođena' "
                    "AND snooze_until<=?", (CANDIDATE, now))
    free = cap() - shown_this_week(wk)
    if free <= 0:
        return []
    act = MIS.active()
    rows = store().rows("SELECT * FROM inspiracije WHERE status=? ORDER BY score DESC, created",
                        (CANDIDATE,))
    rows = [r for r in rows if not MIS.is_quiet(r["mission_id"])
            and MIS.accepts_background(r["mission_id"])]
    rows.sort(key=lambda r: (r["mission_id"] != act, -r["score"]))
    out = []
    for r in rows[:free]:
        objs, state = _attack(r, ask_skeptic)
        cur = store().execute("UPDATE inspiracije SET status=?, week=?, skeptic=?, skeptic_state=?"
                              " WHERE id=? AND status=?",
                              (SHOWN, wk, json.dumps(objs, ensure_ascii=False), state,
                               r["id"], CANDIDATE))
        if cur.rowcount == 1:
            J.log(J.INGEST, "ideas", {"event": "shown", "id": r["id"], "skeptic": state,
                                      "n_objections": len(objs)}, subject=r["id"], verdict="shown")
            out.append(r["id"])
    return out


_PUB_LOCK = threading.Lock()


def publish_async(ask_skeptic=None) -> bool:
    """From the heartbeat: publish in the background (the skeptic may take minutes)
    when there are free slots and candidates. Never two at once."""
    _ensure()
    if cap() - shown_this_week() <= 0:
        return False
    if not store().rows("SELECT 1 FROM inspiracije WHERE status=? LIMIT 1", (CANDIDATE,)):
        return False
    if not _PUB_LOCK.acquire(blocking=False):
        return False

    def work():
        try:
            publish(ask_skeptic=ask_skeptic)
        finally:
            _PUB_LOCK.release()
    t = threading.Thread(target=work, name="ideas-publish", daemon=True)
    t.start()
    if _SYNC_FOR_TESTS:
        t.join()
    return True


def badge() -> int:
    """How many shown ideas wait for the operator (the small badge, no pop-ups)."""
    _ensure()
    return store().rows("SELECT COUNT(*) n FROM inspiracije WHERE status=?", (SHOWN,))[0]["n"]


def shown() -> list[dict]:
    _ensure()
    out = store().rows("SELECT * FROM inspiracije WHERE status=? ORDER BY score DESC", (SHOWN,))
    for r in out:
        r["skeptic"] = json.loads(r["skeptic"] or "[]")
    return out


def get(iid: str) -> Optional[dict]:
    _ensure()
    r = store().rows("SELECT * FROM inspiracije WHERE id=?", (iid,))
    if not r:
        return None
    r[0]["skeptic"] = json.loads(r[0]["skeptic"] or "[]")
    return r[0]


def decide(iid: str, action: str, note: str = "") -> dict:
    """Operator only, and only once: keep · drop · question · snooze."""
    who = OP.require_operator()
    if action not in STATUS_OF:
        raise ValueError(f"radnja mora biti jedna od {sorted(STATUS_OF)}")
    row = get(iid)
    if row is None:
        raise KeyError(iid)
    snooze = time.time() + SNOOZE_S if action == "snooze" else None
    cur = store().execute("UPDATE inspiracije SET status=?, snooze_until=?, decided_by=?, "
                          "decided_at=? WHERE id=? AND status=?",
                          (STATUS_OF[action], snooze, who, time.time(), iid, SHOWN))
    if cur.rowcount != 1:
        raise ValueError(f"ideja '{iid}' nije na odluci (stanje: {row['status']})")
    if action == "question" and row["mission_id"] and MIS.get(row["mission_id"]):
        m = MIS.get(row["mission_id"])
        MIS.step(row["mission_id"],
                 f"otvoreno pitanje iz INSPIRACIJE: {row['idea'][:300]}",
                 "otvoreno (NAŠE-NERECENZIRANO, nije tvrdnja)", m["state"],
                 ref=row["source_ref"])
    J.log(J.INGEST, who, {"event": "idea_decided", "id": iid, "action": action,
                          "note": note[:300]}, subject=iid, verdict=STATUS_OF[action])
    return get(iid)


def weekly_review(week: Optional[str] = None) -> str:
    """The weekly review, as Markdown (what was shown and what became of it)."""
    _ensure()
    wk = week or _week()
    rows = store().rows("SELECT * FROM inspiracije WHERE week=? ORDER BY score DESC", (wk,))
    cand = store().rows("SELECT COUNT(*) n FROM inspiracije WHERE status=?", (CANDIDATE,))[0]["n"]
    from ..i18n import tr
    lines = [tr("## Sedmični pregled ideja — {0}").format(wk), "",
             tr("Prikazano {0} od najviše {1} · kandidata na čekanju: {2}").format(len(rows), cap(), cand), ""]
    for r in rows:
        mt = (MIS.get(r["mission_id"]) or {}).get("title", r["mission_id"])
        lines.append(tr("- **{0}** · {1} · misija: {2} · izvor `{3}`").format(
            tr(r["status"]), r["title"], mt, r["source_ref"]))
    if not rows:
        lines.append(tr("- _(ove sedmice nema prikazanih ideja)_"))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# reading the internet (weekly) and the seeded inspiration
# --------------------------------------------------------------------------- #
def _default_fetch(query: str) -> list:
    from ..ingest import sources as S
    try:
        return S.arxiv_search(query, max_results=10)
    except Exception:                                   # noqa: BLE001 — offline / blocked
        return []


def ideas_round(force: bool = False, fetch=None, ask_main=None, ask_skeptic=None) -> dict:
    """At most weekly: read arXiv for each mission that accepts background work,
    make candidates, then publish into the week's free slots (skeptic first)."""
    _ensure()
    last = store().kv_get(ROUND_KEY, 0)
    if not force and time.time() - last < ROUND_INTERVAL_S:
        return {"skipped": True}
    store().kv_set(ROUND_KEY, time.time())
    fetch = fetch or _default_fetch
    result = {"skipped": False}

    def work():
        new = []
        for m in MIS.all_missions():
            if not MIS.accepts_background(m["id"]):
                continue
            for q in QUERIES.get(m["id"], [m["title"]]):
                new += consider(fetch(q), ask_main=ask_main, missions=[m["id"]])
        shown_ids = publish(ask_skeptic=ask_skeptic)
        result.update(candidates=new, shown=shown_ids)
        J.log(J.INGEST, "ideas", {"event": "round", "candidates": len(new),
                                  "shown": len(shown_ids)}, verdict="round")
    t = threading.Thread(target=work, name="ideas", daemon=True)
    t.start()
    if _SYNC_FOR_TESTS:
        t.join()
    return result


def seed_geometric_langlands() -> Optional[str]:
    """Item 28: geometric Langlands enters ONLY as an INSPIRACIJA (mission 2). Idempotent."""
    _ensure()

    class _I:
        source_ref = "arxiv:2405.03599"
        title = "Gaitsgory–Raskin et al.: proof of the geometric Langlands conjecture I"
        abstract = ("geometric Langlands for function fields; no exponents over Q — "
                    "context for higher degree L-functions and GL(n) functoriality")
        injection_hits: list = []
    if store().rows("SELECT 1 FROM inspiracije WHERE dedup=?", (_dedup_key(_I.source_ref, ""),)):
        return None
    ids = consider([_I()], ask_main=False, missions=[MIS.SECOND_ID])
    if ids:
        store().execute("UPDATE inspiracije SET idea=?, why=?, method_hint=? WHERE id=?", (
            "Geometrijski Langlands (dokaz 2024) ne daje eksponente nad ℚ, ali njegova "
            "struktura (Hecke svojstvene snopove kao analog thete) mogla bi sugerisati gdje "
            "tražiti GL(2) zamjenu za korak „Gaussove sume → kubna theta“.",
            "mapa prenosivosti, korak 2: glavna prepreka; izvor je kontekst, ne alat "
            "(research/langlands-2026-10/REPORT.md)",
            "formulisati konkretan analog nad ℚ (koji koeficijenti, koja suma) i provjeriti "
            "ga na malom primjeru u labu prije bilo kakve tvrdnje", ids[0]))
    return ids[0] if ids else None


def _snapshot(mid: str) -> dict:
    _ensure()
    r = store().rows("SELECT status, COUNT(*) n FROM inspiracije WHERE mission_id=? GROUP BY status",
                     (mid,))
    return {x["status"]: x["n"] for x in r}


MIS.register_snapshot("ideje", _snapshot)
