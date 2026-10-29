"""Round 3, item 29 step 6: Lab plots are interactive (same navigation as Grafovi),
and the PNG stays — every run still writes it, and "Sačuvaj PNG" saves the view."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication


def test_lab_run_is_interactive_and_png_stays(tmp_path):
    app = QApplication.instance() or QApplication([])
    from pse_r.lab import runner as LR
    res = LR.run("z_curve", {"t0": 10.0, "t1": 30.0, "samples": 200}, make_card=False)
    rec = res["record"]
    assert rec["plot_specs"] and rec["plots"]                  # specs for the view + the PNG
    assert (Path(res["dir"]) / rec["plots"][0]).exists()
    from pse_r.gui.lab_plot import LabPlotView
    v = LabPlotView()
    v.resize(900, 600)
    v.show()
    v.show_record(rec, Path(res["dir"]))
    app.processEvents()
    c = v.canvas
    assert v.stack.currentWidget() is c and c.ax.get_lines()
    x0 = c.ax.get_xlim()
    c.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Right, Qt.NoModifier))
    assert c.ax.get_xlim()[0] > x0[0]
    c.pan(0, 0.1)
    c.zoom(0.5)
    c.home()
    assert c.ax.get_xlim() == x0
    p = v.save("png", str(tmp_path / "pogled.png"))
    assert Path(p).stat().st_size > 1000
    q = v.save_csv(str(tmp_path / "pogled.csv"))
    assert Path(q).read_text(encoding="utf-8").startswith("series,x,y")


def test_old_run_without_specs_falls_back_to_png(tmp_path):
    app = QApplication.instance() or QApplication([])
    from pse_r.lab import runner as LR
    res = LR.run("qrh_line", {"points": 20}, make_card=False)
    rec = dict(res["record"])
    rec.pop("plot_specs")                                       # like a run from before step 6
    from pse_r.gui.lab_plot import LabPlotView
    v = LabPlotView()
    v.show_record(rec, Path(res["dir"]))
    app.processEvents()
    assert v.stack.currentIndex() == 1 and not v.png.pixmap().isNull()
