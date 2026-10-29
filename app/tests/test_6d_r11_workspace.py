"""Rule 42–46 in the GUI (round 3, R11): the Missions tab is a workspace —
cards on the left, a click starts the agent, the paper strip folds open, the
memory is reviewed beside „Gdje si stao“, and a `mission:` link opens it."""
import json
import time

import pytest

from pse_r.shared_lib import mission_agent as MA
from pse_r.shared_lib import missions as MIS
from pse_r.shared_lib import pse_registry as PR
from pse_r.shared_lib.store import store


@pytest.fixture
def app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


@pytest.fixture
def ws(app, operator, monkeypatch):
    PR.reset_for_tests()
    mid = MIS.new_mission(f"Radni prostor {time.time_ns()}", "Pitanje?")
    store().propose("arxiv-paper", "rad", {"ref": "arxiv:2699.00011", "title": "Rad A",
                                           "mission": mid, "abstract": "a"}, "arxiv")
    monkeypatch.setattr(MA, "_require_ai", lambda: None)
    calls = []

    def fake(conv, extra="", ask=None):
        calls.append(extra)
        if extra.startswith("Sesija"):
            return json.dumps({"odluceno": ["Idemo dalje."], "sljedeci": ["Lema 3."]})
        return "Vidim jedan rad. Gdje smo stali?"
    monkeypatch.setattr(MA, "_ask", fake)
    from pse_r.gui.qrh_tabs import MissionsTab
    tab = MissionsTab()
    tab.resize(1000, 700)
    tab.show()
    return tab, mid, calls, app


def _idle(tab, app, secs=5.0):
    end = time.time() + secs
    while time.time() < end:
        app.processEvents()
        if not tab.talk._busy and not tab.talk.state.text():
            return
        time.sleep(0.02)


def test_cards_and_click_starts_agent(ws):
    tab, mid, calls, app = ws
    ids = [tab.list.item(i).data(256) for i in range(tab.list.count())]
    assert mid in ids
    item = tab.list.item(ids.index(mid))
    tab._clicked(item)                                   # rule 43
    _idle(tab, app)
    assert tab.talk.conv is not None and tab.talk.conv.mid == mid
    assert calls and calls[0] == MA.FIRST
    assert "1 od 1" in tab.talk.b_papers.text() or "1 of 1" in tab.talk.b_papers.text()
    tab.talk.b_papers.setChecked(True)
    assert tab.talk.papers.isVisible()


def test_end_session_proposes_memory_and_review_saves(ws):
    tab, mid, calls, app = ws
    tab.open_mission(mid)
    _idle(tab, app)
    tab.talk.input.setPlainText("Lema 3.")
    tab.talk._say()
    _idle(tab, app)
    tab.talk.end_session()
    _idle(tab, app)
    mem = MA.memory(mid)
    assert mem and not mem["reviewed"] and len(mem["items"]) == 2
    tab._memory_ready(mid)
    assert tab.memory.list.count() == 2
    from PySide6.QtCore import Qt
    tab.memory.list.item(0).setCheckState(Qt.Unchecked)  # untick the first
    tab.memory._save()
    mem = MA.memory(mid)
    assert mem["reviewed"] and [i["text"] for i in mem["items"]] == ["Lema 3."]


def test_switching_mission_ends_the_session(ws):
    tab, mid, calls, app = ws
    other = MIS.new_mission(f"Druga {time.time_ns()}", "?")
    tab.open_mission(mid)
    _idle(tab, app)
    tab.talk.input.setPlainText("x")
    tab.talk._say()
    _idle(tab, app)
    tab.open_mission(other)                              # rule 45: switch → memory proposal
    _idle(tab, app)
    _idle(tab, app)
    assert MA.memory(mid) is not None
    assert tab.talk.mid == other and mid not in tab.talk._convs


def test_unknown_mission_link(ws):
    tab, mid, calls, app = ws
    assert tab.open_mission("misija-ne-postoji") is False


def test_main_window_mission_link(app, operator):
    from pse_r.gui.main_window import MainWindow
    mid = MIS.new_mission(f"Link {time.time_ns()}", "?")
    w = MainWindow()
    seen = []
    w.tab_missions.open_mission = lambda m: seen.append(m) or True
    w.open_card(f"mission:{mid}")
    assert seen == [mid] and w.tabs.currentWidget() is w._tab(w.tab_missions)
    w.close()
