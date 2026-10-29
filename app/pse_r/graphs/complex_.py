"""
Complex functions on the Grafovi tab (round 3, item 29, step 4).

  phase_rgb()       phase portrait: colour = arg f, brightness = |f| (zeros dark,
                    poles bright) — the classic domain colouring
  sigma_star()      σ* = 11/16 + low side + Δ: the edge of the zero-free half-plane a
                    method gives (7/8 = 11/16 + 3/16); σ* ≥ 1 means the region is gone
  zeros_in_rect()   the number of zeros (minus poles) inside a rectangle by the
                    argument principle: the winding of f along the boundary, sampled
                    finely and refined where the phase jumps — never trusted if a
                    step is still too big (then it says "nesigurno")
  residue()         (1/2πi)∮ f ds on a small circle
  point_info_c()    everything about a complex point s
"""
from __future__ import annotations

import cmath
import math
from typing import Callable, Optional

import numpy as np

LOW_7_8 = 3 / 16                      # 7/8 = 11/16 + 3/16
_ZEROS: list = []


def sigma_star(low: float, delta: float = 0.0) -> float:
    return 11 / 16 + low + delta


def zeta_zeros(n: int = 40) -> list:
    """Ordinates γ of the first n nontrivial zeros (mpmath, cached)."""
    global _ZEROS
    if len(_ZEROS) < n:
        import mpmath as mp
        _ZEROS = [float(mp.zetazero(k).imag) for k in range(1, n + 1)]
    return _ZEROS[:n]


def phase_rgb(W: np.ndarray) -> np.ndarray:
    from matplotlib.colors import hsv_to_rgb
    W = np.asarray(W, complex)
    h = (np.angle(W) + np.pi) / (2 * np.pi)
    m = np.abs(W)
    v = 0.25 + 0.75 * (2 / np.pi) * np.arctan(np.nan_to_num(m, nan=0.0, posinf=1e9))
    # contour bands of log|f| make the modulus readable
    band = (np.log2(np.where(m > 0, m, 1e-300)) % 1.0)
    v = np.clip(v * (0.85 + 0.15 * band), 0, 1)
    hsv = np.stack([h, np.full_like(h, 0.85), v], axis=-1)
    rgb = hsv_to_rgb(np.nan_to_num(hsv))
    rgb[~np.isfinite(m)] = 1.0
    return rgb


def zeros_in_rect(f: Callable[[complex], complex], s0: complex, s1: complex,
                  n: int = 400, max_step: float = 0.5, cancel=None) -> dict:
    """Winding number of f around the rectangle [s0, s1] (counter-clockwise)."""
    a, b = min(s0.real, s1.real), max(s0.real, s1.real)
    c, d = min(s0.imag, s1.imag), max(s0.imag, s1.imag)
    corners = [complex(a, c), complex(b, c), complex(b, d), complex(a, d), complex(a, c)]
    total, worst, evals = 0.0, 0.0, 0

    def arg(z):
        nonlocal evals
        evals += 1
        return cmath.phase(f(z))
    for p, q in zip(corners, corners[1:]):
        k = max(16, int(n * abs(q - p) / (2 * (b - a) + 2 * (d - c))))
        pts = [p + (q - p) * j / k for j in range(k + 1)]
        prev = arg(pts[0])
        for z0, z1 in zip(pts, pts[1:]):
            if cancel is not None and cancel.is_set():
                from .compute import Cancelled
                raise Cancelled("prekinuto")
            cur = arg(z1)
            step = (cur - prev + math.pi) % (2 * math.pi) - math.pi
            depth = 0
            while abs(step) > max_step and depth < 12:      # refine where the phase jumps
                depth += 1
                m = 2 ** depth
                sub = [z0 + (z1 - z0) * i / m for i in range(m + 1)]
                ph = [arg(z) for z in sub]
                steps = [(y - x + math.pi) % (2 * math.pi) - math.pi for x, y in zip(ph, ph[1:])]
                if max(abs(x) for x in steps) <= max_step:
                    step = sum(steps)
                    break
            worst = max(worst, abs(step) if depth == 0 else max_step)
            total += step
            prev = cur
    w = total / (2 * math.pi)
    k = round(w)
    return {"count": int(k), "winding": w, "evals": evals,
            "sure": abs(w - k) < 0.05 and worst <= max_step,
            "rect": [[a, c], [b, d]]}


def residue(f: Callable[[complex], complex], s0: complex, r: float = 1e-3, n: int = 256) -> complex:
    tot = 0j
    for j in range(n):
        th = 2 * math.pi * j / n
        z = s0 + r * cmath.exp(1j * th)
        tot += f(z) * 1j * r * cmath.exp(1j * th)
    return tot * (2 * math.pi / n) / (2j * math.pi)


def cderivative(f: Callable[[complex], complex], s: complex, h: float = 1e-5) -> complex:
    return (f(s + h) - f(s - h)) / (2 * h)


def point_info_c(label: str, level: str, f: Callable[[complex], complex], s: complex,
                 sigma_s: float, is_zeta: bool = False) -> dict:
    w = complex(f(s))
    info = {"s": s, "f(s)": w, "|f|": abs(w), "arg f": cmath.phase(w), "function": label,
            "level": level, "dist_to_1/2": abs(s.real - 0.5), "sigma_star": sigma_s,
            "flags": []}
    if sigma_s >= 1:
        info["flags"].append("oblast bez nula je nestala (σ* ≥ 1)")
    elif s.real > sigma_s:
        info["flags"].append(f"u poluravni bez nula Re s > σ* = {sigma_s:.6g}")
    if 0 < s.real < 1:
        info["flags"].append("u kritičnoj traci 0 < Re s < 1")
    if abs(w) < 1e-6:
        info["flags"].append("nula (|f| < 10⁻⁶)")
    if is_zeta:
        zs = zeta_zeros(60)
        near = min(zs, key=lambda g: abs(complex(0.5, g if s.imag >= 0 else -g) - s))
        z0 = complex(0.5, near if s.imag >= 0 else -near)
        info["nearest_zero"] = {"s": z0, "distance": abs(z0 - s)}
    return info
