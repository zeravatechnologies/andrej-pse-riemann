"""
First-run setup (round 3, item 8) — the logic, without any window.

The GUI (gui/setup.py) only collects choices; everything that changes state
happens here, in one place, so it can be tested and so a later "change the
setup" uses the very same path:

  1. operator          the name (no password — operator = name only)
  2. main AI           a cloud preset (key), a declared OpenAI-compatible
                       address, a GGUF from anywhere (by path + hash, no copy),
                       or "no AI for now"
  3. skeptic           a DIFFERENT model (or none)
  4. declarations      every chosen model is declared: a GGUF's sha256 is
                       compared with the published hash; a new cloud address is
                       a proposal — the operator confirms both right here
  5. "no AI"           what works and what does not (NO_AI_TEXT)
  6. guardian at login yes / no
Everything can be changed later (palette → "Podešavanje").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import settings as S

DONE_KEY = "setup_done_v2"
AUTOSTART_KEY = "guardian_autostart"

NO_AI_TEXT = {
    "radi": ["Lab i svi numerički eksperimenti", "kapija i nivoi izvora",
             "istraživač metoda + vrata (test reprodukcije)", "misije, grafovi, kalkulacije",
             "čuvari izvještaja, tri zla, liječenje (deterministički dio)",
             "SSH čuvar i zaštita domaćina", "SHARED_LIB upiti (bez prirodnog jezika)",
             "praćenje arXiva (bez izvlačenja metoda)"],
    "ne radi": ["chat i glas SHARED_LIB-a (proza)", "izvlačenje metode iz rada",
                "skeptik (ostaju samo determinističke provjere)",
                "trijaža literature modelom", "čitanje table (slike)", "ideje / inspiracije"],
}


@dataclass
class ModelChoice:
    kind: str                         # cloud | custom | gguf | none
    provider: str = ""                # cloud preset id
    key: str = ""                     # API key (cloud / custom), never logged
    model: str = ""                   # model name (cloud / custom)
    custom_name: str = ""
    custom_url: str = ""
    gguf_path: str = ""


@dataclass
class SetupChoices:
    operator: str
    main: ModelChoice
    skeptic: Optional[ModelChoice] = None
    confirm_declarations: bool = True
    guardian_autostart: bool = False
    contact_email: str = ""
    notes: list = field(default_factory=list)


def gguf_check(path: str) -> dict:
    """sha256 of a GGUF and whether it matches a PUBLISHED hash."""
    from .llm import gguf as G
    p = Path(path).expanduser().resolve()
    sha = G.sha256_of(p)
    pub = G.PUBLISHED.get(p.name)
    return {"path": str(p), "sha256": sha,
            "published": bool(pub and pub["sha256"] == sha),
            "source": pub["source"] if pub else "",
            "note": (f"odgovara objavljenom hash-u ({pub['source']})"
                     if pub and pub["sha256"] == sha else
                     "NEMA objavljenog hash-a za ovaj fajl — deklarišeš ga na svoju odgovornost")}


def _materialise(ch: ModelChoice, confirm: bool, notes: list) -> Optional[str]:
    """Turn one choice into a model id, storing keys and declarations."""
    from .guardian import secrets as SEC
    from .llm import providers as P
    from .shared_lib import declarations as DECL
    from .shared_lib.store import store
    if ch.kind == "none":
        return None
    if ch.kind == "cloud":
        pr = P.PRESETS.get(ch.provider)
        if pr is None:
            raise ValueError(f"nepoznat provajder '{ch.provider}'")
        if ch.key:
            SEC.store().set(pr.key_name, ch.key.strip())
        if not SEC.store().has(pr.key_name):
            raise ValueError(f"{pr.label}: nema ključa")
        if ch.model and ch.model != pr.default_model:
            models = dict(S.get("models") or {})
            models[pr.provider] = ch.model
            S.set_("models", models)
        notes.append(f"{pr.label}: ključ sačuvan (secrets.json, 0600)")
        return pr.provider
    if ch.kind == "custom":
        pid = DECL.propose_endpoint(ch.custom_name, ch.custom_url, ch.model,
                                    proposer="setup")
        name = store().get(pid)["payload"]["changes"]["endpoints"]
        (ep_name, ep), = name.items()
        if ch.key:
            SEC.store().set(ep["key_name"], ch.key.strip())
        if not confirm:
            notes.append(f"adresa {ch.custom_url} čeka potvrdu u „Čeka tvoju odluku“ — "
                         "dok je ne potvrdiš, nije dostupna (izaberi je poslije u Modeli)")
            return None
        store().decide(pid, True, "prvo podešavanje: operater potvrdio adresu")
        return P.CUSTOM_PREFIX + ep_name
    if ch.kind == "gguf":
        from .llm import gguf as G
        from .llm import selection as SEL
        chk = gguf_check(ch.gguf_path)
        mid = SEL.add_gguf_path(chk["path"])
        if DECL.model_hash(chk["path"]) != chk["sha256"]:
            pid = G.propose_declaration(chk["path"], chk["sha256"], chk["note"])
            if pid and confirm:
                store().decide(pid, True, "prvo podešavanje: " + chk["note"])
            elif pid:
                notes.append(f"deklaracija {Path(chk['path']).name} čeka potvrdu")
        notes.append(f"GGUF {Path(chk['path']).name}: {chk['note']}")
        return mid
    raise ValueError(f"nepoznata vrsta izbora '{ch.kind}'")


def apply(c: SetupChoices) -> dict:
    """Apply every first-run choice. Returns {"main", "skeptic", "notes"}."""
    from .guardian import secrets as SEC
    from .llm import selection as SEL
    from .shared_lib import declarations as DECL
    from .shared_lib import operator as OP
    OP.set_operator(c.operator)                     # 1 (validated; raises on bad name)
    DECL.install_hooks()
    notes = list(c.notes)
    main = _materialise(c.main, c.confirm_declarations, notes)      # 2 + 4
    S.set_(SEL.SKEPTIC_KEY, "")
    if main is None:
        S.set_(SEL.MAIN_KEY, SEL.NO_AI)
        notes.append("bez AI za sada — radi: " + ", ".join(NO_AI_TEXT["radi"][:3]) + " …")
    else:
        S.set_(SEL.MAIN_KEY, main)
    sk = None
    if c.skeptic is not None and main is not None:                  # 3
        sk = _materialise(c.skeptic, c.confirm_declarations, notes)
        if sk and sk == main:
            raise ValueError("skeptik mora biti drugi model od glavnog")
    S.set_(SEL.SKEPTIC_KEY, sk or SEL.NO_SKEPTIC)
    S.set_(AUTOSTART_KEY, bool(c.guardian_autostart))                # 6
    try:
        from . import autostart as AS
        notes.append("čuvar pri prijavi: " + AS.apply_setting(bool(c.guardian_autostart)))
    except OSError as e:
        notes.append(f"čuvar pri prijavi: nije podešeno ({e})")
    if c.contact_email.strip():
        SEC.store().set("CONTACT_EMAIL", c.contact_email.strip())
    S.set_(DONE_KEY, True)
    SEC.store().set("_WIZARD_DONE", "1")            # the round-2 wizard flag too
    from .core import journal as J
    J.log(J.SYSTEM, c.operator, {"event": "setup_applied", "main": main, "skeptic": sk,
                                 "guardian_autostart": bool(c.guardian_autostart)},
          verdict="applied")
    return {"main": main, "skeptic": sk, "notes": notes}


def needed() -> bool:
    return not S.get(DONE_KEY)
