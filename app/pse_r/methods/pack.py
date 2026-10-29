"""
The method pack and its mandatory reproduction test (plan F8).

A method pack is one self-contained file describing a method well enough that the
app can re-derive its headline number on its own:

    {
      "name": "liu",
      "family": "liu",                 # which exponent family (liu | xs | line)
      "source": "arxiv:2610.12234",    # resolvable reference
      "claimed_B": 0.874957019420,     # the number the paper states
      "dlo": 1e-6,                     # admissible lower edge of δ
      "tol": 1e-7,                     # how close our pipeline must land
      "exact_poly": "1188*xi**3 - ...", # optional, for the record
      "note": "...", "tags": ["qrh","liu"]
    }

The reproduction test is deterministic and stands ABOVE any model: our explorer
computes B* from the recipe and the pack is reproduced only if |B* − claimed_B|
≤ tol. A pack whose recipe does not reproduce the paper's number is refused at
the door, no matter who proposed it. This is the whole point of the "open door":
new results enter as data to be re-derived, not as assertions to be trusted.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import core as C
from .registry import MethodSpec

_FAMILIES = {"liu", "xs", "line"}
FAMILY_AGREEMENT_TOL = 1e-9       # data system vs built-in family, when both are given


class PackError(Exception):
    pass


def default_packs_dir() -> Optional[Path]:
    """
    Where the extracted method packs live. In a checkout that is the research
    folder; in an installed package it is bundled beside the code (the build
    copies it there). Returns the first that exists, or None.
    """
    import sys
    from .. import config
    cands = [config.PROJECT_ROOT / "research" / "qrh-2026-10" / "method-packs",
             config.APP_ROOT / "method-packs",
             config.APP_DIR / "method-packs"]
    meipass = getattr(sys, "_MEIPASS", None)            # PyInstaller onedir/onefile
    if meipass:
        cands.insert(0, Path(meipass) / "method-packs")
    for d in cands:
        if d.is_dir():
            return d
    return None


RESULT_KINDS = {"poluravan", "gustina", "udio-na-pravoj"}


@dataclass
class MethodPack:
    name: str
    family: str
    source: str
    claimed_B: float
    dlo: float = 1 / 8
    ell: float = 0.0                  # 'line' family: the point ℓ
    tol: float = 1e-7
    exact_poly: str = ""
    note: str = ""
    tags: list = field(default_factory=list)
    system: Optional[dict] = None     # the exponent system AS DATA (methods.system)
    # round 3, item 27: what KIND of result, for which family, under which assumptions
    result_kind: str = "poluravan"    # poluravan | gustina | udio-na-pravoj
    degree: int = 1                   # degree d of the L-function family (1 = Dirichlet/Hecke)
    assumptions: list = field(default_factory=list)   # e.g. ["funkcionalnost do GL(3)", "RH"]
    conditional: bool = False         # must be True when assumptions are not empty

    # -- parsing -------------------------------------------------------------- #
    @classmethod
    def from_dict(cls, d: dict) -> "MethodPack":
        if not isinstance(d, dict):
            raise PackError("paket nije objekat")
        if not d.get("family"):
            d = {k: v for k, v in d.items() if k != "family"}
        missing = [k for k in ("name", "source", "claimed_B") if k not in d]
        if missing:
            raise PackError(f"paket nema obavezna polja: {missing}")
        if "family" not in d and "system" not in d:
            raise PackError("paket mora nositi 'system' (sistem eksponenata kao podatak) "
                            "ili 'family' (ugrađena familija)")
        if "system" in d:
            from .system import ExponentSystem, SystemError_
            from .expr import ExprError
            try:
                ExponentSystem.from_dict(d["system"])
            except (SystemError_, ExprError, KeyError, TypeError, ValueError) as e:
                raise PackError(f"sistem eksponenata nije ispravan: {e}") from e
        if "family" in d and d["family"] not in _FAMILIES:
            raise PackError(f"nepoznata familija '{d['family']}' (dozvoljeno: "
                            f"{sorted(_FAMILIES)})")
        try:
            claimed = float(d["claimed_B"])
        except (TypeError, ValueError):
            raise PackError(f"claimed_B nije broj: {d['claimed_B']!r}")
        if not (0.0 < claimed < 1.0):
            raise PackError(f"claimed_B van (0,1): {claimed}")
        kind = str(d.get("result_kind", "poluravan"))
        if kind not in RESULT_KINDS:
            raise PackError(f"nepoznata vrsta rezultata '{kind}' (dozvoljeno: {sorted(RESULT_KINDS)})")
        assumptions = [str(a) for a in d.get("assumptions", [])]
        if assumptions and not d.get("conditional", False):
            # the gate rule (item 27): an unconditional claim may not rest on an
            # unproven assumption — say "conditional": true, as "pod RH" elsewhere
            raise PackError("paket se oslanja na pretpostavke " + str(assumptions) +
                            " ali nije označen kao uslovan (\"conditional\": true)")
        return cls(
            name=str(d["name"]).strip(),
            family=str(d.get("family", "")),
            source=str(d["source"]).strip(),
            claimed_B=claimed,
            dlo=float(d.get("dlo", 1 / 8)),
            ell=float(d.get("ell", 0.0)),
            tol=float(d.get("tol", 1e-7)),
            exact_poly=str(d.get("exact_poly", "")),
            note=str(d.get("note", "")),
            tags=list(d.get("tags", [])),
            system=d.get("system"),
            result_kind=kind,
            degree=int(d.get("degree", 1)),
            assumptions=assumptions,
            conditional=bool(d.get("conditional", False)),
        )

    @classmethod
    def from_file(cls, path: Path) -> "MethodPack":
        try:
            raw = Path(path).read_text(encoding="utf-8")
        except OSError as e:
            raise PackError(f"ne mogu da pročitam paket: {e}") from e
        try:
            return cls.from_dict(json.loads(raw))
        except json.JSONDecodeError as e:
            raise PackError(f"paket nije ispravan JSON: {e}") from e

    def to_dict(self) -> dict:
        return {"name": self.name, **({"family": self.family} if self.family else {}),
                "source": self.source,
                "claimed_B": self.claimed_B, "dlo": self.dlo, "ell": self.ell,
                "tol": self.tol, "exact_poly": self.exact_poly, "note": self.note,
                "tags": self.tags, **({"system": self.system} if self.system else {}),
                "result_kind": self.result_kind, "degree": self.degree,
                "assumptions": self.assumptions, "conditional": self.conditional}

    def spec(self) -> MethodSpec:
        return MethodSpec(self.name, self.family, self.source, self.claimed_B,
                          dlo=self.dlo, ell=self.ell, exact_poly=self.exact_poly,
                          note=self.note, tags=list(self.tags), system=self.system)


def reproduce(pack: MethodPack, tol: Optional[float] = None,
              check_poly: bool = False) -> dict:
    """
    Run the deterministic reproduction test. Returns a dict with:
      ok          |computed_B − claimed_B| ≤ tol
      computed_B  what our pipeline derives
      claimed_B   what the pack asserts
      error       the absolute difference
      poly_ok     None, or whether the exact minimal polynomial agrees too
      reading     a one-line human reading
    Never raises for a numeric mismatch — that is a verdict, not an error.
    """
    tol = pack.tol if tol is None else tol
    spec = pack.spec()
    opt = spec.optimum()
    err = abs(opt.B - pack.claimed_B)
    ok = err <= tol
    notes = []

    # When a pack carries BOTH its data system and a built-in family, the two
    # must agree — that is how a data system is checked against validated code.
    agree = None
    if pack.system and pack.family in ("liu", "xs"):
        ref = (C.optimum(C.E_liu, pack.dlo) if pack.family == "liu"
               else C.optimum(C.E_xs, pack.dlo))
        agree = abs(ref.B - opt.B) <= FAMILY_AGREEMENT_TOL
        if not agree:
            ok = False
            notes.append(f"sistem kao podatak ({opt.B:.12f}) se ne slaže sa ugrađenom "
                         f"familijom '{pack.family}' ({ref.B:.12f})")

    # A claimed minimal polynomial is CHECKED, not recorded: P must change sign at
    # the reproduced boundary. A wrong polynomial refuses the pack.
    poly_ok = None
    if check_poly and pack.exact_poly.strip():
        from .system import check_polynomial
        if "xi" in pack.exact_poly:
            notes.append("polinom u ξ (stari zapis) — nije provjeren; zapiši ga u B")
        else:
            poly_ok, why = check_polynomial(pack.exact_poly, opt.B)
        if poly_ok is False:
            ok = False
            notes.append("tvrđeni polinom: " + why)

    walls = (C.broken_walls(opt.B, opt.l, opt.b, opt.k) if not pack.system
             else [w for w, m in spec.system_obj().wall_margins(opt.b, opt.l, opt.k).items()
                   if m <= 0])
    if err <= tol:
        reading = (f"reprodukovano: naš pipeline daje B*={opt.B:.12f}, rad tvrdi "
                   f"{pack.claimed_B:.12f} (razlika {err:.2e} ≤ tol {tol:.0e}).")
    else:
        reading = (f"NIJE reprodukovano: naš pipeline daje B*={opt.B:.12f}, rad "
                   f"tvrdi {pack.claimed_B:.12f} (razlika {err:.2e} > tol {tol:.0e}).")
    if notes:
        reading += " " + " · ".join(notes)
    if not ok and err <= tol:
        reading = "ODBIJENO uprkos broju — " + reading
    return {"ok": ok, "computed_B": opt.B, "claimed_B": pack.claimed_B,
            "error": err, "poly_ok": poly_ok, "broken_walls": walls,
            "family_agrees": agree, "notes": notes,
            "optimum": {"B": opt.B, "l": opt.l, "b": opt.b, "k": opt.k},
            "reading": reading}
