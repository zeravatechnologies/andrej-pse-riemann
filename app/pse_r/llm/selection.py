"""
Model policy (plan F3, decision 2026-10-25): ONE main AI, plus a skeptic that is
always a DIFFERENT model.

The old role→provider router is replaced by two choices the operator makes:

    MAIN      does every role (math, chat, vision, triage, curate, summarize…)
    SKEPTIC   does ONLY the skeptic role, and must be a different model

Independence is the whole point: a model grading its own output is a weak check;
a different model attacking it is a real one. The two may not be the same model.

A "model id" is either a cloud provider name ("claude", "gemini", "mistral",
"groq") or a local file as "gguf:<filename>". Defaults, when the operator has not
chosen: MAIN = the strongest available (Claude if its key is set), SKEPTIC = a
different available model, preferring a local GGUF (other vendor, free, offline).

Deterministic checks (reproduction test, provenance, gate, source tiers) stay
above every model and are never routed here. If no distinct skeptic is available
the skeptic is "unavailable" and only the deterministic checks attack a claim.
"""
from __future__ import annotations

from typing import Optional

from .. import settings as S
from ..guardian import secrets as SEC
from . import backend as B
from . import gguf as G

def _cloud() -> tuple:
    from . import providers as P
    return tuple(P.all_presets())


CLOUD = ("claude", "openai", "gemini", "mistral", "groq", "deepseek", "xai",
         "openrouter", "together", "fireworks")         # presets; + declared custom:…
MAIN_KEY = "ai_main"
SKEPTIC_KEY = "ai_skeptic"

# "Kad birati" — ✓ bolje kada… / ✗ slabije kada… (for the GUI chooser, F6).
GUIDANCE = {
    "claude": {"+": "najjači za matematiku i izvlačenje; plaćen",
               "-": "troši budžet; traži internet"},
    "gemini": {"+": "besplatan tier, vidi slike", "-": "slabiji na dugom dokazu"},
    "mistral": {"+": "besplatan tier, brz", "-": "bez slika; kraći kontekst"},
    "groq": {"+": "vrlo brz, besplatan — dobar za trijažu/skeptika",
             "-": "manji modeli; bez slika"},
    "gguf": {"+": "lokalno, offline, bez troška — idealan drugi glas (skeptik)",
             "-": "sporiji na CPU; troši RAM; slabiji od plaćenog oblaka"},
}


def _vendor(model_id: str) -> str:
    return "gguf" if model_id.startswith("gguf:") else model_id


def cloud_available() -> list[str]:
    from . import providers as P
    s = SEC.store()
    return [p for p, pr in P.all_presets().items() if s.has(pr.key_name)]


GGUF_PATHS_KEY = "gguf_paths"       # GGUF files OUTSIDE models/, used in place (no copy)


def gguf_paths() -> list[str]:
    return [p for p in (S.get(GGUF_PATHS_KEY) or []) if isinstance(p, str)]


def add_gguf_path(path: str) -> str:
    """Register a GGUF anywhere on disk (by path; admitted by sha256 like any
    other — undeclared + unpublished hash ⇒ refused until the operator declares
    it). Returns its model id."""
    from pathlib import Path
    p = Path(path).expanduser().resolve()
    if p.suffix.lower() != ".gguf" or not p.is_file():
        raise ValueError(f"nije .gguf fajl: {p}")
    cur = gguf_paths()
    if str(p) not in cur:
        S.set_(GGUF_PATHS_KEY, cur + [str(p)])
    return f"gguf:{p}"


def gguf_available() -> list[str]:
    if not G.have_llama():
        return []
    from pathlib import Path
    ids = [f"gguf:{m['name']}" for m in G.list_models()]
    ids += [f"gguf:{p}" for p in gguf_paths() if Path(p).is_file()]
    return ids


def candidates() -> list[dict]:
    """Every model the operator could pick right now, with guidance."""
    out = []
    from . import providers as P
    for p in cloud_available():
        pr = P.get(p)
        guide = {"+": pr.better, "-": pr.worse} if pr and pr.better else GUIDANCE.get(p, {})
        out.append({"id": p, "kind": "cloud", "label": pr.label if pr else p,
                    "guide": guide, "billing": P.billing_advice(p)["text"]})
    from .. import machine as M
    for gid in gguf_available():
        g = dict(GUIDANCE["gguf"])
        w = M.gguf_warning(gid)
        if w:
            g["-"] = g["-"] + " · " + w
        out.append({"id": gid, "kind": "gguf", "label": gid, "guide": g, "warning": w})
    return out


def _available_ids() -> list[str]:
    return cloud_available() + gguf_available()


def default_main() -> Optional[str]:
    av = _available_ids()
    for pref in ("claude", "openai", "gemini", "deepseek", "xai", "mistral", "groq"):
        if pref in av:
            return pref
    return av[0] if av else None


