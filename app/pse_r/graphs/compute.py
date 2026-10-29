"""
"Sve o tački" and calculations on demand (round 3, item 29; Andrej 2026-10-25).

  point_info()   everything known about a point: coordinates, which function/
                 method, its parameters, whether it is a zero / intersection /
                 wall / target, distance to every target, source level, card link.
                 Cheap things are computed right away.
  offers()       at most 4 calculations that fit the KIND of point (the rest
                 under "više…"), each with an estimated duration. Anything over
                 CHEAP_S is only OFFERED ("Želiš li da izračunam …?").
  calculate()    the deterministic calculation itself (Python decides; an AI may
                 only explain later, on request).
  JOBS           a background queue with "prekini": one job at a time, respects
                 the limiters ("→ ∞" pause, free RAM) and the machine profile;
                 results are cached and recorded as a run in SHARED_LIB with the
                 label NAŠE-NERECENZIRANO.
"""
from __future__ import annotations

import hashlib
import json
import math
import queue
import threading
import time
from typing import Callable, Optional

import numpy as np

from . import functions as F

CHEAP_S = 0.3
LABEL = "NAŠE-NERECENZIRANO"
MAX_OFFERS = 4
B_FUNCS = {"B_line", "ext_t", "ext_w"}           # their value IS a boundary B
E_FUNCS = {"E_liu", "E_xs", "vmax_liu"}          # their value is an exponent (≤ 0 passes)
WALL_LINES = {"B": {"zid B ≥ 0.87": 0.87}, "x": {"zid ℓ ≤ 1/5": 0.2}}


class Cancelled(Exception):
    pass


def _check(cancel: Optional[threading.Event]) -> None:
    if cancel is not None and cancel.is_set():
        raise Cancelled("prekinuto")
    try:
        from ..llm import limits as LIM
        if LIM.paused():
            raise Cancelled("„→ ∞“ pauza — računi čekaju odluku operatera")
    except ImportError:
        pass


# --------------------------------------------------------------------------- #
# numerics (deterministic; each takes a scalar f and a cancel event)
# --------------------------------------------------------------------------- #
def _f1(f: F.Function, params=None) -> Callable[[float], float]:
    fn = F.numeric(f, params)
    return lambda x: float(np.asarray(fn(np.array([float(x)])))[0])


def derivative(f1, x: float, h: float = 1e-4, order: int = 1) -> float:
    """Richardson-extrapolated central difference (1st or 2nd derivative)."""
    def d(hh):
        if order == 1:
            return (f1(x + hh) - f1(x - hh)) / (2 * hh)
        return (f1(x + hh) - 2 * f1(x) + f1(x - hh)) / (hh * hh)
    return (4 * d(h / 2) - d(h)) / 3


def taylor(f1, x0: float, n: int = 4, span: float = 1.0, fprec=None) -> dict:
    """Coefficients c_k of Σ c_k (x−x0)^k. A typed function goes through mpmath at
    high precision (exact to many digits); a built-in (Python code) is fitted by a
    least-squares polynomial on a small symmetric stencil — marked as an estimate."""
    if fprec is not None:
        import mpmath as mp
        with mp.workdps(40):
            cs = mp.taylor(fprec, mp.mpf(x0), n)
        return {"coeffs": [float(mp.re(c)) for c in cs], "method": "mpmath (visoka preciznost)"}
    H = 0.02 * (span or 1.0)
    xs = np.linspace(x0 - H, x0 + H, 4 * n + 5)
    ys = np.array([f1(t) for t in xs])
    cs = np.polynomial.polynomial.polyfit(xs - x0, ys, n)
    return {"coeffs": [float(c) for c in cs], "method": f"fit na ±{H:.3g} (procjena)"}


def bisect_root(g, a: float, b: float, tol: float = 1e-13, cancel=None) -> Optional[float]:
    ga, gb = g(a), g(b)
    if not (F.is_finite(ga) and F.is_finite(gb)) or ga * gb > 0:
        return None
    for _ in range(200):
        _check(cancel)
        m = 0.5 * (a + b)
        gm = g(m)
        if ga * gm <= 0:
            b, gb = m, gm
        else:
            a, ga = m, gm
        if b - a < tol:
            break
    return 0.5 * (a + b)


