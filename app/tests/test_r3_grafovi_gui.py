"""Round 3, item 29 (step 2): the Grafovi tab — three panels, moving the view
up/down/left/right (keys, buttons, drag), zoom, "sve o tački", offers, CSV."""
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from pse_r.graphs import functions as F


def _tab():
    app = QApplication.instance() or QApplication([])
    from pse_r.gui.grafovi import GrafoviTab
    t = GrafoviTab()
    t.resize(1400, 800)
    t.show()
    app.processEvents()
    return app, t


def test_pan_in_all_four_directions_and_zoom():
    app, t = _tab()
    c = t.canvas
    x0, y0 = c.ax.get_xlim(), c.ax.get_ylim()
    for key, check in ((Qt.Key_Right, lambda: c.ax.get_xlim()[0] > x0[0]),
                       (Qt.Key_Left, lambda: abs(c.ax.get_xlim()[0] - x0[0]) < 1e-12),
                       (Qt.Key_Up, lambda: c.ax.get_ylim()[0] > y0[0]),
                       (Qt.Key_Down, lambda: abs(c.ax.get_ylim()[0] - y0[0]) < 1e-12)):
        c.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress, key, Qt.NoModifier))
        assert check(), key
    w0 = c.ax.get_xlim()[1] - c.ax.get_xlim()[0]
    c.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Right, Qt.ShiftModifier))
    assert abs(c.ax.get_xlim()[0] - (x0[0] + 0.4 * w0)) < 1e-12           # Shift = bigger step
    c.zoom(0.5)
    assert abs((c.ax.get_xlim()[1] - c.ax.get_xlim()[0]) - w0 / 2) < 1e-12
    c.home()
    assert c.ax.get_xlim() == x0
    c.pan(0, -0.1)                                                       # the ▼ button
    assert c.ax.get_ylim()[0] < y0[0]


def test_click_shows_everything_about_the_point_and_offers():
    app, t = _tab()
    t.funcs.funcs = F.default_set()
    t.redraw()
    t._clicked("bi-B_line", 1 / 6)
    md = t.calc._info_md
    assert "7/8" in md and "RAD" in md and "izvor-openai-7-8" in md
    assert 1 <= t.calc.offers.count() <= 5                               # ≤ 4 + "više…"


def test_csv_has_the_curves_in_view(tmp_path):
    app, t = _tab()
    t.funcs.funcs = [F.builtin("B_line")]
    t.redraw()
    from pse_r.gui.grafovi import write_csv
    n = write_csv(tmp_path / "g.csv", t.canvas, t.funcs.funcs)
    rows = (tmp_path / "g.csv").read_text(encoding="utf-8").splitlines()
    assert n > 100 and rows[0] == "function,level,x,y" and "RAD" in rows[1]


def test_expand_hides_side_panels():
    app, t = _tab()
    t.toggle_expand()
    assert not t.funcs.isVisible() and not t.calc.isVisible()
    t.toggle_expand()
    assert t.funcs.isVisible() and t.calc.isVisible()


def test_each_of_the_three_panels_can_fill_the_tab():
    app, t = _tab()
    for name, btn in (("funcs", t.funcs.b_expand), ("graph", t.b_expand_graph),
                      ("calc", t.calc.b_expand)):
        btn.click()
        app.processEvents()
        assert [k for k, w in t._panels.items() if w.isVisible()] == [name]
        assert btn.text() == "⤡"
        btn.click()
        app.processEvents()
        assert all(w.isVisible() for w in t._panels.values())


def test_unsafe_function_is_refused_before_drawing():
    import pytest
    from pse_r.graphs import fexpr as FX
    with pytest.raises(FX.FExprError):
        F.validate(F.Function("x", "x", "real", "__import__('os').system('ls')"))
    app, t = _tab()
    t.funcs.funcs = [F.Function("u", "u", "real", "sin(30*x)/x", domain=[0, 1])]
    t.redraw()                                                           # NaN at 0 is a gap, not a crash
    xs, ys = t.canvas._lines["u"]
    assert np.isfinite(ys).sum() > 100


