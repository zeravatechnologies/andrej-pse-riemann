"""Rules 50–54 (after live test rc5): borderline needs a real swing; where a
swing is heading (B vs S, drift to C/N) is measured; no AI reader, no
attractor; open measures are re-read by the current rules, the operator decides."""
import json

import pytest

from pse_r.pse import constants as K
from pse_r.pse import measure as M
from pse_r.pse import swing as SW
from pse_r.pse import unit as U
from pse_r.shared_lib import pse_registry as R
from pse_r.shared_lib.store import store


# --------------------------------------------------------------- rules 50–52
def test_one_jump_is_not_borderline():
    r = SW.assess([30] * 6 + [45, 45], boundary_empty=True)       # voice#1, live test
    assert r.attractor == K.HEALTHY and r.turns == 0 and not r.tend


def test_growing_swing_is_borderline_and_heading_there():
    r = SW.assess([30, 32, 29, 33, 27, 35, 25, 37, 23, 40, 20])
    assert r.attractor == K.BORDERLINE and r.tend == K.BORDERLINE


def test_dying_swing_heads_to_schizoid_only_with_empty_boundary():
    xs = [30, 40, 22, 36, 26, 33, 28, 31, 29, 30.5, 29.6, 30.2]
    assert SW.assess(xs, boundary_empty=True).tend == K.SCHIZOID
    full = SW.assess(xs, boundary_empty=False)
    assert full.tend == "" and full.attractor == K.HEALTHY      # calming down, not B


def test_healthy_swing_has_no_tendency():
    r = SW.assess([30, 32, 29, 31, 30, 32, 29, 31, 30, 31, 29], boundary_empty=True)
    assert r.attractor == K.HEALTHY and not r.tend


def test_drift_heads_to_c_or_n():
    up = SW.assess([30 + 0.2 * i for i in range(12)])
    down = SW.assess([30 - 0.2 * i for i in range(12)])
    assert up.tend == K.CODEPENDENT and up.tend_in is not None
    assert down.tend == K.NARCISSISTIC


def test_plateau_still_turns():
    assert len(SW.turning_points([30, 45, 45, 30, 30, 44])) == 2


# --------------------------------------------------------------- rule 53
@pytest.fixture
def lib():
    R.reset_for_tests()
    lb = R.pse()
    yield lb
    for u in list(lb.units.values()):
        if getattr(u, "lab", False) and u.alive:
            lb.end(u, "kraj testa")
    M.set_reader(None)


def _model_unit(lib, name):
    key = f"lab-{name}"
    lib.define(R.AgentSpec(key, U.Mission("s", "a", "o"), 50, "lab", True))
    return lib.unit(key, lab=True)


def test_rules_only_words_give_no_attractor(lib, monkeypatch):
    M.set_reader(None)                                   # no AI reader
    u = _model_unit(lib, "noread")
    before = list(u.theta.attr_series)
    monkeypatch.setattr(M, "rule_floor", lambda *a, **k: {**{k2: 0.0 for k2 in M.SCHEMA},
                                                           "codependent": 1.0})
    res = lib.move(u, words="Naravno, evo.")
    assert res.attractor == K.NOT_ENOUGH                 # „?“: not read by an AI
    assert u.theta.attr_series == before                 # did not enter the attractor series
    assert "borderline" not in res.triggers and "attractor" not in res.triggers


def test_ai_read_words_enter_the_series(lib):
    M.set_reader(M.ReaderSpec(lambda p: json.dumps({k: 0.0 for k in M.SCHEMA}), "fake:1"))
    u = _model_unit(lib, "read")
    n = len(u.theta.attr_series)
    lib.move(u, words="Provjerio sam u izvoru [arxiv:1].")
    assert len(u.theta.attr_series) == n + 1


def test_attr_series_rebuilt_on_load(lib):
    M.set_reader(None)
    u = _model_unit(lib, "reload")
    lib.move(u, words="Naravno, evo.")                  # rules only
    lib.move(u, actions=[M.Action("rad", "f")])          # no words: counts
    uid = u.unit_id
    lib.units.pop(uid)
    row = lib.st.rows("SELECT * FROM pse_units WHERE unit_id=?", (uid,))[0]
    u2 = lib._load(row)
    assert len(u2.theta.series) == len(u2.theta.attr_series) + 1


# --------------------------------------------------------------- rule 54
def _old_measure(lib, u, hard=("borderline",)):
    u.restricted = True
    u.frozen, u.freeze_reason = True, "borderline"
    lib._save(u)
    return store().propose(R.QUEUE_MEASURE, f"Doktor: reset granice za {u.unit_id}",
                           {"unit": u.unit_id, "agent": u.agent, "measure": "reset-granice",
                            "finding": {"attractor": "B", "bad": True, "hard": list(hard),
                                        "measure": "reset-granice", "triggers": list(hard),
                                        "why": "tvrdi znaci: borderline"}}, "doktor")


def test_open_measure_reviewed_and_lifted_only_by_operator(lib, operator):
    u = _model_unit(lib, "review")
    mid = _old_measure(lib, u)
    pids = lib.review_open_measures()
    assert len(pids) == 1
    assert lib.review_open_measures() == []              # not twice
    assert u.frozen and u.restricted                     # nothing lifted on its own
    store().decide(pids[0], True)
    assert not [i for i in store().open_items(R.QUEUE_MEASURE) if i["id"] == mid]
    row = lib.st.rows("SELECT frozen, restricted FROM pse_units WHERE unit_id=?", (u.unit_id,))[0]
    assert not row["frozen"] and not row["restricted"]


def test_review_kept_when_rejected_and_harm_never_reviewed(lib, operator):
    u = _model_unit(lib, "keep")
    mid = _old_measure(lib, u)
    pid = lib.review_open_measures()[0]
    store().decide(pid, False)
    assert [i for i in store().open_items(R.QUEUE_MEASURE) if i["id"] == mid]
    assert lib.review_open_measures() == []              # a rejected review does not come back
    v = _model_unit(lib, "harm")
    _old_measure(lib, v, hard=("harm",))
    assert not [i for i in store().open_items(R.QUEUE_REVIEW)
                if i["payload"].get("unit") == v.unit_id]
    lib.review_open_measures()
    assert not [i for i in store().open_items(R.QUEUE_REVIEW)
                if i["payload"].get("unit") == v.unit_id]