def certify_root(f: F.Function, a: float, b: float, params=None) -> dict:
    """Strict interval certificate: f(a), f(b) of opposite sign AS INTERVALS (so
    rounding cannot fake it) ⇒ a root in [a, b]; f' as an interval over [a, b]
    not containing 0 ⇒ the root is unique. Typed real functions only."""
    from mpmath import iv
    fi = F.interval(f, params)
    fa, fb = fi(iv.mpf(a)), fi(iv.mpf(b))
    sign_ok = (fa.b < 0 < fb.a) or (fb.b < 0 < fa.a)
    out = {"interval": [a, b], "f(a)": [float(fa.a), float(fa.b)],
           "f(b)": [float(fb.a), float(fb.b)], "root_exists": bool(sign_ok), "unique": None}
    try:                                            # derivative enclosure by a symbolic f'
        import sympy as sp
        from . import fexpr as FX
        xs = sp.Symbol("x")
        p = {**F.PARAMS, **(params or {})}
        expr = FX.to_sympy(FX.parse(f.expr, {"x"} | set(F.PARAMS)),
                           {"x": xs, **{k: sp.Rational(str(v)) for k, v in p.items()}})
        dtxt = str(sp.diff(expr, xs)).replace("**", "^")
        df = F.Function("d", "d", "real", dtxt.replace("^", "**"))
        dfi = F.interval(df, params)(iv.mpf([a, b]))
        out["f'([a,b])"] = [float(dfi.a), float(dfi.b)]
        out["unique"] = bool(dfi.a > 0 or dfi.b < 0)
    except Exception as e:                          # noqa: BLE001 — uniqueness not shown
        out["unique_note"] = f"jedinstvenost nije dokazana: {str(e)[:80]}"
    out["certified"] = bool(sign_ok)
    return out


def exact_roots(f: F.Function, a: float, b: float, params=None) -> dict:
    """Exact algebraic roots in [a, b] when f is algebraic (sympy)."""
    import sympy as sp
    from . import fexpr as FX
    xs = sp.Symbol("x", real=True)
    p = {**F.PARAMS, **(params or {})}
    expr = FX.to_sympy(FX.parse(f.expr, {"x"} | set(F.PARAMS)),
                       {"x": xs, **{k: sp.Rational(str(v)) for k, v in p.items()}})
    expr = sp.together(expr)
    num = sp.numer(expr)
    if not num.is_polynomial(xs):
        return {"exact": False, "note": "funkcija nije algebarska — samo numerički korijen"}
    poly = sp.Poly(sp.expand(num), xs)
    roots = [r for r in sp.real_roots(poly) if a - 1e-12 <= float(r) <= b + 1e-12]
    return {"exact": True, "polynomial": str(poly.as_expr()),
            "roots": [{"exact": str(r), "value": float(r)} for r in roots]}


def area_between(f1, g1, a: float, b: float, cancel=None) -> dict:
    import mpmath as mp
    _check(cancel)
    val = mp.quad(lambda t: f1(float(t)) - g1(float(t)), [a, b])
    return {"area": float(val), "a": a, "b": b}


def grad_hess(f2, x: float, y: float, h: float = 1e-4) -> dict:
    fx = (f2(x + h, y) - f2(x - h, y)) / (2 * h)
    fy = (f2(x, y + h) - f2(x, y - h)) / (2 * h)
    fxx = (f2(x + h, y) - 2 * f2(x, y) + f2(x - h, y)) / h ** 2
    fyy = (f2(x, y + h) - 2 * f2(x, y) + f2(x, y - h)) / h ** 2
    fxy = (f2(x + h, y + h) - f2(x + h, y - h) - f2(x - h, y + h) + f2(x - h, y - h)) / (4 * h * h)
    det = fxx * fyy - fxy ** 2
    kind = ("minimum" if det > 0 and fxx > 0 else "maksimum" if det > 0 and fxx < 0
            else "sedlo" if det < 0 else "neodlučeno")
    return {"grad": [fx, fy], "hess": [[fxx, fxy], [fxy, fyy]], "det": det, "kind": kind,
            "sharpness": float(min(abs(np.linalg.eigvalsh([[fxx, fxy], [fxy, fyy]]))))}


