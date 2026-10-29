"""Rule 48 a, b, d (round 3, R9): the thinking budget sits on top of the
answer limit, a cut answer gets one retry with twice the limit (then the app
says so), and a cut reader is shown as "čitač odsječen", never silently
"bez čitača"."""
import json

import pytest

from pse_r.guardian import egress as EG
from pse_r.llm import backend as B
from pse_r.llm import limits as L
from pse_r.llm import providers as P
from pse_r.llm import router as R
from pse_r.pse import measure as M


@pytest.fixture(autouse=True)
def _guard_clean():
    L.resume(); L._LISTENERS.clear(); L._WATCH.clear()
    yield
    L.resume(); L._LISTENERS.clear(); L._WATCH.clear()


class FakeStream:
    def __init__(self, lines):
        self.lines, self.payloads = lines, []

    def __call__(self, url, payload, **kw):
        self.payloads.append(payload)
        return (ln for ln in self.lines)


def _sse(objs):
    return [f"data: {json.dumps(o)}\n".encode() for o in objs]


# ------------------------------------------------------------------ 48 a
def test_thinking_models_are_recognised():
    for m in ("gemini-2.5-flash", "gemini-2.5-pro", "deepseek/deepseek-r1-0528",
              "deepseek-reasoner", "o3-mini", "openai/o4-mini", "claude-opus-5-5",
              "gguf:/x/DeepSeek-R1-0528-Qwen3-8B-Q5_K_M.gguf"):
        assert P.thinks(m), m
    for m in ("llama-3.3-70b-versatile", "mistral-large-latest", "deepseek-chat",
              "gpt-4o", "meta-llama/Llama-3.3-70B-Instruct-Turbo"):
        assert not P.thinks(m), m


def test_gemini_budget_on_top_of_answer(monkeypatch):
    fs = FakeStream(_sse([{"candidates": [{"content": {"parts": [{"text": "ok"}]},
                                           "finishReason": "STOP"}],
                           "usageMetadata": {"promptTokenCount": 3, "candidatesTokenCount": 1,
                                             "thoughtsTokenCount": 40}}]))
    monkeypatch.setattr(EG.egress(), "stream_post", fs)
    r = B.make("gemini", "gemini-2.5-flash").chat([B.Msg("user", "x")], max_tokens=600,
                                                  effort="medium")
    gen = fs.payloads[-1]["generationConfig"]
    assert gen["thinkingConfig"]["thinkingBudget"] == P.THINK_BUDGET["medium"]
    assert gen["maxOutputTokens"] == 600 + P.THINK_BUDGET["medium"]
    assert r.out_tokens == 41                       # thoughts are billed too
    assert r.raw["answer_max"] == 600 and r.raw["think_budget"] == P.THINK_BUDGET["medium"]


def test_non_thinking_model_unchanged(monkeypatch):
    fs = FakeStream(_sse([{"choices": [{"delta": {"content": "ok"}, "finish_reason": "stop"}]}]))
    monkeypatch.setattr(EG.egress(), "stream_post", fs)
    B.make("groq", "llama-3.3-70b-versatile").chat([B.Msg("user", "x")], max_tokens=300)
    assert fs.payloads[-1]["max_tokens"] == 300 and "reasoning" not in fs.payloads[-1]


def test_openrouter_reasoning_capped(monkeypatch):
    fs = FakeStream(_sse([{"choices": [{"delta": {"content": "{}"}, "finish_reason": "stop"}]}]))
    monkeypatch.setattr(EG.egress(), "stream_post", fs)
    B.make("openrouter", "deepseek/deepseek-r1").chat([B.Msg("user", "x")], max_tokens=200,
                                                      effort="low")
    pl = fs.payloads[-1]
    assert pl["max_tokens"] == 200 + P.THINK_BUDGET["low"]
    assert pl["reasoning"] == {"max_tokens": P.THINK_BUDGET["low"]}


# ------------------------------------------------------------------ 48 b
class FakeBackend:
    """Answers from a script of (text, stop_reason); records the limits asked."""

    def __init__(self, script):
        self.script, self.limits = list(script), []

    def chat(self, messages, system="", max_tokens=0, effort="", cancel=None):
        self.limits.append(max_tokens)
        text, stop = self.script.pop(0)
        return B.Reply(text, "gguf", "fake.gguf", 1, 1, stop, {})


