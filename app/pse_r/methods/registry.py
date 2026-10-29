"""
The method registry — the known QRH methods as data.

A MethodSpec is the minimal description the explorer needs to re-derive a
method's boundary B* from its exponent family. It is deliberately small and
declarative: the family selects which E to use, `dlo` is the admissible lower
edge of δ for that family, `claimed_B` is the number the source paper states,
and `source` is a resolvable reference (same grammar as a card source).

The three built-ins are the spine of the research note:
    line    the common line B(ℓ) = 11/12 − ℓ/4 the methods all sit on
    liu     Liu, arXiv 2610.12234 — B* = 0.874957019420 (cubic)
    xs      Xu–Sang, arXiv 2610.15291 — B* = 0.874886647040 (quartic)

11/12 is the ℓ=0 end of the line; 7/8 is ℓ=1/6. New methods arrive as method
packs through the door (pack.py); accepted ones are appended here at runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import core as C


@dataclass
class MethodSpec:
    name: str
    family: str                       # "liu" | "xs" | "line"
    source: str                       # resolvable reference (arxiv:… / doi:… / book:…)
    claimed_B: float                  # the number the paper states
    dlo: float = 1 / 8                # admissible lower edge of δ
    ell: float = 0.0                  # for the 'line' family: the point ℓ (11/12 is ℓ=0, 7/8 is ℓ=1/6)
    exact_poly: str = ""              # optional: claimed minimal polynomial of B, as text
    note: str = ""
    tags: list = field(default_factory=list)
    system: Optional[dict] = None      # exponent system as data (preferred over family)
    _sys: object = field(default=None, repr=False, compare=False)
    _opt: object = field(default=None, repr=False, compare=False)

    def system_obj(self):
        if self.system is None:
            return None
        if self._sys is None:
            from .system import ExponentSystem
            self._sys = ExponentSystem.from_dict(self.system)
        return self._sys

    def optimum(self) -> C.Optimum:
        if self._opt is not None:
            return self._opt
        self._opt = self._compute()
        return self._opt

    def _compute(self) -> C.Optimum:
        if self.system is not None:
            return self.system_obj().optimum()
        if self.family == "liu":
            return C.optimum(C.E_liu, self.dlo)
        if self.family == "xs":
            return C.optimum(C.E_xs, self.dlo)
        if self.family == "line":
            # the line is not optimised; a 'line' method is a POINT on it, B(ℓ).
            return C.Optimum(C.Bof(self.ell), self.ell, 0.0, 2 * C.Bof(self.ell) - 1)
        raise ValueError(f"nepoznata familija '{self.family}'")


KNOWN: list[MethodSpec] = [
    MethodSpec("line", "line", "book:OpenAI 2026, §7/8-11/12", 11 / 12,
               note="zajednička prava B(ℓ)=11/12−ℓ/4; 11/12 je ℓ=0, 7/8 je ℓ=1/6"),
    MethodSpec("liu", "liu", "arxiv:2610.12234", 0.874957019420, dlo=1e-6,
               exact_poly="1188*xi**3 - 2160*xi**2 + 171*xi + 190  (B=(18xi+7)/(18xi+9))",
               note="korijen kubne; tri ravni L0, L_K, H_xi se sijeku u jednoj tački",
               tags=["qrh", "liu"]),
    MethodSpec("xs", "xs", "arxiv:2610.15291", 0.874886647040, dlo=1 / 8,
               exact_poly="133488*B**4 - 376596*B**3 + 384534*B**2 - 167541*B + 26231",
               note="optimum sistema; objavljeni 0.8748867 je ~5.3e-8 iznad optimuma",
               tags=["qrh", "xu-sang"]),
]

_BY_NAME = {m.name: m for m in KNOWN}


def by_name(name: str) -> Optional[MethodSpec]:
    return _BY_NAME.get(name)


def register(spec: MethodSpec) -> None:
    """Append an accepted method (called only by the door, after human approval)."""
    if spec.name in _BY_NAME:
        raise ValueError(f"metoda '{spec.name}' već postoji")
    KNOWN.append(spec)
    _BY_NAME[spec.name] = spec