# --------------------------------------------------------------------------- #
# "sve o tački"
# --------------------------------------------------------------------------- #
def nearest_target(y: float) -> tuple:
    name = min(F.TARGETS, key=lambda k: abs(F.TARGETS[k] - y))
    return name, F.TARGETS[name], abs(F.TARGETS[name] - y)


def point_info(f: F.Function, x: float, others: list = (), params=None,
               yspan: float = 1.0) -> dict:
    """Everything known about the point on f at x (real/builtin functions)."""
    f1 = _f1(f, params)
    y = f1(x)
    tol = max(abs(yspan), 1e-9) * 0.01
    info = {"x": x, "y": y, "function": f.label, "kind": f.kind, "level": f.level,
            "card": f.card, "meaning": f.meaning, "params": {**F.PARAMS, **(params or {})},
            "flags": [], "targets": {}}
    if not F.is_finite(y):
        info["flags"].append("izvan domena (NaN/∞)")
        return info
    if abs(y) < tol:
        info["flags"].append("nula")
    if f.builtin in B_FUNCS or f.kind == "real":
        info["targets"] = {k: y - v for k, v in F.TARGETS.items()}
        n, v, dist = nearest_target(y)
        info["nearest_target"] = {"name": n, "value": v, "distance": dist}
        for wname, wv in WALL_LINES["B"].items():
            if abs(y - wv) < tol:
                info["flags"].append(wname)
    for wname, wv in WALL_LINES["x"].items():
        if f.builtin in B_FUNCS and abs(x - wv) < 0.01 * max(1e-9, f.domain[1] - f.domain[0]):
            info["flags"].append(wname)
    if f.builtin in E_FUNCS:
        info["flags"].append("E ≤ 0: metoda prolazi" if y <= 0 else "E > 0: metoda NE prolazi")
    inter = []
    for g in others:
        if g.id == f.id or g.kind not in ("real", "builtin") or not g.visible:
            continue
        try:
            gy = _f1(g, params)(x)
        except Exception:                               # noqa: BLE001
            continue
        if F.is_finite(gy) and abs(gy - y) < tol:
            inter.append(g.label)
    if inter:
        info["flags"].append("presjek sa: " + ", ".join(inter))
    # cheap things right away
    try:
        info["dydx"] = derivative(f1, x)
        if abs(info["dydx"]) < 1e-3 * max(1.0, abs(yspan)):
            info["flags"].append("stacionarna tačka (moguć optimum)")
    except Exception:                                   # noqa: BLE001
        pass
    return info


def point_info_xy(f: F.Function, x: float, y: float, params=None, z=None) -> dict:
    """"Sve o tački" for a point that is not y = f(x): a path point (ℓ, B), a polar
    point, or a point of a surface over a parameter plane (with its value z)."""
    info = {"x": x, "y": y, "function": f.label, "kind": F.shape(f), "level": f.level,
            "card": f.card, "meaning": f.meaning, "params": {**F.PARAMS, **(params or {})},
            "flags": [], "targets": {}}
    if F.shape(f) == "path":
        info["targets"] = {k: y - v for k, v in F.TARGETS.items()}
        n, v, dist = nearest_target(y)
        info["nearest_target"] = {"name": n, "value": v, "distance": dist}
        if y < 0.87 - 1e-12:
            info["flags"].append("ispod zida B ≥ 0.87")
        if x > 0.2:
            info["flags"].append("preko zida ℓ ≤ 1/5")
    if z is not None:
        info["z"] = z
        if f.builtin == "vmax_lk":
            info["flags"].append("E ≤ 0: metoda prolazi" if z <= 0 else "E > 0: metoda NE prolazi")
            info["B_if_boundary"] = 11 / 12 - x / 4
        try:
            fn = F.numeric(f, params)
            gh = grad_hess(lambda a, b: float(np.asarray(fn(np.array([a]), np.array([b])))[0]), x, y)
            info["grad"], info["hess_kind"] = gh["grad"], gh["kind"]
        except Exception:                               # noqa: BLE001
            pass
    return info