def _router_with(monkeypatch, fb, model="gguf:/x/plain-model.gguf"):
    from pse_r.llm import selection as SEL
    rt = R.Router()
    monkeypatch.setattr(rt, "resolve", lambda role, avoid="": R.Route("gguf", model, role))
    monkeypatch.setattr(SEL, "backend_for", lambda mid: fb)
    return rt


def test_cut_answer_retried_once_with_twice_the_limit(monkeypatch):
    fb = FakeBackend([("pola odgo", "length"), ("cijeli odgovor.", "stop")])
    rt = _router_with(monkeypatch, fb)
    r = rt._call(B.CHAT, [B.Msg("user", "q")], max_tokens=900, who="t")
    assert fb.limits == [900, 1800]
    assert r.text == "cijeli odgovor." and not (r.raw or {}).get("truncated")


def test_still_cut_is_said(monkeypatch):
    fb = FakeBackend([("pola", "MAX_TOKENS"), ("opet pola", "MAX_TOKENS")])
    rt = _router_with(monkeypatch, fb)
    r = rt._call(B.CHAT, [B.Msg("user", "q")], max_tokens=600, who="t")
    assert len(fb.limits) == 2 and r.raw["truncated"]
    assert "odgovor odsječen" in r.text and r.text.startswith("opet pola")


def test_whole_answer_not_retried(monkeypatch):
    fb = FakeBackend([("gotovo", "stop")])
    rt = _router_with(monkeypatch, fb)
    rt._call(B.CHAT, [B.Msg("user", "q")], max_tokens=600, who="t")
    assert fb.limits == [600]


# ------------------------------------------------------------------ 48 d
def test_gguf_reader_gets_thinking_budget(monkeypatch):
    fb = FakeBackend([('{"a": 1}', "stop")])
    fb.lim = type("Lim", (), {"think_budget": 1500})()
    rt = _router_with(monkeypatch, fb, model="gguf:/x/DeepSeek-R1-0528-Qwen3-8B-Q5_K_M.gguf")
    rt.sensor_call(B.SKEPTIC, "p", max_tokens=200)
    assert fb.limits == [1700]


def test_sensor_cut_flag(monkeypatch):
    fb = FakeBackend([('{"K1": 0.', "length"), ('{"K1": 0.2, "K2"', "length")])
    rt = _router_with(monkeypatch, fb)
    t = rt.sensor_call(B.SKEPTIC, "p")
    assert isinstance(t, str) and t.cut


def _full():
    return json.dumps({k: 0.1 for k in M.SCHEMA})


def test_reader_cut_is_named_not_silent():
    cut = M.ReaderSpec(lambda p: R.SensorText('{"K1": 0.3, "K2"', cut=True), "x")
    assert M.model_read_ex("odgovor", "pitanje", cut) == (None, "cut")
    # incomplete JSON without the flag is also a cut
    half = M.ReaderSpec(lambda p: '{"K1": 0.3, "K2": 0.', "x")
    assert M.model_read_ex("odgovor", "pitanje", half)[1] == "cut"
    junk = M.ReaderSpec(lambda p: "ne znam", "x")
    assert M.model_read_ex("odgovor", "pitanje", junk) == (None, "none")
    ok = M.ReaderSpec(lambda p: _full(), "x")
    nums, why = M.model_read_ex("odgovor", "pitanje", ok)
    assert why == "" and set(nums) == set(M.SCHEMA)


def test_read_move_note(monkeypatch):
    M.set_reader(M.ReaderSpec(lambda p: R.SensorText('{"K1"', cut=True), "x"))
    try:
        rd = M.read_move(words="Evo odgovora.", message="pitanje", uses_model=True)
        assert rd.note == M.CUT == "čitač odsječen"
        M.set_reader(M.ReaderSpec(lambda p: "", "x"))
        assert M.read_move(words="Evo.", message="p", uses_model=True).note == "bez čitača"
    finally:
        M.set_reader(None)


def test_lab_shows_reader_cut(operator):
    from pse_r.gui import pse_lab as PL
    M.set_reader(M.ReaderSpec(lambda p: R.SensorText('{"K1"', cut=True), "x"))
    try:
        from pse_r.pse import path as PATH
        PATH.words("voice", "Evo odgovora na pitanje.", message="pitanje")
        uid = PATH._lib().unit("voice").unit_id
    finally:
        M.set_reader(None)
    line = PL._reader_line(uid)
    assert line.startswith("⚠") and "odsječen 1" in line or "odsječen 2" in line
