"""
Limiters for any model, local or cloud (plan F3, master §5 "→ ∞").

A model — especially an 8B GGUF on a 16 GB / 4-core laptop — must never be able
to take the machine down. Every constraint here is mechanical and checked before
and during a call, so a runaway model is paused and freed rather than left to
swap the box to death:

  RAM        do not load if free < model + headroom; unload at once below a floor
  CPU        at most 3 of 4 threads, the process niced down
  context    n_ctx capped (8K); history trimmed to fit
  thinking   a <think> budget plus a hard output cap
  time       a per-call timeout, and exactly one call at a time (a queue lock)
  loops      repetition detection — a model going in circles is cut off
  → ∞        a divergence watchdog (master §5): a watched metric (latency, memory,
             queue length) over the operator's limit L, or rising 3 steps in a
             row, means pause → free → tell the operator. L is set by the operator.

Nothing here imports a model library; it is arithmetic over /proc and short
strings, so it is fully testable without llama-cpp or a GPU.
"""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field
from typing import Optional


def free_ram_gb() -> float:
    """Available RAM in GiB, from /proc/meminfo (MemAvailable). 0.0 if unknown."""
    try:
        with open("/proc/meminfo", encoding="ascii") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024 * 1024)
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def cpu_count() -> int:
    return os.cpu_count() or 1


@dataclass
class Limits:
    # CPU threads for llama-cpp; 0 = cores − reserve
    n_threads: int = 0
    # RAM (GiB)
    ram_headroom_gb: float = 2.0       # need model_size + this free to load
    ram_floor_gb: float = 1.5          # below this: unload immediately
    # CPU
    reserve_cores: int = 1             # leave at least this many cores for the OS/GUI
    # context / output (tokens)
    n_ctx: int = 8192
    think_budget: int = 1500
    max_output: int = 2000
    # time
    call_timeout_s: float = 120.0
    # cloud
    max_calls: int = 0                 # 0 = unlimited (budget module also caps $)
    # divergence watchdog (master §5, "→ ∞"); L is operator-set per metric.
    # latency = generation seconds PER OUTPUT TOKEN (not per call: a long answer
    # is not a runaway, a machine that slows to a crawl is). Typical 8B Q5 on
    # 4 cores ≈ 0.2–0.5 s/token; swapping pushes it past 2.
    L_latency_s: float = 2.0
    L_rss_gb: float = 12.0
    L_queue: int = 8

    @classmethod
    def from_settings(cls) -> "Limits":
        """The machine profile (item 24), then the operator's "→ ∞" ceilings."""
        lim = cls()
        try:
            from .. import machine as M
            p = M.profile()
            lim.n_threads, lim.n_ctx = p.threads, p.n_ctx
            lim.think_budget, lim.max_output = p.think_budget, p.max_output
            lim.call_timeout_s, lim.L_latency_s = p.call_timeout_s, p.s_per_token_L
        except Exception:                           # noqa: BLE001
            pass
        try:
            from .. import settings as S
            Ls = S.load().get("limits_L") or {}
            lim.L_latency_s = float(Ls.get("s_per_token", lim.L_latency_s))
            lim.L_rss_gb = float(Ls.get("rss_gb", lim.L_rss_gb))
            lim.L_queue = int(Ls.get("queue", lim.L_queue))
        except Exception:           # noqa: BLE001 — settings never block a limiter
            pass
        return lim

    def threads(self) -> int:
        if self.n_threads:
            return max(1, min(self.n_threads, cpu_count()))
        return max(1, cpu_count() - self.reserve_cores)

    def can_load(self, model_gb: float) -> bool:
        return free_ram_gb() >= model_gb + self.ram_headroom_gb

    def must_unload(self) -> bool:
        return free_ram_gb() < self.ram_floor_gb


# A single global so that, however many callers exist, only one model call runs
# at a time. A second caller waits; it never starts a parallel decode.
_CALL_LOCK = threading.Lock()
_WAITING = 0                    # callers queued for the slot (the "queue" metric)
_WAITING_LOCK = threading.Lock()


def queue_length() -> int:
    return _WAITING


