"""
Safe expressions for the Grafovi tab (round 3, item 29).

The operator types functions ("Funkcije" panel): real f(x), complex f(s), a
surface f(x, y), a parametric curve. That text must never do anything but math,
so — exactly like methods/expr.py — it is parsed with `ast` and checked node by
node against a whitelist BEFORE it is compiled, and compiled with no builtins.

Differences from methods/expr.py (which guards method packs):
  * a wider function set (trigonometric, ζ, Hardy Z, Γ, Re/Im/arg …);
  * any exponent is allowed, but every literal is turned into a float/complex
    first, so `10**10**10` is an overflow (inf), never a Python big integer that
    eats the machine;
  * three back ends from the same validated tree: numpy (fast grids),
    mpmath (precise points, complex), mpmath.iv (interval certificates).
"""
from __future__ import annotations

import ast
from typing import Callable, Iterable

MAX_LEN = 2000
MAX_NODES = 1500
CONSTS = {"pi", "e", "i", "I"}
# name → (numpy, mpmath, interval) implementation names; None = not available there
FUNCS = {
    "sin": 1, "cos": 1, "tan": 1, "exp": 1, "log": 1, "sqrt": 1, "abs": 1,
    "atan": 1, "asin": 1, "acos": 1, "sinh": 1, "cosh": 1, "tanh": 1,
    "re": 1, "im": 1, "arg": 1, "conj": 1, "floor": 1,
    "zeta": 1, "Z": 1, "gamma": 1, "min": 2, "max": 2,
}
SPECIAL = {"zeta", "Z", "gamma"}          # mpmath only (numpy back end vectorises them)


class FExprError(Exception):
    pass


_BIN = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_UN = (ast.USub, ast.UAdd)


def _check(node, names: set, counter: list) -> None:
    counter[0] += 1
    if counter[0] > MAX_NODES:
        raise FExprError("izraz je prevelik")
    if isinstance(node, ast.Expression):
        return _check(node.body, names, counter)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float, complex)):
            raise FExprError(f"dozvoljeni su samo brojevi, ne {node.value!r}")
        return
    if isinstance(node, ast.Name):
        if node.id not in names and node.id not in CONSTS:
            raise FExprError(f"nepoznato ime '{node.id}' (dozvoljeno: {sorted(names | CONSTS)})")
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, _BIN):
            raise FExprError(f"operacija {type(node.op).__name__} nije dozvoljena")
        _check(node.left, names, counter)
        return _check(node.right, names, counter)
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _UN):
            raise FExprError(f"operacija {type(node.op).__name__} nije dozvoljena")
        return _check(node.operand, names, counter)
    if isinstance(node, ast.Call):
        if not (isinstance(node.func, ast.Name) and node.func.id in FUNCS):
            raise FExprError("dozvoljene funkcije: " + ", ".join(sorted(FUNCS)))
        if node.keywords:
            raise FExprError("imenovani argumenti nisu dozvoljeni")
        want = FUNCS[node.func.id]
        if len(node.args) != want:
            raise FExprError(f"{node.func.id} prima {want} argument(a)")
        for a in node.args:
            _check(a, names, counter)
        return
    raise FExprError(f"konstrukcija {type(node).__name__} nije dozvoljena")


class _Floatify(ast.NodeTransformer):
    """Every literal becomes a float (or complex): no Python big-int arithmetic."""

    def visit_Constant(self, node):
        v = node.value
        return ast.copy_location(ast.Constant(complex(v) if isinstance(v, complex) else float(v)), node)


def parse(text: str, names: Iterable[str]) -> ast.Expression:
    if not isinstance(text, str) or not text.strip():
        raise FExprError("prazan izraz")
    if len(text) > MAX_LEN:
        raise FExprError("izraz je predugačak")
    src = text.strip().replace("^", "**").replace("·", "*").replace("−", "-")
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError as e:
        raise FExprError(f"sintaksa: {e.msg}") from e
    _check(tree, set(names), [0])
    return ast.fix_missing_locations(_Floatify().visit(tree))


def names_in(tree) -> set:
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} - CONSTS


def _fp():
    import mpmath
    return mpmath.fp


