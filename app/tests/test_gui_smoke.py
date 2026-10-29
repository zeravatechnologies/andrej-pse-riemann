"""The main window must still build headless after every phase."""
def test_main_window_builds(operator):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from pse_r import config
    config.ensure_vault()
    from pse_r.vault import seed
    if not seed.is_seeded():
        seed.seed_all()
    from pse_r.gui.main_window import MainWindow
    w = MainWindow()
    assert "Test Operater" in w.lb_op.text()
    # the QRH tabs (F6) must build and refresh headless
    tab_names = [w.tabs.tabText(i) for i in range(w.tabs.count())]
    assert "Misije" in tab_names and "Čeka tvoju odluku" in tab_names
    w.tab_missions.refresh()
    w.tab_queue.refresh()
    w.refresh_status()
    assert "🤖" in w.lb_ai.text() or w.lb_ai.text() == ""   # pill present (or no model)
    w._timer.stop()
    w.close()
    w.deleteLater()
    app.processEvents()


def test_queue_approve_flow_builds(operator):
    """The queue tab's decide path is wired to the real store."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from pse_r.gui.qrh_tabs import QueueTab
    from pse_r.shared_lib.store import store
    pid = store().propose("test", "GUI probni red", {"x": 1}, "unit:test")
    q = QueueTab()
    q.refresh()
    # select our item in the tree (33d) and approve it through the tab
    assert q.select(pid)
    q._decide(True, ask=False)
    assert store().get(pid)["status"] == "approved"
    q.close()
    q.deleteLater()
    app.processEvents()