class one_at_a_time:
    """Context manager: acquire the single call slot, optionally with a timeout."""

    def __init__(self, timeout: float = 0.0):
        self.timeout = timeout
        self._held = False

    def __enter__(self):
        global _WAITING
        with _WAITING_LOCK:
            _WAITING += 1
        try:
            observe("queue", _WAITING)
            self._held = _CALL_LOCK.acquire(timeout=self.timeout if self.timeout else -1)
        finally:
            with _WAITING_LOCK:
                _WAITING -= 1
        if not self._held:
            raise TimeoutError("drugi poziv modelu je u toku — red je zauzet")
        return self

    def __exit__(self, *exc):
        if self._held:
            _CALL_LOCK.release()
            self._held = False


# --------------------------------------------------------------------------- #
# repetition detection
# --------------------------------------------------------------------------- #
def is_looping(text: str, min_run: int = 4, min_len: int = 12) -> bool:
    """
    True if the text is going in circles: the same line repeated `min_run`+ times,
    or a tail that is one phrase (len ≥ min_len) duplicated back to back many times.
    """
    if not text:
        return False
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    run, last = 1, None
    for ln in lines:
        if ln == last and len(ln) >= min_len:
            run += 1
            if run >= min_run:
                return True
        else:
            run, last = 1, ln
    # phrase-level: a chunk that repeats immediately, filling the tail
    tail = text[-400:]
    for n in range(min_len, 80):
        chunk = tail[-n:]
        if chunk.strip() and tail.endswith(chunk * min_run):
            return True
    return False


def trim_history(messages: list, keep_last: int) -> list:
    """Keep the most recent `keep_last` messages (context budget). Simple and safe."""
    return messages[-keep_last:] if keep_last and len(messages) > keep_last else list(messages)


# --------------------------------------------------------------------------- #
# divergence watchdog (master §5)
# --------------------------------------------------------------------------- #
def diverging(series: list[float], L: float) -> bool:
    """
    "→ ∞": the metric has crossed the operator's ceiling L, or it has risen three
    steps in a row (a monotone climb is the signature the kernel watches for).
    """
    if not series:
        return False
    if series[-1] > L:
        return True
    if len(series) >= 4:
        a, b, c, d = series[-4:]
        if a < b < c < d:
            return True
    return False


@dataclass
class Watchdog:
    """Tracks one metric's recent history and says when to pull the plug.

    `floor` (a fraction of L) keeps the "three rises in a row" rule from firing
    on harmless noise: 1.0 s → 1.1 s → 1.2 s → 1.3 s is not a runaway. A climb
    counts only once the latest value is above floor·L; crossing L always counts.
    """
    name: str
    L: float
    history: list = field(default_factory=list)
    window: int = 8
    floor: float = 0.5

    def observe(self, value: float) -> bool:
        self.history.append(value)
        if len(self.history) > self.window:
            self.history = self.history[-self.window:]
        if value > self.L:
            return True
        return value > self.floor * self.L and diverging(self.history, self.L)


# --------------------------------------------------------------------------- #
# the live "→ ∞" guard (A1): watchdogs that are actually fed, and a pause that
# holds until the operator lifts it
# --------------------------------------------------------------------------- #
class Aborted(Exception):
    """A model call was cut off by a limiter. `reason` is a short code:
    timeout · loop · ram · diverging · paused · cancelled."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


_WATCH: dict[str, Watchdog] = {}
_PAUSE: dict = {"on": False, "metric": "", "value": 0.0, "L": 0.0, "at": 0.0}
_PAUSE_LOCK = threading.Lock()
_LISTENERS: list = []           # fn(metric, value, L) — runtime: unload, journal, queue


def configure(lim: "Limits") -> None:
    """(Re)build the watchdogs from the operator's ceilings L."""
    for name, L in (("latency", lim.L_latency_s), ("rss", lim.L_rss_gb),
                    ("queue", float(lim.L_queue))):
        w = _WATCH.get(name)
        if w is None or w.L != L:
            _WATCH[name] = Watchdog(name, L)


def watchdogs() -> dict[str, Watchdog]:
    if not _WATCH:
        configure(Limits())
    return _WATCH


def on_pause(fn) -> None:
    """Register what happens when the guard trips (idempotent)."""
    if fn not in _LISTENERS:
        _LISTENERS.append(fn)


