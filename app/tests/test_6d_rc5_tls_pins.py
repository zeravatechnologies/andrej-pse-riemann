"""Andrej (live test rc5): TLS pins are learned on first contact — the operator
must be told so explicitly, and can re-scan them from the menu."""
import pytest

from pse_r import settings as S
from pse_r.guardian import tls as TLS
from pse_r.guardian.unit import guardian
from pse_r.core import journal as J


@pytest.fixture
def store(operator, tmp_path, monkeypatch):
    ps = TLS.PinStore(tmp_path / "pins.json")
    monkeypatch.setattr(TLS, "_PINS", ps)
    ps.remember("api.ok.test", ["old-ok"], "home")
    ps.remember("api.down.test", ["old-down"], "home")
    yield ps
    for h in ("api.ok.test", "api.down.test"):
        guardian().release(h, "test")


def _probe(store):
    def probe(host):
        if host == "api.down.test":
            raise OSError("mreža nedostupna")
        assert not store.pins(host)               # forgotten before the new contact
        store.remember(host, ["new-ok"], "home")
        return "pinned"
    return probe


def test_rescan_learns_again_and_keeps_old_when_unreachable(store):
    res = TLS.rescan(["api.ok.test", "api.down.test"], probe=_probe(store))
    by = {r["host"]: r for r in res}
    assert by["api.ok.test"]["ok"] and store.pins("api.ok.test") == ["new-ok"]
    assert not by["api.down.test"]["ok"] and store.pins("api.down.test") == ["old-down"]


def test_rescan_releases_quarantine_only_on_success(store):
    guardian().quarantine("api.ok.test", "pin mismatch (test)")
    guardian().quarantine("api.down.test", "pin mismatch (test)")
    TLS.rescan(["api.ok.test", "api.down.test"], probe=_probe(store))
    assert not guardian().is_quarantined("api.ok.test")
    assert guardian().is_quarantined("api.down.test")      # still unknown: stays blocked


def test_rescan_needs_operator(tmp_path, monkeypatch):
    from pse_r.shared_lib import operator as OP
    monkeypatch.setattr(TLS, "_PINS", TLS.PinStore(tmp_path / "p.json"))
    with pytest.raises(OP.NoOperator):
        TLS.rescan(["x.test"], probe=lambda h: "pinned")


def test_notice_shown_until_acknowledged_and_menu_entry(operator):
    from PySide6.QtWidgets import QApplication, QMessageBox
    app = QApplication.instance() or QApplication([])
    from pse_r.gui.main_window import MainWindow
    S.set_(TLS.NOTICE_KEY, False)
    w = MainWindow()
    acts = [a.text() for m in w.menuBar().findChildren(type(w.menuBar().addMenu("x")))
            for a in m.actions()]
    assert any("TLS" in t and "pinove" in t for t in acts)
    w.tls_notice()
    box = w._tls_box
    assert box.isVisible() and "prvom kontaktu" in box.text()
    ok = [b for b in box.buttons() if b.text() in ("Razumijem", "I understand")][0]
    ok.click()
    app.processEvents()
    assert S.get(TLS.NOTICE_KEY) is True
    w._tls_box = None
    w.tls_notice()                                       # acknowledged: not again
    assert w._tls_box is None
    w.tls_notice(force=True)                             # always from Pomoć
    assert w._tls_box is not None
    w._tls_box.close()
    w.close()
