"""Faza 6d R2 (plan 33d, agreement rule 32): the queue in groups."""
import pytest

from pse_r.shared_lib import queue_groups as QG
from pse_r.shared_lib.store import store


def test_tree_groups_by_kind_and_topic(operator):
    a = store().propose("arxiv-paper", "zero-free", {"title": "Zero-free regions of zeta",
                                                     "abstract": "zero-free region"}, "arxiv")
    d = store().propose("doctor-measure", "mjera", {"unit": "chat#1", "agent": "chat",
                                                    "measure": "reset-granice"}, "doktor")
    t = QG.tree()
    kinds = {k["kind"]: k for k in t}
    assert kinds["arxiv-paper"]["bulk"] and not kinds["doctor-measure"]["bulk"]
    assert any(a in [i["id"] for g in kinds["arxiv-paper"]["groups"] for i in g["items"]]
               for _ in [0])
    assert [k["kind"] for k in t].index("doctor-measure") < [k["kind"] for k in t].index("arxiv-paper")
    for pid in (a, d):
        store().withdraw(pid, "test", "kraj")


def test_bulk_only_for_reversible(operator):
    a = store().propose("arxiv-paper", "r1", {"title": "x"}, "arxiv")
    b = store().propose("arxiv-paper", "r2", {"title": "y"}, "arxiv")
    d = store().propose("doctor-measure", "m", {"unit": "u", "measure": "smrt"}, "doktor")
    with pytest.raises(ValueError):
        QG.decide_many([a, d], True)
    assert store().get(a)["status"] == "open"            # nothing happened
    out = QG.decide_many([a, b], False)
    assert set(out["done"]) == {a, b}
    store().withdraw(d, "test", "kraj")


def test_detail_shows_full_abstract(operator):
    abstract = "A" * 3000
    pid = store().propose("arxiv-paper", "dug", {"title": "t", "abstract": abstract}, "arxiv")
    assert abstract in QG.detail_md(store().get(pid))
    store().withdraw(pid, "test", "kraj")
