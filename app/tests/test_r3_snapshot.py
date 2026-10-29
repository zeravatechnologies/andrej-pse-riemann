"""Round 3, item 29b: a screenshot at any moment (F12 / Shift+F12 / 📷), to a chosen
folder, path in the status bar, file name in the journal. Plus: the command palette
opens the right tabs again (indexes were stale after new tabs)."""
from PySide6.QtWidgets import QApplication


def _win(tmp_path, operator):
    app = QApplication.instance() or QApplication([])
    from pse_r.gui import snapshot as SNAP
    SNAP.set_folder(str(tmp_path / "snimci"))
    from pse_r.gui.main_window import MainWindow
    w = MainWindow()
    w.show()
    app.processEvents()
    return app, w


def test_three_ways_to_take_a_screenshot(tmp_path, operator):
    app, w = _win(tmp_path, operator)
    p1 = w.snapshot("main")
    w.tabs.setCurrentWidget(w._tab(w.tab_grafovi))
    app.processEvents()
    p2 = w.snapshot("tab")
    p3 = w.snapshot("window")
    for p in (p1, p2, p3):
        assert p and p.exists() and p.stat().st_size > 1000 and p.parent == tmp_path / "snimci"
    assert "Grafovi" in p2.name and len({p1, p2, p3}) == 3
    assert str(p3) in w.statusBar().currentMessage()
    from pse_r.core import journal as J
    files = [e["payload"].get("file") for e in J.journal().tail(50, J.SYSTEM)
             if e["payload"].get("event") == "screenshot"]
    assert p3.name in files and p1.name in files            # the NAME, not the picture


def test_palette_opens_the_right_tabs(tmp_path, operator):
    app, w = _win(tmp_path, operator)
    import inspect
    src = inspect.getsource(type(w))
    assert "setCurrentIndex(3)" not in src and "setCurrentIndex(6)" not in src
