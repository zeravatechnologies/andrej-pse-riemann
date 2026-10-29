"""Round 3, items 9–11: providers (presets, declared endpoints, GGUF anywhere),
streaming with a real hang-up, and billing advice / worst-case accounting."""
import http.client
import http.server
import json
import socket
import threading
import time
import urllib.parse

import pytest

from pse_r.guardian import egress as EG
from pse_r.guardian import policy
from pse_r.guardian import secrets as SEC
from pse_r.llm import backend as B
from pse_r.llm import budget as BU
from pse_r.llm import limits as L
from pse_r.llm import providers as P
from pse_r.llm import selection as SEL
from pse_r.shared_lib import declarations as DECL
from pse_r.shared_lib.store import store


@pytest.fixture(autouse=True)
def _guard_clean():
    L.resume(); L._LISTENERS.clear(); L._WATCH.clear()
    yield
    L.resume(); L._LISTENERS.clear(); L._WATCH.clear()


# ---------------------------------------------------------------- fake stream
class FakeStream:
    def __init__(self, lines, on_line=None):
        self.lines, self.n, self.closed, self.on_line = lines, 0, False, on_line

    def __call__(self, url, payload, **kw):
        self.url, self.payload, self.kw = url, payload, kw

        def gen():
            try:
                for i, ln in enumerate(self.lines):
                    self.n += 1
                    if self.on_line:
                        self.on_line(i)
                    yield ln
            finally:
                self.closed = True
        return gen()


def _sse(objs):
    return [f"data: {json.dumps(o)}\n".encode() for o in objs]


def _patch(monkeypatch, fs):
    monkeypatch.setattr(EG.egress(), "stream_post", fs)


def test_anthropic_stream_parsed(monkeypatch):
    fs = FakeStream(_sse([
        {"type": "message_start", "message": {"model": "claude-opus-5-5",
                                              "usage": {"input_tokens": 11}}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Zdravo"}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": " svijete"}},
        {"type": "message_delta", "delta": {"stop_reason": "end_turn"},
         "usage": {"output_tokens": 3}},
        {"type": "message_stop"}]))
    _patch(monkeypatch, fs)
    r = B.make("claude").chat([B.Msg("user", "hej")], system="s", max_tokens=100)
    assert r.text == "Zdravo svijete" and r.in_tokens == 11 and r.out_tokens == 3
    assert r.stop_reason == "end_turn" and fs.payload["stream"] is True
    assert fs.payload["model"] == "claude-opus-5-5"
    assert "thinking" not in fs.payload and "temperature" not in fs.payload
    assert fs.payload["output_config"]["effort"]
    assert fs.kw["secret_name"] == "ANTHROPIC_API_KEY"


