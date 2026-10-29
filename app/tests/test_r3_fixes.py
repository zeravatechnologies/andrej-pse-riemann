"""Round 3, item 3–4 — fixes A1–A4: the "→ ∞" guard runs, loops/timeouts cut a
generation off WHILE it streams, and one human decision = one execution."""
import threading

import pytest

from pse_r.llm import limits as L
from pse_r.llm import gguf as G
from pse_r.llm.backend import Msg
from pse_r.shared_lib.store import store
from pse_r.shared_lib import runtime as RT


@pytest.fixture(autouse=True)
def _clean_guard():
    L.resume()
    L._LISTENERS.clear()
    L._WATCH.clear()
    yield
    L.resume()
    L._LISTENERS.clear()
    L._WATCH.clear()


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeLlama:
    """Streams `pieces`; records how many chunks were actually pulled."""

    def __init__(self, pieces, on_chunk=None):
        self.pieces = pieces
        self.pulled = 0
        self.closed = False
        self.on_chunk = on_chunk

    def create_chat_completion(self, stream=False, **kw):
        assert stream, "GGUF must stream so a limiter can cut it off mid-generation"

        def gen():
            try:
                for i, p in enumerate(self.pieces):
                    self.pulled += 1
                    if self.on_chunk:
                        self.on_chunk(i)
                    yield {"choices": [{"delta": {"content": p}, "finish_reason": None}]}
                yield {"choices": [{"delta": {}, "finish_reason": "stop"}]}
            finally:
                self.closed = True
        return gen()

    def tokenize(self, b, add_bos=False):
        return list(b[:10])


def _backend(monkeypatch, llama, **lim):
    b = G.GGUFBackend("/nope/model.gguf", lim=L.Limits(**lim))
    monkeypatch.setattr(b, "_ensure_loaded", lambda: llama)
    monkeypatch.setattr(L, "free_ram_gb", lambda: 10.0)
    return b


# ---- A2: repetition stops the decode in flight ----------------------------- #
def test_loop_cuts_generation_mid_stream(monkeypatch):
    llama = FakeLlama(["ponavljam ovo stalno "] * 500)
    r = _backend(monkeypatch, llama).chat([Msg("user", "x")])
    assert r.stop_reason == "loop"
    assert llama.pulled < 50, f"pulled {llama.pulled} of 500 — not cut off in flight"
    assert llama.closed
    assert "ponavljanje" in r.text


# ---- A3: the timeout covers generation, not only the wait ----------------- #
def test_timeout_covers_generation(monkeypatch):
    clk = FakeClock()
    llama = FakeLlama([f"riječ{i} " for i in range(1000)],
                      on_chunk=lambda i: setattr(clk, "t", clk.t + 1.0))
    b = _backend(monkeypatch, llama, call_timeout_s=30)
    monkeypatch.setattr(L.CallGuard, "__init__", _guard_with(clk))
    r = b.chat([Msg("user", "x")])
    assert r.stop_reason == "timeout"
    assert 25 <= llama.pulled <= 35


def _guard_with(clk):
    orig = L.CallGuard.__init__

    def init(self, lim, cancel=None, clock=None):
        orig(self, lim, cancel=cancel, clock=clk)
    return init


def test_timeout_counts_the_wait_for_the_slot():
    clk = FakeClock()
    g = L.CallGuard(L.Limits(call_timeout_s=10), clock=clk)
    clk.t = 7.0                                     # 7 s spent waiting in the queue
    assert g.remaining() == pytest.approx(3.0)
    clk.t = 11.0
    with pytest.raises(L.Aborted) as e:
        g.tick("")
    assert e.value.reason == "timeout"


def test_external_cancel_stops_stream(monkeypatch):
    ev = threading.Event()
    llama = FakeLlama([f"t{i} " for i in range(1000)],
                      on_chunk=lambda i: ev.set() if i == 5 else None)
    r = _backend(monkeypatch, llama).chat([Msg("user", "x")], cancel=ev)
    assert r.stop_reason == "cancelled" and llama.pulled < 10