# --------------------------------------------------------------------------- #
# offers — at most 4 that fit the kind of point
# --------------------------------------------------------------------------- #
def offers(f: F.Function, info: dict, others: list = ()) -> list:
    c = F.eval_cost(f)
    o = []

    def add(key, title, evals, why="", args=()):
        o.append({"key": key, "title": title, "args": list(args), "est_s": round(evals * c, 3),
                  "why": why, "ask": evals * c > CHEAP_S})
    flags = " ".join(info.get("flags", []))
    if "presjek" in flags:
        add("intersection", "tačan presjek (+ interval-certifikat)", 220, "tačka je presjek")
    if "nula" in flags:
        add("root", "tačan korijen (sympy) + interval-certifikat", 220, "vrijednost je ≈ 0")
    if "stacionarna" in flags:
        add("second", "drugi izvod — da li je optimum i koliko je oštar", 6, "f′ ≈ 0")
    if info.get("nearest_target") and f.builtin in B_FUNCS:
        add("to_target", "pomak parametra do cilja {0} (ili dokaz da ga zid sprečava)", 220,
            "tačka je blizu cilja", (info["nearest_target"]["name"],))
    if f.builtin in ("ext_t", "ext_w"):
        add("mission", "kuda proširenje pomjera B — bliže ili dalje od cilja", 4,
            "misija 1: srž pitanja")
    add("tangent", "izvod i tangenta", 4)
    add("second", "drugi izvod (konkavnost)", 6)
    add("taylor", "Taylorov polinom (stepen 4)", 9)
    if any(g.id != f.id and g.kind in ("real", "builtin") and g.visible for g in others):
        add("area", "osjenčana površina između dvije funkcije („rezerva“)", 300)
    seen, out = set(), []
    for x in o:
        if x["key"] not in seen:
            seen.add(x["key"])
            out.append(x)
    for x in out[MAX_OFFERS:]:
        x["more"] = True                                # under "više…"
    return out


# --------------------------------------------------------------------------- #
# the calculations
# --------------------------------------------------------------------------- #
def calculate(key: str, f: F.Function, x, others: list = (), params=None,
              cancel: Optional[threading.Event] = None, other_id: str = "",
              extra: Optional[dict] = None) -> dict:
    if key.startswith("c_"):
        return _calculate_complex(key, f, complex(x), params, cancel, extra or {})
    f1 = _f1(f, params)
    lo, hi = float(f.domain[0]), float(f.domain[1])
    span = hi - lo or 1.0
    _check(cancel)
    if key == "tangent":
        d = derivative(f1, x)
        y = f1(x)
        return {"dydx": d, "tangent": f"y = {y:.12g} + {d:.12g}·(x − {x:.12g})"}
    if key == "second":
        d2 = derivative(f1, x, h=1e-3, order=2)
        return {"d2ydx2": d2, "concavity": "konveksna (∪)" if d2 > 0 else "konkavna (∩)" if d2 < 0
                else "prevojna?", "optimum": ("maksimum" if d2 < 0 else "minimum" if d2 > 0 else "?")
                + " ako je f′ = 0"}
    if key == "taylor":
        fp = F.precise(f, params) if f.kind == "real" else None
        t = taylor(f1, x, span=span, fprec=fp)
        cs = t["coeffs"]
        return {"x0": x, **t,
                "poly": " + ".join(f"{c:.6g}·(x−{x:.6g})^{k}" for k, c in enumerate(cs))}
    if key in ("root", "intersection"):
        g = None
        if key == "intersection":
            g = next((o for o in others if o.id != f.id and o.visible and o.kind in ("real", "builtin")
                      and (not other_id or o.id == other_id)), None)
        h = (lambda t: f1(t) - _f1(g, params)(t)) if g else f1
        a, b = max(lo, x - 0.05 * span), min(hi, x + 0.05 * span)
        r = bisect_root(h, a, b, cancel=cancel)
        out = {"root": r, "with": g.label if g else None, "bracket": [a, b]}
        if r is not None and f.kind == "real" and g is None:
            w = 1e-9 * max(1.0, abs(r))
            try:
                out["certificate"] = certify_root(f, r - w, r + w, params)
            except Exception as e:                      # noqa: BLE001
                out["certificate"] = {"certified": False, "note": str(e)[:120]}
            try:
                out["exact"] = exact_roots(f, a, b, params)
            except Exception as e:                      # noqa: BLE001
                out["exact"] = {"exact": False, "note": str(e)[:120]}
        elif r is not None:
            out["certificate"] = {"certified": False,
                                  "note": "certifikat samo za upisane izraze (ugrađene funkcije su kod)"}
        return out
    if key == "to_target":
        n, v, _ = nearest_target(f1(x))
        r = bisect_root(lambda t: f1(t) - v, lo, hi, cancel=cancel)
        if r is None:
            ys = f1(lo), f1(hi)
            return {"target": n, "reached": False,
                    "why": f"na domenu [{lo:g}, {hi:g}] f ide od {ys[0]:.6g} do {ys[1]:.6g} — cilj {n} "
                           "nije dostignut (zid domena ili metode)"}
        return {"target": n, "reached": True, "param_at_target": r, "shift": r - x}
    if key == "area":
        g = next((o for o in others if o.id != f.id and o.visible and o.kind in ("real", "builtin")
                  and (not other_id or o.id == other_id)), None)
        if g is None:
            return {"error": "treba druga funkcija"}
        a, b = max(lo, float(g.domain[0])), min(hi, float(g.domain[1]))   # common domain
        if b <= a:
            return {"error": "funkcije nemaju zajednički domen"}
        return {**area_between(f1, _f1(g, params), a, b, cancel), "with": g.label, "with_id": g.id}
    if key == "mission":
        d = derivative(f1, x, h=1e-3 * span)
        n, v, dist = nearest_target(f1(x))
        toward = (d < 0) if f1(x) > v else (d > 0)
        return {"dB/dparam": d, "nearest_target": n, "distance": dist,
                "direction": "bliže" if toward else "dalje" if abs(d) > 1e-12 else "isto"}
    raise ValueError(f"nepoznat račun '{key}'")


