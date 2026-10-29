"""
Swing and attractors on a unit's measured θ series [rules 5, 5a, 23; §5, §7].

Δθ is taken per move. Swing strength = RMSSD over the last 30 moves; an acute
change (PAC) is |Δθ| ≥ 5 points; a sweep is the distance between two
consecutive turning points. All values are θ points.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

from . import constants as K


def rmssd(xs: Sequence[float]) -> float:
    d = [b - a for a, b in zip(xs, xs[1:])]
    return math.sqrt(sum(v * v for v in d) / len(d)) if d else 0.0


def acf1(xs: Sequence[float]) -> float:
    n = len(xs)
    if n < 3:
        return 1.0
    m = sum(xs) / n
    den = sum((x - m) ** 2 for x in xs)
    if den == 0:
        return 1.0
    return sum((xs[i] - m) * (xs[i + 1] - m) for i in range(n - 1)) / den


def _plateaus_merged(xs: Sequence[float]) -> list[tuple[int, float]]:
    """(index, value) with runs of equal values merged — a plateau between a rise
    and a fall is still a turn (30, 45, 45, 30 turns once)."""
    out: list[tuple[int, float]] = []
    for i, x in enumerate(xs):
        if not out or x != out[-1][1]:
            out.append((i, x))
    return out


def turning_points(xs: Sequence[float]) -> list[tuple[int, float]]:
    """Internal turning points (index, value): where θ changes direction."""
    m = _plateaus_merged(xs)
    return [m[i] for i in range(1, len(m) - 1)
            if (m[i][1] - m[i - 1][1]) * (m[i + 1][1] - m[i][1]) < 0]


def sweeps(xs: Sequence[float]) -> list[float]:
    """Distances between consecutive turning points (local extrema), the series'
    ends included."""
    if not xs:
        return []
    turns = [xs[0]] + [v for _, v in turning_points(xs)] + ([xs[-1]] if len(xs) > 1 else [])
    return [abs(b - a) for a, b in zip(turns, turns[1:]) if b != a]


def _fit(ys: Sequence[float]) -> tuple[float, float]:
    """Least-squares line through (i, ys[i]): (intercept, slope)."""
    n = len(ys)
    mx = (n - 1) / 2
    my = sum(ys) / n
    den = sum((i - mx) ** 2 for i in range(n))
    s = sum((i - mx) * (y - my) for i, y in enumerate(ys)) / den if den else 0.0
    return my - s * mx, s


ENV_SLOPE = 0.15                   # |s| below this: the swing neither grows nor dies


def envelope(xs: Sequence[float]) -> Optional[tuple[list[float], float, float, float]]:
    """(last 3–6 sweeps, slope s of log A_i, fitted last A, moves per sweep) or None
    when there is no real swing (< 2 turning points or < 3 sweeps)."""
    turns = turning_points(xs)
    if len(turns) < K.MIN_TURNS:
        return None
    pts = [xs[0]] + [v for _, v in turns] + [xs[-1]]
    amps = [abs(b - a) for a, b in zip(pts, pts[1:]) if b != a][-K.TEND_K[1]:]
    if len(amps) < K.TEND_K[0]:
        return None
    a, s = _fit([math.log(max(x, 0.01)) for x in amps])
    last = math.exp(a + s * (len(amps) - 1))
    spacing = max(1.0, (turns[-1][0] - turns[0][0]) / max(1, len(turns) - 1))
    return amps, s, last, spacing


def tendency(series: Sequence[float], boundary_empty: bool = False) -> tuple[str, Optional[int], str]:
    """Where the swing is heading [rules 50–52]: (attractor, moves until it is
    reached or None, why). Only a measurement and a soft sign — the Doctor acts
    when an attractor is actually reached.

      * the envelope: through the last 3–6 sweeps A_i between turning points,
        log A_i ≈ a + s·i; s > 0 the swing grows, s < 0 it dies out;
      * growing past the amplitude within the horizon → B;
      * dying out below 1 point within the horizon WITH an empty boundary → S
        (with someone on the boundary a calming swing is just healthy);
      * no swing to speak of: the drift of the mean — crossing 33 → C, 27 → N.
    One jump is not a swing: without ≥ 2 turning points there is no B/S tendency."""
    xs = list(series[-K.WIN_SWING:])
    if len(xs) < K.MIN_SWING_MOVES:
        return "", None, ""
    env = envelope(xs)
    if env is not None:
        _amps, s, last, spacing = env
        if s >= ENV_SLOPE:
            need = 0.0 if last > K.AMPLITUDE else (math.log(K.AMPLITUDE) - math.log(last)) / s
            moves = int(round(need * spacing))
            if moves <= K.TEND_HORIZON:
                return K.BORDERLINE, moves, f"zamah raste (nagib {s:.2f} po zamahu)"
        elif s <= -ENV_SLOPE:
            need = 0.0 if last < K.SCHIZOID_SIGMA else (math.log(K.SCHIZOID_SIGMA) - math.log(last)) / s
            moves = int(round(need * spacing))
            if moves <= K.TEND_HORIZON and boundary_empty:
                return K.SCHIZOID, moves, f"zamah se gasi (nagib {s:.2f}) uz praznu granicu"
        return "", None, ""
    a, slope = _fit(xs)
    now = a + slope * (len(xs) - 1)
    if slope > 0.05:
        moves = 0 if now >= K.CODEP_MEAN else int(math.ceil((K.CODEP_MEAN - now) / slope))
        if moves <= K.TEND_HORIZON:
            return K.CODEPENDENT, moves, f"prosjek klizi naviše ({slope:+.2f} po potezu)"
    elif slope < -0.05:
        moves = 0 if now <= K.NARC_MEAN else int(math.ceil((K.NARC_MEAN - now) / slope))
        if moves <= K.TEND_HORIZON:
            return K.NARCISSISTIC, moves, f"prosjek klizi naniže ({slope:+.2f} po potezu)"
    return "", None, ""


@dataclass
class SwingReport:
    attractor: str
    delta: float
    pac: bool
    sigma: float                 # RMSSD over the swing window
    acf1: float
    mean_long: float
    sweep: float
    reasons: list[str] = field(default_factory=list)
    moves: int = 0
    turns: int = 0
    tend: str = ""                     # where it is heading (soft sign) [rules 50–52]
    tend_in: Optional[int] = None      # … in about this many moves
    tend_why: str = ""

    def as_dict(self) -> dict:
        return {"attractor": self.attractor, "delta": round(self.delta, 2),
                "pac": self.pac, "sigma": round(self.sigma, 3),
                "acf1": round(self.acf1, 3), "mean_long": round(self.mean_long, 2),
                "sweep": round(self.sweep, 2), "reasons": self.reasons,
                "moves": self.moves, "turns": self.turns, "tend": self.tend,
                "tend_in": self.tend_in, "tend_why": self.tend_why}


def assess(series: Sequence[float], boundary_empty: bool = False) -> SwingReport:
    """Read the attractor from a unit's θ series (thresholds of rule 5a)."""
    n = len(series)
    delta = series[-1] - series[-2] if n >= 2 else 0.0
    win = list(series[-K.WIN_SWING:])
    longw = list(series[-K.WIN_LONG:])
    sigma = rmssd(win)
    a1 = acf1(win)
    mean_long = sum(longw) / len(longw) if longw else K.THETA_NOM
    sw = sweeps(win)
    last_sweep = sw[-1] if sw else 0.0
    rep = SwingReport(K.HEALTHY, delta, abs(delta) >= K.PAC_POINTS, sigma, a1,
                      mean_long, last_sweep, moves=n, turns=len(turning_points(win)))
    rep.tend, rep.tend_in, rep.tend_why = tendency(series, boundary_empty)
    if n < 3:
        return rep

    # borderline: swings too large — but only a real back-and-forth counts
    # [rule 50]: ≥ 2 turning points over ≥ 10 moves; one jump is a PAC (soft)
    env = envelope(win) if len(win) >= K.MIN_SWING_MOVES else None
    dying = env is not None and env[1] <= -ENV_SLOPE      # a swing that dies out is not B
    if rep.turns < K.MIN_TURNS or len(win) < K.MIN_SWING_MOVES or dying:
        pass
    elif sigma > K.BORDERLINE_SIGMA and a1 < K.BORDERLINE_ACF1:
        rep.reasons.append(f"σ={sigma:.2f} > {K.BORDERLINE_SIGMA} i ACF(1)={a1:.2f} < {K.BORDERLINE_ACF1}")
    if rep.turns >= K.MIN_TURNS and len(win) >= K.MIN_SWING_MOVES and not dying:
        if last_sweep > K.AMPLITUDE:
            rep.reasons.append(f"zamah {last_sweep:.1f} > amplitude {K.AMPLITUDE}")
        if len(sw) >= 4 and sw[-1] > sw[-2] > sw[-3] > sw[-4]:
            rep.reasons.append("zamah raste 3 puta zaredom")
    if rep.reasons:
        rep.attractor = K.BORDERLINE
        return rep

    # level attractors need a calm series (σ < 2) over the swing window
    if n >= K.WIN_SWING and sigma < K.LEVEL_SIGMA:
        recent = sum(win) / len(win)
        if mean_long > K.CODEP_MEAN or recent > K.CODEP_SUSTAINED:
            rep.attractor = K.CODEPENDENT
            rep.reasons.append(f"prosjek {mean_long:.1f} iznad 33 uz σ < 2")
            return rep
        if mean_long < K.NARC_MEAN or recent < K.NARC_SUSTAINED:
            rep.attractor = K.NARCISSISTIC
            rep.reasons.append(f"prosjek {mean_long:.1f} ispod 27 uz σ < 2")
            return rep

    # schizoid: swings too small over the long window + empty boundary
    if n < K.SCHIZOID_MIN_MOVES:
        if n >= K.WIN_SWING and sigma < K.SCHIZOID_SIGMA and boundary_empty:
            rep.reasons.append("šizoidni prag: nedovoljno istorije")
        return rep
    long_sigma = rmssd(longw)
    if long_sigma < K.SCHIZOID_SIGMA and boundary_empty:
        rep.attractor = K.SCHIZOID
        rep.reasons.append(f"σ={long_sigma:.2f} < 1 kroz dugi prozor + prazna granica")
    return rep


def healthy_band(theta: float) -> bool:
    return abs(theta - K.THETA_NOM) <= K.THETA_BAND


def last_or(series: Sequence[float], default: Optional[float] = None) -> float:
    return series[-1] if series else (K.THETA_NOM if default is None else default)
