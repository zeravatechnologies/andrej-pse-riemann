"""
The online-AI kill switch (round 3, item 12).

One action, four effects, in this order:
  1. the egress closes the road: no request to ANY cloud model host leaves
     (checked in the gate, so nothing can route around it);
  2. every model stream still open is hung up (egress.kill_streams);
  3. the model keys are taken out of the application's memory — and, if the
     operator chooses, forgotten for good (removed from secrets.json);
  4. the main AI falls back to a local GGUF, or to "no AI" if there is none.

The state is persisted (SHARED_LIB kv), so it survives a restart, and ONLY the
operator turns online AI back on. It trips by itself when the number, the size
or the cost of cloud calls runs off to infinity ("→ ∞"), with a danger alert
and the links where each key can be revoked.

Honest limit: Python cannot guarantee that the bytes of a removed string are
overwritten in RAM; "out of memory" here means no code path in the app can
reach the key any more.
"""
from __future__ import annotations

import time
from typing import Optional

from ..core import journal as J

KV = "online_ai"
CLOSED_KIND = "online-ai-closed"


def _store():
    from ..shared_lib.store import store
    return store()


def state() -> dict:
    return _store().kv_get(KV, {"closed": False})


def closed() -> bool:
    try:
        return bool(state().get("closed"))
    except Exception:                                   # noqa: BLE001 — fail closed? no:
        return False                                    # a broken store must not brick egress tests


def model_key_names() -> list[str]:
    from ..llm import providers as P
    return sorted({p.key_name for p in P.all_presets().values() if p.key_name})


def revoke_links() -> list[dict]:
    """Where each configured key can be revoked (shown with the alarm)."""
    from ..llm import providers as P
    from . import secrets as SEC
    out = []
    for p in P.all_presets().values():
        if p.console and (SEC.store().has(p.key_name) or SEC.store().was_locked(p.key_name)):
            out.append({"provider": p.label, "url": p.console})
    return out


def close(reason: str, actor: str = "operator", forget_keys: bool = False,
          auto: bool = False) -> dict:
    """Cut online AI now. Idempotent; a second call can still forget keys."""
    from . import secrets as SEC
    from .egress import egress
    links = revoke_links()
    st = state()
    first = not st.get("closed")
    st.update({"closed": True, "at": time.time(), "by": actor, "reason": reason,
               "auto": auto, "forgot": bool(st.get("forgot")) or forget_keys})
    _store().kv_set(KV, st)                              # 1. persisted before anything else
    hung = egress().kill_streams()                       # 2.
    names = model_key_names()
    SEC.store().lock(names)                              # 3. out of memory
    if forget_keys:
        SEC.store().forget(names)                        #    and off the disk
    fallback = _fall_back_to_local()                     # 4.
    J.log(J.THREAT if auto else J.SYSTEM, actor,
          {"event": "online_ai_closed", "reason": reason, "auto": auto,
           "hung_up": hung, "keys_forgotten": forget_keys, "fallback": fallback},
          subject="online-ai", verdict="closed")
    if first and auto:
        if not _store().open_items(CLOSED_KIND):
            _store().propose(CLOSED_KIND,
                             f"⛔ ONLINE AI ISKLJUČEN AUTOMATSKI: {reason}. Ključeve opozovi "
                             "na stranicama provajdera (linkovi u stavci). Uključuje se samo "
                             "ručno, dugmetom „Online AI“.",
                             {"reason": reason, "revoke": links}, proposer="guardian")
    return {"hung_up": hung, "fallback": fallback, "revoke": links}


def reopen(actor: str) -> dict:
    """Only the operator turns online AI back on; the models chosen before come
    back when their keys are there. Returns {"main", "skeptic"?, "missing"}."""
    from ..shared_lib import operator as OP
    from . import secrets as SEC
    who = OP.require_operator()
    if actor and actor != who:
        raise PermissionError("online AI uključuje samo prijavljeni operater")
    st = state()
    st.update({"closed": False, "reopened_at": time.time(), "reopened_by": who})
    _store().kv_set(KV, st)
    SEC.store().unlock()
    for it in _store().open_items(CLOSED_KIND):
        _store().withdraw(it["id"], who, "online AI ponovo uključen")
    back = _restore_after_reopen()
    J.log(J.SYSTEM, who, {"event": "online_ai_reopened", "restored": back.get("main"),
                          "missing": back.get("missing", [])}, subject="online-ai",
          verdict="reopened")
    return back


