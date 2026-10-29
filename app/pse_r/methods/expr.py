"""
Safe arithmetic expressions for method packs.

A method pack carries its exponent system as TEXT written by whoever extracted
it from a paper (a model, or a person). That text must never be able to do
anything but arithmetic. So it is parsed with `ast` and checked node by node
against a whitelist BEFORE anything is compiled:

    allowed   numbers, + − × ÷ ** (numeric exponent only), unary ±, parentheses,
              names from the declared variable set, calls to sqrt / log / exp /
              abs / min / max, and — for walls only — ONE comparison < > <= >=
    refused   everything else: attributes, subscripts, lambdas, strings,
              comprehensions, keyword args, boolean logic, assignments, …

Only a tree that passed the whitelist is compiled, with no builtins in scope, so
the compiled function can reach nothing but the math it was given.

The same validated tree is also turned into a sympy expression (exact rationals
for decimal literals), which is what the exact-polynomial check uses.
"""
from __future__ import annotations

import ast
import math
from fractions import Fraction
from typing import Callable, Iterable

MAX_LEN = 4000
MAX_NODES = 2000
FUNCS = {"sqrt": math.sqrt, "log": math.log, "exp": math.exp, "abs": abs,
         "min": min, "max": max}


class ExprError(Exception):
    pass


_BIN = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow)
_UN = (ast.USub, ast.UAdd)
_CMP = (ast.Lt, ast.Gt, ast.LtE, ast.GtE)


def _check(node: ast.AST, names: set, allow_compare: bool, counter: list) -> None:
    counter[0] += 1
    if counter[0] > MAX_NODES:
        raise ExprError("izraz je prevelik")
    if isinstance(node, ast.Expression):
        return _check(node.body, names, allow_compare, counter)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ExprError(f"dozvoljeni su samo brojevi, ne {node.value!r}")
        return
    if isinstance(node, ast.Name):
        if node.id not in names:
            raise ExprError(f"nepoznato ime '{node.id}' (dozvoljeno: {sorted(names)})")
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, _BIN):
            raise ExprError(f"operacija {type(node.op).__name__} nije dozvoljena")
        if isinstance(node.op, ast.Pow):
            ex = node.right
            if isinstance(ex, ast.UnaryOp) and isinstance(ex.op, _UN):
                ex = ex.operand
            if not (isinstance(ex, ast.Constant) and isinstance(ex.value, (int, float))
                    and abs(ex.value) <= 16):
                raise ExprError("stepen mora biti broj (|n| ≤ 16)")
        _check(node.left, names, False, counter)
        return _check(node.right, names, False, counter)
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _UN):
            raise ExprError(f"operacija {type(node.op).__name__} nije dozvoljena")
        return _check(node.operand, names, False, counter)
    if isinstance(node, ast.Call):
        if not (isinstance(node.func, ast.Name) and node.func.id in FUNCS):
            raise ExprError("dozvoljene funkcije: " + ", ".join(sorted(FUNCS)))
        if node.keywords:
            raise ExprError("imenovani argumenti nisu dozvoljeni")
        for a in node.args:
            _check(a, names, False, counter)
        return
    if isinstance(node, ast.Compare) and allow_compare:
        if len(node.ops) != 1 or not isinstance(node.ops[0], _CMP):
            raise ExprError("zid mora biti jedno poređenje: a < b, a > b, a <= b, a >= b")
        _check(node.left, names, False, counter)
        return _check(node.comparators[0], names, False, counter)
    raise ExprError(f"konstrukcija {type(node).__name__} nije dozvoljena")


def parse(text: str, names: Iterable[str], allow_compare: bool = False) -> ast.Expression:
    if not isinstance(text, str) or not text.strip():
        raise ExprError("prazan izraz")
    if len(text) > MAX_LEN:
        raise ExprError("izraz je predugačak")
    try:
        tree = ast.parse(text.strip().replace("^", "**"), mode="eval")
    except SyntaxError as e:
        raise ExprError(f"sintaksa: {e.msg}") from e
    _check(tree, set(names) | set(FUNCS), allow_compare, [0])
    return tree


def compile_fn(tree: ast.Expression, argnames: list[str]) -> Callable:
    """Compile a VALIDATED tree into f(*args). No builtins are reachable."""
    src = f"lambda {', '.join(argnames)}: ({ast.unparse(tree.body)})"
    code = compile(src, "<method-pack>", "eval")
    return eval(code, {"__builtins__": {}, **FUNCS}, {})       # noqa: S307 — whitelisted tree


def wall_margin(tree: ast.Expression) -> ast.Expression:
    """Turn 'a > b' into the expression (a - b) (positive = satisfied)."""
    cmp = tree.body
    if not isinstance(cmp, ast.Compare):
        raise ExprError("zid mora biti poređenje")
    a, b = cmp.left, cmp.comparators[0]
    if isinstance(cmp.ops[0], (ast.Lt, ast.LtE)):
        a, b = b, a
    return ast.Expression(body=ast.BinOp(left=a, op=ast.Sub(), right=b))


def to_sympy(tree: ast.Expression, symbols: dict):
    """Validated tree -> sympy expression; decimal literals become exact rationals."""
    import sympy as sp
    sfun = {"sqrt": sp.sqrt, "log": sp.log, "exp": sp.exp, "abs": sp.Abs,
            "min": sp.Min, "max": sp.Max}

    def go(n):
        if isinstance(n, ast.Expression):
            return go(n.body)
        if isinstance(n, ast.Constant):
            return sp.Rational(Fraction(str(n.value)))
        if isinstance(n, ast.Name):
            return symbols[n.id]
        if isinstance(n, ast.UnaryOp):
            v = go(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        if isinstance(n, ast.BinOp):
            l, r = go(n.left), go(n.right)
            op = n.op
            if isinstance(op, ast.Add):
                return l + r
            if isinstance(op, ast.Sub):
                return l - r
            if isinstance(op, ast.Mult):
                return l * r
            if isinstance(op, ast.Div):
                return l / r
            return l ** r
        if isinstance(n, ast.Call):
            return sfun[n.func.id](*[go(a) for a in n.args])
        raise ExprError(f"ne mogu u sympy: {type(n).__name__}")
    return go(tree)