def _calculate_complex(key, f, s, params, cancel, extra) -> dict:
    from . import complex_ as CX
    fp = F.precise(f, params)
    fc = lambda z: complex(fp(z))                         # noqa: E731
    _check(cancel)
    if key == "c_deriv":
        d = CX.cderivative(fc, s)
        return {"s": str(s), "f'(s)": str(d), "|f'|": abs(d)}
    if key == "c_zeros":
        r = extra.get("rect") or [[s.real - 0.5, s.imag - 5], [s.real + 0.5, s.imag + 5]]
        fast = F.numeric(f, params)
        g = lambda z: complex(np.asarray(fast(np.array([z])))[0])   # noqa: E731
        out = CX.zeros_in_rect(g, complex(*r[0]), complex(*r[1]), cancel=cancel)
        out["note"] = ("broj nula minus broj polova unutra (princip argumenta)"
                       + ("" if out["sure"] else " — NESIGURNO: faza skače i posle profinjenja"))
        return out
    if key == "c_residue":
        res = CX.residue(fc, s, r=float(extra.get("r", 1e-3)))
        return {"s": str(s), "residue": str(res), "|res|": abs(res)}
    raise ValueError(f"nepoznat račun '{key}'")


def offers_complex(f: F.Function, rect) -> list:
    c = F.eval_cost(f)
    out = [{"key": "c_deriv", "title": "kompleksni izvod f′(s)", "args": [], "est_s": round(4 * c, 3)},
           {"key": "c_zeros", "title": "broj nula u vidljivom pravougaoniku (princip argumenta)",
            "args": [], "est_s": round(900 * c, 3), "extra": {"rect": rect}},
           {"key": "c_residue", "title": "rezidua u tački (kružni integral)", "args": [],
            "est_s": round(256 * c * 8, 3)}]
    for o in out:
        o["ask"] = o["est_s"] > CHEAP_S
        o["why"] = ""
    return out


# --------------------------------------------------------------------------- #
# background queue with "prekini", cache, record in SHARED_LIB
# --------------------------------------------------------------------------- #
_SCHEMA = ["""CREATE TABLE IF NOT EXISTS graph_runs (
    id TEXT PRIMARY KEY, ts REAL NOT NULL, calc TEXT NOT NULL, function TEXT NOT NULL,
    point TEXT NOT NULL, params TEXT NOT NULL, result TEXT NOT NULL,
    seconds REAL NOT NULL, oznaka TEXT NOT NULL DEFAULT 'NAŠE-NERECENZIRANO', operator TEXT)"""]


def _key(calc: str, f: F.Function, x, params, other_id="", extra=None) -> str:
    blob = json.dumps([calc, f.to_dict(), repr(x), params or {}, other_id, extra or {}],
                      sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:24]


