"""
Egress policy — who we are allowed to talk to, and what we are allowed to say.

Default deny. A host not on this list cannot be reached, full stop, and the
attempt is journalled as a threat event. That single rule kills most of what
malicious scraped content could do (beaconing, exfil, pulling a second stage),
because the fetcher physically has nowhere to send it.

Two classes of host, and the distinction is load-bearing:
  CREDENTIALED  the four model APIs. These, and ONLY these, may receive an
                Authorization / x-api-key header.
  ANONYMOUS     the literature/data sources. A request to one of these is
                scanned for key material before it leaves; if a key appears in
                a URL, header or body, the request is blocked, not sanitized.
"""
from __future__ import annotations

from dataclasses import dataclass, field

CREDENTIALED = "credentialed"
ANONYMOUS = "anonymous"


@dataclass(frozen=True)
class HostRule:
    host: str                       # exact host or ".suffix" for subdomains
    klass: str
    why: str
    key_env: str = ""               # secret name allowed to be sent here
    max_rps: float = 1.0            # our own politeness cap
    tags: tuple = field(default_factory=tuple)


# --- model providers ------------------------------------------------------- #
MODEL_HOSTS = [
    HostRule("api.anthropic.com", CREDENTIALED, "Claude — matematičko rezonovanje",
             "ANTHROPIC_API_KEY", 2.0, ("llm", "claude")),
    HostRule("api.mistral.ai", CREDENTIALED, "Mistral — jeftina trijaža",
             "MISTRAL_API_KEY", 2.0, ("llm", "mistral")),
    HostRule("api.groq.com", CREDENTIALED, "Groq — brza/besplatna trijaža",
             "GROQ_API_KEY", 2.0, ("llm", "groq")),
    HostRule("generativelanguage.googleapis.com", CREDENTIALED,
             "Gemini — vizija + trijaža", "GEMINI_API_KEY", 2.0, ("llm", "gemini")),
    # round 3, item 9
    HostRule("api.openai.com", CREDENTIALED, "OpenAI", "OPENAI_API_KEY", 2.0,
             ("llm", "openai")),
    HostRule("api.deepseek.com", CREDENTIALED, "DeepSeek API", "DEEPSEEK_API_KEY", 2.0,
             ("llm", "deepseek")),
    HostRule("api.x.ai", CREDENTIALED, "xAI (Grok)", "XAI_API_KEY", 2.0, ("llm", "xai")),
    HostRule("openrouter.ai", CREDENTIALED, "OpenRouter", "OPENROUTER_API_KEY", 2.0,
             ("llm", "openrouter")),
    HostRule("api.together.xyz", CREDENTIALED, "Together AI", "TOGETHER_API_KEY", 2.0,
             ("llm", "together")),
    HostRule("api.fireworks.ai", CREDENTIALED, "Fireworks AI", "FIREWORKS_API_KEY", 2.0,
             ("llm", "fireworks")),
]

