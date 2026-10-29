"""
An exponent system carried AS DATA — the real "open door" (plan F8, fix 2026-10-25).

A new QRH paper does not need new code: its exponent comparison system is
written into the method pack as text (validated by methods.expr) and this module
derives the method's boundary B* from it, exactly as for the built-in families:

    "system": {
      "defs":     [["h", "(1 + b + 3*ell)/2"], ["c", "2/(3*kappa)"], ...],   # in order
      "branches": [{"E": "<high-side exponent>", "delta": [lo, hi]}, ...],
      "x_grid":   [0.5],                       # where the max over x is taken
      "line":     "11/12 - ell/4",             # the low side: B as a function of ℓ
      "licence":  "2*B - 1",                   # κ licensed by B (fixed point)
      "b_range":  [0, 0.3],  "ell_range": [0, 0.6],
      "walls":    ["6*kappa*ell > 3/4", ...]   # admissibility, enforced as constraints
    }

Names: parameters b, ell, kappa; variables delta, x; B (from the line); and every
name defined earlier in "defs". Walls may use b, ell, kappa, B and defs that do
not depend on delta or x.

The boundary is the largest ℓ (smallest B) such that every wall holds and
V(b,ℓ,κ) = max over branches, x in x_grid, δ in the branch range of E ≤ 0,
maximised over b, with κ iterated to the licence fixed point. Numerics are
scipy-free (golden section + bisection), so this works in the lean package.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import expr as X
from .core import Optimum, _bisect, _gss_argmax

PARAMS = ["b", "ell", "kappa"]
VARS = ["delta", "x"]


class SystemError_(Exception):
    pass


class _Inline(ast.NodeTransformer):
    def __init__(self, defs: dict):
        self.defs = defs

    def visit_Name(self, node):
        if node.id in self.defs:
            return copy.deepcopy(self.defs[node.id])
        return node


@dataclass
class ExponentSystem:
    raw: dict
    branches: list = field(default_factory=list)       # [(fn, lo, hi)]
    walls: list = field(default_factory=list)          # [(text, fn)]
    x_grid: list = field(default_factory=lambda: [0.5])
    line: Callable = None
    inv_line: Callable = None
    licence: Callable = None
    b_range: tuple = (0.0, 0.3)
    ell_range: tuple = (0.0, 0.6)
    _sym_E: list = field(default_factory=list)         # inlined trees, for sympy

    # ------------------------------------------------------------------ #
    @classmethod
    def from_dict(cls, d: dict) -> "ExponentSystem":
        if not isinstance(d, dict):
            raise SystemError_("'system' mora biti objekat")
        allowed = set(PARAMS) | set(VARS) | {"B"}
        defs: dict[str, ast.AST] = {}
        dep_on_vars: set = set()
        for item in d.get("defs", []):
            if not (isinstance(item, (list, tuple)) and len(item) == 2):
                raise SystemError_("svaka definicija je par [ime, izraz]")
            name, text = item
            if not (isinstance(name, str) and name.isidentifier()) or name in allowed \
                    or name in X.FUNCS:
                raise SystemError_(f"nedozvoljeno ime definicije: {name!r}")
            tree = X.parse(text, allowed | set(defs))
            names_used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            if names_used & (set(VARS) | dep_on_vars):
                dep_on_vars.add(name)
            defs[name] = _Inline(defs).visit(copy.deepcopy(tree)).body
        names = allowed | set(defs)

        def inline(text: str, compare: bool = False) -> ast.Expression:
            t = X.parse(text, names, allow_compare=compare)
            return ast.fix_missing_locations(_Inline(defs).visit(copy.deepcopy(t)))

        line_t = inline(d.get("line", "11/12 - ell/4"))
        lic_t = inline(d.get("licence", "2*B - 1"))
        args = PARAMS + VARS + ["B"]
        sysm = cls(raw=d)
        sysm.line = X.compile_fn(line_t, ["ell"])
        sysm.licence = X.compile_fn(lic_t, ["B"])
        brs = d.get("branches")
        if not brs:
            if "E" not in d:
                raise SystemError_("sistem nema ni 'E' ni 'branches'")
            brs = [{"E": d["E"], "delta": d.get("delta", [1e-6, 5 / 6])}]
        for br in brs:
            lo, hi = (float(v) for v in br.get("delta", [1e-6, 5 / 6]))
            if not (0 <= lo < hi <= 1):
                raise SystemError_(f"opseg δ mora biti 0 ≤ lo < hi ≤ 1, a ne {lo, hi}")
            t = inline(br["E"])
            sysm._sym_E.append((t, lo, hi))
            sysm.branches.append((X.compile_fn(t, args), lo, hi))
        for w in d.get("walls", []):
            wt = X.parse(w, names, allow_compare=True)
            used = {n.id for n in ast.walk(wt) if isinstance(n, ast.Name)}
            if used & (set(VARS) | dep_on_vars):
                raise SystemError_(f"zid ne smije zavisiti od δ ili x: {w}")
            m = ast.fix_missing_locations(_Inline(defs).visit(X.wall_margin(wt)))
            sysm.walls.append((w, X.compile_fn(m, ["b", "ell", "kappa", "B"])))
        sysm.x_grid = [float(v) for v in d.get("x_grid", [0.5])]
        sysm.b_range = tuple(float(v) for v in d.get("b_range", [0.0, 0.3]))
        sysm.ell_range = tuple(float(v) for v in d.get("ell_range", [0.0, 0.6]))
        if not sysm.x_grid or not all(0 <= v <= 1 for v in sysm.x_grid):
            raise SystemError_("x_grid mora biti neprazan, vrijednosti u [0,1]")
        # self-check: the compiled functions evaluate to finite numbers somewhere sane
        B0 = sysm.line(1 / 6)
        sysm.V(0.1, 1 / 6, sysm.licence(B0))
        return sysm

    # ------------------------------------------------------------------ #
    def B_of(self, ell: float) -> float:
        return self.line(ell)

    def E(self, b, ell, kappa, delta, x, branch: int = 0) -> float:
        return self.branches[branch][0](b, ell, kappa, delta, x, self.line(ell))

    def V(self, b: float, ell: float, kappa: float) -> float:
        B = self.line(ell)
        best = -float("inf")
        for fn, lo, hi in self.branches:
            for x in self.x_grid:
                f = (lambda d, x=x: fn(b, ell, kappa, d, x, B))
                try:
                    ds = _gss_argmax(f, lo, hi)
                    v = max(f(ds), f(lo), f(hi))
                except (ZeroDivisionError, ValueError, OverflowError):
                    return float("inf")         # undefined there → not admissible
                best = max(best, v)
        return best

    def wall_margins(self, b, ell, kappa) -> dict:
        B = self.line(ell)
        out = {}
        for text, fn in self.walls:
            try:
                out[text] = fn(b, ell, kappa, B)
            except (ZeroDivisionError, ValueError, OverflowError):
                out[text] = -1.0
        return out

    def feasible(self, b, ell, kappa) -> bool:
        if any(m <= 0 for m in self.wall_margins(b, ell, kappa).values()):
            return False
        return self.V(b, ell, kappa) <= 0

    # ------------------------------------------------------------------ #
    def ell_star(self, b: float, kappa: float, steps: int = 240) -> Optional[float]:
        """Largest admissible ℓ for this b, κ (None if none)."""
        lo, hi = self.ell_range
        grid = [hi - (hi - lo) * i / steps for i in range(steps + 1)]
        # A feasible band can be narrower than the grid (Xu–Sang: between the
        # wall 6κℓ > 3/4 and the high side). Add every point where a wall
        # margin changes sign, nudged to both sides, as extra candidates.
        cands = set(grid)
        if self.walls:
            margins = [self.wall_margins(b, l, kappa) for l in grid]
            for i in range(len(grid) - 1):
                for w in margins[i]:
                    m1, m2 = margins[i][w], margins[i + 1][w]
                    if (m1 > 0) != (m2 > 0):
                        a, c = grid[i + 1], grid[i]          # a < c
                        fa = self.wall_margins(b, a, kappa)[w] > 0
                        for _ in range(60):
                            mid = (a + c) / 2
                            if (self.wall_margins(b, mid, kappa)[w] > 0) == fa:
                                a = mid
                            else:
                                c = mid
                        cands.update({a - 1e-12, a, c, c + 1e-12})
        order = sorted((l for l in cands if lo <= l <= hi), reverse=True)
        prev = None
        for l in order:
            if self.feasible(b, l, kappa):
                if prev is None:
                    return l
                a, c = l, prev
                for _ in range(60):
                    m = (a + c) / 2
                    if self.feasible(b, m, kappa):
                        a = m
                    else:
                        c = m
                    if c - a < 1e-14:
                        break
                return a
            prev = l
        return None

    def optimum(self, kfix: Optional[float] = None, iters: int = 8) -> Optimum:
        """The method boundary: smallest B the system admits (see module doc)."""
        b_lo, b_hi = self.b_range
        k = 0.75 if kfix is None else kfix
        best = None
        for _ in range(iters):
            def L(b):
                v = self.ell_star(b, k)
                return -1.0 if v is None else v
            grid = [b_lo + (b_hi - b_lo) * i / 20 for i in range(21)]
            vals = [L(b) for b in grid]
            i = max(range(len(grid)), key=lambda j: vals[j])
            if vals[i] < 0:
                raise SystemError_("sistem nema nijednu dopustivu tačku u zadatim opsezima")
            a = grid[max(i - 1, 0)]
            c = grid[min(i + 1, len(grid) - 1)]
            b = _gss_argmax(L, a, c, tol=1e-10)
            l = L(b)
            if l < 0 or l < vals[i]:
                b, l = grid[i], vals[i]
            B = self.line(l)
            best = Optimum(B, l, b, k)
            if kfix is not None:
                break
            k_new = self.licence(B)
            if abs(k_new - k) < 1e-13:
                break
            k = k_new
        return Optimum(best.B, best.l, best.b, k if kfix is None else kfix)

    # ------------------------------------------------------------------ #
    def sympy_E(self, branch: int = 0):
        """(E as sympy, symbols dict) — for exact work."""
        import sympy as sp
        syms = {n: sp.Symbol(n) for n in PARAMS + VARS + ["B"]}
        tree = self._sym_E[branch][0]
        return X.to_sympy(tree, syms), syms


def check_polynomial(poly_text: str, B_star: float, var: str = "B",
                     window: float = 2e-8) -> tuple[bool, str]:
    """
    Deterministic check that the claimed minimal polynomial really has the
    reproduced boundary as a root: a sign change of P within ±window of B*.
    Polynomials in another variable (e.g. Liu's ξ) need `var` and a mapped B*.
    """
    try:
        t = X.parse(poly_text, {var})
        P = X.compile_fn(t, [var])
        lo, hi = P(B_star - window), P(B_star + window)
    except (X.ExprError, ZeroDivisionError, OverflowError, ValueError) as e:
        return False, f"polinom se ne može izračunati: {e}"
    if lo == 0 or hi == 0 or (lo > 0) != (hi > 0):
        return True, f"P mijenja znak oko B*={B_star:.12f} (±{window:g})"
    return False, f"P ne mijenja znak oko B*={B_star:.12f}: P(−)={lo:.3e}, P(+)={hi:.3e}"
