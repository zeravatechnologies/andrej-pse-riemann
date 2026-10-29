"""
The router — which provider serves which role.

This is the piece that makes twenty days of heavy use nearly free. Bulk work
(triage every abstract the scraper pulls, curate, run the skeptic pass) goes to
providers with generous free tiers. The strong, paid model is reserved for the
two roles where being wrong actually costs you: the mathematics itself, and
reading your handwriting off the whiteboard.

The skeptic is deliberately routed to a *different* provider than the one that
produced the claim where possible. A model grading its own output is a weak
check; a different model attacking it is a real one.

Every route degrades: if the preferred provider has no key, the next one in the
chain takes over, and if none is configured the caller gets a clear error naming
what to set up in the wizard.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..guardian import secrets as SEC
from . import backend as B
from . import providers as P
from . import psel
from .budget import budget

# role -> ordered provider preference. First one with a key wins.
ROUTES: dict[str, list[str]] = {
    B.MATH:      ["claude", "gemini", "mistral", "groq"],
    B.VISION:    ["claude", "gemini"],                       # only these see images
    B.CHAT:      ["claude", "gemini", "mistral", "groq"],
    B.TRIAGE:    ["groq", "mistral", "gemini", "claude"],
    B.CURATE:    ["groq", "mistral", "gemini", "claude"],
    B.SKEPTIC:   ["mistral", "groq", "gemini", "claude"],
    B.SUMMARIZE: ["groq", "mistral", "gemini", "claude"],
}

# Per-role knobs. MATH gets room to think (on Opus 5, max_tokens caps thinking
# and text together, so a tight budget truncates mid-derivation).
ROLE_TUNING: dict[str, dict] = {
    B.MATH:      {"max_tokens": 16000, "effort": "high"},
    B.VISION:    {"max_tokens": 2000, "effort": "medium"},
    B.CHAT:      {"max_tokens": 4000, "effort": "medium"},
    B.TRIAGE:    {"max_tokens": 300, "effort": "low"},
    B.CURATE:    {"max_tokens": 800, "effort": "low"},
    B.SKEPTIC:   {"max_tokens": 700, "effort": "medium"},
    B.SUMMARIZE: {"max_tokens": 1200, "effort": "low"},
}


class NoProvider(Exception):
    pass


class SensorText(str):
    """The reader's raw text; `.cut` = still cut by the limit after the retry."""

    def __new__(cls, text: str = "", cut: bool = False):
        obj = super().__new__(cls, text)
        obj.cut = cut
        return obj


@dataclass
class Route:
    provider: str
    model: str
    role: str


