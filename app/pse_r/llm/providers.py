"""
Provider presets (round 3, item 9) and what each one does with a cut-off stream
(item 11).

Every cloud model speaks one of three wire shapes — Anthropic Messages,
Gemini generateContent, or OpenAI chat-completions — and every call STREAMS
through the Guardian egress (item 10). The presets below are the hosts the
operator can pick without declaring anything; any other OpenAI-compatible
address is a CUSTOM endpoint: the app proposes it as a declaration, and it is
reachable only after the operator confirms it (shared_lib/declarations.py,
kind "endpoints").

Billing on abort (research 2026-10-25, plan §6 item 11):
  cancel_stops = True   closing the stream stops output billing
                        (Anthropic, OpenAI, DeepSeek, xAI, Together, Fireworks)
  cancel_stops = False  the whole completion is billed even if we hang up
                        (Gemini, Mistral, Groq) → stricter max_tokens / input caps
  cancel_stops = None   unknown (OpenRouter depends on the routed provider;
                        custom endpoints) → treated as False (worst case)
Input tokens are always billed; a non-streaming call is always billed in full.
"""
from __future__ import annotations

import re

from dataclasses import dataclass, field
from typing import Optional

ANTHROPIC, GEMINI, OPENAI = "anthropic", "gemini", "openai"


@dataclass(frozen=True)
class Preset:
    provider: str
    label: str
    shape: str                       # anthropic | gemini | openai
    host: str
    path: str                        # chat endpoint path
    key_name: str
    auth_style: str
    default_model: str
    cancel_stops: Optional[bool]
    vision: bool = False
    usage_in_stream: bool = True     # send stream_options.include_usage (openai shape)
    models_path: str = ""            # GET list of models (to offer real names)
    note: str = ""
    better: str = ""                 # "kad birati" ✓
    worse: str = ""                  # "kad birati" ✗
    console: str = ""                # where to create / revoke the key
    extra: dict = field(default_factory=dict)


PRESETS: dict[str, Preset] = {p.provider: p for p in (
    Preset("claude", "Claude (Anthropic)", ANTHROPIC, "api.anthropic.com", "/v1/messages",
           "ANTHROPIC_API_KEY", "x-api-key", "claude-opus-5-5", True, vision=True,
           models_path="/v1/models", note="plaćen — najjači za matematiku i izvlačenje",
           better="duga matematika, izvlačenje metoda iz radova, slike table",
           worse="troši budžet; traži internet",
           console="https://console.anthropic.com/settings/keys"),
    Preset("openai", "OpenAI (ChatGPT)", OPENAI, "api.openai.com", "/v1/chat/completions",
           "OPENAI_API_KEY", "bearer", "gpt-5", True, vision=True,
           models_path="/v1/models", note="plaćen",
           better="jak opšti model; prekid zaustavlja naplatu",
           worse="plaćen; traži internet",
           console="https://platform.openai.com/api-keys"),
    Preset("gemini", "Gemini (Google)", GEMINI, "generativelanguage.googleapis.com",
           "/v1beta/models/{model}:streamGenerateContent?alt=sse", "GEMINI_API_KEY",
           "header:x-goog-api-key", "gemini-2.5-flash", False, vision=True,
           note="besplatan tier (AI Studio)",
           better="besplatan tier, vidi slike",
           worse="prekid NE zaustavlja naplatu — strože granice izlaza",
           console="https://aistudio.google.com/apikey"),
    Preset("mistral", "Mistral", OPENAI, "api.mistral.ai", "/v1/chat/completions",
           "MISTRAL_API_KEY", "bearer", "mistral-large-latest", False,
           usage_in_stream=False, models_path="/v1/models",
           note="besplatan tier (La Plateforme)", better="brz, besplatan tier",
           worse="prekid NE zaustavlja naplatu; bez slika",
           console="https://console.mistral.ai/api-keys"),
    Preset("groq", "Groq", OPENAI, "api.groq.com", "/openai/v1/chat/completions",
           "GROQ_API_KEY", "bearer", "llama-3.3-70b-versatile", False,
           models_path="/openai/v1/models", note="besplatan, vrlo brz",
           better="vrlo brz i besplatan — dobar skeptik/trijaža",
           worse="prekid NE zaustavlja naplatu; manji modeli",
           console="https://console.groq.com/keys"),
    Preset("deepseek", "DeepSeek (cloud)", OPENAI, "api.deepseek.com", "/chat/completions",
           "DEEPSEEK_API_KEY", "bearer", "deepseek-chat", True,
           models_path="/models", note="jeftin",
           better="vrlo jeftin, dobar u matematici; prekid zaustavlja naplatu",
           worse="serveri u Kini — razmisli šta šalješ",
           console="https://platform.deepseek.com/api_keys"),
    Preset("xai", "xAI (Grok)", OPENAI, "api.x.ai", "/v1/chat/completions",
           "XAI_API_KEY", "bearer", "grok-4", True, models_path="/v1/models",
           note="plaćen", better="jak opšti model; prekid zaustavlja naplatu",
           worse="plaćen", console="https://console.x.ai"),
    Preset("openrouter", "OpenRouter", OPENAI, "openrouter.ai", "/api/v1/chat/completions",
           "OPENROUTER_API_KEY", "bearer", "openrouter/auto", None,
           models_path="/api/v1/models", note="jedan ključ, mnogo modela",
           better="jedan ključ za stotine modela",
           worse="naplata pri prekidu zavisi od rutiranog provajdera — računa se najgori slučaj",
           console="https://openrouter.ai/keys"),
    Preset("together", "Together AI", OPENAI, "api.together.xyz", "/v1/chat/completions",
           "TOGETHER_API_KEY", "bearer", "meta-llama/Llama-3.3-70B-Instruct-Turbo", True,
           models_path="/v1/models", note="otvoreni modeli",
           better="otvoreni modeli, prekid zaustavlja naplatu", worse="plaćen",
           console="https://api.together.ai/settings/api-keys"),
    Preset("fireworks", "Fireworks AI", OPENAI, "api.fireworks.ai",
           "/inference/v1/chat/completions", "FIREWORKS_API_KEY", "bearer",
           "accounts/fireworks/models/llama-v3p3-70b-instruct", True,
           models_path="/inference/v1/models", note="otvoreni modeli",
           better="brzi otvoreni modeli, prekid zaustavlja naplatu", worse="plaćen",
           console="https://fireworks.ai/account/api-keys"),
)}