def cached(calc: str, f: F.Function, x, params=None, other_id="", extra=None) -> Optional[dict]:
    from ..shared_lib.store import store
    store().ensure(_SCHEMA)
    r = store().rows("SELECT result FROM graph_runs WHERE id=?",
                     (_key(calc, f, x, params, other_id, extra),))
    return json.loads(r[0]["result"]) if r else None


def record(calc: str, f: F.Function, x, params, result: dict, seconds: float, other_id="",
           extra=None) -> str:
    from ..shared_lib.store import store
    from ..shared_lib import operator as OP
    from ..core import journal as J
    store().ensure(_SCHEMA)
    rid = _key(calc, f, x, params, other_id, extra)
    store().execute("INSERT OR REPLACE INTO graph_runs(id,ts,calc,function,point,params,result,"
                    "seconds,operator) VALUES (?,?,?,?,?,?,?,?,?)",
                    (rid, time.time(), calc, json.dumps(f.to_dict(), ensure_ascii=False),
                     json.dumps(str(x) if isinstance(x, complex) else x, default=str),
                     json.dumps(params or {}, default=str),
                     json.dumps(result, ensure_ascii=False, default=str), seconds, OP.current()))
    J.log(J.LAB, OP.current() or "grafovi", {"event": "graph_calc", "id": rid, "calc": calc,
                                             "function": f.label, "seconds": round(seconds, 3),
                                             "label": LABEL}, subject=rid, verdict="computed")
    return rid


class Jobs:
    """One job at a time in a background thread; each can be cancelled."""

    def __init__(self):
        self._q: "queue.Queue" = queue.Queue()
        self._cancel: dict = {}
        self._t: Optional[threading.Thread] = None
        self.results: dict = {}
        self._lock = threading.Lock()

    def submit(self, calc: str, f: F.Function, x, others=(), params=None, other_id: str = "",
               done: Optional[Callable[[str, dict], None]] = None, extra=None) -> str:
        hit = cached(calc, f, x, params, other_id, extra)
        jid = _key(calc, f, x, params, other_id, extra)
        if hit is not None:
            self.results[jid] = {"status": "keš", **hit}
            if done:
                done(jid, self.results[jid])
            return jid
        ev = threading.Event()
        self._cancel[jid] = ev
        self.results[jid] = {"status": "čeka"}
        self._q.put((jid, calc, f, x, list(others), params, other_id, done, ev, extra))
        with self._lock:
            if self._t is None or not self._t.is_alive():
                self._t = threading.Thread(target=self._run, name="grafovi-jobs", daemon=True)
                self._t.start()
        return jid

    def cancel(self, jid: str) -> None:
        ev = self._cancel.get(jid)
        if ev:
            ev.set()

    def cancel_all(self) -> None:
        for ev in self._cancel.values():
            ev.set()

    def _run(self):
        while True:
            try:
                jid, calc, f, x, others, params, other_id, done, ev, extra = self._q.get(timeout=0.5)
            except queue.Empty:
                return
            self.results[jid] = {"status": "radi"}
            t0 = time.perf_counter()
            try:
                if ev.is_set():
                    raise Cancelled("prekinuto")
                _ram_ok()
                res = calculate(calc, f, x, others, params, ev, other_id, extra)
                secs = time.perf_counter() - t0
                record(calc, f, x, params, res, secs, other_id, extra)
                self.results[jid] = {"status": "gotovo", "seconds": secs, **res}
            except Cancelled as e:
                self.results[jid] = {"status": "prekinuto", "why": str(e)}
            except Exception as e:                      # noqa: BLE001
                self.results[jid] = {"status": "greška", "why": f"{type(e).__name__}: {e}"[:300]}
            self._cancel.pop(jid, None)
            if done:
                try:
                    done(jid, self.results[jid])
                except Exception:                       # noqa: BLE001
                    pass

    def wait(self, jid: str, timeout: float = 60.0) -> dict:
        t0 = time.time()
        while time.time() - t0 < timeout:
            st = self.results.get(jid, {}).get("status")
            if st not in ("čeka", "radi"):
                return self.results[jid]
            time.sleep(0.02)
        return self.results.get(jid, {})


def _ram_ok() -> None:
    try:
        from ..llm import limits as LIM
        if LIM.free_ram_gb() < 0.5:
            raise Cancelled("premalo slobodne memorije (limiter)")
    except ImportError:
        pass


JOBS = Jobs()