class Router:
    def __init__(self):
        self.overrides: dict[str, str] = {}      # role -> forced provider
        self.models = _ModelOverrides()          # provider -> model override (settings)
        self._last_provider: dict[str, str] = {}  # role -> provider last used

    # ------------------------------------------------------------------ #
    def available(self) -> list[str]:
        s = SEC.store()
        from . import providers as P
        return [p for p, pr in P.all_presets().items() if s.has(pr.key_name)]

    def resolve(self, role: str, avoid: str = "") -> Route:
        """
        Plan v2 (decided 2026-10-25): ONE main AI does every role; the skeptic
        role goes to the skeptic, which is always a DIFFERENT model. The old
        per-role provider table (ROUTES) is no longer consulted. `avoid` is kept
        for API compatibility and ignored: independence comes from the skeptic.
        """
        from . import selection as SEL
        mid = SEL.get_skeptic() if role == B.SKEPTIC else SEL.get_main()
        if not mid:
            if role == B.SKEPTIC:
                raise NoProvider("skeptik nedostupan — samo determinističke provjere")
            raise NoProvider(
                "nijedan model nije izabran ni dostupan — unesi ključ u čarobnjaku "
                "ili stavi GGUF u folder models/, pa izaberi glavni AI")
        if mid.startswith("gguf:"):
            return Route("gguf", mid, role)
        cls = B.BACKENDS[mid]
        return Route(mid, self.models.get(mid, cls.default_model), role)

    # ------------------------------------------------------------------ #
    def unit_call(self, unit, role: str, messages: list[B.Msg], *, system_extra: str = "",
                  max_tokens: int = 0) -> B.Reply:
        """A model call on a PSE unit's path (`pse.path.ask` is the only
        caller). Applies the generator (PSE-L system prompt + scrub), the
        budget under "→ ∞", the kill-switch self-trip; disclosure, egress and
        the CallGuard run inside the backend. θ is NOT touched here: the move
        is measured by SHARED_LIB's meter after the call."""
        if unit is None:
            raise NoProvider("poziv modela mimo PSE jedinice nije dozvoljen")
        return self._call(role, messages, system_extra=system_extra, max_tokens=max_tokens,
                          who=f"{unit.unit_id}")

    def sensor_call(self, role: str, prompt: str, max_tokens: int = 200) -> "SensorText":
        """The language reader (a sensor, §0.5.4, not an agent): twelve numbers
        and nothing else. Same brakes; no generator register. The limit is
        200 + the model's thinking budget (rule 48 d, added in the backend);
        `.cut` says the answer was still cut after the one retry."""
        r = self._call(role, [B.Msg("user", prompt)], max_tokens=max_tokens, who="čitač",
                       system="Return only the JSON object requested.", raw=True)
        return SensorText(r.text or "", cut=bool((r.raw or {}).get("truncated")))

    def _call(self, role: str, messages: list[B.Msg], *, system_extra: str = "",
              max_tokens: int = 0, who: str = "", system: str = "",
              raw: bool = False) -> B.Reply:
        route = self.resolve(role)
        tune = ROLE_TUNING.get(role, ROLE_TUNING[B.CHAT])
        effort = "low" if raw else tune["effort"]
        limit = max_tokens or tune["max_tokens"]
        if route.provider == "gguf":
            from . import selection as SEL
            if role == B.VISION:
                raise NoProvider("lokalni GGUF ne čita slike — za tablu izaberi "
                                 "Claude ili Gemini kao glavni AI")
            bk = SEL.backend_for(route.model)
            if P.thinks(route.model):                  # rule 48 d: R1 thinks in the open
                limit += int(getattr(getattr(bk, "lim", None), "think_budget", 0) or 0)
        else:
            bk = B.make(route.provider, route.model)
            budget().check(route.provider)

        system = system or psel.system_prompt(role, system_extra)
        reply = bk.chat(messages, system=system, max_tokens=limit, effort=effort)
        self._account(route, role, who, reply)
        if reply.stop_reason in P.TRUNCATED:
            # rule 48 b: one retry with twice the limit; if it is still cut, say so
            if route.provider != "gguf":
                budget().check(route.provider)
            again = bk.chat(messages, system=system, max_tokens=limit * 2, effort=effort)
            self._account(route, role, who + ":ponovo", again)
            reply = again
            if reply.stop_reason in P.TRUNCATED:
                reply.raw = {**(reply.raw or {}), "truncated": True}
                if not raw:
                    from ..i18n import tr
                    reply.text = (reply.text or "").rstrip() + "\n\n" + tr(
                        "[odgovor odsječen: ni dvostruki limit nije bio dovoljan — "
                        "pitaj kraće ili podijeli pitanje]")
        self._last_provider[role] = route.provider
        if raw:
            return reply
        if reply.refused:
            reply.text = (
                "⛔ Model je odbio ovaj zahtjev (safety klasifikator). "
                "Ovo se povremeno dešava i na sasvim benignim pitanjima. "
                "Preformuliši, ili pošalji isto pitanje drugom provajderu.")
            return reply
        reply.text = psel.scrub(reply.text)
        return reply

    @staticmethod
    def _account(route: Route, role: str, who: str, reply: B.Reply) -> None:
        if route.provider == "gguf":                  # a local model costs nothing
            return
        rw = reply.raw or {}
        out = budget().worst_case_out(route.provider, reply.out_tokens,
                                      int(rw.get("max_tokens", 0)),
                                      bool(rw.get("cut")),
                                      bool(rw.get("usage_reported", True)))
        budget().record(route.provider, reply.model, f"{role}:{who}",
                        reply.in_tokens, out, worst_case=(out != reply.out_tokens))
        from ..guardian import killswitch as KS
        KS.observe_cloud_call(route.provider, reply.in_tokens + out,
                              budget().price(reply.model, reply.in_tokens, out,
                                             route.provider))

    def _ping_once(self, provider: str, model: str):
        bk = B.make(provider, model)
        r = bk.chat([B.Msg("user", "Odgovori samo sa: OK")],
                    system="Odgovaraj jednom riječju.", max_tokens=16, effort="low")
        budget().record(provider, r.model, "ping", r.in_tokens, r.out_tokens)
        return r

    def ping(self, provider: str, model: str = "") -> tuple[bool, str]:
        """Wizard connectivity test: one tiny real call. If the provider answers 404
        (the model was retired — live test: Groq), ask the server for its real models,
        pick one, try once more, and remember it (settings "models")."""
        model = model or self.models.get(provider, "")
        try:
            r = self._ping_once(provider, model)
            if model:                                    # the model that answered is remembered
                from .. import settings as S
                S.set_("models", {**(S.get("models") or {}), provider: model})
            return True, (r.text or "").strip()[:40] or "(prazan odgovor)"
        except Exception as e:                       # noqa: BLE001 — surfaced to UI
            first = str(e)
            if "HTTP 404" not in first:
                return False, first[:300]
        try:
            names = B.list_models(provider)
        except Exception as e:                       # noqa: BLE001
            return False, (f"{first[:200]} — a lista modela nije dostupna: {e}")[:300]
        pick = pick_model(names, model or (B.P.get(provider).model if B.P.get(provider) else ""))
        if not pick:
            return False, f"{first[:200]} — server ne nudi odgovarajući model"[:300]
        try:
            r = self._ping_once(provider, pick)
        except Exception as e:                       # noqa: BLE001
            return False, f"model „{model}“ ne postoji; probao „{pick}“: {str(e)[:150]}"
        from .. import settings as S
        S.set_("models", {**(S.get("models") or {}), provider: pick})
        return True, f"OK — model „{model}“ je povučen, izabran „{pick}“ (zapamćeno)"