# --- literature / data sources (all keyless unless noted) ------------------- #
SOURCE_HOSTS = [
    HostRule("export.arxiv.org", ANONYMOUS, "arXiv API — apstrakti i metapodaci",
             "", 0.34, ("arxiv",)),                      # ~1 req / 3 s, njihovo pravilo
    HostRule("arxiv.org", ANONYMOUS, "arXiv — stranice radova", "", 0.34, ("arxiv",)),
    HostRule(".ar5iv.org", ANONYMOUS, "ar5iv — radovi kao HTML umjesto PDF-a",
             "", 0.5, ("arxiv", "fulltext")),
    HostRule("ar5iv.labs.arxiv.org", ANONYMOUS, "ar5iv (labs)", "", 0.5,
             ("arxiv", "fulltext")),
    HostRule("www.lmfdb.org", ANONYMOUS, "LMFDB — prave nule ζ i L-funkcija",
             "", 1.0, ("data", "zeros")),
    HostRule("lmfdb.org", ANONYMOUS, "LMFDB", "", 1.0, ("data", "zeros")),
    HostRule("oeis.org", ANONYMOUS, "OEIS — nizovi", "", 0.5, ("data",)),
    HostRule("api.openalex.org", ANONYMOUS, "OpenAlex — graf citata (mailto=)",
             "", 2.0, ("biblio",)),
    HostRule("api.crossref.org", ANONYMOUS, "Crossref — DOI metapodaci (polite pool)",
             "", 2.0, ("biblio",)),
    HostRule("api.semanticscholar.org", ANONYMOUS,
             "Semantic Scholar — opcioni besplatan ključ diže kvotu",
             "S2_API_KEY", 1.0, ("biblio",)),
    HostRule("en.wikipedia.org", ANONYMOUS, "Wikipedia — orijentacija, ne izvor",
             "", 2.0, ("ref",)),
    HostRule("api.zbmath.org", ANONYMOUS, "zbMATH Open — recenzije (otvoreni dio)",
             "", 1.0, ("biblio",)),
    HostRule("api.stackexchange.com", ANONYMOUS,
             "MathOverflow/MSE — opcioni besplatan ključ diže kvotu na 10k/dan",
             "STACKEXCHANGE_KEY", 1.0, ("qa",)),
    HostRule("www.numdam.org", ANONYMOUS, "Numdam — francuski arhiv", "", 0.5, ("archive",)),
    HostRule("numdam.org", ANONYMOUS, "Numdam", "", 0.5, ("archive",)),
    HostRule("www.dtc.umn.edu", ANONYMOUS, "Odlyzko — tabele nula ζ", "", 0.34,
             ("data", "zeros")),
    HostRule("www-users.cse.umn.edu", ANONYMOUS, "Odlyzko (stara adresa)", "", 0.34,
             ("data", "zeros")),
    HostRule("terrytao.wordpress.com", ANONYMOUS, "Tao — blog (de Bruijn–Newman itd.)",
             "", 0.5, ("blog",)),
]

ALL_RULES = MODEL_HOSTS + SOURCE_HOSTS
_BY_HOST = {r.host: r for r in ALL_RULES}


def declared_rules() -> list[HostRule]:
    """OpenAI-compatible endpoints the OPERATOR confirmed (declarations kind
    "endpoints"). A proposal alone opens nothing."""
    try:
        from ..shared_lib import declarations as DECL
        eps = DECL.current().get("endpoints") or {}
    except Exception:                                   # noqa: BLE001
        return []
    return [HostRule(e["host"].lower(), CREDENTIALED, f"deklarisano: {name}",
                     e["key_name"], 2.0, ("llm", "custom"))
            for name, e in eps.items() if e.get("host") and e.get("key_name")]


def rule_for(host: str):
    """Exact match, then '.suffix' subdomain match. Returns None = deny."""
    host = (host or "").lower().strip().rstrip(".")
    if host in _BY_HOST:
        return _BY_HOST[host]
    for r in declared_rules():
        if r.host == host:
            return r
    for r in ALL_RULES:
        if r.host.startswith(".") and (host.endswith(r.host) or host == r.host[1:]):
            return r
    return None


def is_allowed(host: str) -> bool:
    return rule_for(host) is not None


def is_credentialed(host: str) -> bool:
    r = rule_for(host)
    return bool(r and r.klass == CREDENTIALED)


def hosts_for_tag(tag: str) -> list[HostRule]:
    return [r for r in ALL_RULES if tag in r.tags]


def describe() -> list[dict]:
    """Table for the wizard's source screen (static + declared endpoints)."""
    return [{"host": r.host, "class": r.klass, "why": r.why,
             "key": r.key_env, "optional_key": bool(r.key_env) and r.klass == ANONYMOUS,
             "rps": r.max_rps, "tags": list(r.tags)}
            for r in ALL_RULES + declared_rules()]
