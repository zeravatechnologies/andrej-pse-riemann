"""F1 — SHARED_LIB layer: operator, human queue, declarations, read-only views."""
import json

import pytest

from pse_r import config
from pse_r.core import journal as J
from pse_r.shared_lib import declarations as DECL
from pse_r.shared_lib import operator as OP
from pse_r.shared_lib import views as V
from pse_r.shared_lib.store import store
from pse_r.vault.card import Card, CITED
from pse_r.vault.gate import gate


def test_operator_name_only_and_validated():
    with pytest.raises(OP.NoOperator):
        OP.require_operator()
    with pytest.raises(ValueError):
        OP.set_operator("x")                      # too short
    with pytest.raises(ValueError):
        OP.set_operator("rm -rf /;")              # illegal characters
    assert OP.set_operator("Andrej Ristić") == "Andrej Ristić"
    assert OP.require_operator() == "Andrej Ristić"
    assert OP.last_used() == "Andrej Ristić"


def test_operator_bound_to_every_journal_event(operator):
    rid = J.log(J.SYSTEM, "test", {"event": "ping"})
    row = [e for e in J.journal().tail(20) if e["id"] == rid][0]
    assert row["payload"]["operator"] == operator


def test_human_queue_needs_operator_and_is_journalled(operator):
    pid = store().propose("test", "Probni prijedlog", {"x": 1}, "unit:test")
    assert any(i["id"] == pid for i in store().open_items())
    OP._reset_for_tests()
    with pytest.raises(OP.NoOperator):
        store().decide(pid, True)
    OP.set_operator(operator)
    seen = []
    store().on_decision("test", lambda item, ok: seen.append((item["id"], ok)))
    item = store().decide(pid, True, "ok")
    assert item["status"] == "approved" and item["decided_by"] == operator
    assert seen == [(pid, True)]
    with pytest.raises(ValueError):
        store().decide(pid, False)                # cannot decide twice
    kinds = [(e["kind"], e["verdict"]) for e in J.journal().tail(10)]
    assert ("decision", "approved") in kinds


def test_declarations_take_effect_only_after_human_approval(operator):
    DECL.install_hooks()
    before = DECL.current()["version"]
    pid = DECL.propose({"models": {"/m/a.gguf": "ab" * 32}}, "system")
    assert DECL.current()["version"] == before    # proposal changes nothing
    store().decide(pid, True)
    cur = DECL.current()
    assert cur["version"] == before + 1
    assert cur["confirmed_by"] == operator
    assert DECL.model_hash("/m/a.gguf") == "ab" * 32
    assert "api.anthropic.com" in DECL.default_proposal()["sources"]


def test_views_read_cards_lab_and_journal(operator):
    v = gate().submit(Card(title="Prva nula zete", type="numeric-fact", status=CITED,
                           sources=["arxiv:2610.12234"], body="γ₁ ≈ 14.1347"),
                      actor="user")
    assert v.ok
    r = V.query("SELECT id, status, author FROM cards WHERE title LIKE 'Prva nula%'")
    assert r["rows"] and r["rows"][0][1] == "CITED"
    r = V.query("SELECT COUNT(*) FROM events WHERE kind='gate' AND verdict='accept'")
    assert r["rows"][0][0] >= 1
    s = V.schema()
    for view in ("cards", "lab_runs", "events", "guardian_events", "pending",
                 "declarations"):
        assert view in s, view


@pytest.mark.parametrize("sql", [
    "INSERT INTO cards(id) VALUES ('x')",
    "DELETE FROM events",
    "UPDATE pending SET status='approved'",
    "DROP TABLE cards",
    "ATTACH DATABASE '/tmp/x.db' AS x",
    "PRAGMA writable_schema=1",
    "SELECT 1; DELETE FROM events",
    "CREATE TABLE t(x)",
    "SELECT load_extension('/tmp/evil')",
    "WITH x AS (SELECT 1) DELETE FROM events",
])
def test_views_refuse_anything_but_reading(sql, operator):
    with pytest.raises(V.QueryRefused):
        V.query(sql)


def test_views_cannot_write_through_to_the_store(operator):
    store().propose("test", "zaštita", {}, "unit:test")
    n = store().rows("SELECT COUNT(*) c FROM pending")[0]["c"]
    with pytest.raises(V.QueryRefused):
        V.query("UPDATE pending SET status='approved'")
    assert store().rows("SELECT COUNT(*) c FROM pending")[0]["c"] == n
    assert all(i["status"] == "open" for i in store().open_items("test")
               if i["title"] == "zaštita")


def test_runaway_query_is_interrupted(operator):
    with pytest.raises(V.QueryRefused):
        V.query("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) "
                "SELECT COUNT(*) FROM c")


def test_journal_chain_still_intact():
    ok, bad = J.journal().verify_chain()
    assert ok, bad


def test_one_decision_takes_effect_once_even_if_hooks_installed_twice(operator):
    calls = []

    def hook(item, ok):
        calls.append(item["id"])
    store().on_decision("dup", hook)
    store().on_decision("dup", hook)
    pid = store().propose("dup", "duplikat", {}, "unit:test")
    store().decide(pid, True)
    assert calls == [pid]
