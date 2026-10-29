"""
Functions on the Grafovi tab (round 3, item 29): what the "Funkcije" panel holds.

Unlimited functions, each with its own colour, of these kinds:

    real        y = f(x)               (names: x + the slider parameters)
    complex     w = f(s)               (s complex; drawn as a phase portrait etc.)
    surface     z = f(x, y)            (3D, or a colour map)
    parametric  (x(u), y(u))
    polar       r = f(θ)               (name: th)
    builtin     the project's own functions: B(ℓ), E_Liu(δ), E_XS(δ), max_δ E(ℓ),
                the extensions B*(t), B*(w) — each with its LEVEL and source card

Every function carries a level: RAD (from a paper, with its card), NAŠE-NERECENZIRANO
(our computation), KORISNIK (typed by the operator). The plot shows it.
The list is kept in the SHARED_LIB store (kv), so it survives a restart and is part
of a mission's "where I stopped" snapshot (item 28a).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

import numpy as np

from . import fexpr as FX

KINDS = ("real", "complex", "surface", "parametric", "polar", "builtin")
PARAMS = {"l": 1 / 6, "b": 0.1234, "k": 0.75, "t": 0.0, "w": 0.25, "d": 1.0,
          "low": 3 / 16, "delta": 0.0}           # sliders (ℓ, b, κ, t, w, d, niska strana, Δ);
#                                                 low = 3/16 gives σ* = 11/16 + 3/16 = 7/8
RAD, OURS, USER = "RAD", "NAŠE-NERECENZIRANO", "KORISNIK"
COLORS = ["#ffb74d", "#4fc3f7", "#81c784", "#e57373", "#ba68c8", "#fff176", "#4db6ac",
          "#f06292", "#a1887f", "#90a4ae"]
TARGETS = {"7/8": 7 / 8, "0.87": 0.87, "5/6": 5 / 6, "3/4": 3 / 4, "1/2": 0.5}
STORE_KEY = "graph_functions"


@dataclass
class Function:
    id: str
    label: str
    kind: str
    expr: str = ""                 # real/complex/surface/polar; parametric: "x(u); y(u)"
    color: str = "#ffb74d"
    level: str = USER
    card: str = ""                 # vault card id (click → open)
    builtin: str = ""
    visible: bool = True
    domain: list = field(default_factory=lambda: [0.0, 1.0])
    meaning: str = ""              # what a point on it means (for "sve o tački")

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Function":
        f = Function(**{k: d[k] for k in Function.__dataclass_fields__ if k in d})
        validate(f)
        return f


def var_names(kind: str) -> list:
    return {"real": ["x"], "complex": ["s"], "surface": ["x", "y"], "parametric": ["u"],
            "polar": ["th"]}.get(kind, [])


def validate(f: Function) -> None:
    if f.kind not in KINDS:
        raise FX.FExprError(f"vrsta mora biti jedna od {KINDS}")
    if f.kind == "builtin":
        if f.builtin not in BUILTINS:
            raise FX.FExprError(f"nepoznata ugrađena funkcija '{f.builtin}'")
        return
    names = set(var_names(f.kind)) | set(PARAMS)
    parts = f.expr.split(";") if f.kind == "parametric" else [f.expr]
    if f.kind == "parametric" and len(parts) != 2:
        raise FX.FExprError("parametarska kriva: „x(u); y(u)“")
    for p in parts:
        FX.parse(p, names)


# --------------------------------------------------------------------------- #
# the project's own functions (exact definitions live in methods/core.py)
# --------------------------------------------------------------------------- #
def _liu_opt():
    from ..methods import core as C
    return _cached("liu", lambda: C.optimum(C.E_liu, 1 / 8))


def _xs_opt():
    from ..methods import core as C
    return _cached("xs", lambda: C.optimum(C.E_xs, 1 / 8))


_CACHE: dict = {}


def _cached(key, fn):
    if key not in _CACHE:
        _CACHE[key] = fn()
    return _CACHE[key]


def _b_line(x, p):
    return 11 / 12 - np.asarray(x, float) / 4


def _e_delta(Ef, opt):
    def f(x, p):
        return np.vectorize(lambda d: Ef(opt.b, opt.l, opt.k, d, 0.5))(np.asarray(x, float))
    return f


def _e_liu(x, p):
    from ..methods import core as C
    return _e_delta(C.E_liu, _liu_opt())(x, p)


def _e_xs(x, p):
    from ..methods import core as C
    return _e_delta(C.E_xs, _xs_opt())(x, p)


def _vmax_l(x, p):
    from ..methods import core as C
    o = _liu_opt()
    return np.vectorize(lambda l: C.vmax(C.E_liu, o.b, l, o.k, 1 / 8))(np.asarray(x, float))


def _ext(which):
    def f(x, p):
        from ..methods import core as C
        g = C.extend_t if which == "t" else C.extend_w
        return np.vectorize(lambda v: g(v).B)(np.asarray(x, float))
    return f


def _path(which):
    """Parametric: the method boundary point (ℓ*, B*) along an extension (t or w)."""
    def f(u, p):
        from ..methods import core as C
        g = C.extend_t if which == "t" else C.extend_w
        pts = [g(float(v)) for v in np.atleast_1d(u)]
        return np.array([o.l for o in pts]), np.array([o.B for o in pts])
    return f


def _vmax_lk(x, y, p):
    """Surface over (ℓ, κ): the worst exponent max_δ E_Liu at b = the b slider
    (it starts at the Liu optimum's b ≈ 0.1234, so moving b moves the boundary)."""
    from ..methods import core as C
    b = float(p.get("b", _liu_opt().b))
    return np.vectorize(lambda l, k: C.vmax(C.E_liu, b, l, k, 1 / 8))(
        np.asarray(x, float), np.asarray(y, float))


def _e_delta_complex(s, p):
    """E_Liu with a complex δ = s, at b from the slider and κ = 2B(ℓ) − 1 (ℓ slider)."""
    from ..methods import core as C
    l = float(p.get("l", 1 / 6))
    k = 2 * (11 / 12 - l / 4) - 1
    return C.E_liu(float(p.get("b", 0.1234)), l, k, np.asarray(s, complex), 0.5)


BUILTINS: dict = {
    "B_line": dict(label="B(ℓ) = 11/12 − ℓ/4", level=RAD, card="izvor-openai-7-8",
                   fn=_b_line, domain=[0.0, 0.3], cost=1e-6,
                   meaning="zajednička prava: ℓ → granica B; 11/12 je ℓ=0, 7/8 je ℓ=1/6"),
    "E_liu": dict(label="E_Liu(δ) na optimumu", level=RAD, card="izvor-liu-2610-12234",
                  fn=_e_liu,
                  domain=[1 / 8, 5 / 6], cost=2e-6,
                  meaning="eksponent visoke strane (Liu) po δ, u optimalnim (b, ℓ, κ); max ≤ 0 = metoda prolazi"),
    "E_xs": dict(label="E_XS(δ) na optimumu", level=RAD, card="izvor-xu-sang-2610-15291",
                 fn=_e_xs,
                 domain=[1 / 8, 5 / 6], cost=2e-6,
                 meaning="eksponent visoke strane (Xu–Sang) po δ; E_XS = E_Liu + T"),
    "vmax_liu": dict(label="max_δ E_Liu(ℓ)", level=OURS, card="izvor-liu-2610-12234",
                     fn=_vmax_l, domain=[0.10, 0.20], cost=2e-4,
                     meaning="najgori δ za dato ℓ; nula = granica metode ℓ*, B* = B(ℓ*)"),
    "ext_t": dict(label="B*(t) — proširenje t", level=OURS, card="", fn=_ext("t"),
                  domain=[0.0, 1.0], cost=4.6, coarse=9,
                  meaning="granica metode duž proširenja t (misija 1: bliže/dalje od cilja)"),
    "ext_w": dict(label="B*(w) — proširenje w", level=OURS, card="izvor-xu-sang-2610-15291",
                  fn=_ext("w"), domain=[0.0, 0.25], cost=1.9, coarse=9,
                  meaning="granica metode duž težine w (w=0.25 je Xu–Sang)"),
    # parametric paths and a surface (round 3, item 29, step 3)
    "path_t": dict(label="putanja (ℓ*(t), B*(t))", level=OURS, card="", fn=_path("t"),
                   domain=[0.0, 1.0], cost=4.0, coarse=7, shape="path",
                   meaning="tačka granice metode u ravni (ℓ, B) dok t ide od Liu (0) do Xu–Sang (1)"),
    "path_w": dict(label="putanja (ℓ*(w), B*(w))", level=OURS, card="izvor-xu-sang-2610-15291",
                   fn=_path("w"), domain=[0.0, 0.25], cost=1.9, coarse=7, shape="path",
                   meaning="tačka granice metode u ravni (ℓ, B) duž težine w"),
    # two exponent surfaces over (ℓ, σ): they cross along the curve σ = B(ℓ) (step 5)
    "plane_sigma": dict(label="z = σ (granica poluravni)", level=OURS, card="", shape="surface",
                        fn=lambda x, y, p: np.asarray(y, float) + 0 * np.asarray(x, float),
                        domain=[0.0, 0.3, 0.80, 0.95], cost=1e-7,
                        meaning="ravan z = σ nad (ℓ, σ); presjek sa z = B(ℓ) je kriva σ = B(ℓ)"),
    "B_surface": dict(label="z = B(ℓ) nad (ℓ, σ)", level=RAD, card="izvor-openai-7-8", shape="surface",
                      fn=lambda x, y, p: 11 / 12 - np.asarray(x, float) / 4 + 0 * np.asarray(y, float),
                      domain=[0.0, 0.3, 0.80, 0.95], cost=1e-7,
                      meaning="granica B(ℓ) kao površ nad (ℓ, σ)"),
    "E_delta_c": dict(label="E_Liu(δ) za kompleksno δ (misija 3)", level=OURS, card="izvor-liu-2610-12234",
                      fn=_e_delta_complex, domain=[0.1, 0.8], cost=2e-6, shape="complex",
                      meaning="nule u δ: dva realna (metoda pada) → dvostruka u ℓ* → konjugovani par (prolazi); pomjeri klizač ℓ"),
    "vmax_lk": dict(label="max_δ E_Liu nad (ℓ, κ)", level=OURS, card="izvor-liu-2610-12234",
                    fn=_vmax_lk, domain=[0.10, 0.22, 0.60, 0.90], cost=1e-4, shape="surface",
                    meaning="najgori eksponent u tački (ℓ, κ) za b sa klizača; ≤ 0 = metoda prolazi; nula = granica ℓ*(κ)"),
}


def shape(f: "Function") -> str:
    """curve · path · surface · complex · polar — what kind of picture f makes."""
    if f.kind == "builtin":
        return BUILTINS[f.builtin].get("shape", "curve")
    return {"real": "curve", "parametric": "path", "surface": "surface",
            "complex": "complex", "polar": "polar"}[f.kind]


def builtin(key: str, color: Optional[str] = None) -> Function:
    b = BUILTINS[key]
    return Function(id=f"bi-{key}", label=b["label"], kind="builtin", builtin=key,
                    color=color or COLORS[list(BUILTINS).index(key) % len(COLORS)],
                    level=b["level"], card=b["card"], domain=list(b["domain"]),
                    meaning=b["meaning"])


# --------------------------------------------------------------------------- #
# evaluation
# --------------------------------------------------------------------------- #
def _params(p: Optional[dict]) -> dict:
    return {**PARAMS, **(p or {})}


def numeric(f: Function, params: Optional[dict] = None) -> Callable:
    """Vectorised numpy f(x) for real/builtin, f(s) for complex, f(x, y) for surfaces,
    (x(u), y(u)) for parametric, r(θ) for polar. Slider parameters are bound."""
    p = _params(params)
    if f.kind == "builtin":
        fn = BUILTINS[f.builtin]["fn"]
        if BUILTINS[f.builtin].get("shape") == "complex":
            return lambda s: fn(s, p)
        if BUILTINS[f.builtin].get("shape") == "surface":
            return lambda x, y: fn(x, y, p)
        return lambda x: fn(x, p)
    names = var_names(f.kind)
    allp = list(PARAMS)
    if f.kind == "parametric":
        fx, fy = (FX.compile_fn(FX.parse(e, set(names) | set(PARAMS)), names + allp)
                  for e in f.expr.split(";"))
        vals = [p[k] for k in allp]
        sx, sy = _safe(lambda t: fx(t, *vals)), _safe(lambda t: fy(t, *vals))
        return lambda t: (sx(t), sy(t))
    g = FX.compile_fn(FX.parse(f.expr, set(names) | set(PARAMS)), names + allp)
    vals = [p[k] for k in allp]
    return _safe(lambda *a: g(*a, *vals))


def _safe(fn: Callable) -> Callable:
    """Overflow, ÷0, log of a negative … → NaN (a gap in the curve), never an exception;
    a constant expression is broadcast to the shape of its input."""
    def call(*a):
        shape = np.broadcast(*[np.asarray(x) for x in a]).shape if a else ()
        try:
            with np.errstate(all="ignore"):
                out = fn(*a)
        except (OverflowError, ZeroDivisionError, ValueError, FloatingPointError):
            return np.full(shape, np.nan)
        out = np.asarray(out)
        return np.broadcast_to(out, shape).copy() if out.shape != shape else out
    return call


def precise(f: Function, params: Optional[dict] = None) -> Callable:
    """mpmath point evaluation (real/complex); builtins fall back to float."""
    p = _params(params)
    if f.kind == "builtin":
        fn = BUILTINS[f.builtin]["fn"]
        if BUILTINS[f.builtin].get("shape") == "complex":
            return lambda s: complex(np.asarray(fn(np.array([complex(s)]), p))[0])
        return lambda x: float(np.asarray(fn(np.array([float(x)]), p))[0])
    names = var_names(f.kind)
    allp = list(PARAMS)
    g = FX.compile_fn(FX.parse(f.expr, set(names) | set(PARAMS)), names + allp, "mp")
    vals = [p[k] for k in allp]
    return lambda *a: g(*a, *vals)


def interval(f: Function, params: Optional[dict] = None) -> Callable:
    """mpmath.iv evaluation for interval certificates (typed real functions only)."""
    if f.kind != "real":
        raise FX.FExprError("interval-certifikat samo za upisane realne funkcije")
    p = _params(params)
    allp = list(PARAMS)
    g = FX.compile_fn(FX.parse(f.expr, {"x"} | set(PARAMS)), ["x"] + allp, "iv")
    from mpmath import iv
    vals = [iv.mpf(p[k]) for k in allp]
    return lambda x: g(x, *vals)


def speed_factor() -> float:
    """Declared costs were measured on the Dell (i5-6600, 4 cores); the Acer i3
    (2c/4t) is estimated ~1.8× slower — an ESTIMATE, as in the machine profile."""
    try:
        from .. import machine as MC
        key = MC.profile().key
    except Exception:                                   # noqa: BLE001
        key = ""
    return 1.8 if key == "acer" else 1.0


def eval_cost(f: Function, params: Optional[dict] = None) -> float:
    """Seconds per evaluation — measured once (a few points), else the declared cost."""
    import time
    if f.kind == "builtin":
        return BUILTINS[f.builtin]["cost"] * speed_factor()
    try:
        fn = numeric(f, params)
        xs = np.linspace(f.domain[0] or 0.1, f.domain[1] or 1.0, 64)
        t0 = time.perf_counter()
        if f.kind == "surface":
            fn(xs, xs)
        elif f.kind == "complex":
            fn(xs + 0.5j)
        else:
            fn(xs)
        return max((time.perf_counter() - t0) / 64, 1e-7)
    except Exception:                                   # noqa: BLE001
        return 1e-3


def is_finite(v) -> bool:
    try:
        return math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------- #
# the list the operator keeps (SHARED_LIB kv)
# --------------------------------------------------------------------------- #
def default_set() -> list:
    return [builtin("B_line"), builtin("E_liu"), builtin("E_xs")]


def load() -> list:
    from ..shared_lib.store import store
    raw = store().kv_get(STORE_KEY)
    if not raw:
        return default_set()
    out = []
    for d in raw:
        try:
            out.append(Function.from_dict(d))
        except Exception:                               # noqa: BLE001 — a bad entry is skipped
            continue
    return out


def save(funcs: list) -> None:
    from ..shared_lib.store import store
    store().kv_set(STORE_KEY, [f.to_dict() for f in funcs])


def next_color(funcs: list) -> str:
    used = {f.color for f in funcs}
    for c in COLORS:
        if c not in used:
            return c
    return COLORS[len(funcs) % len(COLORS)]