CUSTOM_PREFIX = "custom:"


def custom_presets() -> dict[str, Preset]:
    """OpenAI-compatible endpoints the operator has DECLARED (confirmed)."""
    try:
        from ..shared_lib import declarations as DECL
        eps = DECL.current().get("endpoints") or {}
    except Exception:                                   # noqa: BLE001
        return {}
    out = {}
    for name, e in eps.items():
        pid = CUSTOM_PREFIX + name
        out[pid] = Preset(pid, f"{name} (vlastita adresa)", OPENAI, e["host"],
                          e.get("path", "/v1/chat/completions"), e["key_name"], "bearer",
                          e.get("model", ""), None, usage_in_stream=False,
                          models_path=e.get("models_path", ""),
                          note="deklarisana OpenAI-kompatibilna adresa",
                          better="bilo koji OpenAI-kompatibilan servis",
                          worse="naplata pri prekidu nepoznata — računa se najgori slučaj")
    return out


def all_presets() -> dict[str, Preset]:
    return {**PRESETS, **custom_presets()}


def get(provider: str) -> Optional[Preset]:
    return all_presets().get(provider)


def cancel_stops_billing(provider: str) -> bool:
    """Worst case for unknown: False."""
    p = get(provider)
    return bool(p and p.cancel_stops)


# --------------------------------------------------------------------------- #
# billing advice (item 11): what the operator should know per provider
# --------------------------------------------------------------------------- #
def billing_advice(provider: str) -> dict:
    p = get(provider)
    if p is None:
        return {"provider": provider, "cancel_stops": None, "text": "nepoznat provajder"}
    if p.provider.startswith("gguf"):
        return {"provider": provider, "cancel_stops": True, "text": "lokalno — bez naplate"}
    if p.cancel_stops is True:
        text = ("Prekid (dugme, Ctrl+K, „→ ∞“) zaustavlja naplatu izlaza čim se veza "
                "zatvori. Ulaz se uvijek naplaćuje. Preporuka: normalne granice.")
        caps = "normal"
    elif p.cancel_stops is False:
        text = ("Prekid NE zaustavlja naplatu: provajder naplati cijeli odgovor do "
                "max_tokens čak i ako prekinemo. Preporuka: strože max_tokens i manji ulaz "
                "(aplikacija ih sama smanjuje), budžet računa najgori slučaj.")
        caps = "strict"
    else:
        text = ("Nije poznato da li prekid zaustavlja naplatu (zavisi od servisa). "
                "Računa se najgori slučaj: strože granice, budžet do max_tokens.")
        caps = "strict"
    return {"provider": provider, "cancel_stops": p.cancel_stops, "text": text, "caps": caps}


STRICT_MAX_OUTPUT = 1500         # tokens, for providers that bill the full completion
STRICT_MAX_INPUT_CHARS = 60_000  # ~15k tokens of prompt


def effective_caps(provider: str, max_tokens: int) -> tuple[int, int]:
    """(max_tokens, max_input_chars) after the billing rule for this provider."""
    if cancel_stops_billing(provider):
        return max_tokens, 400_000
    return min(max_tokens, STRICT_MAX_OUTPUT), STRICT_MAX_INPUT_CHARS


# --------------------------------------------------------------------------- #
# Thinking budget (rule 48 a, d): models that think spend their reasoning out
# of the same output limit. The budget is added ON TOP of the answer limit, so
# thinking never eats the answer. Per role via effort (router.ROLE_TUNING).
# --------------------------------------------------------------------------- #
THINK_BUDGET = {"low": 512, "medium": 1024, "high": 4096}

_THINKING_MARKS = ("gemini-2.5", "gemini-3", "deepseek-r1", "deepseek-reasoner", "-r1-",
                   "reasoning", "thinking", "qwq", "gpt-5", "grok-3-mini", "magistral",
                   "openrouter/auto", "claude-opus-5", "claude-sonnet-5", "claude-fable-5")
_O_SERIES = re.compile(r"(^|/)o[134](-|$)")


def thinks(model: str) -> bool:
    """Whether the model spends reasoning tokens out of max_tokens."""
    m = (model or "").lower()
    return any(k in m for k in _THINKING_MARKS) or m.endswith("-r1") or bool(_O_SERIES.search(m))


def think_budget(model: str, effort: str = "medium") -> int:
    """Tokens reserved for thinking on top of the answer (0 for models that do not think)."""
    return THINK_BUDGET.get(effort, THINK_BUDGET["medium"]) if thinks(model) else 0


# Stop reasons that mean "the output limit cut the answer" (rule 48 b).
TRUNCATED = {"max_tokens", "MAX_TOKENS", "length"}
