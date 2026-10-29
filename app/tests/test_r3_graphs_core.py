"""Round 3, item 29 (step 1): the Grafovi computing core — safe expressions,
the project's functions, "sve o tački", offers with estimates, calculations,
the background queue with cancel, cache and the SHARED_LIB record."""
import threading

import numpy as np
import pytest

from pse_r.graphs import compute as C
from pse_r.graphs import fexpr as FX
from pse_r.graphs import functions as F


@pytest.mark.parametrize("bad", ["__import__('os')", "x.__class__", "[x for x in y]",
                                 "lambda: 1", "'a'", "open('f')", "x if x else 1"])
def test_only_math_gets_through(bad):
    with pytest.raises(FX.FExprError):
        FX.parse(bad, {"x"})


def test_huge_numbers_are_nan_not_a_hang():
    f = F.Function("p", "p", "real", "10**10**10")
    assert np.isnan(F.numeric(f)(np.array([1.0, 2.0]))).all()
    assert np.isnan(F.numeric(F.Function("q", "q", "real", "log(x)"))(np.array([-1.0]))[0])


def test_builtins_reproduce_the_methods():
    B = F.numeric(F.builtin("B_line"))
    assert abs(B(np.array([1 / 6]))[0] - 7 / 8) < 1e-15
    e = F.numeric(F.builtin("E_liu"))(np.linspace(1 / 8, 5 / 6, 41))
    assert e.max() <= 1e-9 and e.max() > -1e-3               # optimum: max_δ E ≈ 0
    assert F.builtin("E_liu").level == F.RAD and F.builtin("vmax_liu").level == F.OURS


def test_complex_and_parametric():
    z = F.precise(F.Function("z", "z", "complex", "zeta(s)"))(0.5 + 14.134725141734693j)
    assert abs(z) < 1e-9
    x, y = F.numeric(F.Function("c", "c", "parametric", "cos(u); sin(u)"))(np.array([0.0]))
    assert x[0] == 1 and y[0] == 0


def test_point_info_knows_target_and_intersection():
    B, line = F.builtin("B_line"), F.Function("h", "7/8", "real", "0*x + 7/8", domain=[0, 0.3])
    info = C.point_info(B, 1 / 6, [B, line], yspan=0.1)
    assert info["nearest_target"]["name"] == "7/8" and info["nearest_target"]["distance"] < 1e-12
    assert any("presjek" in fl for fl in info["flags"]) and info["level"] == F.RAD
    offs = C.offers(B, info, [B, line])
    assert offs[0]["key"] == "intersection" and sum(not o.get("more") for o in offs) <= 4


def test_exact_root_with_interval_certificate():
    g = F.Function("g", "g", "real", "x**3 - 2", domain=[0, 2])
    r = C.calculate("root", g, 1.26)
    assert abs(r["root"] - 2 ** (1 / 3)) < 1e-12
    assert r["certificate"]["certified"] and r["certificate"]["unique"]
    assert r["exact"]["roots"][0]["exact"] == "2**(1/3)"


def test_liu_cubic_root_is_B_star():
    from pse_r.methods import core as MC
    poly, B_star = MC.exact_polynomial("liu")
    f = F.Function("liu", "Liu kubni", "real", str(poly.as_expr()).replace("B", "x"),
                   domain=[0.87, 0.88])
    r = C.calculate("root", f, 0.875)
    assert abs(r["root"] - B_star) < 1e-12 and r["certificate"]["certified"]
    assert r["exact"]["exact"] and abs(r["exact"]["roots"][0]["value"] - B_star) < 1e-14


def test_taylor_area_target_mission():
    g = F.Function("g", "g", "real", "x**3 - 2", domain=[0, 2])
    assert np.allclose(C.calculate("taylor", g, 1.0)["coeffs"], [-1, 3, 3, 1, 0], atol=1e-10)
    h = F.Function("h", "h", "real", "x**2", domain=[0, 1])
    assert abs(C.calculate("area", g, 0.5, [g, h])["area"] + 25 / 12) < 1e-10
    t = C.calculate("to_target", F.builtin("B_line"), 0.17)
    assert t["reached"] and abs(t["param_at_target"] - 1 / 6) < 1e-10
    far = C.calculate("to_target", F.Function("k", "k", "real", "0.9 + 0*x", domain=[0, 1]), 0.5)
    assert not far["reached"]


def test_jobs_cache_record_and_cancel(operator):
    g = F.Function("g2", "g2", "real", "x**2 + 1", domain=[0, 1])
    jid = C.JOBS.submit("second", g, 0.5)
    assert C.JOBS.wait(jid)["status"] == "gotovo"
    assert C.JOBS.results[C.JOBS.submit("second", g, 0.5)]["status"] == "keš"
    from pse_r.shared_lib.store import store
    row = store().rows("SELECT oznaka, operator FROM graph_runs WHERE id=?", (jid,))[0]
    assert row["oznaka"] == "NAŠE-NERECENZIRANO" and row["operator"] == operator
    ev = threading.Event()
    ev.set()
    with pytest.raises(C.Cancelled):
        C.bisect_root(lambda x: x - 0.3, 0, 1, cancel=ev)


def test_expensive_builtin_is_only_offered():
    f = F.builtin("ext_t")
    offs = C.offers(f, {"flags": []}, [f])
    assert all(o["ask"] for o in offs) and all(o["est_s"] > C.CHEAP_S for o in offs)
