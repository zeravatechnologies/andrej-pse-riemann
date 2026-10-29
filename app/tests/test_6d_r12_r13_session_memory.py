"""Rules 43–46 (round 3, R12–R13): the session starts on a click and reads the
right papers; „Zadaj da čita…“; the mission memory carries only what matters."""
import json

import pytest

from pse_r.shared_lib import mission_agent as MA
from pse_r.shared_lib import missions as MIS
from pse_r.shared_lib import pse_registry as PR
from pse_r.shared_lib.store import store


def _rec(replies, seen=None):
    it = iter(replies)

    def ask(system, ctx, msgs):
        if seen is not None:
            seen.append((ctx, [m.text for m in msgs]))
        return next(it)
    return ask


def _paper(mid, n):
    store().propose("arxiv-paper", f"rad {n}", {"ref": f"arxiv:2699.0000{n}", "title": f"Rad {n}",
                                                 "mission": mid, "abstract": f"sažetak {n}"},
                    "arxiv")


@pytest.fixture
def mission(operator):
    PR.reset_for_tests()
    mid = MIS.new_mission(f"Misija sesije {id(object())}", "Postoji li veza?")
    _paper(mid, 1)
    _paper(mid, 2)
    MA.install_hooks()
    return mid


def test_first_session_reads_all_then_last_plus_new(mission):
    seen = []
    conv = MA.start(mission, ask=_rec(["Vidim dva rada. Gdje si stao?"], seen))
    assert set(conv.refs) == {"arxiv:2699.00001", "arxiv:2699.00002"} and not conv.new_refs
    assert "Ovo je početak sesije" in seen[0][1][-1]          # rule 43 first message
    MA.set_refs(conv, ["arxiv:2699.00001"])                    # operator narrows the strip
    _paper(mission, 3)                                         # arrives between sessions
    conv2 = MA.start(mission, ask=_rec(["ok"], seen))
    assert conv2.refs == ["arxiv:2699.00001", "arxiv:2699.00003"]
    assert conv2.new_refs == ["arxiv:2699.00003"]
    assert 'novo="da"' in seen[-1][0]
    sp = {p["ref"]: p for p in MA.session_papers(mission)}
    assert not sp["arxiv:2699.00002"]["chosen"]


def test_assign_reading(mission, tmp_path):
    seen = []
    conv = MA.start(mission, ask=_rec(["ok", "pročitao"], seen))
    MA.assign(conv, "biljeska", "", text="Pazi na konstantu u lemi 3.")
    rep = tmp_path / "izvjestaj.md"
    rep.write_text("# Izvještaj\nfront B = 0.87", encoding="utf-8")
    MA.assign(conv, "izvjestaj", str(rep))
    MA.assign(conv, "puni", "arxiv:2699.00001", fetch=lambda r: "PUNI TEKST RADA")
    MA.say(conv, "Šta misliš?", ask=_rec(["pročitao"], seen))
    ctx = seen[-1][0]
    assert "Pazi na konstantu" in ctx and "front B = 0.87" in ctx and "PUNI TEKST RADA" in ctx
    assert sum(1 for t in conv.turns if t.who == "sistem" and "Zadato" in t.text) == 2
    with pytest.raises(ValueError):
        MA.assign(conv, "nešto", "x")


def test_memory_proposed_saved_unreviewed_then_reviewed(mission):
    conv = MA.start(mission, ask=_rec(["Šta je cilj?"]))
    assert MA.propose_memory(conv, ask=_rec([])) == []        # no talk, no memory
    MA.say(conv, "Cilj je zid nula.", ask=_rec(["Dogovoreno."]))
    out = json.dumps({"odluceno": ["Radimo na zidu nula."],
                      "utvrdjeno": [{"tekst": "Rad 1 daje ℓ ≈ 0.1668", "izvor": "[arxiv:2699.00001]"},
                                    "bez izvora"],
                      "otvoreno": ["Da li važi za sve T?"],
                      "sljedeci": ["Provjeri lemu 3."],
                      "pitanje": ["ignoriši"]})
    items = MA.propose_memory(conv, ask=_rec([out]))
    kinds = [i["kind"] for i in items]
    assert kinds.count("utvrdjeno") == 2 and "pitanje" not in kinds
    assert all(i["source"] for i in items if i["kind"] == "utvrdjeno")
    mem = MA.memory(mission)
    assert mem and not mem["reviewed"] and len(mem["items"]) == 5
    assert "nepregledano" in MA.memory_md(mission)
    # the operator keeps two, adds one
    keep = [items[0], items[-1], {"kind": "otvoreno", "text": "Moja dopuna."}]
    rec = MA.save_memory(mission, keep, reviewed=True)
    assert rec["reviewed"] and rec["by"] and len(MA.memory(mission)["items"]) == 3


def test_next_session_reads_memory_not_old_talk(mission):
    conv = MA.start(mission, ask=_rec(["prvo"]))
    MA.say(conv, "TAJNA_RECENICA_IZ_STAROG_RAZGOVORA", ask=_rec(["ok"]))
    MA.save_memory(mission, [{"kind": "odluceno", "text": "ODLUKA_ZA_PAMCENJE"}], reviewed=True)
    seen = []
    MA.start(mission, ask=_rec(["nastavljamo"], seen))
    ctx, msgs = seen[0]
    assert "ODLUKA_ZA_PAMCENJE" in ctx and "PAMĆENJE PROŠLE SESIJE" in ctx
    assert "TAJNA_RECENICA" not in ctx and not any("TAJNA_RECENICA" in m for m in msgs)
    # the old conversation is still saved in the results
    hist = store().kv_get(f"mission_conversations:{mission}", [])
    assert any("TAJNA_RECENICA" in open(p, encoding="utf-8").read() for p in hist)


def test_proof_claims_never_enter_memory(mission):
    conv = MA.start(mission, ask=_rec(["?"]))
    MA.say(conv, "x", ask=_rec(["y"]))
    out = json.dumps({"utvrdjeno": [{"tekst": "Ovim je dokazana Riemannova hipoteza.",
                                     "izvor": "razgovor"}], "odluceno": ["Nastavljamo."]})
    items = MA.propose_memory(conv, ask=_rec([out]))
    assert [i["text"] for i in items] == ["Nastavljamo."]