def _fall_back_to_local() -> str:
    from .. import settings as S
    from ..llm import selection as SEL
    main = S.get(SEL.MAIN_KEY) or ""
    if main.startswith("gguf:"):
        return main
    ggufs = SEL.gguf_available()
    # remember the cloud choice ONCE: a second close (e.g. "forget the keys")
    # must not overwrite it with "bez AI" — reopen() brings it back
    if main and main != SEL.NO_AI:
        S.set_(SEL.PREV_MAIN_KEY, main)
        sk = S.get(SEL.SKEPTIC_KEY) or ""
        S.set_(SEL.PREV_SKEPTIC_KEY, "" if sk == SEL.NO_SKEPTIC else sk)
    if ggufs:
        S.set_(SEL.SKEPTIC_KEY, ggufs[1] if len(ggufs) > 1 else SEL.NO_SKEPTIC)
        S.set_(SEL.MAIN_KEY, ggufs[0])
        return ggufs[0]
    S.set_(SEL.MAIN_KEY, SEL.NO_AI)
    S.set_(SEL.SKEPTIC_KEY, SEL.NO_SKEPTIC)
    return "bez AI"


def _restore_after_reopen() -> dict:
    """Bring back the main and skeptic chosen before the switch was closed, when
    their keys are still there (live test rc2: after Ctrl+K and reopen the app
    stayed "bez AI" although the keys and models worked)."""
    from .. import settings as S
    from ..llm import selection as SEL
    prev, prev_sk = S.get(SEL.PREV_MAIN_KEY) or "", S.get(SEL.PREV_SKEPTIC_KEY) or ""
    cur = S.get(SEL.MAIN_KEY) or ""
    if not prev or prev == SEL.NO_AI:
        return {"main": None, "missing": []}
    if cur and cur not in (SEL.NO_AI, prev) and not cur.startswith("gguf:"):
        return {"main": cur, "missing": []}            # the operator already chose another
    av = SEL.cloud_available()
    missing = [m for m in (prev, prev_sk) if m and not m.startswith("gguf:") and m not in av]
    if prev not in av:
        return {"main": None, "missing": missing}      # keys forgotten: Podešavanje
    S.set_(SEL.SKEPTIC_KEY, "")
    S.set_(SEL.MAIN_KEY, prev)
    if prev_sk and prev_sk != prev and (prev_sk.startswith("gguf:") or prev_sk in av):
        S.set_(SEL.SKEPTIC_KEY, prev_sk)
    S.set_(SEL.PREV_MAIN_KEY, "")
    S.set_(SEL.PREV_SKEPTIC_KEY, "")
    return {"main": prev, "skeptic": SEL.get_skeptic(), "missing": missing}


def on_startup() -> None:
    """A closed switch stays closed across a restart: keys stay locked."""
    if closed():
        from . import secrets as SEC
        SEC.store().lock(model_key_names())


# --------------------------------------------------------------------------- #
# automatic trip: "→ ∞" of number, size and cost of cloud calls
# --------------------------------------------------------------------------- #
_WATCH: dict = {}
DEFAULT_L = {"calls_per_10min": 60, "tokens_per_call": 40_000, "usd_per_hour": None}
# usd_per_hour defaults to the whole DAILY cap: spending a day's budget within one
# hour is a runaway (round 3 benchmark: a fixed $3/h tripped on normal heavy use)
_calls: list = []                  # (t, tokens, usd)


def _limits() -> dict:
    try:
        from .. import settings as S
        L = {**DEFAULT_L, **(S.load().get("killswitch_L") or {})}
    except Exception:                                   # noqa: BLE001
        L = dict(DEFAULT_L)
    if L.get("usd_per_hour") is None:
        try:
            from ..llm.budget import budget
            L["usd_per_hour"] = float(budget().daily_cap)
        except Exception:                               # noqa: BLE001
            L["usd_per_hour"] = 5.0
    return L


def observe_cloud_call(provider: str, tokens: int, usd: float,
                       now: Optional[float] = None) -> Optional[str]:
    """Feed one finished cloud call. Returns the trip reason if it tripped."""
    from ..llm.limits import Watchdog
    now = now or time.time()
    _calls.append((now, tokens, usd))
    del _calls[:-2000]
    Ls = _limits()
    n10 = sum(1 for t, _, _ in _calls if now - t <= 600)
    usd_h = sum(u for t, _, u in _calls if now - t <= 3600)
    metrics = {"calls_per_10min": float(n10), "tokens_per_call": float(tokens),
               "usd_per_hour": float(usd_h)}
    for name, val in metrics.items():
        w = _WATCH.get(name)
        if w is None or w.L != float(Ls[name]):
            # rolling sums rise by construction during their first window, so for
            # them a climb counts only near the ceiling (round 3 benchmark, k-slow-ok)
            floor = 0.9 if name in ("calls_per_10min", "usd_per_hour") else 0.5
            w = _WATCH[name] = Watchdog(name, float(Ls[name]), floor=floor)
        if w.observe(val):
            reason = (f"„→ ∞“ {name} = {val:.4g} (L = {w.L:.4g}, provajder {provider})")
            close(reason, actor="guardian", auto=True)
            from ..core import journal as JJ
            JJ.log(JJ.THREAT, "guardian", {"event": "killswitch_tripped",
                                          "metric": name, "value": val, "L": w.L},
                   subject="online-ai", verdict="tripped")
            return reason
    return None


def _reset_for_tests() -> None:
    _WATCH.clear()
    _calls.clear()