def observe(metric: str, value: float) -> bool:
    """Feed one sample. A trip pauses all model calls and tells the listeners."""
    w = watchdogs().get(metric)
    if w is None or not w.observe(float(value)):
        return False
    trip(metric, float(value), w.L, history=list(w.history), floor=w.floor)
    return True


def trip(metric: str, value: float, L: float, notify: bool = True,
         history: Optional[list] = None, floor: float = 0.5) -> None:
    import time as _t
    with _PAUSE_LOCK:
        already = _PAUSE["on"]
        _PAUSE.update(on=True, metric=metric, value=value, L=L, at=_t.time(),
                      history=list(history) if history else [float(value)],
                      floor=floor)
    if already or not notify:
        return
    for fn in list(_LISTENERS):
        try:
            fn(metric, value, L)
        except Exception:           # noqa: BLE001 — a listener must not hide the pause
            pass


def paused() -> bool:
    return _PAUSE["on"]


def pause_state() -> dict:
    return dict(_PAUSE)


def resume() -> None:
    """Only the operator lifts the pause (via the human queue)."""
    with _PAUSE_LOCK:
        _PAUSE.update(on=False)
    for w in _WATCH.values():
        w.history.clear()


def rss_gb() -> float:
    """Resident memory of this process in GiB (VmRSS), 0.0 if unknown."""
    try:
        with open("/proc/self/status", encoding="ascii") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / (1024 * 1024)
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


class CallGuard:
    """
    One model call, start to finish (A2, A3). The deadline is set when the call
    is REQUESTED, so it covers the wait for the slot AND the generation. While
    tokens stream in, tick() cuts the call off on: deadline passed, the text
    going in circles, free RAM under the floor, this process over the RSS
    ceiling, the global "→ ∞" pause, or an external cancel (kill switch).
    Call started() when generation begins; finish(n_tokens) feeds the latency
    watchdog with seconds per token of the generation alone, and the memory one.
    """

    LOOP_EVERY = 48             # chars between repetition checks
    RES_EVERY_S = 1.0           # seconds between RAM / RSS checks

    def __init__(self, lim: "Limits", cancel: Optional[threading.Event] = None,
                 clock=None):
        import time as _t
        self.lim = lim
        self.clock = clock or _t.monotonic
        self.t0 = self.clock()
        self.deadline = self.t0 + lim.call_timeout_s
        self.cancel = cancel
        self._checked_len = 0
        self._res_at = self.t0
        self.t_gen = None
        configure(lim)

    def started(self) -> None:
        self.t_gen = self.clock()

    def remaining(self) -> float:
        return max(0.0, self.deadline - self.clock())

    def check(self) -> None:
        if paused():
            st = pause_state()
            raise Aborted("paused", f"„→ ∞“ ({st['metric']}={st['value']:.3g} > L={st['L']:.3g})"
                          " — čeka operatera")
        if self.cancel is not None and self.cancel.is_set():
            raise Aborted("cancelled", "prekinuto spolja")
        if self.clock() > self.deadline:
            raise Aborted("timeout", f"poziv duži od {self.lim.call_timeout_s:.0f} s")

    def tick(self, text: str) -> None:
        self.check()
        if len(text) - self._checked_len >= self.LOOP_EVERY:
            self._checked_len = len(text)
            if is_looping(text):
                raise Aborted("loop", "detektovano ponavljanje")
        now = self.clock()
        if now - self._res_at >= self.RES_EVERY_S:
            self._res_at = now
            if self.lim.must_unload():
                raise Aborted("ram", "slobodan RAM ispod praga")
            r = rss_gb()
            if r and r > self.lim.L_rss_gb:
                trip("rss", r, self.lim.L_rss_gb)
                raise Aborted("diverging", f"memorija procesa {r:.1f} GB > L")

    def finish(self, n_tokens: int = 0) -> float:
        """Feed the watchdogs; returns generation seconds per token."""
        t1 = self.clock()
        gen = t1 - (self.t_gen if self.t_gen is not None else self.t0)
        spt = gen / max(1, n_tokens)
        if n_tokens >= 8:                       # too few tokens = no rate to judge
            observe("latency", spt)
        r = rss_gb()
        if r:
            observe("rss", r)
        return spt
