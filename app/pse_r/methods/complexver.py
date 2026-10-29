"""
Mission 3 — the complex version (round 3, item 32).

(a) Does the boundary depend on the height γ? In the Liu / Xu–Sang exponent systems
    E(b, ℓ, κ, δ, x) contains no γ at all (|X^s| = X^σ; the phase only feeds the
    cancellation that the exponents already summarise), so INSIDE these methods
    σ*(γ) ≡ B: the line Re s = B does not bend. Any γ-dependence would have to come
    from terms the method absorbs into ε (powers of log γ). This is our reading of
    the formalism — NAŠE-NERECENZIRANO — not a theorem.

(b) Let the exponent take a complex argument. At the critical x = 1/2 the numerator
    of E(δ) is a QUADRATIC in δ (computed exactly with sympy). So "signal meets the
    low side" has a complex meaning:
        ℓ > ℓ*  two real roots — E > 0 between them, the method fails;
        ℓ = ℓ*  a double root δ* — the boundary (discriminant 0);
        ℓ < ℓ*  a complex-conjugate pair — the method passes, and |Im δ| measures
                how far it is from failing (≈ c·√(ℓ* − ℓ)).
    The complex version gives no new B; it gives an algebraic characterisation of
    the boundary (a zero of a discriminant) and a margin. "Nothing new" is a result
    too, and it is written down.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Optional

from . import core as C

FAMILIES = {"liu": C.E_liu, "xs": C.E_xs}


@lru_cache(maxsize=4096)
def quadratic(family: str, b: float, l: float, k: float, x: float = 0.5) -> tuple:
    """Exact coefficients (a2, a1, a0) of the numerator of E(δ) as a polynomial in δ."""
    import sympy as sp
    d = sp.Symbol("d")
    Ef = FAMILIES[family]
    e = sp.together(Ef(sp.Rational(repr(b)), sp.Rational(repr(l)), sp.Rational(repr(k)), d,
                       sp.Rational(repr(x))))
    num = sp.Poly(sp.expand(sp.numer(e)), d)
    if num.degree() != 2:
        raise ValueError(f"brojilac E(δ) je stepena {num.degree()}, ne 2 — karakterizacija ne važi")
    a2, a1, a0 = (float(c) for c in num.all_coeffs())
    return a2, a1, a0


def roots(family: str, b: float, l: float, k: float) -> tuple:
    """The two roots δ of E(δ) = 0 (complex when the method passes)."""
    a2, a1, a0 = quadratic(family, b, l, k)
    D = a1 * a1 - 4 * a2 * a0
    sq = complex(D) ** 0.5
    return ((-a1 + sq) / (2 * a2), (-a1 - sq) / (2 * a2)), D


def disc(family: str, b: float, l: float, k: float) -> float:
    a2, a1, a0 = quadratic(family, b, l, k)
    return a1 * a1 - 4 * a2 * a0


def l_from_discriminant(family: str, b: float, lo: float, hi: float) -> Optional[float]:
    """ℓ where the discriminant changes sign, with κ = 2B(ℓ) − 1 (the licence)."""
    g = lambda l: disc(family, b, l, 2 * C.Bof(l) - 1)          # noqa: E731
    ga, gb = g(lo), g(hi)
    if ga * gb > 0:
        return None
    for _ in range(80):
        m = (lo + hi) / 2
        gm = g(m)
        if ga * gm <= 0:
            hi, gb = m, gm
        else:
            lo, ga = m, gm
    return (lo + hi) / 2


def margin_curve(family: str, n: int = 41, span: float = 0.01) -> dict:
    """Im δ (and Re δ) of the root pair along ℓ around ℓ*, at the method's b*."""
    opt = C.optimum(FAMILIES[family], 1 / 8)
    rows = []
    for i in range(n):
        l = opt.l - span + (span * 1.2) * i / (n - 1)
        (r1, r2), D = roots(family, opt.b, l, 2 * C.Bof(l) - 1)
        rows.append((l, abs(r1.imag), r1.real, r2.real, D))
    l_disc = l_from_discriminant(family, opt.b, opt.l - span, opt.l + 0.2 * span)
    # c in |Im δ| ≈ c √(ℓ* − ℓ), fitted on the passing side
    pts = [(opt.l - l, im) for l, im, *_ in rows if l < opt.l - 1e-6 and im > 0]
    c = (sum(im * math.sqrt(dl) for dl, im in pts) / sum(dl for dl, _ in pts)) if pts else None
    return {"family": family, "l_star": opt.l, "b_star": opt.b, "l_disc": l_disc,
            "agree": None if l_disc is None else abs(l_disc - opt.l), "c": c, "rows": rows,
            "delta_star": roots(family, opt.b, opt.l, 2 * C.Bof(opt.l) - 1)[0][0].real}


GAMMA_NOTE = ("E(b, ℓ, κ, δ, x) ne sadrži γ: |X^s| = X^σ, a faza ulazi samo kroz poništavanje koje "
              "eksponenti već sažimaju. Zato je u okviru Liu / Xu–Sang metode σ*(γ) ≡ B — prava "
              "Re s = B se ne savija ni prema 1/2 ni od nje. Zavisnost od γ mogla bi doći samo iz "
              "članova koje metoda guta u ε (stepeni log γ). NAŠE-NERECENZIRANO čitanje formalizma, "
              "ne teorema.")