_SKIP = ("whisper", "guard", "tts", "embed", "moderation", "audio", "vision-preview", "distil")


def chat_models(names: list) -> list:
    """Only the models one can chat with (no speech, guard, embedding …), sorted."""
    out = [n.split("/", 1)[1] if n.startswith("models/") else n for n in names]
    return sorted({n for n in out if n and not any(k in n.lower() for k in _SKIP)})


def pick_model(names: list, wanted: str = "") -> str:
    """The closest chat model the server really offers: same family as `wanted`,
    preferring larger / "versatile" ones; never speech, guard or embedding models."""
    cand = [n.split("/", 1)[1] if n.startswith("models/") else n for n in names]
    cand = [n for n in cand if n and not any(k in n.lower() for k in _SKIP)]
    if not cand:
        return ""
    stem = (wanted or "").lower().split("-")[0]

    def score(n):
        low = n.lower()
        return ((stem and low.startswith(stem)) * 4 + ("versatile" in low) * 2 +
                ("70b" in low or "large" in low or "pro" in low) * 2 + ("instant" in low) * -1)
    return sorted(cand, key=lambda n: (-score(n), n))[0]


class _ModelOverrides(dict):
    """provider → model chosen by the operator (settings "models"), live."""

    def get(self, k, default=None):
        from .. import settings as S
        return (S.get("models") or {}).get(k) or dict.get(self, k) or default


_R: Optional[Router] = None


def router() -> Router:
    global _R
    if _R is None:
        _R = Router()
    return _R
