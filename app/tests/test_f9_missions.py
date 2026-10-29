"""F9 — missions and the arXiv → door → mission pipeline (project srž)."""
import pytest

from pse_r.shared_lib import missions as MIS
from pse_r.shared_lib.store import store
from pse_r.methods import door as DOOR
from pse_r.methods import arxiv as AX


def test_first_mission_is_the_continuous_transformation_question():
    mid = MIS.seed_first()
    assert mid == MIS.FIRST_ID
    m = MIS.get(mid)
    assert m and "transformacij" in m["question"].lower()
    assert MIS.seed_first() == mid             # idempotent
    # a brand-new mission starts with no frontier (no evidence yet)
    fresh = MIS.create("m-fresh", "T", "Q?", "start")
    assert MIS.get(fresh)["best_B"] is None


def test_mission_is_a_fact_layer_view(operator):
    from pse_r.shared_lib import views as V
    MIS.seed_first()
    s = V.schema()
    assert "missions" in s and "mission_steps" in s
    r = V.query("SELECT id, question FROM missions WHERE id=?", (MIS.FIRST_ID,))
    assert r["rows"] and MIS.FIRST_ID == r["rows"][0][0]


def test_steps_record_closer_and_move_the_frontier(operator):
    mid = MIS.create("m2", "Test", "Pitanje?", "start", best_B=None)
    MIS.record_method(mid, "liu", 0.874957019420)
    m = MIS.get(mid)
    assert abs(m["best_B"] - 0.874957019420) < 1e-12
    assert len(m["steps"]) == 1 and "prva tačka" in m["steps"][0]["outcome"]

    MIS.record_method(mid, "xs", 0.874886647040)       # lower → closer
    m = MIS.get(mid)
    assert abs(m["best_B"] - 0.874886647040) < 1e-12
    assert m["steps"][1]["outcome"].startswith("bliže")

    MIS.record_method(mid, "worse", 0.90)              # higher → farther, frontier holds
    m = MIS.get(mid)
    assert abs(m["best_B"] - 0.874886647040) < 1e-12
    assert m["steps"][2]["outcome"].startswith("dalje")


def test_arxiv_recipe_goes_through_the_door_and_updates_the_mission(operator):
    DOOR.install_hooks()
    mid = MIS.create("m3", "Transformacija", "Pitanje?", "start")
    # a real recipe (Liu) reproduces → queued, linked to the mission
    out = AX.propose_from_recipe("arxiv:2610.12234", "liu", 0.874957019420,
                                 proposer="model:claude", dlo=1e-6, mission_id=mid,
                                 name="liu-f9")
    assert out["reproduced"] and out["pid"]
    assert MIS.get(mid)["best_B"] is None              # not yet — waits for operator
    store().decide(out["pid"], True)                   # operator confirms
    m = MIS.get(mid)
    assert m["best_B"] is not None and abs(m["best_B"] - 0.874957019420) < 1e-7
    assert m["steps"] and "liu-f9" in m["steps"][0]["action"]


def test_arxiv_bogus_recipe_is_refused_and_mission_untouched(operator):
    DOOR.install_hooks()
    mid = MIS.create("m4", "Transformacija", "Pitanje?", "start")
    out = AX.propose_from_recipe("arxiv:9999.99999", "liu", 0.5,
                                 proposer="model:claude", dlo=1e-6, mission_id=mid)
    assert out["reproduced"] is False and out["pid"] is None
    assert MIS.get(mid)["best_B"] is None
    assert MIS.get(mid)["steps"] == []


def test_watch_is_offline_safe():
    # No network in the test environment — must return a list, never raise.
    assert isinstance(AX.watch(max_results=3), list)
