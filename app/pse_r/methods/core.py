"""
The exponent math, ported verbatim from the validated research pipeline
(research/qrh-2026-10/scripts: sys_.py, step23.py, pipeline.py, walls_ladder.py)
and checked against its recorded outputs:

    Liu optimum   B* = 0.874957019420   (root of 1188ξ³−2160ξ²+171ξ+190, mapped to B)
    Xu–Sang opt   B* = 0.874886647040   (root of 133488B⁴−376596B³+384534B²−167541B+26231)
    transform     E_XS = E_Liu + T, agreement 2·10⁻¹⁶ on random points
    walls         geometry ladder bottoms out at ≈ 5/6 (structural)

Numerics here are deliberately scipy-free (golden-section maximisation and
bisection), so the method explorer works in the lean package too. sympy is used
only for the exact minimal polynomial, which the base package carries.

Geometry on the common line B(ℓ) = 11/12 − ℓ/4, licence κ = 2B − 1:
    h  = (1 + b + 3ℓ)/2        l_x = (1 − b − ℓ)/2        l_y = (1 + b − ℓ)/2
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

_SQRT5 = 5 ** 0.5
_GR = (_SQRT5 - 1) / 2            # golden ratio conjugate


# --------------------------------------------------------------------------- #
# exponent families (numeric)
# --------------------------------------------------------------------------- #
def geom(b: float, l: float) -> dict:
    return {"lx": (1 - b - l) / 2, "ly": (1 + b - l) / 2, "h": (1 + b + 3 * l) / 2}


def R(kappa: float, d: float, x: float) -> float:
    """Row-counting recovery factor (Liu form; Xu–Sang's 2c with c=1/(3κ) is the same)."""
    c = 2 / (3 * kappa)
    D = 3 - (1 + c) * x
    P = (2 - c * x) * (1 - x)
    J = (5 / 6 - d) * D + d * P
    return 1 - d + (5 / 6 - d) * d * P / (2 * J)


def E_liu(b: float, l: float, k: float, d: float, x: float) -> float:
    g = geom(b, l)
    return -0.25 + b / 6 + 5 * l / 4 + (0.5 + l) * d + l * x * d - g["h"] * (1 - R(k, d, x))


def E_xs(b: float, l: float, k: float, d: float, x: float, w: float = 0.25) -> float:
    g = geom(b, l)
    c = 1 / (3 * k)
    return (-0.25 + b / 6 + 5 * l / 4 + d / 2
            + d * x * (l + c * (g["h"] / 4 - g["ly"] / 2))
            - g["h"] * (1 - w) * (1 - R(k, d, x)))


def Bof(l: float) -> float:
    return 11 / 12 - l / 4


def lof(B: float) -> float:
    return 4 * (11 / 12 - B)


# --------------------------------------------------------------------------- #
# scipy-free optimisation
# --------------------------------------------------------------------------- #
def _gss_argmax(f: Callable[[float], float], a: float, b: float,
                tol: float = 1e-12, it: int = 200) -> float:
    c = b - _GR * (b - a)
    d = a + _GR * (b - a)
    fc, fd = f(c), f(d)
    for _ in range(it):
        if b - a < tol:
            break
        if fc < fd:
            a, c, fc = c, d, fd
            d = a + _GR * (b - a)
            fd = f(d)
        else:
            b, d, fd = d, c, fc
            c = b - _GR * (b - a)
            fc = f(c)
    return (a + b) / 2


def _bisect(f: Callable[[float], float], a: float, b: float,
            tol: float = 1e-13, it: int = 200) -> float:
    fa = f(a)
    for _ in range(it):
        m = (a + b) / 2
        fm = f(m)
        if (fm > 0) == (fa > 0):
            a, fa = m, fm
        else:
            b = m
        if b - a < tol:
            break
    return (a + b) / 2


def vmax(Ef: Callable, b: float, l: float, k: float, dlo: float,
         x: float = 0.5, dhi: float = 5 / 6) -> float:
    """max over δ of E at the (validated) critical x = 1/2."""
    dstar = _gss_argmax(lambda d: Ef(b, l, k, d, x), dlo, dhi)
    return Ef(b, l, k, dstar, x)


@dataclass
class Optimum:
    B: float
    l: float
    b: float
    k: float
    x: float = 0.5


def optimum(Ef: Callable, dlo: float, kfix: Optional[float] = None,
            bfix: Optional[float] = None, iters: int = 6) -> Optimum:
    """
    The method boundary: the largest ℓ (smallest B) the family admits.
    κ is iterated to its fixed point κ = 2B − 1 unless pinned with `kfix`.
    Port of step23.opt().
    """
    k = 0.75 if kfix is None else kfix
    b = bfix if bfix is not None else 0.0
    l = 0.0
    for _ in range(iters):
        def l_of_b(bb: float) -> float:
            return _bisect(lambda ll: vmax(Ef, bb, ll, k, dlo), 0.0, 0.6)
        if bfix is None:
            b = _gss_argmax(l_of_b, 0.0, 0.3)
            l = l_of_b(b)
        else:
            b, l = bfix, l_of_b(bfix)
        if kfix is not None:
            break
        k = 2 * Bof(l) - 1
    return Optimum(Bof(l), l, b, k)


# --------------------------------------------------------------------------- #
# admissibility walls (Xu–Sang §6.2), positive = satisfied
# --------------------------------------------------------------------------- #
def walls(B: float, l: float, b: float, k: float) -> dict:
    g = geom(b, l)
    h, lx, ly = g["h"], g["lx"], g["ly"]
    return {
        "6kl-3/4": 6 * k * l - 0.75,
        "1/(6k)-l/h": 1 / (6 * k) - l / h,
        "lx-l": lx - l,
        "ly-l-11b/6": ly - l - 11 * b / 6,
        "1/2-ly": 0.5 - ly,
        "ly-h/2": ly - h / 2,
        "1/5-l": 0.2 - l,
        "B-0.87": B - 0.87,
        "(1+k)/2-B": (1 + k) / 2 - B,
    }


def broken_walls(B: float, l: float, b: float, k: float) -> list[str]:
    return [name for name, v in walls(B, l, b, k).items() if v <= 1e-12]


# --------------------------------------------------------------------------- #
# transform between two methods, and its extensions
# --------------------------------------------------------------------------- #
def transform_residual(b: float, l: float, k: float, n: int = 2000,
                       seed: int = 12345) -> float:
    """
    Max |E_XS − (E_Liu + T)| over n random (δ,x), where T is the closed form
    T = (h/4)(1−R) − ℓδ + c·δ·x·(h/4 − l_y/2), c = 1/(3κ).
    The research recorded 2·10⁻¹⁶; we just confirm it is ~machine zero.
    """
    import random
    rng = random.Random(seed)
    g = geom(b, l)
    c = 1 / (3 * k)
    worst = 0.0
    for _ in range(n):
        d = rng.uniform(1e-3, 5 / 6 - 1e-3)
        x = rng.uniform(0.0, 0.5)
        T = (g["h"] / 4) * (1 - R(k, d, x)) - l * d + c * d * x * (g["h"] / 4 - g["ly"] / 2)
        worst = max(worst, abs(E_xs(b, l, k, d, x) - (E_liu(b, l, k, d, x) + T)))
    return worst


def extend_t(t: float, dlo: float = 1 / 8) -> Optimum:
    """E_Liu + t·(E_XS − E_Liu): "more of the same idea" (t=0 Liu, t=1 Xu–Sang)."""
    def Ef(b, l, k, d, x):
        return E_liu(b, l, k, d, x) + t * (E_xs(b, l, k, d, x) - E_liu(b, l, k, d, x))
    return optimum(Ef, dlo)


def extend_w(w: float, dlo: float = 1 / 8) -> Optimum:
    """Share of row-counting benefit given up (Xu–Sang sit at w=1/4; w≥0.26 breaks)."""
    return optimum(lambda b, l, k, d, x: E_xs(b, l, k, d, x, w), dlo)


# --------------------------------------------------------------------------- #
# verdict against the targets
# --------------------------------------------------------------------------- #
TARGETS = (0.87, 5 / 6, 3 / 4, 1 / 2)      # 5/6 ≈ 0.8333, the structural wall


def verdict(B_from: float, B_to: float, eps: float = 1e-9) -> str:
    """closer / farther / same, phrased toward the targets (smaller B is better)."""
    if B_to < B_from - eps:
        return "bliže"
    if B_to > B_from + eps:
        return "dalje"
    return "isto"


# --------------------------------------------------------------------------- #
# exact minimal polynomial of B* (sympy, resultants) — base package
# --------------------------------------------------------------------------- #
def exact_polynomial(family: str = "liu"):
    """
    Return (sympy Poly in B, numeric root B*) for the method optimum, derived by
    eliminating δ, b, ℓ from the stationarity system (port of pipeline.py).
    Validated: for 'liu' this is Liu's cubic mapped to B; for 'xs' the quartic
    133488B⁴ − 376596B³ + 384534B² − 167541B + 26231.
    """
    import sympy as sp
    d, l, b, B = sp.symbols("delta ell b B")
    H = sp.Rational(1, 2)

    def Rs(k, d, x):
        c = 2 / (3 * k)
        D = 3 - (1 + c) * x
        P = (2 - c * x) * (1 - x)
        J = (sp.Rational(5, 6) - d) * D + d * P
        return 1 - d + (sp.Rational(5, 6) - d) * d * P / (2 * J)

    k = sp.Rational(5, 6) - l / 2          # κ = 2B − 1 with B = 11/12 − ℓ/4
    h = (1 + b + 3 * l) / 2
    ly = (1 + b - l) / 2
    c = 1 / (3 * k)
    x = H
    if family == "liu":
        E = -sp.Rational(1, 4) + b / 6 + 5 * l / 4 + (H + l) * d + l * x * d - h * (1 - Rs(k, d, x))
        guess = [0.3886, 0.16684, 0.1234]
    elif family == "xs":
        # Xu–Sang sit at w = 1/4: only 3/4 of the row-counting benefit is used.
        E = (-sp.Rational(1, 4) + b / 6 + 5 * l / 4 + d / 2
             + d * x * (l + c * (h / 4 - ly / 2))
             - h * (1 - sp.Rational(1, 4)) * (1 - Rs(k, d, x)))
        guess = [0.4693449, 0.1671200785, 0.0865350]
    else:
        raise ValueError(f"nepoznata familija '{family}'")

    E = sp.together(E)
    N = sp.expand(sp.numer(E))
    sol = sp.nsolve([N, sp.numer(sp.together(sp.diff(E, b))),
                     sp.numer(sp.together(sp.diff(E, d)))], [d, l, b], guess,
                    prec=40, dict=True)[0]
    N1 = sp.expand(N.coeff(b, 1))
    N0 = sp.expand(N.coeff(b, 0))
    g = sp.numer(sp.together(sp.diff(E, d).subs(b, -N0 / N1)))

    def ok(f):
        return f.has(d) and abs(sp.N(f.subs(sol), 30)) < 1e-12

    cl = [f for f, m in sp.factor_list(N1)[1] if ok(f)]
    gl = [f for f, m in sp.factor_list(g)[1] if ok(f)]
    for f, m in sp.factor_list(sp.resultant(cl[0], gl[0], d))[1]:
        if f.has(l) and abs(sp.N(f.subs(sol), 30)) < 1e-10:
            pB = sp.Poly(sp.expand(f.subs(l, 4 * (sp.Rational(11, 12) - B))), B).primitive()[1]
            root = float(sp.Rational(11, 12) - sol[l] / 4)
            return sp.Poly(pB, B), root
    raise RuntimeError(f"nije nađen minimalni polinom za '{family}'")
