"""
Every action declares whether it can be undone (round 3, item 5; Svarog S4).

What the guardians, the keepers and the Doctor may do ON THEIR OWN depends on
one question only: can it be undone? An action runs automatically only if it is
declared reversible AND says how it is undone. Anything else — and anything
that was never declared at all — is treated as IRREVERSIBLE and goes to the
operator through the human queue ("Čeka tvoju odluku").

    declare("ssh.block-ip-24h", reversible=True,
            undo="blokada se sama skida posle 24 h (ili operater ranije)")
    spec("nešto-nepoznato").reversible   → False
    may_auto("fisija")                    → False

The registry is code, not configuration: a model can never declare an action,
and a declaration cannot be changed at run time without a journal entry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from . import journal as J


@dataclass(frozen=True)
class ActionSpec:
    name: str
    reversible: bool
    undo: str = ""              # how it is undone (required for reversible)
    description: str = ""
    declared: bool = True

    @property
    def auto(self) -> bool:
        """May run without asking the operator."""
        return self.declared and self.reversible and bool(self.undo)

    @property
    def tier(self) -> int:
        return 1 if self.auto else 2


_REGISTRY: dict[str, ActionSpec] = {}


class NotAllowed(Exception):
    """An irreversible (or undeclared) action was about to run automatically."""


def declare(name: str, reversible: bool, undo: str = "", description: str = "") -> ActionSpec:
    if reversible and not undo:
        raise ValueError(f"povratna akcija '{name}' mora reći kako se poništava")
    prev = _REGISTRY.get(name)
    s = ActionSpec(name, reversible, undo, description)
    if prev is not None and prev != s:
        J.log(J.SYSTEM, "actions", {"event": "redeclared", "action": name,
                                    "reversible": reversible}, subject=name,
              verdict="redeclared")
    _REGISTRY[name] = s
    return s


def spec(name: str) -> ActionSpec:
    """The declaration — or, if there is none, an irreversible placeholder."""
    return _REGISTRY.get(name) or ActionSpec(name, reversible=False, declared=False,
                                             description="nedeklarisano → nepovratno")


def may_auto(name: str) -> bool:
    return spec(name).auto


def tier(name: str) -> int:
    return spec(name).tier


def require_auto(name: str) -> ActionSpec:
    """Call before doing something without the operator. Raises if not allowed."""
    s = spec(name)
    if not s.auto:
        why = "nije deklarisana" if not s.declared else "nepovratna"
        J.log(J.SYSTEM, "actions", {"event": "auto_refused", "action": name,
                                    "why": why}, subject=name, verdict="refused")
        raise NotAllowed(f"akcija '{name}' je {why} — ide operateru")
    return s


def all_specs() -> list[ActionSpec]:
    return sorted(_REGISTRY.values(), key=lambda s: s.name)


def find(name: str) -> Optional[ActionSpec]:
    return _REGISTRY.get(name)


# --------------------------------------------------------------------------- #
# the declarations (one place, reviewed by a human)
# --------------------------------------------------------------------------- #
# healing — declared before Faza 6d; kept so that old journal records and replays
# still resolve (the PSE Doctor's own measures are declared in pse_registry.py)
declare("contain", True, "operater pušta agenta iz karantina (heal-release)",
        "zamrzni upis i pozive modela zaraženog agenta")
declare("boundary-reset", True, "granica agenta se vraća na prethodnu iz dnevnika",
        "vrati agentu početnu granicu misije")
declare("vraćanje-fajlova-iz-pečata", True,
        "izmijenjena verzija je sačuvana u forensic/ i može se vratiti",
        "vrati finalni izvještaj iz pečata čuvara")
declare("označi-REFUTED/SUSPECT", True, "oznaka se skida; ništa nije obrisano",
        "označi upise zaraženog agenta")
declare("fisija", False, description="zaštitna fisija: B jedinica umire posle forenzike")
declare("zamjena", False, description="jedinica se gasi i zamjenjuje svježom")
declare("ponovni-prijem-modela", False, description="model se oslobađa i ponovo prima")
declare("vraćanje-fajlova-operatera", False,
        description="prepisivanje operaterovih fajlova")
declare("smrt", False, description="harvest-and-terminate")
# limiters (llm/limits.py, shared_lib/runtime.py)
declare("model.unload", True, "model se ponovo učitava pri sljedećem pozivu",
        "oslobodi lokalni model iz RAM-a")
declare("guard.pause", True, "operater odobrava nastavak (guard-pause)",
        "pauziraj sve pozive modelu („→ ∞“)")
# keepers (shared_lib/reports.py)
declare("report.seal", True, "pečat se može ponovo napraviti; original ostaje",
        "zapečati finalni izvještaj")
