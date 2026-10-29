"""Round 3, item 28a: one active mission, park "for later" with a note, the
"Gdje si stao" card, frozen by default / collecting quietly on request."""
import pytest

from pse_r.shared_lib import missions as MIS
from pse_r.shared_lib import runtime as RT
from pse_r.shared_lib.store import store


class _It:
    def __init__(self, ref, title):
        self.source_ref, self.title, self.abstract = ref, title, "abs"


def _both():
    """The test store is shared across the session: start from a clean turn state."""
    MIS.seed_first()
    MIS.seed_second()
    MIS.install_hooks()
    for k in (RT.ARXIV_KIND, MIS.SWITCH_KIND):
        for it in store().open_items(k):
            store().withdraw(it["id"], "test", "reset")
    store().kv_set(MIS.ACTIVE_KEY, None)
    store().execute("UPDATE missions SET parked=0, parked_at=NULL, parked_note=NULL, "
                    "parked_snapshot=NULL, background='freeze'")
    for m in MIS.all_missions():
        store().kv_set(f"mission_held:{m['id']}", [])


def test_switch_parks_previous_and_cycles(operator):
    _both()
    ids = [m["id"] for m in MIS.all_missions()]           # other tests may add missions
    assert MIS.active() == MIS.FIRST_ID == ids[0]
    card = MIS.set_active(MIS.SECOND_ID, "stao kod T za w=0.2")
    assert MIS.active() == MIS.SECOND_ID and card["mission"] == MIS.SECOND_ID
    assert MIS.is_parked(MIS.FIRST_ID) and not MIS.is_parked(MIS.SECOND_ID)
    while MIS.next_id() != MIS.FIRST_ID:                   # "Sljedeća" walks the cycle
        MIS.next_mission("dalje")
    back = MIS.next_mission("mapa: korak 3")
    assert MIS.active() == MIS.FIRST_ID                     # cycle wraps around
    assert back["note"] == "stao kod T za w=0.2"
    assert back["snapshot"]["n_steps"] == len(MIS.get(MIS.FIRST_ID)["steps"])
    assert not MIS.is_parked(MIS.FIRST_ID)


def test_only_operator_switches_app_only_proposes(operator):
    _both()
    pid = MIS.propose_switch(MIS.SECOND_ID, "nov rad o GL(2)")
    assert MIS.active() == MIS.FIRST_ID                         # proposal changes nothing
    store().decide(pid, True)
    assert MIS.active() == MIS.SECOND_ID
    from pse_r.shared_lib import operator as OP
    OP._reset_for_tests()
    with pytest.raises(Exception):
        MIS.set_active(MIS.FIRST_ID)


def test_frozen_by_default_then_quiet_collect(operator):
    _both()
    MIS.next_mission("pauza")                                   # mission 1 parked
    assert MIS.background(MIS.FIRST_ID) == MIS.FREEZE
    r = RT.arxiv_round(force=True, fetch=lambda: [_It("arxiv:2610.00001", "QRH A")])
    assert r.get("frozen") == MIS.FIRST_ID
    assert not store().open_items(RT.ARXIV_KIND)

    MIS.set_background(MIS.FIRST_ID, MIS.COLLECT)
    r = RT.arxiv_round(force=True, fetch=lambda: [_It("arxiv:2610.00002", "QRH B")])
    assert r["quiet"] and r["new"] == ["arxiv:2610.00002"]
    assert not store().open_items(RT.ARXIV_KIND)                # no badge / no queue noise
    card = MIS.set_active(MIS.FIRST_ID, "nazad")
    assert len(card["released"]) == 1                           # shown on resume
    assert len(store().open_items(RT.ARXIV_KIND)) == 1
    MIS.set_background(MIS.FIRST_ID, MIS.FREEZE)                # always reversible
    assert MIS.background(MIS.FIRST_ID) == MIS.FREEZE


def test_active_mission_watches_normally(operator):
    _both()
    r = RT.arxiv_round(force=True, fetch=lambda: [_It("arxiv:2610.00003", "QRH C")])
    assert not r["quiet"] and len(store().open_items(RT.ARXIV_KIND)) == 1
    assert "AKTIVNA MISIJA" in MIS.context_line()
