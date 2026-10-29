"""Item 33c: "⚙ Podešavanje" in the tab menu opens the setup and returns."""
from PySide6.QtWidgets import QApplication


def test_setup_tab_opens_setup_and_returns(operator, monkeypatch):
    app = QApplication.instance() or QApplication([])
    from pse_r.gui.main_window import MainWindow
    w = MainWindow()
    opened = []
    monkeypatch.setattr(MainWindow, "open_setup", lambda self: opened.append(1))
    w.tabs.setCurrentWidget(w._tab(w.tab_missions))
    before = w.tabs.currentIndex()
    w.tabs.setCurrentIndex(w.tabs.count() - 1)
    assert opened == [1] and w.tabs.currentIndex() == before
    assert "Podešavanje" in w.tabs.tabText(w.tabs.count() - 1)
