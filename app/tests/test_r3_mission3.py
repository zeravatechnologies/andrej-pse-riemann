"""Round 3, item 32: mission 3 (the complex version). E with a complex δ: the method's
boundary is the zero of the discriminant of a quadratic numerator; |Im δ| is the margin."""
import numpy as np

from pse_r.methods import complexver as CV
from pse_r.methods import core as C


def test_numerator_is_quadratic_and_boundary_is_discriminant_zero():
    for fam, Ef in (("liu", C.E_liu), ("xs", C.E_xs)):
        o = C.optimum(Ef, 1 / 8)
        l = CV.l_from_discriminant(fam, o.b, o.l - 0.01, o.l + 0.002)
        assert abs(l - o.l) < 1e-10, fam
        (r1, r2), D = CV.roots(fam, o.b, o.l - 1e-4, 2 * C.Bof(o.l - 1e-4) - 1)
        assert D < 0 and abs(r1.imag) > 0 and abs(r1 - r2.conjugate()) < 1e-12   # passes: pair
        (s1, s2), D2 = CV.roots(fam, o.b, o.l + 1e-3, 2 * C.Bof(o.l + 1e-3) - 1)
        assert D2 > 0 and s1.imag == 0 == s2.imag                               # fails: two real
        k = 2 * C.Bof(o.l + 1e-3) - 1                    # E > 0 between the real roots
        mid = (s1.real + s2.real) / 2
        assert Ef(o.b, o.l + 1e-3, k, mid, 0.5) > 0


def test_margin_scales_like_square_root():
    r = CV.margin_curve("liu", n=41)
    assert 2.5 < r["c"] < 2.75
    o = r["l_star"]
    (a, _), _ = CV.roots("liu", r["b_star"], o - 1e-4, 2 * C.Bof(o - 1e-4) - 1)
    (b, _), _ = CV.roots("liu", r["b_star"], o - 1e-5, 2 * C.Bof(o - 1e-5) - 1)
    assert abs(abs(a.imag) / abs(b.imag) - np.sqrt(10)) < 0.05


def test_mission3_in_the_cycle_and_lab_records_a_step(operator):
    from pse_r.shared_lib import missions as MIS
    MIS.seed_first()
    MIS.seed_second()
    MIS.seed_third()
    m = MIS.get(MIS.THIRD_ID)
    assert m and int(m["goal"]) == 1 and "σ*(γ) ≡ B" in m["steps"][0]["outcome"]
    assert MIS.THIRD_ID in [x["id"] for x in MIS.all_missions()]
    n0 = len(m["steps"])
    from pse_r.lab import runner as LR
    res = LR.run("qrh_complex", {"family": 0, "n": 21}, make_card=False)
    assert res["record"]["plots"] and res["record"]["numbers"]["razlika"] < 1e-10
    assert "novo B: ne" in MIS.get(MIS.THIRD_ID)["steps"][-1]["outcome"]
    assert len(MIS.get(MIS.THIRD_ID)["steps"]) == n0 + 1


def test_grafovi_builtin_complex_delta():
    from pse_r.graphs import functions as F
    f = F.builtin("E_delta_c")
    assert F.shape(f) == "complex"
    o = C.optimum(C.E_liu, 1 / 8)
    p = {"l": o.l + 1e-3, "b": o.b}
    (s1, _), _ = CV.roots("liu", o.b, p["l"], 2 * C.Bof(p["l"]) - 1)
    assert abs(F.precise(f, p)(s1)) < 1e-9                  # the root really is a zero