def _ns_numpy():
    import numpy as np

    def vec(fn):
        v = np.vectorize(lambda z: complex(fn(z)), otypes=[complex])

        def f(a):
            out = v(a)
            return out.real if np.all(np.abs(out.imag) < 1e-300) and not np.iscomplexobj(a) else out
        return f
    return {"sin": np.sin, "cos": np.cos, "tan": np.tan, "exp": np.exp,
            "log": lambda a: np.log(a + 0j) if np.iscomplexobj(a) else np.log(a),
            "sqrt": lambda a: np.sqrt(a + 0j) if np.iscomplexobj(a) else np.sqrt(a),
            "abs": np.abs, "atan": np.arctan, "asin": np.arcsin, "acos": np.arccos,
            "sinh": np.sinh, "cosh": np.cosh, "tanh": np.tanh, "re": np.real, "im": np.imag,
            "arg": np.angle, "conj": np.conj, "floor": np.floor,
            "min": np.minimum, "max": np.maximum,
            # grids use mpmath's float back end (~0.09 ms per ζ value, 8× the mp one);
            # precise points go through the mpmath back end below
            "zeta": vec(lambda z: _fp().zeta(z)),
            "Z": np.vectorize(lambda t: float(_fp().siegelz(float(t))), otypes=[float]),
            "gamma": vec(lambda z: _fp().gamma(z)),
            "pi": np.pi, "e": np.e, "i": 1j, "I": 1j}


def _ns_mp():
    import mpmath as mp
    return {"sin": mp.sin, "cos": mp.cos, "tan": mp.tan, "exp": mp.exp, "log": mp.log,
            "sqrt": mp.sqrt, "abs": mp.fabs, "atan": mp.atan, "asin": mp.asin, "acos": mp.acos,
            "sinh": mp.sinh, "cosh": mp.cosh, "tanh": mp.tanh, "re": mp.re, "im": mp.im,
            "arg": mp.arg, "conj": mp.conj, "floor": mp.floor, "min": min, "max": max,
            "zeta": mp.zeta, "Z": mp.siegelz, "gamma": mp.gamma,
            "pi": mp.pi, "e": mp.e, "i": mp.mpc(0, 1), "I": mp.mpc(0, 1)}


def _ns_iv():
    import mpmath as mp
    iv = mp.iv
    ns = {"abs": abs, "pi": iv.pi, "e": iv.e}
    for name in ("sin", "cos", "tan", "exp", "log", "sqrt", "atan", "sinh", "cosh"):
        fn = getattr(iv, name, None)
        if fn is not None:                      # mpmath.iv lacks some (e.g. atan)
            ns[name] = fn
    return ns


def compile_fn(tree: ast.Expression, argnames: list, backend: str = "numpy") -> Callable:
    """Compile a VALIDATED tree into f(*args) on the chosen back end."""
    if backend == "iv":
        used = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call)}
        bad = used - set(_ns_iv())
        if bad or any(isinstance(n, ast.Name) and n.id in ("i", "I") for n in ast.walk(tree)):
            raise FExprError("interval-certifikat nije dostupan za: " + ", ".join(sorted(bad) or ["i"]))
        ns = _ns_iv()
    else:
        ns = _ns_numpy() if backend == "numpy" else _ns_mp()
    src = f"lambda {', '.join(argnames)}: ({ast.unparse(tree.body)})"
    code = compile(src, "<grafovi>", "eval")
    return eval(code, {"__builtins__": {}, **ns}, {})       # noqa: S307 — whitelisted tree


def to_sympy(tree: ast.Expression, symbols: dict):
    """Validated tree → sympy (floats become exact rationals) — for exact roots."""
    import sympy as sp
    from fractions import Fraction
    fn = {"sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "exp": sp.exp, "log": sp.log,
          "sqrt": sp.sqrt, "abs": sp.Abs, "atan": sp.atan, "asin": sp.asin, "acos": sp.acos,
          "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh, "re": sp.re, "im": sp.im,
          "arg": sp.arg, "conj": sp.conjugate, "floor": sp.floor, "min": sp.Min, "max": sp.Max,
          "zeta": sp.zeta, "gamma": sp.gamma}
    cst = {"pi": sp.pi, "e": sp.E, "i": sp.I, "I": sp.I}

    def go(n):
        if isinstance(n, ast.Expression):
            return go(n.body)
        if isinstance(n, ast.Constant):
            v = n.value
            if isinstance(v, complex):
                return sp.Rational(Fraction(repr(v.real))) + sp.I * sp.Rational(Fraction(repr(v.imag)))
            return sp.Rational(Fraction(repr(v)))           # 0.1 → 1/10 exactly
        if isinstance(n, ast.Name):
            return symbols.get(n.id) if n.id in symbols else cst[n.id]
        if isinstance(n, ast.UnaryOp):
            v = go(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp):
            a, b = go(n.left), go(n.right)
            op = n.op
            return (a + b if isinstance(op, ast.Add) else a - b if isinstance(op, ast.Sub)
                    else a * b if isinstance(op, ast.Mult) else a / b if isinstance(op, ast.Div)
                    else a ** b)
        if isinstance(n, ast.Call):
            if n.func.id not in fn:
                raise FExprError(f"{n.func.id} nema tačan (sympy) oblik")
            return fn[n.func.id](*[go(a) for a in n.args])
        raise FExprError(f"ne mogu u sympy: {type(n).__name__}")
    return go(tree)