def test_openai_shape_stream_parsed(monkeypatch):
    fs = FakeStream(_sse([
        {"model": "gpt-5", "choices": [{"delta": {"content": "A"}}]},
        {"choices": [{"delta": {"content": "B"}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 7, "completion_tokens": 2}}])
        + [b"data: [DONE]\n"])
    _patch(monkeypatch, fs)
    r = B.make("openai").chat([B.Msg("user", "x")])
    assert (r.text, r.in_tokens, r.out_tokens, r.stop_reason) == ("AB", 7, 2, "stop")
    assert fs.payload["stream_options"] == {"include_usage": True}
    assert fs.url == "https://api.openai.com/v1/chat/completions"


def test_gemini_stream_parsed(monkeypatch):
    fs = FakeStream(_sse([
        {"candidates": [{"content": {"parts": [{"text": "x"}]}}]},
        {"candidates": [{"content": {"parts": [{"text": "y"}]}, "finishReason": "STOP"}],
         "usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 2}}]))
    _patch(monkeypatch, fs)
    r = B.make("gemini").chat([B.Msg("user", "x")])
    assert r.text == "xy" and r.out_tokens == 2
    assert ":streamGenerateContent?alt=sse" in fs.url


def test_loop_hangs_up_the_cloud_stream(monkeypatch):
    fs = FakeStream(_sse([{"choices": [{"delta": {"content": "ponavljam ovo stalno "}}]}] * 500))
    _patch(monkeypatch, fs)
    r = B.make("deepseek").chat([B.Msg("user", "x")])
    assert r.stop_reason == "loop" and fs.closed and fs.n < 60


def test_cancel_hangs_up(monkeypatch):
    ev = threading.Event()
    fs = FakeStream(_sse([{"choices": [{"delta": {"content": f"t{i} "}}]} for i in range(500)]),
                    on_line=lambda i: ev.set() if i == 3 else None)
    _patch(monkeypatch, fs)
    r = B.make("openai").chat([B.Msg("user", "x")], cancel=ev)
    assert r.stop_reason == "cancelled" and fs.closed and fs.n < 10


# ---------------------------------------------------------------- billing (11)
def test_billing_advice_per_provider():
    for p in ("claude", "openai", "deepseek", "xai", "together", "fireworks"):
        assert P.cancel_stops_billing(p) and P.billing_advice(p)["caps"] == "normal"
    for p in ("gemini", "mistral", "groq", "openrouter"):
        assert not P.cancel_stops_billing(p) and P.billing_advice(p)["caps"] == "strict"


def test_strict_caps_for_providers_that_bill_full(monkeypatch):
    fs = FakeStream(_sse([{"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}]))
    _patch(monkeypatch, fs)
    long = B.Msg("user", "x" * 200_000)
    B.make("groq").chat([B.Msg("user", "staro " * 100), long], max_tokens=8000)
    assert fs.payload["max_tokens"] == P.STRICT_MAX_OUTPUT
    sent = sum(len(m["content"]) for m in fs.payload["messages"] if isinstance(m["content"], str))
    assert sent <= P.STRICT_MAX_INPUT_CHARS
    bk = B.make("claude")
    bk.chat([B.Msg("user", "y")], max_tokens=8000)
    # rule 48 a: the thinking budget comes on top of the answer limit
    assert fs.payload["max_tokens"] == 8000 + P.think_budget(bk.model, "high")


def test_worst_case_budget():
    wc = BU.Budget.worst_case_out
    assert wc("groq", 120, 1500, cut=True, usage_reported=True) == 1500   # billed in full
    assert wc("claude", 120, 8000, cut=True, usage_reported=True) == 120  # hang-up stops it
    assert wc("claude", 0, 8000, cut=False, usage_reported=False) == 8000  # no usage → worst


# ---------------------------------------------------------------- providers (9)
def test_all_presets_allowlisted_and_keys_bound():
    for name, pr in P.PRESETS.items():
        r = policy.rule_for(pr.host)
        assert r is not None and r.klass == policy.CREDENTIALED, name
        assert r.key_env == pr.key_name, name


def test_custom_endpoint_opens_only_after_operator(operator):
    DECL.install_hooks()
    pid = DECL.propose_endpoint("moj-server", "https://llm.example.org/v1", "neki-model")
    assert policy.rule_for("llm.example.org") is None          # proposal opens nothing
    assert "custom:moj-server" not in P.all_presets()
    store().decide(pid, True)
    r = policy.rule_for("llm.example.org")
    assert r and r.key_env == "CUSTOM_MOJ_SERVER_API_KEY"
    pr = P.get("custom:moj-server")
    assert pr and pr.path == "/v1/chat/completions" and not P.cancel_stops_billing(pr.provider)
    with pytest.raises(ValueError):
        DECL.propose_endpoint("x", "http://plain.example.org/v1")


def test_gguf_from_anywhere_by_path(tmp_path):
    f = tmp_path / "negdje" / "model.gguf"
    f.parent.mkdir()
    f.write_bytes(b"GGUF" + b"\0" * 10)
    mid = SEL.add_gguf_path(str(f))
    assert mid == f"gguf:{f.resolve()}"
    bk = SEL.backend_for(mid)
    assert bk.model == str(f.resolve())                         # used in place
    with pytest.raises(ValueError):
        SEL.add_gguf_path(str(tmp_path / "nije.txt"))


# ---------------------------------------------------------------- real socket (10)
class _SlowSSE(http.server.BaseHTTPRequestHandler):
    sent = 0
    broke = threading.Event()

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        try:
            for i in range(2000):
                self.wfile.write(f"data: {{\"i\": {i}}}\n\n".encode())
                self.wfile.flush()
                type(self).sent += 1
                time.sleep(0.01)
        except (BrokenPipeError, ConnectionResetError):
            type(self).broke.set()

    def log_message(self, *a):
        pass


@pytest.fixture
def slow_server(monkeypatch):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _SlowSSE)
    _SlowSSE.sent = 0
    _SlowSSE.broke.clear()
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    port = srv.server_address[1]
    eg = EG.egress()

    def gate(method, url, headers, body, secret_name, auth_style):
        parts = urllib.parse.urlsplit(url)
        return url, dict(headers or {}), "api.openai.com", parts.path, parts, \
            policy.rule_for("api.openai.com"), 0

    def connect(host, parts, timeout):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=timeout)
        c.connect()
        return c, "test"
    monkeypatch.setattr(eg, "_gate", gate)
    monkeypatch.setattr(eg, "_connect", connect)
    yield eg
    srv.shutdown()


def test_closing_the_stream_hangs_up_the_socket(slow_server):
    gen = slow_server.stream_post("https://api.openai.com/v1/chat/completions", {})
    got = [next(gen) for _ in range(6)]
    assert got and slow_server.live_streams() == 1
    gen.close()
    assert slow_server.live_streams() == 0
    assert _SlowSSE.broke.wait(5), "server kept writing — the connection was not cut"
    assert _SlowSSE.sent < 400


def test_kill_streams_cuts_every_live_stream(slow_server):
    out = {}

    def reader():
        n = 0
        for _ in slow_server.stream_post("https://api.openai.com/v1/chat/completions", {}):
            n += 1
        out["n"] = n
    t = threading.Thread(target=reader)
    t.start()
    for _ in range(100):
        if slow_server.live_streams():
            break
        time.sleep(0.02)
    time.sleep(0.1)
    assert slow_server.kill_streams() == 1
    t.join(5)
    assert not t.is_alive() and out["n"] < 1000
    assert _SlowSSE.broke.wait(5)