# ---- A1: the "→ ∞" watchdog is live and pauses until the operator --------- #
def test_watchdog_is_fed_and_trip_pauses_calls(monkeypatch, operator):
    RT.install_hooks()
    lim = L.Limits(L_latency_s=2.0)                 # L = 2 s per token
    clk = FakeClock()
    g = L.CallGuard(lim, clock=clk)
    clk.t = 100.0                                   # load/wait: not counted
    g.started()
    clk.t = 160.0                                   # 20 tokens in 60 s = 3 s/token > L
    g.finish(20)
    assert L.paused()
    items = store().open_items(RT.GUARD_KIND)
    assert len(items) == 1 and items[0]["payload"]["metric"] == "latency"
    # while paused, a GGUF call is refused before it starts
    llama = FakeLlama(["ok"])
    with pytest.raises(G.GGUFUnavailable):
        _backend(monkeypatch, llama).chat([Msg("user", "x")])
    assert llama.pulled == 0
    # a second trip does not queue a second item
    L.trip("latency", 99, 5)
    assert len(store().open_items(RT.GUARD_KIND)) == 1
    # operator approves → calls resume
    store().decide(items[0]["id"], True)
    assert not L.paused()


def test_pause_survives_restart(operator):
    RT.install_hooks()
    L.trip("rss", 13.0, 12.0)
    assert store().open_items(RT.GUARD_KIND)
    L.resume()                                      # simulate a fresh process…
    RT.install_hooks()                              # …booting with the item still open
    assert L.paused()
    store().decide(store().open_items(RT.GUARD_KIND)[0]["id"], True)
    assert not L.paused()


def test_long_answer_or_slow_load_is_not_a_runaway():
    clk = FakeClock()
    g = L.CallGuard(L.Limits(L_latency_s=2.0), clock=clk)
    clk.t = 140.0                                   # first call: hash + load
    g.started()
    clk.t = 240.0                                   # 400 tokens in 100 s = 0.25 s/token
    assert g.finish(400) == pytest.approx(0.25)
    assert not L.paused()


def test_slow_noise_does_not_trip():
    w = L.Watchdog("latency", L=2.0)
    assert not any(w.observe(v) for v in (0.20, 0.22, 0.24, 0.26, 0.28))
    assert w.observe(2.5)


def test_queue_length_is_watched():
    L.configure(L.Limits(L_queue=1))
    with L.one_at_a_time(timeout=1.0):
        def second():
            try:
                with L.one_at_a_time(timeout=0.3):
                    pass
            except TimeoutError:
                pass
        ts = [threading.Thread(target=second) for _ in range(3)]
        [t.start() for t in ts]
        [t.join() for t in ts]
    assert L.paused() and L.pause_state()["metric"] == "queue"


# ---- A4 + S2/P5: one decision = one execution ----------------------------- #
def test_racing_decisions_one_wins_hook_runs_once(operator):
    calls = []
    store().on_decision("r3-race", lambda item, ok: calls.append(ok))
    pid = store().propose("r3-race", "trka", {}, proposer="test")
    errs, barrier = [], threading.Barrier(8)

    def go(ok):
        barrier.wait()
        try:
            store().decide(pid, ok)
        except ValueError as e:
            errs.append(e)
    ts = [threading.Thread(target=go, args=(i % 2 == 0,)) for i in range(8)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(calls) == 1 and len(errs) == 7
    assert store().get(pid)["consumed_at"] is not None


def test_consume_is_true_exactly_once(operator):
    pid = store().propose("r3-once", "jednom", {}, proposer="test")
    assert not store().consume(pid)                 # open items cannot be consumed
    store().decide(pid, True)                       # decide consumes it
    assert not store().consume(pid)                 # and never again


def test_sha256_only_at_admission_and_after_a_change(monkeypatch, tmp_path):
    f = tmp_path / "m.gguf"
    f.write_bytes(b"x" * 100)
    b = G.GGUFBackend(str(f), lim=L.Limits())
    n = {"verify": 0}
    monkeypatch.setattr(G, "have_llama", lambda: True)
    monkeypatch.setattr(b, "verify", lambda: (n.__setitem__("verify", n["verify"] + 1), (True, ""))[1])
    monkeypatch.setattr(L, "free_ram_gb", lambda: 10.0)
    import sys, types
    monkeypatch.setitem(sys.modules, "llama_cpp", types.SimpleNamespace(Llama=lambda **kw: object()))
    G.GGUFBackend.unload()
    b._ensure_loaded(); b._ensure_loaded(); b._ensure_loaded()
    assert n["verify"] == 1
    import os, time
    f.write_bytes(b"y" * 101)                       # the weights changed on disk
    os.utime(f, ns=(time.time_ns(), time.time_ns()))
    b._ensure_loaded()
    assert n["verify"] == 2
    G.GGUFBackend.unload()