# ---- step 3: parametric, polar, vector field, shaded reserve ---------------- #
def _mode(app, t, m):
    t.mode.setCurrentIndex(t.mode.findData(m))
    app.processEvents()


def test_parametric_and_polar_are_drawn_and_clickable():
    app, t = _tab()
    t.funcs.funcs = [F.Function("c", "krug", "parametric", "cos(u); sin(u)", domain=[0, 6.283]),
                     F.Function("p", "kardioida", "polar", "1 + cos(th)")]
    t.redraw()
    _mode(app, t, "parametric")
    xs, ys = t.canvas._lines["c"]
    assert np.allclose(xs ** 2 + ys ** 2, 1)
    _mode(app, t, "polar")
    xs, ys = t.canvas._lines["p"]
    assert abs(xs.max() - 2) < 1e-3                         # r(0) = 2
    t._clicked_xy("p", 2.0, 0.0)
    assert "kardioida" in t.calc._info_md


def test_vector_field_over_l_kappa_finds_the_boundary():
    app, t = _tab()
    t.funcs.funcs = [F.builtin("vmax_lk")]
    t.redraw()
    _mode(app, t, "field")
    f, X, Y, Z = t.canvas._field
    row = Z[Z.shape[0] // 2]
    cross = X[0][np.where(np.diff(np.sign(row)) != 0)[0][0]]
    assert abs(cross - 0.1668) < 0.01                        # zero of max_δ E ≈ ℓ*
    t._clicked_xy("bi-vmax_lk", 0.15, 0.75)
    assert "prolazi" in t.calc._info_md and "Gradijent" in t.calc._info_md


def test_area_result_shades_the_reserve():
    app, t = _tab()
    t.funcs.funcs = [F.Function("a", "a", "real", "x", domain=[0, 1]),
                     F.Function("b", "b", "real", "x**2", domain=[0, 1])]
    t.redraw()
    t._clicked("a", 0.5)
    from pse_r.graphs import compute as C
    jid = C.JOBS.submit("area", t.funcs.funcs[0], 0.5, t.funcs.funcs, dict(t.funcs.params))
    res = C.JOBS.wait(jid)
    assert abs(res["area"] - 1 / 6) < 1e-12 and res["with_id"] == "b"
    t.calc._job_done("površina", dict(res))
    app.processEvents()
    assert t.canvas.shade == ("a", "b", 0.0, 1.0)


# ---- step 4: complex views, linked views, the low side + Δ slider ----------- #
def _zeta_tab():
    app, t = _tab()
    t.funcs.funcs = [F.Function("z", "ζ", "complex", "zeta(s)")]
    t.redraw()
    return app, t


def test_phase_portrait_click_knows_the_zero_and_counts_zeros():
    import time
    app, t = _zeta_tab()
    _mode(app, t, "complex")
    t0 = time.time()
    while t.canvas._cgrid is None and time.time() - t0 < 60:
        app.processEvents()
        time.sleep(0.05)
        t.canvas.redraw()
    assert t.canvas._cgrid is not None
    t._clicked_xy("z", 0.5, 14.1347)
    assert "14.1347251" in t.calc._info_md and "kritičnoj traci" in t.calc._info_md
    from pse_r.graphs import compute as C
    jid = C.JOBS.submit("c_zeros", t.funcs.funcs[0], complex(0.5, 14), extra={"rect": [[0.1, 1], [0.9, 30]]})
    r = C.JOBS.wait(jid)
    assert r["count"] == 3 and r["sure"]                      # γ = 14.13, 21.02, 25.01


def test_residue_of_zeta_at_one():
    from pse_r.graphs import compute as C
    r = C.calculate("c_residue", F.Function("z", "ζ", "complex", "zeta(s)"), 1 + 0j)
    assert abs(r["|res|"] - 1) < 1e-6


def test_slice_and_linked_follow_the_sliders():
    app, t = _zeta_tab()
    _mode(app, t, "slice")
    ts, absz = t.canvas._lines["z"]
    k = int(np.argmin(np.abs(ts - 14.134725)))
    assert absz[k] < 0.05                                     # |ζ(1/2 + iγ1)| ≈ 0
    _mode(app, t, "linked")
    from pse_r.graphs import complex_ as CX
    assert abs(t.canvas._sigma_star() - 7 / 8) < 1e-12           # low = 3/16 by default
    t.funcs.sliders["delta"].setValue(1000)                   # Δ = 0.3 → σ* > 1
    app.processEvents()
    assert t.canvas._sigma_star() > 1 and "nestala" in t.funcs.sigma.text()
    assert CX.sigma_star(3 / 16, 1 / 8) == 1.0                # Δ that 7/8 tolerates: 1/8


# ---- step 5: 3D, 4th dimension as colour, 5th as slider/animation, small multiples, parallel #
def _wait_bg(app, t, pred, sec=90):
    import time
    t0 = time.time()
    while not pred() and time.time() - t0 < sec:
        app.processEvents()
        time.sleep(0.05)
    t.canvas.redraw()
    app.processEvents()


def test_3d_rotates_and_shows_both_exponent_surfaces():
    app, t = _tab()
    t.funcs.funcs = [F.builtin("plane_sigma"), F.builtin("B_surface")]
    t.redraw()
    _mode(app, t, "3d")
    _wait_bg(app, t, lambda: sum(1 for k, v in t.canvas._coarse.items() if k[0] == "3D" and v is not None) >= 2)
    assert hasattr(t.canvas.ax, "view_init")
    az = t.canvas.ax.azim
    t.canvas.pan(0.1, 0)                                      # ▶ rotates in 3D
    assert abs(t.canvas.ax.azim - az - 9) < 1e-9
    labels = [l.get_label() for l in t.canvas.ax.get_lines()]
    assert any("σ = B(ℓ)" in s for s in labels)              # the crossing curve is drawn
    _mode(app, t, "cartesian")
    assert not hasattr(t.canvas.ax, "view_init")              # back to a 2D plot


def test_fifth_dimension_moves_the_boundary_in_small_multiples():
    app, t = _tab()
    t.funcs.funcs = [F.builtin("vmax_lk")]
    t.redraw()
    t.cb_anim.setCurrentIndex(t.cb_anim.findData("b"))
    _mode(app, t, "multiples")
    assert len(t.canvas.axes) == 6
    titles = [a.get_title() for a in t.canvas.axes]
    assert titles[0].startswith("b = 0") and titles[-1].startswith("b = 0.3")
    f = F.builtin("vmax_lk")
    z0 = F.numeric(f, {"b": 0.0})(np.array([0.165]), np.array([0.75]))[0]
    z1 = F.numeric(f, {"b": 0.1234})(np.array([0.165]), np.array([0.75]))[0]
    assert z0 != z1                                          # b really is a dimension now


def test_animation_steps_the_chosen_slider():
    app, t = _tab()
    t.cb_anim.setCurrentIndex(t.cb_anim.findData("w"))
    v0 = t.funcs.sliders["w"].value()
    t._anim_step()
    assert t.funcs.sliders["w"].value() == (v0 + 25) % 1001


def test_parallel_coordinates_have_all_methods():
    app, t = _tab()
    _mode(app, t, "parallel")
    _wait_bg(app, t, lambda: t.canvas._coarse.get(("PARALLEL",)) is not None, 180)
    data, N = t.canvas._par
    names = [d[0] for d in data]
    assert names[:2] == ["Liu", "Xu–Sang"] and len(names) == 8
    assert abs(data[0][1][3] - 0.874957019420) < 1e-9          # B of Liu
    assert N.min() >= 0 and N.max() <= 1
