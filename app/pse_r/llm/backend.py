"""
LLM backend interface + the four providers, spoken as raw REST.

Why raw REST and not the official SDKs: nothing may be installed on this machine
before the trip (4 GB, no time, and every added dependency is another thing that
can break on a hotel WiFi at 23:00). More importantly, going through
`guardian.egress` is what makes the Guardian's guarantees real — an SDK would
open its own sockets with its own TLS stack and bypass the pinning, the
allowlist, the rate limiting and the anomaly scoring in one step.

Roles, not models. Callers ask for MATH or TRIAGE; `router.py` decides which
provider and model serves that role. That is what lets a free Groq tier do the
bulk curation while Claude only sees the mathematics.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Optional

import threading

from ..guardian import policy
from ..guardian.egress import EgressBlocked, egress
from . import providers as P

# --------------------------------------------------------------------------- #
# Roles
# --------------------------------------------------------------------------- #
MATH = "math"            # zeta reasoning — the only role that gets the strong model
VISION = "vision"        # whiteboard -> LaTeX transcription
CHAT = "chat"            # ordinary conversation in the right pane
TRIAGE = "triage"        # is this paper relevant? cheap, high volume
CURATE = "curate"        # rank/dedupe/summarize scraped material
SKEPTIC = "skeptic"      # attack a claim — deliberately a different model
SUMMARIZE = "summarize"  # rewrite your own note

ROLES = [MATH, VISION, CHAT, TRIAGE, CURATE, SKEPTIC, SUMMARIZE]


@dataclass
class Msg:
    role: str                     # "user" | "assistant"
    text: str = ""
    image_png: Optional[bytes] = None      # whiteboard capture, for VISION


@dataclass
class Reply:
    text: str
    provider: str
    model: str
    in_tokens: int = 0
    out_tokens: int = 0
    stop_reason: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def refused(self) -> bool:
        return self.stop_reason == "refusal"


class Backend:
    """One provider. `chat()` is the whole surface; every cloud call STREAMS
    (round 3, item 10) under a CallGuard, so a timeout, a loop, the "→ ∞"
    pause, the kill switch or an explicit cancel hangs up the connection while
    the model is still writing."""

    provider = ""
    host = ""
    key_name = ""
    auth_style = "x-api-key"
    default_model = ""
    supports_vision = False

    def __init__(self, model: str = ""):
        self.model = model or self.default_model

    def chat(self, messages: list[Msg], system: str = "",
             max_tokens: int = 4096, effort: str = "high",
             cancel: Optional[threading.Event] = None) -> Reply:
        raise NotImplementedError

    @staticmethod
    def _b64(data: bytes) -> str:
        return base64.b64encode(data).decode()


def _sse_data(lines):
    """Yield parsed JSON objects from an SSE / data-lines stream."""
    for raw in lines:
        line = raw.decode("utf-8", "replace").strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            yield json.loads(data)
        except json.JSONDecodeError:
            continue


class StreamingBackend(Backend):
    """Shared streaming loop; subclasses build the request and read one event."""

    preset: P.Preset = None

    def __init__(self, model: str = "", preset: Optional[P.Preset] = None):
        if preset is not None:
            self.preset = preset
        pr = self.preset
        self.provider, self.host = pr.provider, pr.host
        self.key_name, self.auth_style = pr.key_name, pr.auth_style
        self.default_model, self.supports_vision = pr.default_model, pr.vision
        super().__init__(model)

    # subclass hooks
    def _url(self) -> str:
        return f"https://{self.host}{self.preset.path}"

    def _headers(self) -> dict:
        return {}

    def _payload(self, messages, system, max_tokens, effort) -> dict:
        raise NotImplementedError

    def _event(self, ev: dict, st: dict) -> str:
        """Consume one event; update st (in, out, stop, model); return new text."""
        raise NotImplementedError

    def chat(self, messages, system="", max_tokens=4096, effort="high",
             cancel=None) -> Reply:
        from . import limits as L
        max_tokens, max_in = P.effective_caps(self.provider, max_tokens)
        messages = _cap_input(messages, max_in)
        guard = L.CallGuard(L.Limits.from_settings(), cancel=cancel)
        try:
            guard.check()
        except L.Aborted as a:
            raise EgressBlocked(f"{self.provider}: {a}") from None
        payload = self._payload(messages, system, max_tokens, effort)
        sent_max = max_tokens + P.think_budget(self.model, effort)   # rule 48 a
        from ..guardian import disclosure as DISC          # item 21: measured BEFORE sending
        try:
            DISC.check_and_spend(self.host, DISC.payload_text(payload),
                                 actor=f"model:{self.provider}")
        except DISC.DisclosureExceeded as e:
            raise EgressBlocked(str(e)) from None
        st = {"in": 0, "out": 0, "stop": "", "model": self.model, "error": ""}
        parts: list[str] = []
        gen = egress().stream_post(self._url(), payload, headers=self._headers(),
                                   secret_name=self.key_name, auth_style=self.auth_style,
                                   timeout=max(30.0, guard.remaining()), cancel=cancel)
        guard.started()
        try:
            for ev in _sse_data(gen):
                piece = self._event(ev, st)
                if st["error"]:
                    raise EgressBlocked(f"{self.provider}: {st['error']}")
                if piece:
                    parts.append(piece)
                guard.tick("".join(parts) if piece else "")
        except L.Aborted as a:
            st["stop"] = a.reason
        finally:
            gen.close()                                 # hang up now
        guard.finish(0)
        text = "".join(parts)
        if st["stop"] in _CUT:
            text = text.rstrip() + f"\n\n[prekinuto: {_CUT[st['stop']]}]"
        return Reply(text, self.provider, st["model"], st["in"], st["out"],
                     st["stop"], {"stream": True, "max_tokens": sent_max,
                                  "answer_max": max_tokens,
                                  "think_budget": sent_max - max_tokens,
                                  "cut": st["stop"] in _CUT,
                                  "usage_reported": bool(st["out"] or st["in"])})


_CUT = {"loop": "detektovano ponavljanje", "timeout": "isteklo vrijeme poziva",
        "paused": "„→ ∞“ pauza", "cancelled": "prekinuto (veza zatvorena)",
        "ram": "slobodan RAM ispod praga", "diverging": "„→ ∞“"}


def _cap_input(messages: list[Msg], max_chars: int) -> list[Msg]:
    """Keep the most recent messages within max_chars (oldest dropped first;
    the last message is truncated from its start only if it alone is too long)."""
    out, total = [], 0
    for m in reversed(messages):
        n = len(m.text or "")
        if total + n > max_chars:
            if not out:
                out.append(Msg(m.role, (m.text or "")[-max_chars:], m.image_png))
            break
        out.append(m)
        total += n
    return list(reversed(out))


class AnthropicBackend(StreamingBackend):
    """
    Anthropic Messages API, streamed (SSE), over raw HTTPS through the egress.

      * default model claude-opus-5-5: thinking is always on (never send
        `thinking: disabled` or budget_tokens — 400), effort is the only control
        and defaults to `medium`, so it is always sent explicitly;
      * temperature / top_p / top_k are rejected — never sent;
      * `stop_reason == "refusal"` arrives as a normal 200 — checked by callers
        via Reply.refused; the server-side fallback is on (`fallbacks: "default"`),
        so a refused request is re-run on a fallback model inside the same call.
    """

    preset = P.PRESETS["claude"]

    def _headers(self) -> dict:
        return {"anthropic-version": "2023-06-01",
                "anthropic-beta": "server-side-fallback-2026-07-01"}

    def _payload(self, messages, system, max_tokens, effort) -> dict:
        content_msgs = []
        for m in messages:
            blocks = []
            if m.image_png:
                blocks.append({"type": "image", "source": {
                    "type": "base64", "media_type": "image/png",
                    "data": self._b64(m.image_png)}})
            if m.text:
                blocks.append({"type": "text", "text": m.text})
            content_msgs.append({"role": m.role, "content": blocks or [
                {"type": "text", "text": ""}]})
        total = max_tokens + P.think_budget(self.model, effort)   # thinking + text share it
        payload = {"model": self.model, "max_tokens": total, "stream": True,
                   "messages": content_msgs, "output_config": {"effort": effort},
                   "fallbacks": "default"}
        if system:
            payload["system"] = [{"type": "text", "text": system,
                                  "cache_control": {"type": "ephemeral"}}]
        return payload

    def _event(self, ev, st) -> str:
        t = ev.get("type")
        if t == "message_start":
            msg = ev.get("message") or {}
            st["model"] = msg.get("model", st["model"])
            st["in"] = int((msg.get("usage") or {}).get("input_tokens", 0))
        elif t == "content_block_delta":
            d = ev.get("delta") or {}
            if d.get("type") == "text_delta":
                return d.get("text", "")
        elif t == "message_delta":
            st["stop"] = (ev.get("delta") or {}).get("stop_reason") or st["stop"]
            st["out"] = int((ev.get("usage") or {}).get("output_tokens", st["out"]))
        elif t == "error":
            st["error"] = (ev.get("error") or {}).get("message", str(ev))
        return ""


class GeminiBackend(StreamingBackend):
    preset = P.PRESETS["gemini"]

    def _url(self) -> str:
        return f"https://{self.host}" + self.preset.path.replace("{model}", self.model)

    def _payload(self, messages, system, max_tokens, effort) -> dict:
        contents = []
        for m in messages:
            parts = []
            if m.image_png:
                parts.append({"inlineData": {"mimeType": "image/png",
                                             "data": self._b64(m.image_png)}})
            if m.text:
                parts.append({"text": m.text})
            contents.append({"role": "user" if m.role == "user" else "model",
                             "parts": parts or [{"text": ""}]})
        # Gemini 2.5 spends thinking out of maxOutputTokens (live test, rc1: a
        # 600-token limit left 24 visible tokens). Rule 48 a: a budget per role
        # (via effort) and the limit = answer + budget.
        budget = P.think_budget(self.model, effort)
        gen = {"maxOutputTokens": max_tokens + budget}
        if budget:
            gen["thinkingConfig"] = {"thinkingBudget": budget}
        payload = {"contents": contents, "generationConfig": gen}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}
        return payload

    def _event(self, ev, st) -> str:
        if "error" in ev:
            st["error"] = (ev["error"] or {}).get("message", str(ev))
            return ""
        u = ev.get("usageMetadata") or {}
        if u:
            st["in"] = int(u.get("promptTokenCount", st["in"]))
            st["out"] = (int(u.get("candidatesTokenCount", 0))
                         + int(u.get("thoughtsTokenCount", 0))) or st["out"]
        cands = ev.get("candidates") or []
        if not cands:
            return ""
        st["stop"] = cands[0].get("finishReason", st["stop"]) or st["stop"]
        return "".join(p.get("text", "") for p in
                       (cands[0].get("content") or {}).get("parts", []))


class OpenAICompatBackend(StreamingBackend):
    """OpenAI chat-completions shape: OpenAI, Mistral, Groq, DeepSeek, xAI,
    OpenRouter, Together, Fireworks, and any declared custom endpoint."""

    def _payload(self, messages, system, max_tokens, effort) -> dict:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        for m in messages:
            if m.image_png and self.supports_vision:
                msgs.append({"role": m.role, "content": [
                    {"type": "text", "text": m.text or ""},
                    {"type": "image_url", "image_url": {
                        "url": "data:image/png;base64," + self._b64(m.image_png)}}]})
            else:
                msgs.append({"role": m.role, "content": m.text})
        budget = P.think_budget(self.model, effort)              # rule 48 a, d
        payload = {"model": self.model, "messages": msgs, "max_tokens": max_tokens + budget,
                   "stream": True}
        if budget and self.provider == "openrouter":
            payload["reasoning"] = {"max_tokens": budget}
        if self.preset.usage_in_stream:
            payload["stream_options"] = {"include_usage": True}
        return payload

    def _event(self, ev, st) -> str:
        if "error" in ev:
            err = ev["error"]
            st["error"] = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            return ""
        st["model"] = ev.get("model", st["model"])
        u = ev.get("usage") or {}
        if u:
            st["in"] = int(u.get("prompt_tokens", st["in"]))
            st["out"] = int(u.get("completion_tokens", st["out"]))
        ch = (ev.get("choices") or [{}])
        if not ch:
            return ""
        ch = ch[0]
        st["stop"] = ch.get("finish_reason") or st["stop"]
        return (ch.get("delta") or {}).get("content") or ""


def _class_for(pr: P.Preset):
    return {P.ANTHROPIC: AnthropicBackend, P.GEMINI: GeminiBackend}.get(
        pr.shape, OpenAICompatBackend)


class _BackendTable(dict):
    """provider → backend factory, recomputed so declared endpoints appear."""

    def _all(self):
        return {name: _bound(pr) for name, pr in P.all_presets().items()}

    def __getitem__(self, k):
        return self._all()[k]

    def get(self, k, default=None):
        return self._all().get(k, default)

    def __contains__(self, k):
        return k in P.all_presets()

    def items(self):
        return self._all().items()

    def keys(self):
        return P.all_presets().keys()

    def __iter__(self):
        return iter(P.all_presets())


def _bound(pr: P.Preset):
    cls = _class_for(pr)

    class Bound(cls):
        preset = pr
    Bound.__name__ = f"{cls.__name__}[{pr.provider}]"
    for attr, val in (("provider", pr.provider), ("host", pr.host),
                      ("key_name", pr.key_name), ("auth_style", pr.auth_style),
                      ("default_model", pr.default_model), ("supports_vision", pr.vision)):
        setattr(Bound, attr, val)
    return Bound


BACKENDS = _BackendTable()
ClaudeBackend = _bound(P.PRESETS["claude"])
MistralBackend = _bound(P.PRESETS["mistral"])
GroqBackend = _bound(P.PRESETS["groq"])


def make(provider: str, model: str = "") -> Backend:
    pr = P.get(provider)
    if pr is None:
        raise ValueError(f"nepoznat provajder '{provider}'")
    return _bound(pr)(model)


def provider_info() -> list[dict]:
    """Table for the setup screens (wizard, first-run)."""
    out = []
    for name, pr in P.all_presets().items():
        rule = policy.rule_for(pr.host)
        out.append({"provider": name, "label": pr.label, "host": pr.host,
                    "key": pr.key_name, "default_model": pr.default_model,
                    "vision": pr.vision, "note": pr.note, "better": pr.better,
                    "worse": pr.worse, "console": pr.console,
                    "cancel_stops": pr.cancel_stops,
                    "advice": P.billing_advice(name)["text"],
                    "allowed": rule is not None})
    return out


def list_models(provider: str) -> list[str]:
    """Real model names from the provider (GET models endpoint), through the egress."""
    pr = P.get(provider)
    if pr is None or not pr.models_path:
        return []
    hdr = {"anthropic-version": "2023-06-01"} if pr.shape == P.ANTHROPIC else {}
    r = egress().request("GET", f"https://{pr.host}{pr.models_path}", headers=hdr,
                         secret_name=pr.key_name, auth_style=pr.auth_style, timeout=20)
    d = r.json()
    items = d.get("data") or d.get("models") or []
    return sorted({(x.get("id") or x.get("name") or "") for x in items if isinstance(x, dict)} - {""})
