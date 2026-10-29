"""⤢ / ⤡ on every split panel where it makes sense (Andrej, 2026-10-26)."""
from PySide6.QtWidgets import QApplication, QPushButton, QSplitter


def test_every_split_panel_can_fill_its_place(operator):
    app = QApplication.instance() or QApplication([])
    from pse_r.gui.main_window import MainWindow
    w = MainWindow()
    w.resize(1600, 900)
    w.show()
    app.processEvents()
    checked = 0
    for sp in w.findChildren(QSplitter):
        if sp.objectName() in ("main", "grafovi"):
            continue
        for i in range(sp.count()):
            pane = sp.widget(i)
            btns = [b for b in pane.findChildren(QPushButton, "expandBtn") if b.parent() is pane]
            if isinstance(pane, QSplitter) or pane is w.tab_lab.plot:
                assert not btns                          # nested splitter / own ⤢: no duplicate
                continue
            assert len(btns) == 1, (sp.objectName(), i)
            b = btns[0]
            others = [sp.widget(j) for j in range(sp.count()) if j != i]
            vis0 = [o.isHidden() for o in others]
            b.click()
            assert all(o.isHidden() for o in others) and b.text() == "⤡"
            b.click()
            assert [o.isHidden() for o in others] == vis0 and b.text() == "⤢"
            checked += 1
    assert checked >= 8
    f1, f2 = w.tab_overview._cards
    assert [b for b in f1.findChildren(QPushButton, "expandBtn")]