def default_skeptic(main: Optional[str]) -> Optional[str]:
    """A different model from `main`, preferring a local GGUF, then another vendor."""
    av = [m for m in _available_ids() if m != main]
    ggufs = [m for m in av if m.startswith("gguf:")]
    if ggufs:
        return ggufs[0]
    other = [m for m in av if _vendor(m) != _vendor(main or "")]
    return (other or av or [None])[0]


def get_main() -> Optional[str]:
    m = S.get(MAIN_KEY)
    if m == NO_AI:
        return None
    if m and not m.startswith("gguf:"):
        from ..guardian import killswitch as KS
        if KS.closed():
            return None                 # a cloud main is unreachable while the switch is off
    return m or default_main()


NO_SKEPTIC = "none"           # operator chose "no skeptic" (e.g. offline with one GGUF)
NO_AI = "none"                # main: "bez AI" (first-run choice, or the kill switch)


def get_skeptic() -> Optional[str]:
    chosen = S.get(SKEPTIC_KEY)
    if chosen == NO_SKEPTIC:
        return None
    main = get_main()
    if chosen and chosen != main:
        return chosen
    return default_skeptic(main)


def set_main(model_id: str) -> None:
    if model_id not in _available_ids():
        raise ValueError(f"model '{model_id}' nije dostupan")
    if model_id == S.get(SKEPTIC_KEY):
        raise ValueError("glavni i skeptik ne smiju biti isti model")
    S.set_(MAIN_KEY, model_id)


def set_skeptic(model_id: str) -> None:
    if model_id not in _available_ids():
        raise ValueError(f"model '{model_id}' nije dostupan")
    if model_id == get_main():
        raise ValueError("skeptik mora biti drugi model od glavnog")
    S.set_(SKEPTIC_KEY, model_id)


def skeptic_available() -> bool:
    sk, main = get_skeptic(), get_main()
    return bool(sk) and sk != main


def backend_for(model_id: str) -> B.Backend:
    """A ready Backend for a model id. Does not load a GGUF until it is called."""
    if model_id.startswith("gguf:"):
        name = model_id.split(":", 1)[1]
        from pathlib import Path
        if Path(name).is_absolute():
            return G.GGUFBackend(name)                  # used in place, never copied
        from .. import config
        return G.GGUFBackend(str(config.DIR_MODELS / name))
    return B.make(model_id)


class B_NoModel(Exception):
    pass


# --------------------------------------------------------------------------- #
# No internet (plan §1): the app ASKS which local GGUF to use — it never decides.
# --------------------------------------------------------------------------- #
class _Hosts:
    def get(self, m, default=None):
        from . import providers as P
        pr = P.get(m)
        return pr.host if pr else default


_HOSTS = _Hosts()
PREV_MAIN_KEY = "ai_main_before_offline"
PREV_SKEPTIC_KEY = "ai_skeptic_before_offline"


def main_reachable(timeout: float = 5.0) -> bool:
    """Can the selected main model be reached? A GGUF always can. The probe goes
    through the guardian egress (the only network path), never a raw socket."""
    m = get_main()
    if not m or m.startswith("gguf:"):
        return True
    host = _HOSTS.get(m)
    if not host:
        return True
    from ..guardian.egress import EgressBlocked, egress
    try:
        egress().probe(host, timeout=timeout)       # TLS + pin only, never an HTTP page
        return True
    except EgressBlocked:
        return False
    except Exception:                                   # noqa: BLE001
        return False


def offline_options() -> dict:
    """What to offer the operator when the main model is unreachable."""
    ggufs = gguf_available()
    return {"main_was": get_main(), "ggufs": ggufs,
            "suggest_main": ggufs[0] if ggufs else None,
            "suggest_skeptic": ggufs[1] if len(ggufs) > 1 else None,
            "skeptic_possible": len(ggufs) > 1}


def go_offline(main: str, skeptic: Optional[str]) -> None:
    """Apply the operator's offline choice, remembering the previous main."""
    prev = get_main()
    if prev and not prev.startswith("gguf:"):
        S.set_(PREV_MAIN_KEY, prev)
    S.set_(SKEPTIC_KEY, "")             # free the slot: main may be today's skeptic
    set_main(main)
    if skeptic and skeptic != main:
        set_skeptic(skeptic)
    else:
        S.set_(SKEPTIC_KEY, NO_SKEPTIC)  # skeptic "nedostupan": deterministic checks only


def offer_restore() -> Optional[str]:
    """The cloud main that was active before going offline, if any."""
    return S.get(PREV_MAIN_KEY) or None


def restore_online() -> None:
    prev = offer_restore()
    if prev:
        S.set_(SKEPTIC_KEY, "")
        S.set_(MAIN_KEY, prev)
        S.set_(PREV_MAIN_KEY, "")
