"""Faza 6d P3 (plan 33f, agreement rules 28–31): the mission agent."""
import json

import pytest

from pse_r.shared_lib import mission_agent as MA
from pse_r.shared_lib import missions as MIS
from pse_r.shared_lib import pse_registry as PR
from pse_r.shared_lib.store import store


def _fake(replies):
    it = iter(replies)
    return lambda system, ctx, msgs: next(it)


@pytest.fixture
def mission(operator):
    PR.reset_for_tests()
    mid = MIS.seed_first()
    store().propose("arxiv-paper", "rad", {"ref": "arxiv:2699.00001", "title": "A QRH paper",
                                           "mission": mid, "abstract": "zero-free region"},
                    "arxiv")
    MA.install_hooks()
    return mid


def test_papers_of_a_mission(mission):
    refs = [p["ref"] for p in MA.papers(mission)]
    assert "arxiv:2699.00001" in refs


def test_without_ai_it_says_so(mission, monkeypatch):
    from pse_r.llm import selection as SEL
    monkeypatch.setattr(SEL, "get_main", lambda: None)
    with pytest.raises(MA.NoAI):
        MA.start(mission, [])


def test_at_most_three_questions():
    t = MA.trim_questions("Vidim vezu. Prvo? Drugo? Treće? Četvrto? Peto?")
    assert t.count("?") == 3


def test_conversation_moves_skeptic_and_save(mission, monkeypatch):
    from pse_r.llm import selection as SEL
    monkeypatch.setattr(SEL, "skeptic_available", lambda: True)
    conv = MA.start(mission, ["arxiv:2699.00001"],
                    ask=_fake(["Rad daje zid ℓ ≈ 0.1668. Koji cilj? Koji rad prvo?"]),
                    ask_skeptic=lambda *a: '[{"prigovor": "p", "razlog": "r"}]')
    assert [t.who for t in conv.turns][:2] == ["agent", "skeptik"]   # claim → skeptic
    MA.say(conv, "Cilj 1.", ask=_fake(["Dobro, idemo redom."]),
           ask_skeptic=lambda *a: "[]")
    assert conv.turns[-1].who == "agent"                              # no claim → no skeptic
    assert MA.LABEL in open(conv.path, encoding="utf-8").read()
    u = PR.pse().unit(MA.agent_key(mission))
    assert u.core.open_lifespan and u.uses_model
    n = store().rows("SELECT COUNT(*) n FROM pse_moves WHERE unit_id=?", (u.unit_id,))[0]["n"]
    assert n >= 2                                                     # every move measured
    assert MIS.snapshot(mission)["razgovori-o-misiji"]["razgovori"] >= 1


def test_conclusion_becomes_separate_queue_items(mission):
    conv = MA.start(mission, [], ask=_fake(["Šta te zanima"]))
    out = json.dumps({"korak": ["pročitati rad A"], "pitanje": ["da li zid zavisi od κ"],
                      "ideja": [], "cilj": 2, "metoda": None})
    pids = MA.conclude(conv, ask=_fake([out]))
    assert len(pids) == 3
    items = [store().get(p) for p in pids]
    assert {i["payload"]["type"] for i in items} == {"korak", "pitanje", "cilj"}
    n0 = len(MIS.get(mission)["steps"])
    store().decide(pids[0], True)
    assert len(MIS.get(mission)["steps"]) == n0 + 1                   # only after approval


def test_full_text_only_for_arxiv(mission):
    conv = MA.start(mission, [], ask=_fake(["ok"]))
    msg = MA.load_fulltext(conv, "doi:10.1/x")
    assert "samo za arXiv" in msg
    txt = MA.load_fulltext(conv, "arxiv:2699.00001", fetch=lambda r: "PUNI TEKST")
    assert txt == "PUNI TEKST" and conv.fulltext["arxiv:2699.00001"]


def test_closing_the_mission_ends_its_agent(mission):
    MA.start(mission, [], ask=_fake(["ok"]))
    out = MA.close_mission(mission, "test")
    assert out["ended"]
    h = store().rows("SELECT reason FROM pse_handover WHERE agent=?", (MA.agent_key(mission),))
    assert h and "zatvorena" in h[-1]["reason"]
    assert MIS.get(mission)["state"] == "zatvorena"
